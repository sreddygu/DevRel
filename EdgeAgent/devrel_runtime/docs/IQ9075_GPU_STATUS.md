# IQ-9075 GPU (Adreno 663) — Status: Blocked, Not Self-Serviceable

> **Bottom line:** on the Dragonwing IQ-9075 EVK (QLI 2.0), the QNN **GPU**
> backend does not initialize. This is a **driver package gap, not a DevRel bug
> and not a hardware failure** — the GPU is present and enumerates. It cannot be
> fixed from DevRel or devrelAgent. Use the **NPU** (HTP v73) path instead.

_Author: Pavan R_

---

## What works and what doesn't

| Layer | Result |
|-------|--------|
| GPU device node `/dev/kgsl-3d0` | ✅ Present |
| GPU model `Adreno663v1` | ✅ Reported (`/sys/class/kgsl/kgsl-3d0/gpu_model`) |
| Kernel driver | ✅ Clean init (`dmesg: DRIVER ADRENO Ready`) |
| OpenCL enumeration (`clinfo`) | ✅ 1 device found |
| **QNN GPU backend (`libQnnGpu.so`)** | ✗ **Fails at dynamic-symbol resolution** |

## Root cause — missing OpenCL symbols

`libQnnGpu.so` requires symbols that are **absent from Adreno OpenCL driver
build 0855.5** shipped on this board image:

- `clGetDeviceImageInfoQCOM` (QCOM vendor extension)
- `clSetPerfHintQCOM` (QCOM vendor extension)
- `cl*RecordingQCOM` family (QCOM vendor extension)
- `cl*SemaphoreKHR` family (Khronos `cl_khr_semaphore` extension)

The surfaced error (`QNN_BACKEND_ERROR_CANNOT_INITIALIZE`) does **not** mention
this — only `LD_DEBUG=libs` revealed the real cause by tracing dynamic symbol
resolution at `libQnnGpu.so` load time.

## Why newer QAIRT does not fix it

Three QAIRT versions were tested — **2.45.40**, **2.47.0** (board-native), and
**2.48.40** (full SDK). All three hit the **same 11 missing symbols**. The
blocker is the **Adreno OpenCL userspace driver package**, not QAIRT, so a QAIRT
bump cannot resolve it.

## Why it is not self-serviceable

The Adreno OpenCL userspace driver package itself must be updated. On this board
image there is:

- no package-manager feed for the driver,
- no `fwupd` channel,
- no newer driver `.so` present anywhere on the filesystem to swap in.

Resolving it requires a **Qualcomm-provided Adreno driver package update for QLI
2.0**. Track that with Qualcomm support; do not spend bring-up time
re-investigating — this document IS the investigation result.

## Also: `.bin` is backend-locked (don't try to route around it)

A compiled HTP context binary (`.bin`) is **backend-locked to the NPU**. Loading
an HTP `.bin` against `libQnnGpu.so` fails with `GPU_ERROR_DOES_NOT_EXIST`
(a different, confusing error). Even if the GPU backend worked, GPU inference
needs a portable `.dlc`, not the HTP `.bin`. devrelAgent's
`qnn_utils.validate_backend_artifact()` now rejects this combination up front
with a clear message.

## What to do instead

Use the **NPU (HTP v73)** path — fully validated on this board:

```sh
qnn-net-run --retrieve_context model.bin --backend libQnnHtp.so --perf_profile burst
```

or, for the ONNX Runtime developer path, `devrel_client.ort_qnn.create_npu_session()`.
