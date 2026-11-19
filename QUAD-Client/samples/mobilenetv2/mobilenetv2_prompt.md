# MobileNetV2 Benchmark — Sample Prompt for QUAD App Builder

Use this prompt with Claude Code (with QUAD installed) to reproduce the
`samples/mobilenetv2` application from scratch.

---

## The Prompt

Copy and paste the following into Claude Code:

---

> Build a complete MobileNetV2 image classification benchmark application
> for Windows on Snapdragon X Elite. Here are the requirements:
>
> **Model:** MobileNetV2 from the ONNX Model Zoo (mobilenetv2-12.onnx)
>
> **Task:** ImageNet 1000-class image classification
>
> **Target:** Windows AI PC with Snapdragon X Elite (Oryon CPU, Adreno X1-85 GPU, Hexagon NPU)
>
> **App type:** Python script (single-file, all-in-one)
>
> **What the app should do:**
>
> 1. **Download** the MobileNetV2 ONNX model and ImageNet class labels
>    automatically. Also download a default test image (dog photo) if no
>    image is provided. If download fails, generate a synthetic 224x224
>    random image so the pipeline still runs.
>
> 2. **Simplify** the ONNX model with onnxsim to fold constant subgraphs
>    (Gather/Concat shape ops that QAIRT can't evaluate at conversion time).
>
> 3. **Convert** the model to QNN format via the QUAD MCP server using
>    stdio transport (spawn `python -m quad.mcp.server` as a subprocess,
>    call `convert_model`, and let it exit). Use FP32 quantization, QNN
>    target SDK, input shape `1,3,224,224`, input name `input`.
>
> 4. **Benchmark on three backends** with a side-by-side comparison:
>    - **CPU**: Run 10 timed inferences via onnxruntime with
>      CPUExecutionProvider. Track per-run latency and CPU utilization
>      via psutil.
>    - **GPU**: Run a duration-based benchmark via `qnn-net-run.exe`
>      with `--backend QnnGpu.dll` for Adreno GPU inference. Use the
>      `benchmark_qnn_net_run` function from `quad_mcp_client.qnn_utils`
>      with `backend="gpu"`.
>    - **NPU**: Run a duration-based benchmark via `qnn-net-run.exe`
>      with `--backend QnnHtp.dll` and `--perf_profile burst`. Use the
>      same `benchmark_qnn_net_run` function with default HTP backend.
>    - Gracefully skip GPU/NPU if the SDK or backend DLL is not available.
>
> 5. **Preprocess** images with ImageNet normalization:
>    mean=[123.675, 116.28, 103.53], std=[58.395, 57.12, 57.375],
>    resize to 224x224, transpose HWC to NCHW.
>
> 6. **Print results** as a formatted comparison table showing:
>    - Average latency, min latency, throughput (FPS), speedup vs CPU
>    - Number of iterations (CPU: 10 runs, GPU/NPU: hundreds via --duration)
>    - CPU utilization and estimated package power (CPU TDP 23W, GPU 8W, NPU 4.5W)
>    - Top-5 ImageNet predictions with class names and probabilities
>    - ASCII bar chart of per-run CPU latency
>
> 7. **CLI interface** with argparse:
>    `--image`, `--model`, `--skip-download`, `--output-dir`,
>    `--server` (stdio or HTTP URL), `--server-python`, `--adapter-mode`
>    (mock/real), `--target-sdk` (qnn/snpe), `--sdk` (auto/qnn/snpe),
>    `--warmup`, `--runs`, `--top-k`, `--calibration`
>
> **SDK discovery:** Auto-discover the QUAD server Python by walking up
> the directory tree to find `QUAD/.venv/Scripts/python.exe`. Auto-discover
> the QAIRT SDK root via `.QUAD/sdk/` junction, env vars (QNN_SDK_ROOT,
> QAIRT_SDK_ROOT), or `quad.sdk_manager.resolve_sdk_root()`. Also find
> a Python 3.10 x86_64 interpreter for QAIRT converter compatibility
> via `.QUAD/qairt-venv/` or the `py -3.10` launcher.
>
> **Windows compatibility:** Force UTF-8 stdout/stderr on Windows
> (cp1252 consoles can't render Unicode box-drawing characters).
>
> **Conventions:** Include `run.ps1` (uv-based venv + dependency installer)
> and `requirements.txt` with `>=` version pins. Place the app under
> `samples/mobilenetv2/`. Include a `README.md` with quick start,
> prerequisites, how it works, expected output, CLI options, examples,
> and troubleshooting table.
>
> **Dependencies:** fastmcp>=2.0, numpy>=1.24, Pillow>=10.0, psutil>=5.9,
> onnxruntime>=1.18, onnx>=1.14, onnxsim>=0.4.35
