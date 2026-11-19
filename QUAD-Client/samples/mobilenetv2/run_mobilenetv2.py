"""
run_mobilenetv2.py — Download, convert, and test MobileNetV2 INT8 on Snapdragon X Elite.

Steps performed automatically:
  1. Download mobilenetv2-12.onnx from ONNX Model Zoo
  2. Convert to INT8 QNN context binary via QUAD MCP server
  3. Run inference on CPU, GPU (Adreno), and NPU and print top-5 predictions

Usage
-----
    python run_mobilenetv2.py --image test_input.jpg

    # Skip download if model already exists:
    python run_mobilenetv2.py --image test_input.jpg --skip-download

    # Use calibration images for better INT8 accuracy:
    python run_mobilenetv2.py --image test_input.jpg --calibration calibration/

    # Remote QUAD server:
    python run_mobilenetv2.py --image test_input.jpg --server http://localhost:8080/sse

    # SNPE DLC instead of QNN .bin (for Android / Linux targets):
    python run_mobilenetv2.py --image test_input.jpg --target-sdk snpe
"""

from __future__ import annotations

import argparse
import asyncio
import io
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

# Force UTF-8 output on Windows (cp1252 consoles can't render → ─ █ …)
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() not in ("utf-8", "utf8"):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MODEL_URL = (
    "https://github.com/onnx/models/raw/main/validated/vision/classification/"
    "mobilenet/model/mobilenetv2-12.onnx"
)
LABELS_URL = (
    "https://raw.githubusercontent.com/pytorch/hub/master/imagenet_classes.txt"
)
# Dog/cat test images — multiple mirrors so at least one works on corp networks.
# pytorch/hub is reliable when GitHub raw is accessible.
# Wikimedia is a public fallback with no bot-blocking.
TEST_IMAGE_URLS = [
    "https://raw.githubusercontent.com/pytorch/hub/master/images/dog.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/4/43/Cute_dog.jpg/320px-Cute_dog.jpg",
]
# Keep the legacy single-URL constant for any code that references it directly.
TEST_IMAGE_URL = TEST_IMAGE_URLS[0]

# ImageNet mean / std (matches what convert_int8.py records in the context binary)
IMAGENET_MEAN = [123.675, 116.28,  103.53]
IMAGENET_STD  = [58.395,  57.12,   57.375]


# ---------------------------------------------------------------------------
# Step 1 — Download
# ---------------------------------------------------------------------------

def _write_synthetic_image(dest: Path) -> None:
    """Write a 224×224 random RGB JPEG — used when the real test image can't be downloaded."""
    import numpy as np
    from PIL import Image as PILImage
    arr = np.random.randint(0, 256, (224, 224, 3), dtype=np.uint8)
    PILImage.fromarray(arr).save(dest, format="JPEG")


def _download(url: str, dest: Path) -> None:
    """Download with corporate-proxy TLS auto-retry (issue 24), urllib fallback."""
    try:
        from quad_mcp_client.local.download import download_file

        download_file(url, dest)
        return
    except ImportError:
        urllib.request.urlretrieve(url, dest)


