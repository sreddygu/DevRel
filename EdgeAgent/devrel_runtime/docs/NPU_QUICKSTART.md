# DevRel NPU Quickstart — Read This First

> The zero-to-first-NPU-inference guide, written around the exact traps the
> IQ-9075 bring-up retrospective surfaced. If you only read one doc before
> running NPU inference on a Snapdragon box, read this one.

_Author: Pavan R_
_Last updated: 2026-07-15_

---

## 1. Python: 3.10–3.12, **native ARM64** only

The NPU wheels (`onnxruntime-qnn`, `onnxruntime-genai`) exist **only** for
**Python 3.10–3.12** and **only** for **native ARM64** (win-arm64). Two failure
modes that waste hours if you don't know them:

- **Python 3.14 (or any 3.13+)**: `pip install onnxruntime-qnn` fails with a
  cryptic "no matching wheel" error that never says *why*. Use 3.10–3.12.
- **Emulated x86-64 Python on a Snapdragon box**: installs may appear to work
  but NPU support silently never loads. On Snapdragon X Elite, Python's
  `platform.machine()` can even *report* `AMD64` while the CPU is ARM64 — so you
  can't eyeball it. Install **native ARM64** Python.

`devrel-agent doctor` checks both (Python version **and** arch) and tells you
exactly what's wrong. Run it first.

## 2. The two-venv pattern

Use **two** separate Python environments — they have conflicting requirements:

| Venv | Python | What goes in it |
|------|--------|-----------------|
| `.venv` | 3.10–3.12 (x86-64 is fine here) | DevRel tooling, `devrel-mcp-client` CLI, QAI Hub Models packages, general dev |
| `.venv-arm64` | 3.10–3.12 **native ARM64** | NPU inference only — `onnxruntime-qnn` (+ `onnxruntime-genai`) |

Run NPU code with the `.venv-arm64` interpreter; run CLI/tooling with `.venv`.
`devrel-agent doctor` warns if you run NPU code from the wrong environment.

## 3. `onnxruntime-qnn` **replaces** `onnxruntime` — never install both

`onnxruntime` and `onnxruntime-qnn` both write `onnxruntime/capi/onnxruntime.dll`
to the **same** location. Whichever installs **last silently overwrites** the
other — no error, no warning. If you install `onnxruntime-qnn` and then
`onnxruntime` (or vice-versa), NPU support quietly disappears and the only
symptom is `QNNExecutionProvider` missing from the provider list.

> **onnxruntime-qnn is the complete engine with NPU support built in.** Install
> only `onnxruntime-qnn` in `.venv-arm64`. Never both.

`devrel-agent doctor` detects both-installed and tells you to
`pip uninstall onnxruntime`.

## 4. The QAIRT SDK lives on the **remote server**, not your laptop

Your laptop is a **client**. The QAIRT SDK and all model-conversion tools run on
the **remote DevRel MCP server** — your laptop sends requests and receives
results. **No local QAIRT install is required.** Don't try to find/install/debug
QAIRT locally; if `hardware_detect` shows an SDK status, that's the server's SDK.

## 5. Verify the NPU is actually active — completing inference is NOT proof

ONNX Runtime **silently falls back to CPU** when the QNN EP fails to initialize.
Inference still completes and results still look correct — the *only* reliable
signal is the active provider:

```python
from devrel_client import ort_qnn

sess = ort_qnn.create_npu_session("model_qdq.onnx")  # raises if NPU isn't active
assert sess.get_providers()[0] == "QNNExecutionProvider"   # the one check that matters
```

`create_npu_session` runs this check for you and raises `NPUFallbackError` rather
than silently running on CPU (pass `allow_fallback=True` to opt into CPU).

## 6. First NPU run is 10–20× slower — that's HTP compile, not a bug

The **first** inference of a QDQ INT8 model on the Hexagon HTP compiles the model
to a native HTP binary (several seconds). Every run after that uses the cached
binary and is fast (~ms). So:

- Treat the first inference as **warmup** and exclude it from timing.
  `ort_qnn.warmup(sess, feeds)` does this and prints that it's excluded.
- Set a persistent `cache_dir` so compilation happens **once across runs**:
  `ort_qnn.create_npu_session("m.onnx", cache_dir="./htp_cache")`.

## 7. Small models may **not** beat CPU on the NPU — expected, not broken

On Snapdragon X Elite, models **below ~100M parameters** may run as fast or
faster on the high-performance Oryon CPU than on the NPU, because the per-op
dispatch + Q/DQ overhead outweighs the int8 compute savings on small/shallow
graphs. MobileNetV2 (3.4M) and ResNet-50 (25M) are both below the crossover —
**CPU winning on these does not mean anything is misconfigured.** Quantization
should be evaluated **per-model**, not applied by default. (On MobileNetV2 the
IQ-9075 measured NPU **FP32 faster than NPU INT8** for this reason.)

## 8. Validate `convert_model` as its own step

Test the `convert_model` MCP tool **standalone** before running benchmarks, so a
conversion failure surfaces immediately instead of hiding behind a later
benchmark error. Convert → verify the artifact exists → then profile/benchmark.

## 9. Setup sequence (the order that works)

1. Open the installer **as Administrator**.
2. Have your **QGenie API key** ready (see `VPN_QGENIE.md`).
3. Ensure `.claude/settings.json` points at the DevRel MCP server.
4. Connect the **BIG-IP Edge Client VPN** (required for QGenie/Claude).
5. Set the model-access token **in the shell you'll launch Claude Code from**
   (the VS Code GUI does not inherit shell env vars — see `VPN_QGENIE.md`).
6. Run `install.sh` / `install.ps1`.
7. Run `devrel-agent doctor` and fix any FAIL/WARN it reports.

## 10. Corporate network: `SSL: CERTIFICATE_VERIFY_FAILED` on model downloads

On a corporate network a TLS-inspecting proxy (Netskope, Zscaler, …) presents
its **own** CA. Python doesn't trust it out of the box, so model downloads fail:

```
SSL: CERTIFICATE_VERIFY_FAILED
certificate verify failed: unable to get local issuer certificate
```

DevRel handles this **automatically**: `devrel_client.local.download.download_file`
(used by the bundled samples) and the server's model fetcher retry once with a
corporate-compatible TLS context — the OS trust store (`truststore`), then a CA
bundle from `DevRel_CA_BUNDLE` / `REQUESTS_CA_BUNDLE` / `SSL_CERT_FILE`, then an
unverified fallback with a warning.

To make it permanent (and silence the warning), point DevRel at your corporate CA:

```powershell
$env:DevRel_CA_BUNDLE = "C:\path\to\corp-ca.pem"   # or REQUESTS_CA_BUNDLE
# or, preferred, use the OS trust store:
pip install truststore
```

**Manual workaround** in your own download code (equivalent to the unverified
fallback — use only if the above isn't an option):

```python
import ssl
ssl._create_default_https_context = ssl._create_unverified_context
```

`devrel-agent doctor` reports a WARN when `REQUESTS_CA_BUNDLE` / `SSL_CERT_FILE`
points at a file that doesn't exist — a common cause of this error.

## Runnable example

See `samples/npu_ort/` — `run_npu_ort.py` does all of the above: creates a
verified NPU session, warms up (excluded from timing), benchmarks, prints the
per-layer NPU/CPU split, and compares against a CPU baseline.
