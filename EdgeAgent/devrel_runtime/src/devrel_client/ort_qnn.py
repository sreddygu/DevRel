"""onnxruntime-qnn NPU helper — the QNNExecutionProvider developer path.

This module is the *code* behind the IQ-9075 retrospective findings that the
sample scripts never actually implemented (they shelled out to ``qnn-net-run``
instead). It gives developers a small, correct API for running ONNX models on
the Hexagon NPU through ONNX Runtime's QNN Execution Provider, with the guard
rails the retrospective asked for:

* **No silent CPU fallback** (issue 8) — :func:`create_npu_session` raises
  :class:`NPUFallbackError` when the NPU EP fails to become active, unless the
  caller explicitly opts in with ``allow_fallback=True``.
* **Provider verification** (issue 9) — :func:`assert_npu_active` /
  ``session.get_providers()[0]`` is the one reliable check that inference is on
  the NPU. ``create_npu_session`` runs it for you.
* **Per-layer NPU/CPU split** (issues 11, 12) — :func:`provider_split` reports
  which ops ran on the NPU (HTP) vs CPU. ONNX Runtime has **no**
  ``get_node_provider_assignments()`` API, so we parse the session profiling
  JSON (``enable_profiling``) — the same data ORT itself records.
* **First-run HTP warmup** (issue 21) — :func:`warmup` runs the one-time HTP
  compilation pass and prints that it is excluded from timing; combine with a
  persistent ``cache_dir`` so compilation happens once across runs.
* **QNN EP double-registration guard** (issue IQ9-32) — a module-level guard
  keeps a single process from registering the QNN EP twice (which masked the
  real GPU error during bring-up).

The heavy imports (``onnxruntime``, ``numpy``) are function-local so importing
this module never fails on a machine without the NPU wheels — the caller gets a
clear error only when they actually try to use it.
"""

from __future__ import annotations

import json
import platform
import sys
import threading
from collections import Counter
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - typing only
    import onnxruntime as ort  # noqa: F401

QNN_EP = "QNNExecutionProvider"
CPU_EP = "CPUExecutionProvider"
# ORT 1.27+ registers the QNN plugin EP under the short name "QNN" rather than
# "QNNExecutionProvider". We check both so the module works across ORT versions.
_QNN_EP_ALIASES = {"QNNExecutionProvider", "QNN"}

# Module-level guard: a process should register the QNN EP once. Registering it
# twice (e.g. an NPU attempt followed by a GPU attempt) masked the real GPU
# error during IQ-9075 bring-up. Guarded behind a lock for thread safety.
_registration_lock = threading.Lock()
_qnn_registered = False


class NPUFallbackError(RuntimeError):
    """Raised when the NPU (QNN EP) is not the active provider.

    ONNX Runtime silently falls back to the CPU EP when QNN initialization or
    execution fails — inference still completes and results look correct, so the
    only signal is the active provider. This error makes that failure loud
    instead of silent.
    """

    def __init__(self, active_provider: str, model_path: str = "") -> None:
        self.active_provider = active_provider
        self.model_path = model_path
        super().__init__(
            f"NPU (QNNExecutionProvider) is not active — ONNX Runtime is using "
            f"'{active_provider}'. Inference would run on the CPU, not the NPU. "
            f"Common causes: onnxruntime (not onnxruntime-qnn) is installed, the "
            f"model is not QNN-compatible, or the QNN backend libraries are not on "
            f"the path. Pass allow_fallback=True to permit CPU execution."
        )


class ConvIntegerFormatError(RuntimeError):
    """Raised when an INT8 model uses ConvInteger format instead of QDQ.

    The Hexagon HTP only accepts QDQ (QuantizeLinear/DequantizeLinear) INT8. A
    ConvInteger / MatMulInteger / DynamicQuantizeLinear model loads without any
    error but is silently rejected by the HTP and run on CPU (IQ9 issue 23).
    We detect it before session creation and fail loudly.
    """

    def __init__(self, ops: list[str], model_path: str = "") -> None:
        self.ops = ops
        self.model_path = model_path
        op_str = ", ".join(sorted(set(ops))) or "ConvInteger"
        super().__init__(
            f"Model uses ConvInteger INT8 format ({op_str}) — not supported on "
            "Hexagon HTP. The NPU requires QDQ (QuantizeLinear/DequantizeLinear) "
            "quantization; a ConvInteger model runs on CPU with no error. "
            "Re-quantize with QuantFormat.QDQ (onnxruntime quantize_static) or "
            "AIMET. Pass check_format=False / allow_fallback=True to bypass."
        )