def step1_download(model_path: Path, labels_path: Path, image_path: str, *, skip: bool) -> str:
    """Download model, labels, and (if needed) a default test image. Returns resolved image path."""
    print("=" * 60)
    print("STEP 1 — Download model")
    print("=" * 60)

    if skip and model_path.exists():
        print(f"  [skip] {model_path} already exists.")
    else:
        print(f"  Downloading {MODEL_URL}")
        print(f"  → {model_path} …", end="", flush=True)
        model_path.parent.mkdir(parents=True, exist_ok=True)
        _download(MODEL_URL, model_path)
        size_mb = model_path.stat().st_size / 1_048_576
        print(f" done  ({size_mb:.1f} MB)")
        # Reset the simplification marker so the freshly downloaded model
        # gets re-simplified with pinned batch_size=1. Without this, a stale
        # marker from a previous run would skip simplification on the new file.
        model_path.with_suffix(".onnxsim_done").unlink(missing_ok=True)

    if not labels_path.exists():
        print("  Downloading ImageNet labels …", end="", flush=True)
        _download(LABELS_URL, labels_path)
        print(" done")
    else:
        print(f"  [skip] {labels_path} already exists.")

    # Auto-download a test image if the specified path doesn't exist
    if not Path(image_path).exists():
        dest = Path(image_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        print(f"  Image '{image_path}' not found — downloading default test image …", end="", flush=True)
        downloaded = False
        for _url in TEST_IMAGE_URLS:
            try:
                req = urllib.request.Request(
                    _url,
                    headers={"User-Agent": "QUAD-MobileNetV2-Sample/1.0"},
                )
                with urllib.request.urlopen(req, timeout=15) as resp:
                    data = resp.read()
                if len(data) < 1024:
                    continue  # suspiciously small -- try next mirror
                dest.write_bytes(data)
                print(f" done  ({len(data) // 1024} KB)")
                downloaded = True
                break
            except Exception:
                continue
        if not downloaded:
            print(" failed (all mirrors tried)")
            print("  Generating synthetic test image instead …", end="", flush=True)
            _write_synthetic_image(dest)
            print(" done  (224x224 random RGB -- predictions will be meaningless but pipeline is tested)")

    print()
    return image_path


# ---------------------------------------------------------------------------
# Step 1.5 — ONNX pre-processing (simplification for QAIRT compatibility)
# ---------------------------------------------------------------------------

def _simplify_onnx_inplace(model_path: Path) -> None:
    """Simplify the ONNX model in-place using onnx-simplifier.

    mobilenetv2-12 from the ONNX Model Zoo uses Reshape ops whose shape
    tensors are computed via Gather/Concat constant subgraphs.  QAIRT
    v2.41.0 cannot evaluate these at conversion time, causing a shape
    mismatch error (e.g. 'ReshapeOp::calculateShape … 19200 != 2036823520').

    onnxsim folds all constant subgraphs so the converter sees plain
    initializer tensors instead of dynamic computations.

    Runs at most once per model file; a marker file *.onnxsim_done* is
    written alongside the model so subsequent runs skip the step.
    """
    marker = model_path.with_suffix(".onnxsim_done")
    if marker.exists():
        return

    try:
        import onnx
        import onnxsim
    except ImportError:
        print("  [info] onnxsim not installed — ONNX simplification skipped.")
        print("         Install with:  pip install onnxsim onnx")
        print("         If conversion fails, simplification is likely required.")
        return

    print(f"  Simplifying {model_path.name} with onnxsim …", end="", flush=True)
    try:
        model = onnx.load(str(model_path))
        # Pin the first input to batch_size=1 so QAIRT sees static shapes.
        # mobilenetv2-12 from the ONNX Model Zoo ships with a dynamic batch
        # dimension; calling simplify() without input_shapes leaves it dynamic
        # and the QAIRT converter produces bogus shape values (4294967295).
        input_name = model.graph.input[0].name
        model_simplified, ok = onnxsim.simplify(
            model,
            overwrite_input_shapes={input_name: [1, 3, 224, 224]},
        )
        if ok:
            onnx.save(model_simplified, str(model_path))
            marker.touch()
            size_mb = model_path.stat().st_size / 1_048_576
            print(f" done  ({size_mb:.1f} MB)")
        else:
            print(" verification failed — using original model")
    except Exception as exc:
        print(f" error: {exc} — using original model")


# ---------------------------------------------------------------------------
# Step 2 — Convert via QUAD MCP server
# ---------------------------------------------------------------------------

def _resolve_qairt_python() -> str | None:
    """Return a Python 3.10 x86_64 interpreter compatible with the QAIRT SDK .pyd extensions.

    Requirements:
      - Python 3.10 (the .pyd files are compiled for CPython 3.10 x86_64)
      - numpy 1.x  (the C extensions use the numpy 1 ABI; numpy 2 corrupts
                    IrStaticTensor data, causing garbage permute orders)
      - onnx ~1.17  (onnx.mapping compat shim must be present; QAIRT v2.41
                     imports it from converters/onnx/util.py)

    Search order:
      1. .QUAD/qairt-venv/Scripts/python.exe (walking up from script dir)
      2. QAIRT_PYTHON env var
      3. py -3.10 via the Windows py.exe launcher (fallback)
    """
    # 1. Walk up from this script to find .QUAD/qairt-venv
    here = Path(__file__).resolve()
    for ancestor in here.parents:
        venv_py = ancestor / ".QUAD" / "qairt-venv" / "Scripts" / "python.exe"
        if venv_py.exists():
            return str(venv_py)

    # 2. Explicit env var
    if os.environ.get("QAIRT_PYTHON"):
        return os.environ["QAIRT_PYTHON"]

    # 3. Fallback: Windows py.exe launcher
    import shutil
    import subprocess
    py_exe = shutil.which("py")
    if py_exe:
        try:
            r = subprocess.run(
                [py_exe, "-3.10", "-c", "import sys; print(sys.executable)"],
                capture_output=True, text=True, timeout=5,
            )
            if r.returncode == 0:
                return r.stdout.strip()
        except (OSError, subprocess.TimeoutExpired):
            pass
    return None


def _get_sdk_root_safe() -> str | None:
    """Return the SDK root, skipping env vars that point at non-existent paths.

    QNN_SDK_ROOT / QAIRT_SDK_ROOT can be stale (pointing at a previously
    installed SDK version that was later removed). Validating the path
    before returning prevents 'qnn-net-run.exe not found' warnings that
    mislead the user into thinking the SDK is missing when it's actually
    just mis-pointed.
    """
    for var in ("QNN_SDK_ROOT", "QAIRT_SDK_ROOT"):
        val = os.environ.get(var, "").strip()
        if val and Path(val).is_dir():
            return val
    # Fallback: walk up the workspace tree and pick the newest sdks/ subdir
    here = Path(__file__).resolve()
    for ancestor in here.parents:
        sdks_dir = ancestor / "QUAD" / "sdks"
        if sdks_dir.is_dir():
            candidates = sorted(
                (d for d in sdks_dir.iterdir() if d.is_dir()),
                key=lambda p: p.name, reverse=True,
            )
            if candidates:
                return str(candidates[0])
    return None


def _find_quad_python(override: str | None) -> str:
    """
    Return a Python executable that can import quad.mcp.server.

    Search order:
      1. --server-python CLI override
      2. QUAD_PYTHON environment variable
      3. .venv next to the QUAD repo (../../../QUAD/.venv on Windows)
      4. sys.executable (current interpreter)

    Exits with a helpful message if none of the candidates work.
    """
    import os

    def _can_import(py: str) -> bool:
        # Check by inspecting the venv's site-packages on disk — no subprocess.
        # Handles both regular installs and editable installs (via .pth files).
        py_path = Path(py)
        if not py_path.exists():
            return False
        venv_root = py_path.parent.parent  # .venv/Scripts/python.exe -> .venv
        # Windows: Lib/site-packages   POSIX: lib/pythonX.Y/site-packages
        sp_dirs = list(venv_root.glob("Lib/site-packages")) + \
                  list(venv_root.glob("lib/python*/site-packages"))
        for sp in sp_dirs:
            # Direct install
            if (sp / "quad" / "mcp" / "server.py").exists():
                return True
            # Editable install: .pth files add extra search paths
            for pth in sp.glob("*.pth"):
                try:
                    for line in pth.read_text(errors="ignore").splitlines():
                        line = line.strip()
                        if line and not line.startswith(("#", "import ")):
                            if (Path(line) / "quad" / "mcp" / "server.py").exists():
                                return True
                except Exception:
                    pass
        return False

    candidates: list[str] = []
    if override:
        candidates.append(override)
    if os.environ.get("QUAD_PYTHON"):
        candidates.append(os.environ["QUAD_PYTHON"])

    # Walk up from this script to find <workspace>/QUAD/.venv
    here = Path(__file__).resolve()
    for ancestor in here.parents:
        venv_py = ancestor / "QUAD" / ".venv" / "Scripts" / "python.exe"  # Windows
        if venv_py.exists():
            candidates.append(str(venv_py))
            break
        venv_py = ancestor / "QUAD" / ".venv" / "bin" / "python"  # POSIX
        if venv_py.exists():
            candidates.append(str(venv_py))
            break

    candidates.append(sys.executable)

    for py in candidates:
        if _can_import(py):
            return py

    # No local Python can serve quad.mcp.server. Rather than hard-failing,
    # fall back to the remote MCP server configured in .claude/settings.json
    # (retrospective issue 5) — the QAIRT SDK lives on the server anyway.
    remote = _remote_mcp_url()
    if remote:
        print(f"[info] Local server not found — routing to remote MCP at {remote}")
        return f"remote:{remote}"

    print("[error] Could not find a Python that can import quad.mcp.server,")
    print("        and no remote MCP server is configured in .claude/settings.json.")
    print()
    print("  Options:")
    print("    1. Pass --server-python <path>  to point at the right interpreter")
    print("    2. Set the QUAD_PYTHON env var:  set QUAD_PYTHON=C:\\path\\to\\python.exe")
    print("    3. Activate the QUAD venv and re-run:  .venv\\Scripts\\activate")
    print("    4. Configure a remote server:  quad-client install --transport sse-http --sse-url <url>")
    sys.exit(1)


def _resolve_sdk_root(quad_python: str) -> str | None:
    """Resolve the QAIRT/QNN SDK root directory.

    Search order:
      1. QNN_SDK_ROOT / QAIRT_SDK_ROOT env vars
      2. .QUAD/sdk/ directory (walking up from script dir)
      3. quad.sdk_manager.resolve_sdk_root() via the QUAD venv subprocess
      4. Direct scan of <workspace>/QUAD/sdks/ — picks the newest directory
    """
    for var in ("QNN_SDK_ROOT", "QAIRT_SDK_ROOT"):
        val = os.environ.get(var, "")
        if val and Path(val).is_dir():
            return val

    # Walk up from this script to find .QUAD/sdk/ (junction or real dir)
    here = Path(__file__).resolve()
    for ancestor in here.parents:
        sdk_dir = ancestor / ".QUAD" / "sdk"
        if sdk_dir.is_dir() and (sdk_dir / "lib" / "python").is_dir():
            return str(sdk_dir)

    # Ask the QUAD venv
    try:
        r = subprocess.run(
            [quad_python, "-c",
             "from quad.sdk_manager import resolve_sdk_root; "
             "info = resolve_sdk_root(); print(info.root if info else '')"],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except Exception:
        pass

    # Walk up from this script to find <workspace>/QUAD/sdks/
    for ancestor in here.parents:
        sdks_dir = ancestor / "QUAD" / "sdks"
        if sdks_dir.is_dir():
            versions = sorted(
                [d for d in sdks_dir.iterdir() if d.is_dir()],
                key=lambda p: p.name, reverse=True,
            )
            if versions:
                return str(versions[0])
    return None


def _run_qairt_converter_direct(
    model_path: Path,
    output_dir: Path,
    *,
    quad_python: str,
    input_name: str = "input",
    input_dims: str = "1,3,224,224",
) -> Path:
    """Run qairt-converter directly as a subprocess, bypassing the MCP server.

    This avoids a known deadlock with Python 3.13's ProactorEventLoop on Windows
    when asyncio.create_subprocess_exec is used (the MCP server path).

    Returns the output .dlc path.
    """
    sdk_root = _resolve_sdk_root(quad_python)
    if not sdk_root:
        print("[error] Cannot find QAIRT SDK root.")
        print("  Set QNN_SDK_ROOT or QAIRT_SDK_ROOT, or install the QUAD SDK.")
        sys.exit(1)

    sdk_root_path = Path(sdk_root)
    converter = sdk_root_path / "bin" / "x86_64-windows-msvc" / "qairt-converter"
    if not converter.exists():
        # Try aarch64
        converter = sdk_root_path / "bin" / "aarch64-windows-msvc" / "qairt-converter"
    if not converter.exists():
        print(f"[error] qairt-converter not found under {sdk_root_path / 'bin'}")
        sys.exit(1)

    output_dlc = output_dir / model_path.with_suffix(".dlc").name

    # Build CLI args
    cmd: list[str] = []

    # The converter is a Python script — needs a Python 3.10 interpreter
    qairt_py = _resolve_qairt_python()
    if qairt_py:
        cmd.append(qairt_py)

    cmd += [
        str(converter),
        "--input_network", str(model_path.resolve()),
        "--source_model_input_shape", input_name, input_dims,
        "--output_path", str(output_dlc),
    ]

    # Build env with PYTHONPATH pointing to SDK lib/python
    env = os.environ.copy()
    sdk_pylib = str(sdk_root_path / "lib" / "python")
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = sdk_pylib + (os.pathsep + existing if existing else "")
    env.setdefault("QAIRT_SDK_ROOT", sdk_root)
    env.setdefault("QNN_SDK_ROOT", sdk_root)

    print(f"  Converter    : {converter}")
    if qairt_py:
        print(f"  Python       : {qairt_py}")
    print(f"  SDK root     : {sdk_root}")

    t0 = time.perf_counter()
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300, env=env)
    elapsed = time.perf_counter() - t0

    if result.returncode != 0:
        print(f"[error] qairt-converter failed (exit {result.returncode}):")
        print(result.stderr[:1000] if result.stderr else "(no stderr)")
        sys.exit(1)

    if not output_dlc.exists():
        print(f"[error] Converter finished but output not found: {output_dlc}")
        sys.exit(1)

    size_mb = output_dlc.stat().st_size / 1_048_576
    print(f"  Output       : {output_dlc} ({size_mb:.1f} MB)")
    print(f"  Time         : {elapsed:.1f}s")

    return output_dlc


async def _call_convert(python_exe: str, tool_args: dict, adapter_mode: str) -> dict:
    try:
        from fastmcp import Client  # type: ignore[import-untyped]
        from fastmcp.client.transports.stdio import StdioTransport  # type: ignore[import-untyped]
    except ImportError:
        print("[error] fastmcp not installed. Run:  pip install fastmcp")
        sys.exit(1)

    # Remote fallback: when no local Python can serve quad.mcp.server,
    # _find_quad_python returns a "remote:<url>" sentinel instead of exiting.
    # Route the same convert_model call to the remote MCP over HTTP so the
    # developer isn't blocked by a missing local server (retrospective issue 5).
    if python_exe.startswith("remote:"):
        url = python_exe[len("remote:"):]
        return await _call_convert_remote(url, tool_args)

    # Pass QUAD_ADAPTER_MODE to the server subprocess so it uses the real SDK
    # rather than the mock adapter when the user requests real conversion.
    server_env = dict(os.environ)
    server_env["QUAD_ADAPTER_MODE"] = adapter_mode
    # Suppress the FastMCP startup banner — it goes to stdout and corrupts the
    # stdio MCP channel, causing JSONRPC parse errors on the client side.
    server_env["FASTMCP_SHOW_SERVER_BANNER"] = "false"

    # If QAIRT_SDK_ROOT is not in the environment (e.g. activate.ps1 was not
    # sourced in this shell), resolve it via the QUAD python so the server
    # subprocess can find the real adapter.
    if adapter_mode == "real" and not server_env.get("QAIRT_SDK_ROOT"):
        try:
            import subprocess as _sp
            r = _sp.run(
                [python_exe, "-c",
                 "from quad.sdk_manager import resolve_sdk_root; "
                 "info = resolve_sdk_root(); print(info.root if info else '')"],
                capture_output=True, text=True, timeout=10,
            )
            sdk_root = r.stdout.strip()
            if sdk_root:
                server_env["QAIRT_SDK_ROOT"] = sdk_root
                server_env.setdefault("QNN_SDK_ROOT", sdk_root)
                server_env.setdefault("SNPE_ROOT", sdk_root)
        except Exception:
            pass  # best-effort; server will warn if SDK still not found

    transport = StdioTransport(
        command=python_exe,
        args=["-m", "quad.mcp.server"],
        env=server_env,
        keep_alive=False,
    )

    async with Client(transport) as client:  # type: ignore[arg-type]
        response = await client.call_tool("convert_model", tool_args)

    return _parse_tool_result(response)


def _parse_tool_result(response) -> dict:  # noqa: ANN001
    # response is a CallToolResult: .content is list[ContentBlock], .structured_content is dict|None
    if getattr(response, "structured_content", None):
        return response.structured_content
    raw = next((b.text for b in response.content if hasattr(b, "text")), "{}")
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, AttributeError):
        return {"raw": raw}


