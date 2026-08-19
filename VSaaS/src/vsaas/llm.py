"""Optional LLM integration for VSaaS.

If `VSAAS_LLM_BASE_URL` is set, the cloud API uses an OpenAI-compatible chat
endpoint to summarize events for the operator.

Environment:
- `VSAAS_LLM_BASE_URL` (default: empty/disabled)
  - Hosted example: `https://api.example.com/v1`
  - Local example: `http://127.0.0.1:8080`
- `VSAAS_LLM_MODEL` (default: `qwen3_vl_32b_instruct`)
- `VSAAS_LLM_API_KEY` (optional): passed as `Authorization: Bearer ...`
- `VSAAS_LLM_X_APIKEY` (optional): passed as `x-apikey: ...`
- `VSAAS_LLM_EXTRA_HEADERS_JSON` (optional): JSON dict of extra headers
- `VSAAS_LLM_DEBUG` (optional): when set, logs status/latency (no secrets)
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass


def _llm_debug_enabled() -> bool:
    return os.environ.get("VSAAS_LLM_DEBUG", "").strip().lower() in {"1", "true", "yes"}


def _llm_debug(msg: str) -> None:
    if not _llm_debug_enabled():
        return
    print(f"[vsaas.llm] {msg}", file=sys.stderr, flush=True)


def _pick_header(headers: object, keys: list[str]) -> str | None:
    for k in keys:
        try:
            v = headers.get(k)
        except Exception:
            v = None
        if v:
            return str(v)
    return None


@dataclass(frozen=True)
class LlmClient:
    base_url: str
    model: str = "qwen3_vl_32b_instruct"
    api_key: str | None = None
    x_apikey: str | None = None
    extra_headers: dict[str, str] | None = None

    def _chat_urls(self) -> list[str]:
        # OpenAI-style servers typically expose `/v1/chat/completions`.
        # Some gateways expect the base URL to already include `/v1` and then use `/chat/completions`.
        base = self.base_url.rstrip("/")

        # If user already passed the OpenAI-compatible base.
        if base.endswith("/api/v1"):
            return [f"{base}/chat/completions"]

        # If base ends with /v1, try `/chat/completions` first; if it 404s, fall back to `/api/v1/chat/completions`.
        if base.endswith("/v1"):
            urls = [f"{base}/chat/completions"]
            alt_base = f"{base[:-3]}/api/v1"  # replace trailing /v1 -> /api/v1
            urls.append(f"{alt_base}/chat/completions")
            return urls

        return [f"{base}/v1/chat/completions"]

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        if self.x_apikey:
            headers["x-apikey"] = self.x_apikey
        if self.extra_headers:
            headers.update({str(k): str(v) for k, v in self.extra_headers.items()})
        return headers

    def chat(self, system: str, user: str, max_tokens: int = 256, temperature: float = 0.2) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        urls = self._chat_urls()
        last_err: Exception | None = None

        for attempt, url in enumerate(urls, start=1):
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers=self._headers(),
                method="POST",
            )

            t0 = time.time()
            _llm_debug(
                "llm_request "
                f"attempt={attempt}/{len(urls)} url={url} model={self.model} max_tokens={max_tokens} "
                f"temperature={temperature} system_chars={len(system)} user_chars={len(user)}"
            )

            try:
                with urllib.request.urlopen(req, timeout=120) as r:
                    raw = r.read()
                    ms = int((time.time() - t0) * 1000)
                    status = getattr(r, "status", None) or r.getcode()
                    req_id = _pick_header(
                        r.headers,
                        [
                            "x-request-id",
                            "x-correlation-id",
                            "x-amzn-requestid",
                            "x-amz-request-id",
                            "request-id",
                        ],
                    )
                    _llm_debug(
                        f"llm_response attempt={attempt} status={status} ms={ms} bytes={len(raw)} request_id={req_id or '-'}"
                    )
                    obj = json.loads(raw)
                msg = obj["choices"][0]["message"]
                return (msg.get("content") or msg.get("reasoning_content") or "").strip()

            except urllib.error.HTTPError as e:
                ms = int((time.time() - t0) * 1000)
                req_id = _pick_header(
                    getattr(e, "headers", None) or {},
                    [
                        "x-request-id",
                        "x-correlation-id",
                        "x-amzn-requestid",
                        "x-amz-request-id",
                        "request-id",
                    ],
                )
                _llm_debug(
                    f"llm_http_error attempt={attempt} status={e.code} ms={ms} reason={e.reason} request_id={req_id or '-'}"
                )
                last_err = e
                if e.code == 404 and attempt < len(urls):
                    continue
                raise

            except urllib.error.URLError as e:
                ms = int((time.time() - t0) * 1000)
                _llm_debug(f"llm_url_error attempt={attempt} ms={ms} reason={getattr(e, 'reason', e)}")
                last_err = e
                raise

        if last_err is not None:
            raise last_err
        raise RuntimeError("LLM request failed unexpectedly")


def get_llm() -> LlmClient | None:
    base = os.environ.get("VSAAS_LLM_BASE_URL", "").strip()
    if not base:
        return None
    model = os.environ.get("VSAAS_LLM_MODEL", "qwen3_vl_32b_instruct")

    api_key = os.environ.get("VSAAS_LLM_API_KEY", "").strip() or None
    x_apikey = os.environ.get("VSAAS_LLM_X_APIKEY", "").strip() or None

    extra_headers_raw = os.environ.get("VSAAS_LLM_EXTRA_HEADERS_JSON", "").strip()
    extra_headers: dict[str, str] | None
    if extra_headers_raw:
        try:
            extra_headers = json.loads(extra_headers_raw)
        except Exception:
            extra_headers = None
    else:
        extra_headers = None

    return LlmClient(base_url=base, model=model, api_key=api_key, x_apikey=x_apikey, extra_headers=extra_headers)
