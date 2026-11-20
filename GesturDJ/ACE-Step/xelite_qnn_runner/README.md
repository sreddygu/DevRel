# ACE-Step X Elite QNN Runner

This is the native Windows Arm64 runner project for the qualified ACE-Step
transformer blocks. It currently provides a buildable, fail-closed artifact
preflight only; it does not execute an NPU graph and cannot generate a WAV.

## Build

Use a native Arm64 Visual Studio developer prompt with the C++ ARM64 workload
installed. The regular PowerShell environment is not sufficient: its configured
Visual Studio Build Tools instance does not provide the required ARM64 MSBuild
platform.

```powershell
cmake -S . -B build -A ARM64
cmake --build build --config Release
```

If CMake reports that the `ARM64` platform does not exist, install the Visual
Studio C++ ARM64 build tools, open the matching developer prompt, then rerun
the commands above.

## Validate artifacts

```powershell
.\build\Release\ace_step_qnn_runner.exe --case-root ..\data\iq8
```

The command requires each block's `manifest.json`, `inputs.npz`,
`reference_output.npy`, and its qualified DLC. It accepts the early campaign
base DLC filename for blocks 0-1 as well as the later `_preserve_layout` name.
A JSON response with `execution_enabled:false` is a successful preflight, not
an HTP inference.

## Load persistent HTP contexts

The runner includes a QAIRT high-level C++ API probe that attempts to build and
retain one HTP runtime per qualified DLC. It loads no inputs and deliberately
performs no inference.

```powershell
$qairt = "C:\Qualcomm\AIStack\QAIRT\2.51.40.260930"
$env:PATH = "$qairt\lib\aarch64-windows-msvc;$env:PATH"
$env:ADSP_LIBRARY_PATH = "$qairt\lib\hexagon-v73\unsigned"
.\build\Release\ace_step_qnn_runner.exe --case-root ..\data\iq8 --load-contexts `
  --qairt-system "$qairt\lib\aarch64-windows-msvc\QairtSystem.dll"
```

The command requires every DLC to expose exactly one graph with nine inputs
and one output. A successful `contexts_loaded` response proves only context
composition and the graph I/O count; tensor execution remains disabled.

**Current QAIRT 2.51 result:** on November 18, 2026, both the native Arm64 and
Arm64X `QairtSystem.dll` variants fail during `QairtSystemBuilder::build()`
with `Function not supported by current QAIRT Version`. The probe is retained
as a fail-closed diagnostic, but it is not a usable HTP loader on this system.
Continue the persistent runner with the low-level QNN backend/context and DLC
composition APIs from the installed QNN SampleApp, rather than the QAIRT
high-level C++ runtime.

## Verify the low-level QNN ABI

The low-level fallback starts with an in-process ABI probe. It resolves the
backend and system provider entry points directly and confirms that both expose
a compatible QNN interface; it does not create a backend or execute a graph.

```powershell
$qairt = "C:\Qualcomm\AIStack\QAIRT\2.51.40.260930"
$env:PATH = "$qairt\lib\aarch64-windows-msvc;$env:PATH"
.\build\Release\ace_step_qnn_runner.exe --case-root ..\data\iq8 --probe-qnn-low-level `
  --qnn-backend "$qairt\lib\aarch64-windows-msvc\QnnHtp.dll" `
  --qnn-system "$qairt\lib\aarch64-windows-msvc\QnnSystem.dll"
```

## Next source change

Add the QAIRT HTP backend/context lifecycle using the installed SDK SampleApp
as the ABI reference. The implementation must load all 24 contexts once,
retrieve graphs once, validate the nine-input/one-output tensor contract from
the manifests, and execute all blocks sequentially. Do not add a
`qnn-net-run` subprocess loop.

## Persistent execution checkpoint

`--execute-qualified-blocks` now creates one HTP backend, composes the 24
qualified fixed-shape DLCs into retained contexts and graphs, then executes the
saved raw inputs for every block. The command requires the same QAIRT runtime
environment as the per-block validation scripts:

```powershell
$qairt = "C:\Qualcomm\AIStack\QAIRT\2.51.40.260930"
$env:PATH = "$qairt\lib\aarch64-windows-msvc;$env:PATH"
$env:ADSP_LIBRARY_PATH = "$qairt\lib\hexagon-v73\unsigned"
.\build\Release\ace_step_qnn_runner.exe --case-root ..\data\iq8 `
  --execute-qualified-blocks --output-dir ..\data\iq8\xelite_qnn_runner_qualified_outputs `
  --qnn-backend "$qairt\lib\aarch64-windows-msvc\QnnHtp.dll" `
  --qnn-system "$qairt\lib\aarch64-windows-msvc\QnnSystem.dll"
```

The X Elite V73 cannot keep all 24 graphs resident: it rejects additional
persistent weight mappings after block 16. The runner therefore retains one
HTP backend while loading, executing, and releasing bounded eight-graph batches.
On November 18, 2026, the native Arm64 runner completed all 24 fixed-fixture
blocks with this strategy and every output passed the cosine `>= 0.999` gate.

This validates only the fixed-fixture block sequence. Do not wire the executor
into the DiT forward loop or claim an NPU WAV until all 24 live `108x6` DLCs are
exported and qualified, and an end-to-end DiT-forward parity gate passes.

## Live tensor transport

The native runner can remain alive as a request server for the WSL ACE-Step
sampler. It uses a shared directory for the nine float32 raw tensors and writes
one float32 hidden-state output per request:

```powershell
$qairt = "C:\Qualcomm\AIStack\QAIRT\2.51.40.260930"
$env:PATH = "$qairt\lib\aarch64-windows-msvc;$env:PATH"
$env:ADSP_LIBRARY_PATH = "$qairt\lib\hexagon-v73\unsigned"
.\build\Release\ace_step_qnn_runner.exe --case-root ..\data\iq8 --serve-real-blocks `
  --transport-dir C:\Dropbox\DevRel\academy\GesturDJ\ACE-Step\data\iq8\xelite_live_transport `
  --qnn-backend "$qairt\lib\aarch64-windows-msvc\QnnHtp.dll" `
  --qnn-system "$qairt\lib\aarch64-windows-msvc\QnnSystem.dll"
```

In the WSL ACE-Step environment, set `ACE_XELITE_NPU_TRANSPORT_DIR` to the same
folder through `/mnt/c/...`, import `attach_xelite_npu_executor` from
`acestep.xelite_npu_bridge`, and attach it to `pipe.ace_step_transformer`.
The bridge fails closed if the server is unavailable, a request fails, or a raw
output has the wrong shape.

`run_xelite_npu_text2music.ps1` starts the server and WSL sampler together for
the deterministic 10.031021-second, 27-step text-to-music request. It writes
`data/outputs/ace_xelite_npu_10s_27steps.wav` and the matching result JSON.