# Integer-compute / dynamic-quant ops that mark an ONNX model as ConvInteger
# style — unloadable on the Hexagon HTP. Mirrors
# ``devrel.compiler.quant_format.CONVINTEGER_OPS`` on the server side.
_CONVINTEGER_OPS = frozenset({
    "ConvInteger", "MatMulInteger", "DynamicQuantizeLinear",
    "QLinearConv", "QLinearMatMul",
})


def convinteger_ops(model_path: str | Path) -> list[str]:
    """Return the ConvInteger-style op_types present in an ONNX model.

    Empty list means the model is QDQ or float (HTP-loadable), or the model
    couldn't be inspected (onnx not installed / unreadable) — in which case we
    never block, matching the "probe failure must not break the flow" rule.
    """
    if not str(model_path).lower().endswith(".onnx"):
        return []
    try:
        import onnx  # noqa: PLC0415
    except ImportError:
        return []
    try:
        model = onnx.load(str(model_path), load_external_data=False)
    except Exception:  # noqa: BLE001
        return []
    found = [
        n.op_type
        for n in model.graph.node
        if getattr(n, "op_type", "") in _CONVINTEGER_OPS
    ]
    return found


def qnn_backend_library() -> str:
    """Return the QNN HTP backend library name for this OS.

    ``QnnHtp.dll`` on Windows, ``libQnnHtp.so`` elsewhere. HTP = Hexagon Tensor
    Processor (the NPU).
    """
    return "QnnHtp.dll" if sys.platform == "win32" else "libQnnHtp.so"


def _qnn_provider_options(cache_dir: str | Path | None) -> dict[str, str]:
    """Build the QNN EP provider-options dict.

    ``backend_path`` selects the HTP (NPU) backend. When ``cache_dir`` is set we
    enable ONNX Runtime's EP context cache so the compiled HTP binary is written
    once and reused across sessions/processes — eliminating the 10–20× first-run
    compile penalty on every subsequent run (issue 21).
    """
    opts: dict[str, str] = {"backend_path": qnn_backend_library()}
    if cache_dir is not None:
        cache_dir = Path(cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)
        # ONNX Runtime EPContext cache: persist the compiled context next to the
        # model so HTP compilation is a one-time cost.
        opts["ep.context_enable"] = "1"
        opts["ep.context_file_path"] = str(cache_dir / "qnn_context.onnx")
    return opts


