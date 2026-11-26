---
name: quad-qnn-runtime-debug
description: Use when the user is debugging a QNN/QAIRT runtime failure on already-compiled artifacts -- "QNN backend won't initialize", "unable to find a valid interface", "QNN_BACKEND_ERROR_CANNOT_INITIALIZE", "GPU_ERROR_DOES_NOT_EXIST", "qnn-net-run fails", "my .bin/.dlc won't load", "backend initialization failure", or invokes /quad-qnn-runtime-debug. Diagnoses backend-init, ABI/version, symbol-resolution, and input-contract failures at the dynamic-loader level rather than trusting generic QNN error strings.
trigger: "qnn-runtime-debug"
user-invocable: true
allowed-tools:
  - Bash(quad-client *)
  - Bash(.venv/Scripts/python.exe *)
  - Bash(qnn-net-run *)
  - Bash(qairt-net-run *)
  - Bash(adb *)
  - Bash(ssh *)
---

# /quad-qnn-runtime-debug -- Runtime debugging of compiled QNN artifacts

This skill is for **runtime** failures of *already-compiled* QNN/QAIRT artifacts
(`.bin` / `.dlc`) and backend initialization — NOT for conversion (use
`/quad-convert`) or benchmarking (use `/quad-profile`). It captures the proven
diagnostic sequence from IQ-9075 bring-up: exact failure signatures, real
command sequences, driver-level investigation, symbol-resolution diagnostics,
and known dead ends.

Arguments passed: `$ARGUMENTS`

---

## 0. First, record versions (mandatory — do not skip)

Version mismatch is the single most common root cause. Record **all** of:

- The runner tool version. `qnn-net-run` and `qairt-net-run` are **distinct
  tools** — do not assume one when the user has the other. Version output often
  goes to **stderr**, so always capture it: `qnn-net-run --version 2>&1`.
- The exact QAIRT/QNN SDK version the artifact was built with — read the
  artifact metadata (`tool_versions.qairt` in the bundle / `metadata.json`).
- The backend library version.

**Compare artifact metadata vs board runtime BEFORE running** (`tool_versions.qairt`
vs `qnn-net-run --version`). This shifts diagnosis from reactive to predictive.

## 1. Tool ↔ backend library ABI matching

The runner and the backend library **must** come from the same QAIRT release.
The documented ABI failure mode when they don't:

> **"unable to find a valid interface"**

means the backend `.so`/`.dll` and the runner are from different QAIRT releases.
Fix: align them to one release. A **newer context binary on an older SDK** (and
the reverse) produces DLC/`.bin` load failures — a runtime-version compatibility
wall, not a corrupt artifact.

## 2. Artifact-type distinctions (frequently confused)

- **QNN context binary (`.bin`)** — compiled for a **specific backend**, so it is
  effectively **NPU-targeted**. Not portable across backends.
- **DLC (`.dlc`)** — backends are **selected at runtime**, so a DLC is the right
  choice for **GPU testing**.
- **QNN DLC vs SNPE DLC** — identical `.dlc` extension does **NOT** imply
  compatibility. They are different containers; confirm which toolchain produced it.

## 3. Symbol-level backend diagnosis (the core contribution)

**Do not trust generic error strings.** `QNN_BACKEND_ERROR_CANNOT_INITIALIZE`,
`GPU_ERROR_DOES_NOT_EXIST`, and "Backend initialization failure" are often
**unresolved-symbol problems inside a dependent driver library**, not evidence
that the hardware is absent.

Treat the **dynamic loader** as the authoritative source of truth:

```bash
LD_DEBUG=libs qnn-net-run --backend libQnnHtp.so ... 2>&1 | tee ldd-trace.txt
# On the target board (Linux SoC) for GPU/DSP backends likewise:
LD_DEBUG=libs,bindings <runner> --backend libQnnGpu.so ...
```

Read the trace for the **first** library that fails to resolve a symbol — that
dependent driver library is the real failure, not the QNN backend.

**Driver-gap vs SDK-gap separation:** missing-symbol failures are more often a
property of the **board's installed driver stack** than of the QAIRT version.
Decide which before proposing a fix.

## 4. Ordered GPU / OpenCL troubleshooting workflow

Work top-down; stop at the first layer that fails:

1. Kernel/firmware loaded? (KGSL / DRM node present)
2. Underlying compute API enumerates devices? (OpenCL `clinfo` lists a device)
3. ICD registration valid? (`/etc/OpenCL/vendors/*.icd` points at a real `.so`)
4. Symbol tracing (`LD_DEBUG=libs`, per §3)
5. Alternate backend library evaluation (try a different backend `.so`)

## 5. Input-contract validation

Wrong inputs usually produce **plausible-but-wrong outputs rather than crashes**,
so validate the contract explicitly:

- Layout may be **NHWC**, not NCHW.
- Input range may be **[0,1]**, not [0,255] or ImageNet-normalized.
- **Inspect `metadata.json`** rather than assuming ImageNet conventions.

## 6. Boundary with ONNX Runtime QNN EP

Two execution paths exist:

- **Direct execution** — `qnn-net-run` / `qairt-net-run`.
- **ONNX Runtime QNN Execution Provider** (the plugin path).

If ORT's *discovery* mechanism is the blocker (e.g. `QNNExecutionProvider` never
appears in `get_available_providers()` on a Linux SoC board), **switch to direct
QNN execution** rather than continuing to debug the plugin path. Cross-link:
`/quad-npu-prereqs` (EP provisioning), `/quad-profile` (measured latency).

## 7. Known dead ends (do not re-investigate)

- Generic QNN backend error text is not a hardware-presence signal (see §3).
- On a Qualcomm Linux SoC board, `onnxruntime-qnn` installs cleanly but
  `QNNExecutionProvider` may **never** appear in `get_available_providers()` —
  an unverified, non-primary path. Use the CLI tools instead.

<!-- skills-hub:begin -->

## Compatibility

| Item | Details |
| --- | --- |
| Devkits | Not device-specific |
| Target OS | No target OS constraint declared |
| Host OS | Windows, Linux (or WSL) |
| Requirements | Python 3.10+; a reachable QUAD MCP server; Qualcomm AI Runtime (QAIRT) SDK 2.47 and Snapdragon X Elite for NPU workflows |

References: [QUAD Client README](https://github.com/sreddygu/DevRel/blob/main/QUAD-Client/README.md).

## Example prompts

- My QNN backend won't initialize. What is wrong?
- I get "Unable to find a valid interface provider"
- My model fails to load with a symbol error on the NPU
- Check for an SDK version mismatch between my model and the runtime
- Why does my model load on CPU but fail on the HTP backend?
- Verify my model's input shapes and data types match what the runtime expects

<!-- skills-hub:end -->
