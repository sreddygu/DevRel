# QUAD Sample Projects

Example projects you can build with the QUAD platform, organized by complexity.

---

## Beginner -- Single Model, Single Backend

### 1. Image Classification Benchmark

> **Existing sample:** [`samples/mobilenetv2`](mobilenetv2/)

Download a pretrained model, convert to QNN, run CPU vs NPU inference, and compare latency and power.

### 2. GPU Inference

> **Existing sample:** [`samples/gpu_inference`](gpu_inference/)

Detect hardware, convert model, profile on GPU, and generate Adreno GPU inference code using `libQnnGpu`.

### 3. Object Detection API

YOLOv8n on NPU with a FastAPI wrapper -- detect objects in uploaded images under a 5 W power budget.

### 3. Style Transfer App

Convert a style-transfer ONNX model, run on NPU, and serve via a simple GUI or CLI.

---

## Intermediate -- Multi-Step Pipelines

### 4. Real-Time Vision Pipeline

YOLOv8n + EfficientNet-B0 + DeepLabV3 running concurrently on NPU -- detection, classification, and segmentation at 30 FPS within 8 W.

### 5. Streaming Speech-to-Text

Whisper-tiny with NPU encoder + CPU decoder, 80 ms audio chunks, <200 ms first-word latency -- live transcription from a microphone.

### 6. Smart Camera Security System

Person detection (NPU) followed by face recognition (NPU) followed by an alert pipeline -- orchestrated across backends with `orchestrate_workload`.

---

## Advanced -- LLMs & Custom Kernels

### 7. On-Device Chatbot

Llama 3 8B INT4 on NPU with dual-graph prefill/decode, KV-cache management, and 15+ tok/s streaming output.

### 8. Document Q&A Assistant

Embedding model on NPU for retrieval + LLM for generation -- a fully local RAG pipeline.

### 9. Custom Fused Operator

Write a fused LayerNorm+GeLU Hexagon HVX kernel, compile, validate bit-accuracy, and integrate into a model graph.

---

## End-to-End Application Patterns

### 10. AI-Powered Meeting Assistant

Whisper ASR (NPU) into a summarization LLM (NPU) into action-item extraction -- all on-device, power-aware.

### 11. Edge ML Model Zoo

Batch-convert a catalog of ONNX models, profile each on NPU, and generate a comparison dashboard of latency, power, and accuracy.

---

## The Common Workflow

Every project follows the same 5-tool MCP pattern:

```
hardware_detect -> convert_model -> profile_workload -> orchestrate_workload -> generate_code
```

You can develop and test all of these in **mock mode** (no hardware or SDK needed), then switch to **real mode** (`QUAD_ADAPTER_MODE=real`) when deploying to a Snapdragon device.