def _remote_mcp_url() -> str | None:
    """Read the remote QUAD MCP URL from .claude/settings.json, if configured.

    Walks up from this script looking for a .claude/settings.json with an
    ``mcpServers.quad.transport`` of type http/sse and a ``url``. Returns the
    URL or None. This is what lets the sample fall back to the remote server
    when no local quad.mcp.server can be spawned (retrospective issue 5).
    """
    here = Path(__file__).resolve()
    for ancestor in [here.parent, *here.parents]:
        settings = ancestor / ".claude" / "settings.json"
        if not settings.is_file():
            continue
        try:
            cfg = json.loads(settings.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        servers = (cfg.get("mcpServers") or {})
        for server in servers.values():
            transport = (server.get("transport") or {}) if isinstance(server, dict) else {}
            if transport.get("type") in ("http", "sse") and transport.get("url"):
                return transport["url"]
    return None


async def _call_convert_remote(url: str, tool_args: dict) -> dict:
    """Call convert_model on a remote MCP server over HTTP/SSE."""
    from fastmcp import Client  # type: ignore[import-untyped]

    # fastmcp does NOT auto-read auth from the environment. If the remote server
    # requires a bearer token, read it from QUAD_MCP_TOKEN and inject an
    # Authorization header via an explicit HTTP transport; otherwise fall back to
    # passing the URL directly.
    token = os.environ.get("QUAD_MCP_TOKEN", "").strip()
    if token:
        from fastmcp.client.transports import (
            StreamableHttpTransport,  # type: ignore[import-untyped]
        )
        transport = StreamableHttpTransport(
            url, headers={"Authorization": f"Bearer {token}"}
        )
        client_target = transport
    else:
        client_target = url

    async with Client(client_target) as client:  # type: ignore[arg-type]
        response = await client.call_tool("convert_model", tool_args)
    return _parse_tool_result(response)


def step2_convert(
    model_path: Path,
    output_dir: Path,
    *,
    calibration: str | None,
    server: str,
    server_python: str | None,
    target_sdk: str,
    adapter_mode: str,
) -> tuple[Path, str]:
    """Returns (converted_model_path, quad_python_exe)."""
    print("=" * 60)
    print("STEP 2 — Convert to INT8")
    print("=" * 60)

    output_dir.mkdir(parents=True, exist_ok=True)

    # Resolve which Python can serve quad.mcp.server (stdio) or use URL as-is (http)
    if server == "stdio":
        python_exe = _find_quad_python(server_python)
    else:
        python_exe = server  # unused for HTTP path; kept for type consistency

    server_display = (
        f"{python_exe} -m quad.mcp.server" if server == "stdio" else server
    )

    print(f"  Adapter mode : {adapter_mode}")
    print(f"  Model        : {model_path}")
    print("  Quantization : INT8")
    print(f"  Target SDK   : {target_sdk}")
    print(f"  Server       : {server_display}")

    # ── MCP server conversion ────────────────────────────────────────

    tool_args: dict = {
        "source_format":    "onnx",
        "model_path":       str(model_path.resolve()),
        "target_sdk":       target_sdk,
        "quantization":     "fp32",
        "input_name":       "input",
        "input_dimensions": "1,3,224,224",
    }
    if calibration:
        cal = Path(calibration)
        if cal.is_dir():
            tool_args["calibration_data"] = str(cal.resolve())
        else:
            print(f"  [warn] Calibration directory not found: {cal} — skipping.")

    if "calibration_data" in tool_args:
        print(f"  Calibration  : {tool_args['calibration_data']}")
    print()

    result = asyncio.run(_call_convert(python_exe, tool_args, adapter_mode))

    if result.get("status") == "error":
        print(f"[error] Conversion failed: {result.get('message', result)}")
        sys.exit(1)

    # Print conversion table
    rows = [
        ("Original size",   result.get("original_size_mb",    "?"), "MB"),
        ("Output size",     result.get("model_size_mb",       "?"), "MB"),
        ("Compression",     result.get("compression_ratio",   "?"), "×"),
        ("Quantization",    result.get("quantization_applied","?"), ""),
        ("Supported ops",   result.get("supported_ops_pct",   "?"), "%"),
        ("Conversion time", result.get("conversion_time_s",   "?"), "s"),
        ("Target SDK",      result.get("target_sdk",          "?"), ""),
        ("Output path",     result.get("output_path",         "?"), ""),
    ]
    col = max(len(r[0]) for r in rows) + 2
    for label, value, unit in rows:
        print(f"  {label:<{col}} {value} {unit}".rstrip())

    notes = result.get("image_format_notes")
    if notes:
        print()
        print("  Image format guidance:")
        for note in (notes if isinstance(notes, list) else [notes]):
            print(f"    • {note}")

    unsupported = result.get("unsupported_ops", [])
    if unsupported:
        print()
        print(f"  [warn] {len(unsupported)} op(s) will fall back to CPU: {unsupported}")

    output_path = Path(result.get("output_path", output_dir))
    print()
    # If conversion was routed to a remote MCP (no local server python), the
    # downstream LOCAL steps (NPU inference, SDK pythonpath) still need a local
    # interpreter — hand back the current one rather than the "remote:" sentinel.
    local_python = sys.executable if python_exe.startswith("remote:") else python_exe
    return output_path, local_python


def _inject_sdk_pythonpath(quad_python: str) -> str | None:
    """
    Resolve the QAIRT/QNN SDK root and inject <sdk_root>/lib/python into
    sys.path + os.environ so qnn_wrapper_api is importable without any
    manual env-var setup.

    Discovery order (first hit wins):
      1. QNN_SDK_ROOT / QAIRT_SDK_ROOT already in the current environment
      2. quad.sdk_manager.resolve_sdk_root() via the QUAD venv subprocess
      3. Direct scan of <workspace>/QUAD/sdks/ — picks the newest directory

    Returns the SDK root path on success, None if no SDK is found.
    """
    def _inject(sdk_root: str) -> str | None:
        lib_python = str(Path(sdk_root) / "lib" / "python")
        if not Path(lib_python).is_dir():
            return None
        if lib_python not in sys.path:
            sys.path.insert(0, lib_python)
        os.environ.setdefault("QNN_SDK_ROOT", sdk_root)
        os.environ.setdefault("QAIRT_SDK_ROOT", sdk_root)
        existing = os.environ.get("PYTHONPATH", "")
        if lib_python not in existing:
            os.environ["PYTHONPATH"] = f"{lib_python}{os.pathsep}{existing}" if existing else lib_python
        return sdk_root

    # 1. Env vars already set (e.g. permanent User-scope vars in a new session)
    for var in ("QNN_SDK_ROOT", "QAIRT_SDK_ROOT"):
        val = os.environ.get(var, "")
        if val and Path(val).is_dir():
            result = _inject(val)
            if result:
                return result

    # 1b. .QUAD/sdk/ directory (junction or real dir, walking up from script)
    here = Path(__file__).resolve()
    for ancestor in here.parents:
        sdk_dir = ancestor / ".QUAD" / "sdk"
        if sdk_dir.is_dir() and (sdk_dir / "lib" / "python").is_dir():
            result = _inject(str(sdk_dir))
            if result:
                return result

    # 2. Ask quad.sdk_manager in the QUAD venv subprocess
    script = (
        "import json; "
        "from quad.sdk_manager import resolve_sdk_root; "
        "info = resolve_sdk_root(); "
        "print(json.dumps(info.to_dict()) if info else 'null')"
    )
    try:
        out = subprocess.check_output(
            [quad_python, "-c", script],
            stderr=subprocess.DEVNULL,
            timeout=10,
            text=True,
        ).strip()
        if out and out != "null":
            info = json.loads(out)
            sdk_root = info.get("root", "")
            if sdk_root:
                result = _inject(sdk_root)
                if result:
                    return result
    except Exception:
        pass

    # 3. Direct scan of <workspace>/QUAD/sdks/ — works even before env vars
    #    are active in the current session
    here = Path(__file__).resolve()
    for ancestor in here.parents:
        sdks_dir = ancestor / "QUAD" / "sdks"
        if sdks_dir.is_dir():
            # Sort descending by name — newest version first (e.g. qairt-2.46 > qairt-2.41)
            candidates = sorted(
                (d for d in sdks_dir.iterdir() if d.is_dir()),
                reverse=True,
            )
            for sdk_dir in candidates:
                result = _inject(str(sdk_dir))
                if result:
                    return result
            break

    return None


# ---------------------------------------------------------------------------
# Step 3 — Test on target
# ---------------------------------------------------------------------------

def _preprocess(image_path: str) -> np.ndarray:
    import numpy as np
    from PIL import Image  # type: ignore[import-untyped]

    img = Image.open(image_path).convert("RGB").resize((224, 224))
    arr = np.array(img, dtype=np.float32)
    arr = (arr - np.array(IMAGENET_MEAN, dtype=np.float32)) / np.array(IMAGENET_STD, dtype=np.float32)
    arr = arr.transpose(2, 0, 1)          # NHWC → NCHW
    return np.expand_dims(arr, axis=0)    # (1, 3, 224, 224)


def _run_qnn(model_path: str, inp: np.ndarray) -> tuple[np.ndarray, float]:
    """Run a QNN context binary via qnn-net-run.exe.

    Delegates to quad_mcp_client.qnn_utils which handles:
      • Windows ARM64 arch detection (PROCESSOR_IDENTIFIER / PROCESSOR_ARCHITEW6432)
      • Correct SDK arch-dir selection (aarch64-windows-msvc vs x86_64-windows-msvc)
      • libcdsprpc.dll discovery in the Windows DriverStore
      • Subprocess PATH construction and qnn-net-run invocation
    """
    from quad_mcp_client.qnn_utils import run_qnn_net_run

    # Only accept env-var values when the path actually exists on disk.
    # QNN_SDK_ROOT can be stale (e.g. pointing at a previously installed
    # SDK version that was later removed). Fall back to the walk-up
    # discovery so a stale var doesn't silently block GPU/NPU benchmarks.
    sdk_root = None
    for var in ("QNN_SDK_ROOT", "QAIRT_SDK_ROOT"):
        val = os.environ.get(var, "").strip()
        if val and Path(val).is_dir():
            sdk_root = val
            break

    if not sdk_root:
        # Auto-discover by walking the workspace tree (mirrors _resolve_sdk_root)
        here = Path(__file__).resolve()
        for ancestor in here.parents:
            sdks_dir = ancestor / "QUAD" / "sdks"
            if sdks_dir.is_dir():
                candidates = sorted(
                    (d for d in sdks_dir.iterdir() if d.is_dir()),
                    key=lambda p: p.name, reverse=True,
                )
                if candidates:
                    sdk_root = str(candidates[0])
                    break

    if not sdk_root:
        raise RuntimeError("QNN_SDK_ROOT not set and SDK not found — cannot run qnn-net-run")

    return run_qnn_net_run(model_path, inp, sdk_root)


def _run_onnxruntime(onnx_path: str, inp: np.ndarray) -> tuple[np.ndarray, float]:
    """CPU fallback via onnxruntime when QNN/SNPE bindings are not available."""
    try:
        import onnxruntime as ort  # type: ignore[import-untyped]
    except ImportError:
        print("[error] onnxruntime not installed. Run:  pip install onnxruntime")
        sys.exit(1)

    sess = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])
    input_name = sess.get_inputs()[0].name
    t0 = time.perf_counter()
    outputs = sess.run(None, {input_name: inp})
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    return outputs[0], elapsed_ms


