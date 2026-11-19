---
name: devrel-convert
description: Use when the user asks to "convert a model", "compile this ONNX", "quantize my PyTorch model", "convert to QNN/SNPE", or invokes /devrel-convert. Walks through model conversion with calibration data + image format guidance.
trigger: "convert"
---

# DevRel Model Conversion Skill

Convert ONNX / PyTorch / TensorFlow / TFLite models to QNN context
binaries (.bin) or SNPE DLC (.dlc) files, with optional INT8/INT4
quantization.

## Pre-conversion checklist

1. **Source file exists?** If not, ask the user to share the path.
2. **Source format?** Inspect file extension (.onnx / .pt / .pb / .tflite).
   PyTorch users need to export to ONNX first — use `torch.onnx.export`.
3. **Target SDK?** Default to `qnn` on Windows (Snapdragon X Elite),
   `snpe` on Linux/Android. Ask if unclear.
4. **Quantization?** `int8` is a reasonable **starting hypothesis**, not a
   settled recommendation — verify it with `devrel-profile`. On real IQ-9075
   hardware INT8 measured **42% slower than FP32** on the same NPU, and the
   INT8 artifact was **larger**, not smaller. Convert both and let measured
   latency/size decide. Use `int4` only with real calibration data + AIMET
   (`use_aimet=True`).
5. **Image input?** Ask about layout (NCHW from PyTorch / NHWC from
   TensorFlow) and channel order (RGB / BGR). Set `input_layout=` and
   `channel_order=` accordingly so DevRel inserts the right transposes.

## Steps

1. Call `mcp__devrel__convert_model` with the right args. Always
   provide:
   - `source_format`
   - `model_path`
   - `target_sdk`
   - `quantization`
   - `input_layout` (default `nchw` for ONNX from PyTorch)
   - `channel_order` (default `rgb`)

2. Format the response with `devrel.ui.format_conversion(result)`. The
   table shows original/output size, compression ratio, supported-ops
   percent, conversion time, and target SDK.

3. If `unsupported_ops` is non-empty, surface it prominently — those
   ops will fall back to CPU and may dominate latency.

4. Surface the `image_format_notes` from the response — they tell the
   user how to preprocess inputs at inference time. This is one of the
   biggest sources of "model returns garbage" bug reports.

5. If the user is doing INT4 + has no `calibration_data`, raise the
   AIMET tip: "Random-data calibration produces wrong scales. Provide
   real calibration samples via `calibration_data=`."

6. Suggest the next step:
   - "Now profile it on the NPU: `devrel-profile <output_path>`"
   - "Want to allocate it across CPU/GPU/NPU? Use `devrel-orchestrate`"

7. End with 1-2 tips from `devrel.tips.get_tips_for("convert")`.

## Model input sources (round-trip)

The server can obtain the model in several ways — the client no longer needs
the file to already live on the server. Pass `model_source` (or use the
`DevRelClient.convert_model` conveniences):

- **Local upload** — `upload="./model.onnx"`: the client POSTs the file to the
  server first, then converts the uploaded copy.
- **HuggingFace** — `model_source={"kind": "huggingface", "repo_id": "org/model",
  "filename": "model.onnx", "revision"?: "main"}` (honors the server's `HF_TOKEN`).
- **GitHub** — `model_source={"kind": "github", "repo": "org/name",
  "path": "sub/model.onnx", "ref"?: "main"}`.
- **Direct URL** — `model_source={"kind": "url", "url": "https://.../model.onnx",
  "sha256"?: "..."}`.
- **Server path** — `model_path="..."` (legacy; the file already exists on the server).

**AI Hub Models routing** (`aihub`): `auto` (default) sends Gen-AI/LLM,
precompiled, or INT4-without-calibration models to the AI Hub Models cloud and
does everything else locally; `force` always uses the cloud; `never` stays local
(errors if the model truly requires the cloud). Set `aihub_device=` /
`model_id=` for catalog models.

**Auto-download**: over an sse-http (hosted) server, the result carries a
`download_url` and the client auto-fetches the artifact into `./devrel_artifacts`
(override with `download_dir=`), verifying `sha256`. The saved path is returned
as `local_path`. On a local stdio server the output is already on disk at
`output_path`.

## Common gotchas to call out

- **PyTorch model_path with .pt** — PyTorch frontend uses a mock IR
  for now. Recommend exporting to ONNX first.
- **Symbolic batch dim** — ONNX models with `dim_param` need
  `input_dimensions={"input": "1,3,224,224"}` to bind a concrete shape.
- **MNIST / single-channel** — provide `input_layout` correctly; the
  MNIST preset is `{1, 1, 28, 28}` not `{1, 3, 224, 224}`.
- **Mean values** — many ImageNet models expect normalisation
  (e.g. mean=`[123.675, 116.28, 103.53]`). Pass via `mean_values=`.
- **ConvInteger INT8 is rejected for the NPU.** The Hexagon HTP only accepts
  **QDQ** (QuantizeLinear/DequantizeLinear) INT8. onnxruntime's
  `quantize_dynamic` emits **ConvInteger/MatMulInteger**, which loads without
  error but silently runs on **CPU**. `convert_model` (and
  `create_npu_session`) now reject such models with a clear message — re-quantize
  with `quantize_static(..., quant_format=QuantFormat.QDQ)` or AIMET.

## Confirmed failure modes (IQ-9075)

1. **Remote-host filesystem visibility is a hard boundary.** When the MCP server
   runs on a **separate host**, `mcp__devrel__convert_model` returns "Model not
   found" for a genuinely-valid *local* path — confirmed failing identically
   across two different paths. This is an access boundary, not a typo or a
   transient error. Fallbacks:
   - Use `model_source` (upload / HuggingFace / URL) instead of a bare
     `model_path` so the server obtains the file itself.
   - Or use **AI Hub Models' cloud compiler** with `--skip-profiling --skip-inferencing`.
2. **External-data `.data` file gotcha.** Large ONNX models store weights in a
   sidecar `.data` file. When pushing/deploying a model, the `.data` file must
   travel with the `.onnx` or conversion/inference fails cryptically.

## Example response

```markdown
### Model converted: `output/mobilenetv2-12.dlc`

|                  |                    |
| :---             | :---               |
| Original size    | 13.3 MB            |
| Output size      | 3.3 MB             |
| Compression      | 4.05× smaller      |
| Quantization     | int8               |
| Supported ops    | 100%               |
| Conversion time  | 1.33 s             |
| Target SDK       | qairt              |

**Image format guidance:**
- Input layout is NCHW (PyTorch). SNPE requires NHWC — transpose
  before inference: `np.transpose(img, (0, 2, 3, 1))`
- Channel order is RGB — standard for most modern frameworks.

💡 _Pass real calibration_data to INT8/INT4 conversion. Random noise
produces wrong quantization scales._
```
