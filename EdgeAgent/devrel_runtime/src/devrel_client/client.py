"""DevRelClient — the typed Python SDK for the DevRel MCP server.

The rest of :mod:`devrel_client` provisions IDEs (Claude Code / opencode) to
talk to a DevRel MCP server. This module is the *programmatic* path: a typed,
resilient client an application (or a sample script) uses to call the six DevRel
MCP tools directly.

Design:

* **Lazy fastmcp** — the transport is `fastmcp.Client`, imported only when you
  actually connect, so the core `devrel-mcp-client` package stays lightweight
  (typer + httpx). Install ``devrel-mcp-client[samples]`` (or ``pip install
  fastmcp``) to use the SDK.
* **Transport auto-resolution** — :func:`create_client` figures out where the
  server is from (in precedence order) explicit args, ``DevRel_MCP_URL`` /
  ``DevRel_MCP_TOKEN`` env, or a discovered ``.claude/settings.json``.
* **Resilience** — configurable retries with exponential backoff on transient
  transport errors (:class:`RetryPolicy`).
* **Auth** — bearer token and optional mTLS (client cert/key) for ``sse-http``.
* **Typed tool methods** — one method per MCP tool, each returning the parsed
  result dict; plus :meth:`DevRelClient.call_tool` for the raw envelope and
  :meth:`DevRelClient.search_aihub` pagination helper.
* **Schema-compat** — tolerates both the ``structured_content`` dict and the
  ``content[0].text`` JSON-string envelope shapes across fastmcp versions.

Example::

    from devrel_client import create_client

    async with create_client() as client:
        hw = await client.hardware_detect(platform="windows")
        conv = await client.convert_model(
            source_format="onnx", model_path="m.onnx",
            target_sdk="qnn", quantization="int8",
        )
"""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

__all__ = [
    "DevRelClient",
    "create_client",
    "RetryPolicy",
    "ClientAuth",
    "DevRelClientError",
    "DevRelToolError",
    "DevRelConnectionError",
]


# ── Errors ───────────────────────────────────────────────────────────────────


class DevRelClientError(RuntimeError):
    """Base class for all DevRelClient errors."""


class DevRelConnectionError(DevRelClientError):
    """Could not establish / maintain a connection to the DevRel MCP server."""


class DevRelToolError(DevRelClientError):
    """A tool call returned an error envelope or unparseable payload."""


# ── Config dataclasses ─────────────────────────────────────────────────────────


@dataclass(frozen=True)
class RetryPolicy:
    """Exponential-backoff retry policy for transient transport failures.

    A call is retried up to ``max_retries`` times; the delay before attempt *n*
    is ``min(base_delay_s * (multiplier ** n), max_delay_s)``. Only transport /
    connection errors are retried — a tool that returns an error *envelope* is
    a definitive answer and is not retried.
    """

    max_retries: int = 3
    base_delay_s: float = 0.5
    multiplier: float = 2.0
    max_delay_s: float = 10.0

    def delay_for(self, attempt: int) -> float:
        return min(self.base_delay_s * (self.multiplier**attempt), self.max_delay_s)


@dataclass(frozen=True)
class ClientAuth:
    """Authentication material for an ``sse-http`` DevRel MCP server.

    * ``token`` — bearer token sent as ``Authorization: Bearer <token>``.
    * ``client_cert`` / ``client_key`` — PEM paths for mutual TLS.
    * ``ca_bundle`` — PEM path to a custom CA (corporate TLS-inspecting proxy).
    """

    token: str | None = None
    client_cert: str | None = None
    client_key: str | None = None
    ca_bundle: str | None = None

    @classmethod
    def from_env(cls) -> ClientAuth:
        return cls(
            token=os.environ.get("DevRel_MCP_TOKEN") or None,
            client_cert=os.environ.get("DEVREL_CLIENT_CERT") or None,
            client_key=os.environ.get("DEVREL_CLIENT_KEY") or None,
            ca_bundle=os.environ.get("DevRel_MCP_CA_BUNDLE") or os.environ.get("DevRel_CA_BUNDLE") or None,
        )

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}


@dataclass
class _Transport:
    """Resolved transport target for the DevRel MCP server."""

    kind: Literal["stdio-local", "sse-http"]
    # stdio-local
    command: str | None = None
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    # sse-http
    url: str | None = None
    auth: ClientAuth = field(default_factory=ClientAuth)