def create_npu_session(
    model_path: str | Path,
    *,
    allow_fallback: bool = False,
    check_format: bool = True,
    cache_dir: str | Path | None = None,
    session_options: ort.SessionOptions | None = None,
) -> ort.InferenceSession:
    """Create an ONNX Runtime session pinned to the Hexagon NPU (QNN EP).

    The QNN EP is listed first with the CPU EP only as an explicit fallback. We
    then verify the NPU is actually the active provider — ORT silently falls
    back to CPU on QNN failure, so this is the only reliable check.

    Args:
        model_path: Path to the ONNX model (ideally QDQ INT8 for the HTP).
        allow_fallback: When False (default), raise :class:`NPUFallbackError` if
            the NPU EP did not become active. When True, a CPU session is
            allowed — matches the retrospective's "fallback must be opt-in".
        check_format: When True (default), reject a ConvInteger INT8 model with
            :class:`ConvIntegerFormatError` before session creation — the HTP
            silently runs such models on CPU (issue 23). Skipped when
            ``allow_fallback`` is True (the caller accepts CPU execution).
        cache_dir: Directory for the persistent HTP context cache (issue 21).
        session_options: Optional pre-built ``ort.SessionOptions``.

    Raises:
        ConvIntegerFormatError: ONNX model is ConvInteger INT8 and
            ``check_format`` is True and ``allow_fallback`` is False.
        NPUFallbackError: NPU EP not active and ``allow_fallback`` is False.
        RuntimeError: onnxruntime-qnn is not installed / QNN EP unavailable.
    """
    global _qnn_registered

    import onnxruntime as ort

    # Reject ConvInteger INT8 up front — before ORT silently falls back to CPU.
    if check_format and not allow_fallback:
        conv_ops = convinteger_ops(model_path)
        if conv_ops:
            raise ConvIntegerFormatError(conv_ops, str(model_path))

    # ORT 1.27+: onnxruntime-qnn is a plugin EP — register it before checking
    # available providers, otherwise get_available_providers() only shows CPU.
    try:
        import onnxruntime_qnn as _qnn_pkg
        if hasattr(ort, "register_execution_provider_library"):
            with _registration_lock:
                if not _qnn_registered:
                    ort.register_execution_provider_library(
                        "QNN", _qnn_pkg.get_library_path()
                    )
                    _qnn_registered = True
    except ImportError:
        pass  # onnxruntime-qnn not installed; will surface below

    available = ort.get_available_providers()
    active_qnn_ep = next((ep for ep in available if ep in _QNN_EP_ALIASES), None)
    if active_qnn_ep is None and not allow_fallback:
        raise RuntimeError(
            "QNNExecutionProvider is not available in this onnxruntime build. "
            "Install 'onnxruntime-qnn' (which bundles the QNN EP) — NOT the plain "
            "'onnxruntime' package — into a native ARM64 Python 3.10–3.12 "
            f"environment. Available providers: {available}"
        )

    providers: list[Any] = []
    if active_qnn_ep is not None:
        with _registration_lock:
            # The guard is advisory: ORT tolerates re-registration within a
            # process, but re-registering across backends (NPU then GPU) masked
            # the real GPU error during bring-up, so we note it. This must flip
            # whenever the QNN EP is active -- not only on the plugin-EP
            # registration path above -- since a statically-linked QNN EP
            # build never goes through register_execution_provider_library.
            _qnn_registered = True
        providers.append((active_qnn_ep, _qnn_provider_options(cache_dir)))
    providers.append(CPU_EP)

    sess = ort.InferenceSession(
        str(model_path), sess_options=session_options, providers=providers
    )

    active = sess.get_providers()[0]
    if active not in _QNN_EP_ALIASES and not allow_fallback:
        raise NPUFallbackError(active, str(model_path))
    return sess


def assert_npu_active(session: ort.InferenceSession) -> None:
    """Assert that the session's active provider is the QNN EP (the NPU).

    This is the single check the quickstart should teach:
    ``sess.get_providers()[0] == 'QNNExecutionProvider'``. Completing inference
    is NOT proof the NPU was used — ORT silently uses CPU on QNN failure.
    """
    providers = session.get_providers()
    active = providers[0] if providers else "(none)"
    if active not in _QNN_EP_ALIASES:
        raise NPUFallbackError(active)


def is_double_registered() -> bool:
    """Whether the QNN EP has already been registered in this process.

    Exposed for callers that attempt NPU then GPU in one process and want to
    avoid the double-registration that masks the real GPU error (issue IQ9-32).
    """
    return _qnn_registered


def reset_registration_guard() -> None:
    """Reset the module-level QNN-registration guard (mainly for tests)."""
    global _qnn_registered
    with _registration_lock:
        _qnn_registered = False


def warmup(session: ort.InferenceSession, feeds: dict[str, Any], n: int = 1) -> None:
    """Run ``n`` warmup inferences, excluded from any timing.

    The first NPU inference triggers a one-time HTP binary compilation that can
    be 10–20× slower than steady state. Callers must run this BEFORE timing and
    must not include these runs in benchmark numbers (issue 21).
    """
    print(
        "[NPU] First run — compiling HTP binary. This compilation step is "
        "excluded from timing. Subsequent runs will be significantly faster."
    )
    output_names = [o.name for o in session.get_outputs()]
    for _ in range(max(n, 1)):
        session.run(output_names, feeds)