def _run_snpe(model_path: str, inp: np.ndarray) -> tuple[np.ndarray, float]:
    try:
        from snpe import snpe_utils  # type: ignore[import-untyped]
    except ImportError:
        raise RuntimeError("snpe not importable")

    inp_nhwc = inp.transpose(0, 2, 3, 1)   # NCHW → NHWC for SNPE
    runner = snpe_utils.SNPERunner(model_path, runtime="dsp")
    runner.load()
    t0 = time.perf_counter()
    outputs = runner.execute({"input_1:0": inp_nhwc})
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    runner.unload()
    return outputs["MobilenetV2/Predictions/Reshape_1:0"], elapsed_ms


def _topk(logits: np.ndarray, k: int) -> list[tuple[int, float]]:
    import numpy as np
    scores = logits.flatten()
    scores = scores - scores.max()
    exp = np.exp(scores)
    probs = exp / exp.sum()
    indices = np.argsort(probs)[::-1][:k]
    return [(int(i), float(probs[i])) for i in indices]


def _bench(
    run_fn: Any,
    model_path: str,
    inp: np.ndarray,
    warmup: int,
    runs: int,
    label: str,
) -> dict:
    """
    Warm up then time `runs` inference calls.
    Also samples CPU utilisation and process CPU-time during each run as
    a lightweight power proxy (higher CPU time → more power drawn).
    Returns a dict with timing stats, CPU stats, and the final logits.
    """
    import numpy as np
    import psutil

    proc = psutil.Process()

    print(f"  [{label}] warmup ({warmup} run(s)) …")
    for _ in range(warmup):
        logits, _ = run_fn(model_path, inp)

    print(f"  [{label}] timed  ({runs} run(s)) …")
    times_ms: list[float] = []
    cpu_pcts: list[float] = []
    cpu_times_s: list[float] = []

    for i in range(runs):
        psutil.cpu_percent(interval=None)          # reset the interval counter
        ct_before = sum(proc.cpu_times()[:2])      # user + system seconds
        logits, ms = run_fn(model_path, inp)
        ct_after = sum(proc.cpu_times()[:2])
        cpu_pct = psutil.cpu_percent(interval=None)

        times_ms.append(ms)
        cpu_pcts.append(cpu_pct)
        cpu_times_s.append(ct_after - ct_before)
        print(f"    run {i+1:>2}: {ms:6.1f} ms   CPU {cpu_pct:4.0f}%")

    return {
        "label":        label,
        "logits":       logits,
        "times_ms":     times_ms,
        "avg_ms":       float(np.mean(times_ms)),
        "min_ms":       float(np.min(times_ms)),
        "p95_ms":       float(np.percentile(times_ms, 95)),
        "fps":          float(1000.0 / np.mean(times_ms)),
        "cpu_pct_avg":  float(np.mean(cpu_pcts)),
        "cpu_time_s":   float(np.mean(cpu_times_s)),
    }


