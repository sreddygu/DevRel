# GPU Inference Sample

End-to-end demonstration of targeting the Adreno GPU backend via QUAD.

## What it does

1. **Detect** hardware and confirm `gpu_backend_available: true`
2. **Convert** an ONNX model to QNN format
3. **Profile** the model with `runtime="gpu"` to get GPU latency and power
4. **Generate** C++ inference code using `libQnnGpu` (Adreno GPU backend)

## Setup

```powershell
.\run.ps1
```

## Run

```powershell
.venv\Scripts\python.exe gpu_inference.py

# Or with a custom model:
.venv\Scripts\python.exe gpu_inference.py --model path/to/model.onnx
```

## Requirements

- QUAD MCP server running (mock mode works for development)
- For real GPU execution: Snapdragon device with Adreno GPU + QAIRT SDK

## Output

The generated C++ code will contain `libQnnGpu.dll` as the backend
library instead of the default `libQnnHtp.dll`, targeting the Adreno
GPU for inference.