def provider_split(
    model_path: str | Path,
    feeds: dict[str, Any] | None = None,
    *,
    cache_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Report which ops ran on the NPU (HTP) vs CPU, as structured JSON.

    ONNX Runtime exposes no per-node provider API, so we enable session
    profiling (``enable_profiling``), run one inference, and parse the profiling
    JSON — each op event carries its execution provider. The returned shape
    matches the retrospective's requested format::

        {
          "Conv_0": "QNNExecutionProvider",
          "Softmax_3": "CPUExecutionProvider",
          ...
          "summary": {"total_nodes": N, "on_npu": .., "on_cpu": ..,
                       "npu_percent": .., "cpu_percent": ..}
        }

    Falls back gracefully (empty ``assignments`` + a ``note``) when the ORT
    build doesn't emit provider info in its profiling events.
    """
    import numpy as np
    import onnxruntime as ort

    so = ort.SessionOptions()
    so.enable_profiling = True

    sess = create_npu_session(
        model_path, allow_fallback=True, cache_dir=cache_dir, session_options=so
    )

    if feeds is None:
        # Synthesize a zero input matching the model's first input.
        feeds = {}
        for inp in sess.get_inputs():
            shape = [d if isinstance(d, int) and d > 0 else 1 for d in inp.shape]
            feeds[inp.name] = np.zeros(shape, dtype=np.float32)

    output_names = [o.name for o in sess.get_outputs()]
    sess.run(output_names, feeds)
    profile_path = sess.end_profiling()

    assignments = _parse_provider_assignments(profile_path)
    summary = _summarize_assignments(assignments)

    result: dict[str, Any] = dict(assignments)
    result["summary"] = summary
    if not assignments:
        result["note"] = (
            "This ONNX Runtime build did not emit per-node execution-provider "
            "info in its profiling events; per-layer split is unavailable."
        )
    return result


def _parse_provider_assignments(profile_path: str) -> dict[str, str]:
    """Parse ORT profiling JSON into {node_name: execution_provider}."""
    try:
        data = json.loads(Path(profile_path).read_text())
    except (OSError, ValueError):
        return {}

    assignments: dict[str, str] = {}
    for event in data if isinstance(data, list) else data.get("traceEvents", []):
        if not isinstance(event, dict):
            continue
        args = event.get("args") or {}
        # ORT kernel events carry the provider in args as one of these keys.
        provider = (
            args.get("provider")
            or args.get("execution_provider")
            or args.get("ep_type")
        )
        node = args.get("node_name") or event.get("name")
        if provider and node and event.get("cat") in (None, "Node", "Kernel", "node"):
            # Normalize e.g. "QNNExecutionProvider" / "CPUExecutionProvider".
            if "QNN" in provider:
                assignments[node] = QNN_EP
            elif "CPU" in provider:
                assignments[node] = CPU_EP
            else:
                assignments[node] = provider
    return assignments


def _summarize_assignments(assignments: dict[str, str]) -> dict[str, Any]:
    """Compute NPU/CPU counts + percentages from a node→provider map."""
    counts = Counter(assignments.values())
    total = sum(counts.values())
    on_npu = counts.get(QNN_EP, 0)
    on_cpu = counts.get(CPU_EP, 0)

    def pct(n: int) -> float:
        return round(100.0 * n / total, 1) if total else 0.0

    return {
        "total_nodes": total,
        "on_npu": on_npu,
        "on_cpu": on_cpu,
        "npu_percent": pct(on_npu),
        "cpu_percent": pct(on_cpu),
    }


def native_arm64_python() -> bool:
    """Whether the active interpreter is native ARM64 (required for NPU wheels).

    The onnxruntime-qnn / onnxruntime-genai wheels are win-arm64 only. An
    emulated x86-64 Python on a Snapdragon box silently fails to load them.
    """
    machine = platform.machine().lower()
    return "arm64" in machine or "aarch64" in machine