def _print_comparison(cpu: dict, npu: dict, top_k: int, labels: dict, gpu: dict | None = None) -> None:
    """Print a side-by-side CPU vs GPU vs NPU comparison table."""

    has_gpu = gpu is not None
    col = 18

    def row(label: str, cpu_val: str, gpu_val: str, npu_val: str) -> None:
        if has_gpu:
            print(f"  {label:<22}  {cpu_val:>{col}}  {gpu_val:>{col}}  {npu_val:>{col}}")
        else:
            print(f"  {label:<28}  {cpu_val:>{col+4}}  {npu_val:>{col+4}}")

    if has_gpu:
        title = "COMPARISON — CPU vs GPU (Adreno) vs NPU (QNN HTP)"
        sep = "─" * (22 + 2 + col + 2 + col + 2 + col + 2)
    else:
        title = "COMPARISON — CPU (onnxruntime) vs NPU (QNN HTP)"
        sep = "─" * (28 + 2 + (col + 4) + 2 + (col + 4) + 2)

    print()
    print("=" * 60)
    print(title)
    print("=" * 60)
    print()

    if has_gpu:
        print(f"  {'Metric':<22}  {'CPU':>{col}}  {'GPU (Adreno)':>{col}}  {'NPU (HTP)':>{col}}")
    else:
        print(f"  {'Metric':<28}  {'CPU (onnxruntime)':>{col+4}}  {'NPU (QNN HTP)':>{col+4}}")
    print(f"  {sep}")

    speedup_npu = cpu["avg_ms"] / npu["avg_ms"] if npu["avg_ms"] > 0 else float("nan")
    gpu_speedup_str = ""
    if has_gpu:
        speedup_gpu = cpu["avg_ms"] / gpu["avg_ms"] if gpu["avg_ms"] > 0 else float("nan")
        gpu_speedup_str = f"{speedup_gpu:.1f}×"

    row("Avg latency",
        f"{cpu['avg_ms']:.1f} ms",
        f"{gpu['avg_ms']:.2f} ms" if has_gpu else "",
        f"{npu['avg_ms']:.2f} ms")
    row("Min latency",
        f"{cpu['min_ms']:.1f} ms",
        f"{gpu['min_ms']:.2f} ms" if has_gpu else "",
        f"{npu['min_ms']:.2f} ms")
    row("Throughput",
        f"{cpu['fps']:.0f} FPS",
        f"{gpu['fps']:.0f} FPS" if has_gpu else "",
        f"{npu['fps']:.0f} FPS")
    row("Speedup",
        "1.0×",
        gpu_speedup_str,
        f"{speedup_npu:.1f}×")

    # NPU iteration count (batch benchmark gives this)
    npu_iters = npu.get("num_iters")
    if npu_iters:
        gpu_iters_str = str(gpu.get("num_iters", len(gpu.get("times_ms", [])))) if has_gpu else ""
        row("Iterations",
            f"{len(cpu.get('times_ms', []))}",
            gpu_iters_str,
            f"{npu_iters}")

    # Power estimates (Snapdragon X Elite X1E78100 TDP envelope)
    CPU_TDP_W = 23.0   # peak CPU package power
    GPU_TDP_W = 8.0    # Adreno GPU typical active power
    NPU_TDP_W = 4.5    # HTP NPU typical active power
    cpu_pct = cpu.get("cpu_pct_avg", 0)
    if cpu_pct > 0:
        print(f"  {sep}")
        cpu_est_w = CPU_TDP_W * cpu_pct / 100.0
        row("Avg CPU util",
            f"{cpu_pct:.0f}%",
            f"~{gpu.get('cpu_pct_avg', 0):.0f}%" if has_gpu else "",
            "~0% (offloaded)")
        row("Est. pkg power",
            f"~{cpu_est_w:.1f} W",
            f"~{GPU_TDP_W:.1f} W" if has_gpu else "",
            f"~{NPU_TDP_W:.1f} W")
    print()

    # Timeline bar chart — CPU only (NPU used batch mode, no per-run breakdown)
    cpu_times = cpu.get("times_ms", [])
    if cpu_times:
        print("  CPU latency per run:")
        cpu_avg = cpu["avg_ms"]
        BAR_WIDTH = 30
        for i, ms in enumerate(cpu_times):
            bar_len = max(1, int(ms / cpu_avg * BAR_WIDTH / 2))
            bar = "█" * bar_len
            print(f"    run {i+1:>2}: {bar:<{BAR_WIDTH}} {ms:.1f} ms")
        print()

    # Top-K predictions (NPU preferred, then GPU, then CPU)
    if npu.get("logits") is not None:
        best, source = npu, "NPU"
    elif has_gpu and gpu.get("logits") is not None:
        best, source = gpu, "GPU"
    else:
        best, source = cpu, "CPU"
    predictions = _topk(best["logits"], k=top_k)
    print(f"  Top-{top_k} predictions ({source}):")
    for rank, (class_id, prob) in enumerate(predictions, 1):
        label_str = labels.get(class_id, f"class_{class_id}")
        print(f"    {rank}. {label_str:<30} {prob*100:5.1f}%")
    print()