# ── Transport resolution ───────────────────────────────────────────────────────


def _maybe_unzip_bundle(dest: Path) -> Path:
    """If ``dest`` is a .zip bundle, extract it and return the inner .onnx.

    A QDQ ONNX with external-data weights is delivered as a .zip containing
    ``<stem>-qdq.onnx`` + ``model.data``. The .onnx references ``model.data``
    by relative name, so both must land in the same directory. We extract into
    a sibling folder (``<stem>-qdq/``), drop the zip, and return the inner
    .onnx path (with ``model.data`` beside it). Non-zips are returned as-is.
    """
    if dest.suffix.lower() != ".zip":
        return dest
    import zipfile

    extract_dir = dest.with_suffix("")  # <stem>-qdq/
    try:
        with zipfile.ZipFile(dest) as zf:
            extract_dir.mkdir(parents=True, exist_ok=True)
            zf.extractall(extract_dir)
            onnx_members = [n for n in zf.namelist() if n.lower().endswith(".onnx")]
    except zipfile.BadZipFile:
        return dest  # not really a zip — hand back what we got
    dest.unlink(missing_ok=True)  # drop the zip; keep the extracted dir
    if onnx_members:
        return extract_dir / onnx_members[0]
    return extract_dir


def _discover_settings_json(start: Path | None = None) -> dict[str, Any] | None:
    """Walk up from ``start`` (or cwd) looking for a ``.claude/settings.json``."""
    here = (start or Path.cwd()).resolve()
    for parent in (here, *here.parents):
        cand = parent / ".claude" / "settings.json"
        if cand.is_file():
            try:
                return json.loads(cand.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                return None
    return None


def _resolve_transport(
    *,
    url: str | None,
    command: str | None,
    args: list[str] | None,
    auth: ClientAuth | None,
) -> _Transport:
    """Resolve where the DevRel MCP server is, in precedence order.

    1. explicit ``url`` (→ sse-http) or ``command`` (→ stdio-local)
    2. ``DevRel_MCP_URL`` env (→ sse-http)
    3. a discovered ``.claude/settings.json`` (http transport or stdio command)
    4. default stdio-local: ``python -m devrel.mcp.server``
    """
    resolved_auth = auth or ClientAuth.from_env()

    if url:
        return _Transport(kind="sse-http", url=url, auth=resolved_auth)
    if command:
        return _Transport(kind="stdio-local", command=command, args=list(args or []))

    env_url = os.environ.get("DevRel_MCP_URL")
    if env_url:
        return _Transport(kind="sse-http", url=env_url, auth=resolved_auth)

    settings = _discover_settings_json()
    if settings:
        server = (settings.get("mcpServers") or {}).get("devrel") or {}
        transport = server.get("transport") or {}
        if transport.get("type") == "http" and transport.get("url"):
            # Expand ${env:VAR} in the Authorization header if present.
            hdr = (transport.get("headers") or {}).get("Authorization", "")
            token = resolved_auth.token
            if not token and hdr.startswith("Bearer "):
                raw = hdr[len("Bearer "):]
                token = _expand_env(raw) or None
            return _Transport(
                kind="sse-http",
                url=transport["url"],
                auth=ClientAuth(
                    token=token,
                    client_cert=resolved_auth.client_cert,
                    client_key=resolved_auth.client_key,
                    ca_bundle=resolved_auth.ca_bundle,
                ),
            )
        if server.get("command"):
            return _Transport(
                kind="stdio-local",
                command=server["command"],
                args=list(server.get("args") or []),
                env=dict(server.get("env") or {}),
            )

    # Default: spawn the server locally.
    import sys

    return _Transport(
        kind="stdio-local",
        command=sys.executable,
        args=["-u", "-m", "devrel.mcp.server"],
        env={"FASTMCP_SHOW_SERVER_BANNER": "false"},
    )


def _expand_env(raw: str) -> str:
    """Expand ``${env:VAR}`` / ``$VAR`` references from the environment."""
    import re

    def repl(m: re.Match[str]) -> str:
        return os.environ.get(m.group(1) or m.group(2) or "", "")

    return re.sub(r"\$\{env:([A-Z_][A-Z0-9_]*)\}|\$([A-Z_][A-Z0-9_]*)", repl, raw)


# ── The client ─────────────────────────────────────────────────────────────────


class DevRelClient:
    """A typed, resilient client for the six DevRel MCP tools.

    Construct via :func:`create_client` (which resolves the transport) and use
    as an async context manager. Direct construction is supported for advanced
    callers who already have a :class:`_Transport`.
    """

    #: Canonical MCP tool names the server exposes.
    TOOLS = (
        "hardware_detect",
        "convert_model",
        "profile_workload",
        "orchestrate_workload",
        "generate_code",
        "aihub_select",
    )

    def __init__(
        self,
        transport: _Transport,
        *,
        retry: RetryPolicy | None = None,
        timeout_s: float = 300.0,
    ) -> None:
        self._transport = transport
        self._retry = retry or RetryPolicy()
        self._timeout_s = timeout_s
        self._client: Any | None = None  # fastmcp.Client, lazily built

    # ── connection lifecycle ─────────────────────────────────────────────────

    async def __aenter__(self) -> DevRelClient:
        await self.connect()
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    async def connect(self) -> None:
        """Open the underlying fastmcp transport (idempotent)."""
        if self._client is not None:
            return
        try:
            from fastmcp import Client
        except ImportError as e:  # pragma: no cover - env-dependent
            raise DevRelConnectionError(
                "fastmcp is required for the DevRelClient SDK. Install it with "
                "`pip install fastmcp` or `pip install devrel-mcp-client[samples]`."
            ) from e

        fastmcp_transport = self._build_fastmcp_transport()
        self._client = Client(fastmcp_transport)
        try:
            await self._client.__aenter__()
        except Exception as e:  # pragma: no cover - network-dependent
            self._client = None
            raise DevRelConnectionError(f"Could not connect to the DevRel MCP server: {e}") from e

    async def close(self) -> None:
        if self._client is not None:
            try:
                await self._client.__aexit__(None, None, None)
            finally:
                self._client = None

    def _build_fastmcp_transport(self) -> Any:
        t = self._transport
        if t.kind == "sse-http":
            # Import from the transports package root: fastmcp 3.x no longer
            # exposes the `streamable_http` submodule path, but the symbol is
            # re-exported at the package level across versions.
            from fastmcp.client.transports import StreamableHttpTransport

            return StreamableHttpTransport(url=t.url, headers=t.auth.headers or None)
        from fastmcp.client.transports import StdioTransport

        return StdioTransport(
            command=t.command,
            args=t.args,
            env={**os.environ, **t.env},
            keep_alive=False,
        )

    # ── raw tool call (with retries + schema-compat) ─────────────────────────

    async def call_tool(self, name: str, args: dict[str, Any] | None = None) -> Any:
        """Call an MCP tool by name, returning the raw fastmcp result.

        Retries transient transport failures per the :class:`RetryPolicy`.
        Samples that pre-date the typed methods use this directly and read
        ``result.content[0].text``.
        """
        if self._client is None:
            raise DevRelConnectionError("Not connected — use `async with create_client()` or call connect().")

        last_exc: Exception | None = None
        for attempt in range(self._retry.max_retries + 1):
            try:
                return await asyncio.wait_for(
                    self._client.call_tool(name, args or {}),
                    timeout=self._timeout_s,
                )
            except (asyncio.TimeoutError, ConnectionError, OSError) as e:
                last_exc = e
                if attempt < self._retry.max_retries:
                    await asyncio.sleep(self._retry.delay_for(attempt))
                    continue
                raise DevRelConnectionError(
                    f"Tool {name!r} failed after {self._retry.max_retries + 1} attempts: {e}"
                ) from e
        raise DevRelConnectionError(f"Tool {name!r} failed: {last_exc}")  # pragma: no cover

    async def call_tool_dict(
        self,
        name: str,
        args: dict[str, Any] | None = None,
        *,
        strict: bool = False,
    ) -> dict[str, Any]:
        """Call a tool and return its result as a parsed dict (schema-compat).

        Handles both envelope shapes: ``structured_content`` (modern fastmcp)
        and a ``content[0].text`` JSON string (older).

        DevRel action envelopes use ``{ok: false, error: ...}`` for
        recoverable/soft failures. By default those are returned verbatim so
        the caller can inspect ``.ok`` (not every false-ok is fatal). Pass
        ``strict=True`` to raise :class:`DevRelToolError` on such an envelope
        instead. An unparseable payload always raises (via
        :func:`_extract_payload`).
        """
        result = await self.call_tool(name, args)
        payload = _extract_payload(result)
        if (
            isinstance(payload, dict)
            and payload.get("error")
            and "ok" in payload
            and payload.get("ok") is False
        ):
            if strict:
                raise DevRelToolError(str(payload.get("error")))
            # caller inspects .ok — not every false-ok is fatal
            return payload
        return payload

    # ── typed tool methods ────────────────────────────────────────────────────

    async def hardware_detect(
        self, platform: Literal["windows", "linux", "android", "gateway", "robotics"]
    ) -> dict[str, Any]:
        return await self.call_tool_dict("hardware_detect", {"platform": platform})

    async def convert_model(
        self,
        *,
        source_format: Literal["onnx", "pytorch", "tensorflow", "tflite"],
        model_path: str = "",
        target_sdk: Literal["qnn", "snpe", "nwaios", "executorch"] = "qnn",
        quantization: Literal["fp32", "int8", "int4"] = "fp32",
        runtime: str = "qnn-htp",
        model_source: dict[str, Any] | None = None,
        upload: str | Path | None = None,
        aihub: Literal["auto", "force", "never"] = "auto",
        aihub_device: str | None = None,
        model_id: str | None = None,
        auto_download: bool = True,
        download_dir: str | Path | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Convert/quantize a model on the server, with an optional round-trip.

        Input selection (in precedence order):
          * ``upload`` — a local file to POST to the server first (sse-http only);
            the server converts the uploaded copy.
          * ``model_source`` — an explicit source dict the server resolves
            (``{"kind": "huggingface"|"github"|"url"|"server_path"|"upload", ...}``).
          * ``model_path`` — a path already on the server (legacy).

        ``aihub`` routes to the AI Hub Models cloud when required ('auto'),
        always ('force'), or never. When ``auto_download`` and the result carries
        a ``download_url``, the artifact is fetched to ``download_dir`` (default
        ``./devrel_artifacts``) and ``local_path`` is added to the result.
        """
        # 1. Upload a local file first, if requested.
        if upload is not None:
            upload_id = await self.upload_file(upload)
            model_source = {"kind": "upload", "upload_id": upload_id}

        args: dict[str, Any] = {
            "source_format": source_format,
            "model_path": model_path,
            "target_sdk": target_sdk,
            "quantization": quantization,
            "runtime": runtime,
            "aihub": aihub,
            **kwargs,
        }
        if model_source is not None:
            args["model_source"] = model_source
        if aihub_device is not None:
            args["aihub_device"] = aihub_device
        if model_id is not None:
            args["model_id"] = model_id

        result = await self.call_tool_dict("convert_model", args)

        # 3. Auto-download the produced artifact back to the client.
        if (
            auto_download
            and isinstance(result, dict)
            and result.get("download_url")
            and self._transport.kind == "sse-http"
        ):
            try:
                dest_dir = Path(download_dir) if download_dir else Path("./devrel_artifacts")
                local = await self.download_artifact(
                    result["download_url"],
                    dest_dir,
                    filename=result.get("artifact_filename"),
                    expected_sha256=result.get("sha256"),
                )
                result["local_path"] = str(local)
            except Exception as e:  # download failure shouldn't lose the result
                result.setdefault("warnings", []).append(
                    f"auto-download failed (artifact remains on server at "
                    f"{result.get('download_url')}): {e}"
                )
        return result

    # ── data-plane helpers (upload / download over the HTTP base URL) ────────

    def _http_base(self) -> tuple[str, dict[str, str]]:
        """Return (base_url, auth_headers) for direct HTTP data-plane calls.

        The MCP tool channel runs over ``/mcp``; uploads/downloads are plain
        HTTP routes on the same host. Derive that host from the sse-http URL.
        """
        if self._transport.kind != "sse-http" or not self._transport.url:
            raise DevRelClientError(
                "upload/download require an sse-http transport (a hosted server URL)."
            )
        url = self._transport.url
        # Strip a trailing /mcp (or /sse) path segment to get the host root.
        for suffix in ("/mcp", "/sse"):
            if url.endswith(suffix):
                url = url[: -len(suffix)]
                break
        base = url.rstrip("/")
        return base, dict(self._transport.auth.headers)

    async def upload_file(self, path: str | Path) -> str:
        """Upload a local model file to the server; return its ``upload_id``.

        POSTs the raw bytes to ``{base}/uploads`` with an ``X-Filename`` header.
        """
        p = Path(path)
        if not p.is_file():
            raise DevRelClientError(f"upload file not found: {p}")
        base, headers = self._http_base()
        headers = {**headers, "X-Filename": p.name, "Content-Type": "application/octet-stream"}
        try:
            import httpx
        except ImportError as e:  # pragma: no cover
            raise DevRelClientError("httpx is required for uploads.") from e

        async def _read():
            with p.open("rb") as f:
                while True:
                    chunk = f.read(1024 * 256)
                    if not chunk:
                        break
                    yield chunk

        async with httpx.AsyncClient(timeout=None) as client:
            resp = await client.post(f"{base}/uploads", headers=headers, content=_read())
            if resp.status_code != 200:
                raise DevRelToolError(
                    f"upload failed ({resp.status_code}): {resp.text[:300]}"
                )
            data = resp.json()
        upload_id = data.get("upload_id")
        if not upload_id:
            raise DevRelToolError(f"upload response missing upload_id: {data}")
        return upload_id

    async def download_artifact(
        self,
        url_or_path: str,
        dest_dir: str | Path,
        *,
        filename: str | None = None,
        expected_sha256: str | None = None,
        auto_unzip: bool = True,
    ) -> Path:
        """Download a converted artifact to ``dest_dir``; verify sha256 if given.

        ``url_or_path`` is the relative ``download_url`` from a convert result
        (or an absolute URL). Streams with Range-friendly httpx; returns the
        local path.
        """
        import hashlib

        try:
            import httpx
        except ImportError as e:  # pragma: no cover
            raise DevRelClientError("httpx is required for downloads.") from e

        base, headers = self._http_base()
        full = url_or_path if url_or_path.startswith("http") else f"{base}{url_or_path}"
        dest_dir = Path(dest_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)

        h = hashlib.sha256()
        tmp_name = filename or "artifact.bin"
        async with httpx.AsyncClient(timeout=None, follow_redirects=True) as client:
            async with client.stream("GET", full, headers=headers) as resp:
                if resp.status_code != 200:
                    body = await resp.aread()
                    raise DevRelToolError(
                        f"download failed ({resp.status_code}): {body[:300]!r}"
                    )
                # Prefer the server-provided filename from Content-Disposition.
                if not filename:
                    cd = resp.headers.get("content-disposition", "")
                    if "filename=" in cd:
                        tmp_name = cd.split("filename=", 1)[1].strip().strip('"') or tmp_name
                dest = dest_dir / tmp_name
                tmp = dest.with_suffix(dest.suffix + ".part")
                with tmp.open("wb") as out:
                    async for chunk in resp.aiter_bytes(chunk_size=1024 * 256):
                        if not chunk:
                            continue
                        out.write(chunk)
                        h.update(chunk)
        if expected_sha256 and h.hexdigest().lower() != expected_sha256.lower():
            tmp.unlink(missing_ok=True)
            raise DevRelToolError(
                f"artifact sha256 mismatch: expected {expected_sha256}, got {h.hexdigest()}"
            )
        import os as _os

        _os.replace(tmp, dest)

        # A QDQ ONNX with external-data weights arrives as a .zip bundle
        # (<stem>-qdq.onnx + model.data). Unzip so the .onnx and its sidecar
        # land together — the .onnx references "model.data" by relative name,
        # so both must sit in the same dir to load. Return the inner .onnx.
        if auto_unzip:
            return _maybe_unzip_bundle(dest)
        return dest

    async def profile_workload(
        self,
        *,
        model_path: str,
        platform: str = "windows",
        runtime: str = "auto",
        duration_s: int = 10,
        profiling_level: Literal["basic", "detailed", "linting", "qhas"] = "detailed",
        **kwargs: Any,
    ) -> dict[str, Any]:
        return await self.call_tool_dict(
            "profile_workload",
            {
                "model_path": model_path,
                "platform": platform,
                "runtime": runtime,
                "duration_s": duration_s,
                "profiling_level": profiling_level,
                **kwargs,
            },
        )

    async def orchestrate_workload(
        self,
        *,
        model_path: str,
        power_mode: Literal["performance", "balanced", "efficiency"] = "balanced",
        **kwargs: Any,
    ) -> dict[str, Any]:
        return await self.call_tool_dict(
            "orchestrate_workload",
            {"model_path": model_path, "power_mode": power_mode, **kwargs},
        )

    async def generate_code(
        self,
        *,
        platform: str,
        sdk: Literal["qnn", "snpe", "nwaios", "executorch"] = "qnn",
        language: str = "python",
        model_path: str = "model.bin",
        runtime: str = "npu",
        **kwargs: Any,
    ) -> dict[str, Any]:
        return await self.call_tool_dict(
            "generate_code",
            {
                "platform": platform,
                "sdk": sdk,
                "language": language,
                "model_path": model_path,
                "runtime": runtime,
                **kwargs,
            },
        )

    async def aihub_select(self, *, action: str = "search", **kwargs: Any) -> dict[str, Any]:
        return await self.call_tool_dict("aihub_select", {"action": action, **kwargs})

    # ── pagination helper ─────────────────────────────────────────────────────

    async def search_aihub(
        self, query: str = "", *, page_size: int = 25, max_results: int | None = None
    ) -> AsyncIterator[dict[str, Any]]:
        """Yield AI Hub Models catalog matches, transparently paging the search action.

        The server's ``aihub_select action=search`` returns a ``matches`` list
        and (when more exist) a ``next_offset``. This walks those pages so the
        caller sees a flat stream, capped at ``max_results`` when given.
        """
        offset = 0
        yielded = 0
        while True:
            res = await self.aihub_select(
                action="search", query=query, limit=page_size, offset=offset
            )
            matches = res.get("matches") or res.get("results") or []
            for m in matches:
                yield m
                yielded += 1
                if max_results is not None and yielded >= max_results:
                    return
            next_offset = res.get("next_offset")
            if not next_offset or next_offset <= offset or not matches:
                return
            offset = next_offset


# ── payload extraction (schema-compat) ─────────────────────────────────────────


def _extract_payload(result: Any) -> dict[str, Any]:
    """Pull a dict payload out of a fastmcp CallToolResult, across versions."""
    # Modern fastmcp: .structured_content is a dict (or None)
    structured = getattr(result, "structured_content", None)
    if isinstance(structured, dict) and structured:
        return structured
    # Fallback: first content block's .text is a JSON string
    content = getattr(result, "content", None) or []
    for block in content:
        text = getattr(block, "text", None)
        if text:
            try:
                parsed = json.loads(text)
                if isinstance(parsed, dict):
                    return parsed
                return {"result": parsed}
            except (json.JSONDecodeError, TypeError):
                return {"raw": text}
    # Some fastmcp versions return .data
    data = getattr(result, "data", None)
    if isinstance(data, dict):
        return data
    raise DevRelToolError(f"Could not extract a payload from tool result: {result!r}")


# ── factory ─────────────────────────────────────────────────────────────────


def create_client(
    *,
    url: str | None = None,
    command: str | None = None,
    args: list[str] | None = None,
    token: str | None = None,
    auth: ClientAuth | None = None,
    retry: RetryPolicy | None = None,
    timeout_s: float = 300.0,
) -> DevRelClient:
    """Build a :class:`DevRelClient`, resolving the transport automatically.

    With no arguments, resolves the server from ``DevRel_MCP_URL`` /
    ``.claude/settings.json`` / a local spawn (see :func:`_resolve_transport`).
    Pass ``url=`` for an explicit hosted server, ``command=``/``args=`` for an
    explicit local spawn, ``token=`` (or ``auth=``) for bearer/mTLS auth.

    Returns an unconnected client — use it as an async context manager.
    """
    if token and auth is None:
        auth = ClientAuth(token=token)
    transport = _resolve_transport(url=url, command=command, args=args, auth=auth)
    return DevRelClient(transport, retry=retry, timeout_s=timeout_s)