def step3_test(
    model_path: Path,
    image_path: str,
    labels_path: Path,
    *,
    quad_python: str,
    sdk: str,
    warmup: int,
    runs: int,
    top_k: int,
) -> None:

    print("=" * 60)
    print("STEP 3 — CPU vs GPU vs NPU Benchmark (Snapdragon X Elite)")
    print("=" * 60)

    # Auto-detect SDK from extension.
    # Always use the QNN path: run_qnn_net_run handles both context binaries
    # (.bin via --retrieve_context) and DLC files (.dlc via --dlc_path +
    # QnnModelDlc.dll).  The SNPE Python-bindings path is kept for explicit
    # --sdk snpe overrides only.
    if sdk == "auto":
        sdk = "qnn"

    # Inject SDK Python bindings + set QNN_SDK_ROOT in os.environ
    sdk_root = _inject_sdk_pythonpath(quad_python)
    if sdk_root:
        print(f"  SDK      : {sdk_root}")

    print(f"  Model    : {model_path}")
    print(f"  Image    : {image_path}")
    print()

    inp = _preprocess(image_path)
    # Derive the original ONNX name — strip any conversion suffixes that the
    # adapter may have appended (_int8, _quantized, _simplified, _static).
    stem = model_path.stem
    for _sfx in ("_quantized", "_int8", "_simplified", "_static"):
        if stem.endswith(_sfx):
            stem = stem[: -len(_sfx)]
            break
    # Search both the converted model's directory and the script's directory
    # (direct conversion puts the DLC in output/ while the ONNX stays at root).
    _onnx_name = stem + ".onnx"
    onnx_path = str(model_path.parent / _onnx_name)
    if not Path(onnx_path).exists():
        _script_dir = Path(__file__).resolve().parent
        onnx_path = str(_script_dir / _onnx_name)

    # Load labels
    labels: dict[int, str] = {}
    if labels_path.exists():
        lines = labels_path.read_text().splitlines()
        labels = {i: line.strip() for i, line in enumerate(lines)}

    # --- CPU benchmark (always runs) ----------------------------------------
    print("  ── CPU (onnxruntime) ──────────────────────────────")
    if not Path(onnx_path).exists():
        print(f"  [error] ONNX model not found at {onnx_path} — cannot run CPU benchmark")
        sys.exit(1)
    cpu_result = _bench(_run_onnxruntime, onnx_path, inp, warmup, runs, "CPU")
    print()

    # --- GPU benchmark (attempted; graceful skip if SDK missing) ------------
    print("  ── GPU (Adreno via QNN) ───────────────────────────")
    gpu_result: dict | None = None
    if sdk == "qnn":
        try:
            from quad_mcp_client.qnn_utils import benchmark_qnn_net_run

            gpu_sdk_root = _get_sdk_root_safe()
            if not gpu_sdk_root:
                raise RuntimeError("QNN_SDK_ROOT not set and SDK not found")

            duration_s = max(3, runs)
            print(f"  Running qnn-net-run --duration {duration_s}s --backend libQnnGpu ...")
            bench = benchmark_qnn_net_run(
                str(model_path), inp, gpu_sdk_root,
                duration_s=duration_s, perf_profile="burst",
                timeout=duration_s + 60,
                backend="gpu",
            )
            print(f"  {bench['num_iters']} iterations in {bench['wall_s']:.1f}s"
                  f"  (avg {bench['avg_ms']:.2f} ms, {bench['fps']:.0f} FPS)")
            print()

            gpu_result = {
                "label":       "GPU",
                "logits":      bench["logits"],
                "avg_ms":      bench["avg_ms"],
                "min_ms":      bench["avg_ms"],
                "p95_ms":      bench["avg_ms"],
                "fps":         bench["fps"],
                "cpu_pct_avg": 0.0,
                "cpu_time_s":  0.0,
                "num_iters":   bench["num_iters"],
                "wall_s":      bench["wall_s"],
            }
        except (RuntimeError, FileNotFoundError, TypeError) as exc:
            first_line = str(exc).splitlines()[0]
            print(f"  [warn] GPU benchmark skipped: {first_line}")
            print()

    # --- NPU benchmark (attempted; graceful skip if SDK missing) ------------
    print("  ── NPU (QNN HTP) ──────────────────────────────────")
    npu_result: dict | None = None
    if sdk == "qnn":
        try:
            from quad_mcp_client.qnn_utils import benchmark_qnn_net_run

            npu_sdk_root = _get_sdk_root_safe()
            if not npu_sdk_root:
                raise RuntimeError("QNN_SDK_ROOT not set and SDK not found")

            # Single-process benchmark: qnn-net-run --duration keeps the graph
            # loaded and iterates for `runs` seconds, avoiding per-call process
            # spawn overhead (~1 s) that dominates single-inference timing.
            duration_s = max(3, runs)  # at least 3 seconds
            print(f"  Running qnn-net-run --duration {duration_s}s --perf_profile burst ...")
            bench = benchmark_qnn_net_run(
                str(model_path), inp, npu_sdk_root,
                duration_s=duration_s, perf_profile="burst",
                timeout=duration_s + 60,
            )
            print(f"  {bench['num_iters']} iterations in {bench['wall_s']:.1f}s"
                  f"  (avg {bench['avg_ms']:.2f} ms, {bench['fps']:.0f} FPS)")
            print()

            # Build a result dict compatible with _print_comparison
            npu_result = {
                "label":       "NPU",
                "logits":      bench["logits"],
                "avg_ms":      bench["avg_ms"],
                "min_ms":      bench["avg_ms"],   # single-process — no per-iter breakdown
                "p95_ms":      bench["avg_ms"],
                "fps":         bench["fps"],
                "cpu_pct_avg": 0.0,               # NPU offloads compute; CPU mostly idle
                "cpu_time_s":  0.0,
                "num_iters":   bench["num_iters"],
                "wall_s":      bench["wall_s"],
            }
        except (RuntimeError, FileNotFoundError) as exc:
            first_line = str(exc).splitlines()[0]
            print(f"  [warn] NPU benchmark skipped: {first_line}")
            print()
            print("  To enable NPU inference:")
            print("    1. Install the QUAD server with a real QAIRT SDK")
            print("       (see https://github.qualcomm.com/pavanr/QUAD)")
            print("    2. Re-run with:  python run_mobilenetv2.py --adapter-mode real")
            print("       or set:       set QUAD_ADAPTER_MODE=real")
            print("    3. Verify setup: quad doctor")
            print()
    else:
        # SNPE path — keep the Python-loop approach
        npu_run_fn = _run_snpe
        try:
            npu_result = _bench(npu_run_fn, str(model_path), inp, warmup, runs, "NPU")
        except (RuntimeError, FileNotFoundError) as exc:
            first_line = str(exc).splitlines()[0]
            print(f"  [warn] NPU benchmark skipped: {first_line}")
            print()

    # --- Comparison ---------------------------------------------------------
    if npu_result is None and gpu_result is None:
        # Both GPU and NPU unavailable — print CPU-only summary
        print()
        print("  ── CPU-only summary (GPU/NPU unavailable) ────────")
        print(f"    Avg : {cpu_result['avg_ms']:.1f} ms  ({cpu_result['fps']:.0f} FPS)")
        print(f"    Min : {cpu_result['min_ms']:.1f} ms")
        print(f"    P95 : {cpu_result['p95_ms']:.1f} ms")
        print()
        predictions = _topk(cpu_result["logits"], k=top_k)
        print(f"  Top-{top_k} predictions (CPU):")
        for rank, (class_id, prob) in enumerate(predictions, 1):
            label_str = labels.get(class_id, f"class_{class_id}")
            print(f"    {rank}. {label_str:<30} {prob*100:5.1f}%")
        print()
    elif npu_result is not None:
        _print_comparison(cpu_result, npu_result, top_k, labels, gpu=gpu_result)
    else:
        # GPU available but NPU not — compare CPU vs GPU only
        _print_comparison(cpu_result, gpu_result, top_k, labels)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Download, convert, and test MobileNetV2 INT8 on Snapdragon X Elite.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    # Step 1
    p.add_argument("--model",         default="mobilenetv2.onnx",
                   help="Local path for the downloaded ONNX model")
    p.add_argument("--labels",        default="imagenet_classes.txt",
                   help="Local path for ImageNet class labels")
    p.add_argument("--skip-download", action="store_true",
                   help="Skip download if the model file already exists")
    # Step 2
    p.add_argument("--output-dir",    default="output",
                   help="Directory to write the converted INT8 model")
    p.add_argument("--calibration",   default=None,
                   help="Directory of calibration images (optional, improves INT8 accuracy)")
    p.add_argument("--server",        default="stdio",
                   help="QUAD server: 'stdio' (local subprocess) or HTTP/SSE URL")
    p.add_argument("--server-python", default=None,
                   help=(
                       "Python executable that can import quad.mcp.server "
                       "(default: auto-detected from QUAD/.venv). "
                       "Also honoured via the QUAD_PYTHON env var."
                   ))
    p.add_argument("--adapter-mode",  default=None,
                   choices=["mock", "real"],
                   help=(
                       "QUAD server adapter mode. 'real' uses the installed QAIRT SDK "
                       "to produce an actual QNN context binary; 'mock' returns simulated "
                       "metrics without writing a file. "
                       "Defaults to the QUAD_ADAPTER_MODE env var, or 'real' if unset."
                   ))
    p.add_argument("--target-sdk",    default="qnn",
                   choices=["qnn", "snpe", "qairt"],
                   help="Target Qualcomm SDK")
    # Step 3
    p.add_argument("--image",         default="test_input.jpg",
                   help="Test image path (JPEG / PNG). Auto-downloaded if not found (default: test_input.jpg)")
    p.add_argument("--sdk",           default="auto",
                   choices=["auto", "qnn", "snpe"],
                   help="Inference SDK (auto detects from model extension)")
    p.add_argument("--warmup",        type=int, default=3,
                   help="Warmup runs before timing")
    p.add_argument("--runs",          type=int, default=10,
                   help="Timed inference runs")
    p.add_argument("--top-k",         type=int, default=5,
                   help="Top-K predictions to display")
    return p.parse_args()


def main() -> None:
    args = _parse_args()

    model_path  = Path(args.model)
    labels_path = Path(args.labels)
    output_dir  = Path(args.output_dir)

    # Resolve adapter mode: CLI flag > env var > default 'real'
    adapter_mode = (
        args.adapter_mode
        or os.environ.get("QUAD_ADAPTER_MODE", "real")
    )

    # Step 1 — Download
    image_path = step1_download(model_path, labels_path, args.image, skip=args.skip_download)

    # Step 1.5 — Simplify ONNX for QAIRT compatibility
    _simplify_onnx_inplace(model_path)

    # Step 2 — Convert
    converted_path, quad_python = step2_convert(
        model_path,
        output_dir,
        calibration=args.calibration,
        server=args.server,
        server_python=args.server_python,
        target_sdk=args.target_sdk,
        adapter_mode=adapter_mode,
    )

    # Step 3 — Test on target
    step3_test(
        converted_path,
        image_path,
        labels_path,
        quad_python=quad_python,
        sdk=args.sdk,
        warmup=args.warmup,
        runs=args.runs,
        top_k=args.top_k,
    )


if __name__ == "__main__":
    main()
