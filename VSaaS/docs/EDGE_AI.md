# VSaaS Edge AI (Demo Scope)

Target: keep the majority of video intelligence on the edge device (IQ8), and transmit only privacy-safe metadata upstream.

## What runs on the edge
- **Object detection (people/objects)**: produces bounding boxes + scores.
- **Tracking**: stabilizes IDs across frames (enables zone entry + dwell).
- **Intrusion**: raises an event when a tracked object enters a *restricted* zone.
- **Dwell**: raises an event when a tracked object remains inside a *dwell* zone longer than a threshold.
- **PPE**: checks for missing safety gear (helmet/vest) and raises violations.

The prototype can run with a **mock detector** (no model dependencies) or with real detectors (ONNX YOLOv8 or QNN YOLOv8 DLC).

## Real object detection (YOLOv8 ONNX)
This repo supports a real detector using ONNX Runtime:

1. Install edge deps:
   - `pip install -r requirements.txt`
2. Download the demo model:
   - `./scripts/get_models.sh`
3. Run the edge camera agent with the real detector:
   - `export VSAAS_DETECTOR=onnx_yolov8`
   - `export VSAAS_YOLO_ONNX_PATH=$PWD/models/yolov8n.onnx`
   - `./scripts/run_edge_camera.sh`

- Notes:
- This is a real model that runs via CPUExecutionProvider by default; you can also enable the QNN execution provider for hardware acceleration (see QNN DLC section below).
 - Default model is COCO; it supports `person` detection out-of-the-box.

## Real object detection (YOLOv8 QNN DLC on IQ8 NPU/HTP)
If you have a YOLOv8 QNN DLC exported (e.g., from Qualcomm AI Hub) you can run detection on IQ8’s NPU (HTP):

- AI Hub model page: https://aihub.qualcomm.com/models/yolov8_det?domain=Computer+Vision&useCase=Object+Detection
- Example artifact in this repo: `models/yolov8_det_w8a8/yolov8_det_w8a8.dlc`

Run:
- `export VSAAS_DETECTOR=qnn_yolov8`
- `export VSAAS_QNN_BACKEND=/lib/libQnnHtp.so`
- `export VSAAS_QNN_DLC_PATH=$PWD/models/yolov8_det_w8a8/yolov8_det_w8a8.dlc`
- `export VSAAS_QNN_INPUT_NAME=images`
- `export VSAAS_QNN_INPUT_SIZE=640`
- `export VSAAS_DET_CONF=0.15`
- `export VSAAS_DET_TOPK=8`
- `export VSAAS_VIDEO_SOURCE="qmmf://video_0"` (CSI path; keep `cam-server.service` active)
- `./scripts/run_edge_camera.sh`

## Build the YOLOv8 NPU context yourself with QAIRT 2.51 (no AI Hub account)

Verified 2026-11-27 with QAIRT SDK 2.51.40.260930 on a Windows-on-Snapdragon PC and a Dragonwing IQ-8275 (IQ8, Hexagon v75)
running Qualcomm Linux 2.0 with a QNN 2.51.40 runtime (`qnn-net-run`, `libQnnHtp.so`). The runtime on the board must be the
same QAIRT release as the compiler, or the context will not load.

1. **Host Python.** The SDK's converter modules are x64 builds, so use an **x64 Python 3.10** venv even on an ARM64 PC
   (`pip install numpy==1.26.4 packaging==24.0 pandas==2.3.3 pyyaml==6.0.3 scipy==1.15.3 onnx==1.17.0 "protobuf<6"`).
   An ARM64 Python 3.12 fails with "not a valid Win32 application". Set `QAIRT_SDK_ROOT`, `PYTHONPATH=$QAIRT_SDK_ROOT/lib/python`
   and put `bin/x86_64-windows-msvc` and `lib/x86_64-windows-msvc` on `PATH`.
2. **Convert** the ONNX from `scripts/get_models.sh`: `qairt-converter --input_network yolov8n.onnx --output_path yolov8n.dlc`.
3. **Quantize with 16-bit activations** using a few dozen calibration images (preprocessed to 640x640 float32 NCHW `.raw`, listed as
   `images:=<file>`): `qairt-quantizer --input_dlc yolov8n.dlc --input_list calib_list.txt --output_dlc yolov8n_w8a16.dlc --act_bitwidth 16 --weights_bitwidth 8`.
4. **Compile for v75** with `qnn-context-binary-generator --backend QnnHtp.dll --dlc_path yolov8n_w8a16.dlc --binary_file yolov8n_w8a16_v75 --output_dir ctx --config_file cfg.json`,
   where `cfg.json` points `backend_extensions` at `QnnHtpNetRunExtensions.dll` and the HTP config is
   `{"graphs":[{"graph_names":["yolov8n"],"vtcm_mb":8,"fp16_relaxed_precision":1,"O":3}],"devices":[{"htp_arch":75}]}`.
   Use the `x86_64-windows-msvc` toolchain; the `aarch64-windows-msvc` one rejected the graph. The line
   `unexpected GraphHtpSettings option 66` is printed on success and can be ignored.
5. **Run on the board:** `export LD_LIBRARY_PATH=<qnn_rt>/lib ADSP_LIBRARY_PATH="<qnn_rt>/lib/hexagon-v75/unsigned;/usr/lib/rfsa/adsp;/dsp"`, then
   `qnn-net-run --backend libQnnHtp.so --retrieve_context yolov8n_w8a16_v75.bin --input_list input_list.txt --output_dir out`
   (this is exactly what `src/vsaas/qnn_yolov8.py` shells out to; set `VSAAS_QNN_RETRIEVE_CONTEXT` to the `.bin`).

Measured on the IQ8 (about 0.35 s per `qnn-net-run` call including context load; 0 kernel external aborts), 16 calibration samples from 4 images,
compared with ONNX Runtime fp32 on the PC:

| Image | NPU w8a16 detections | CPU fp32 detections | Class-score cosine |
| --- | --- | --- | --- |
| `dog.jpg` (in the calibration set) | dog 0.31 | dog 0.55 | 0.80 |
| `zidane.jpg` (held out) | person 0.87, person 0.86, tie 0.41 | person 0.85, person 0.77, tie 0.35, tie 0.29 | 0.98 |

Pitfalls found on the way:

- **w8a8 loses every class score.** YOLOv8's single output tensor mixes box pixels (0 to 640) with class probabilities (0 to 1), so 8-bit
  steps of about 2.5 round the scores to zero (boxes matched at cosine 0.9995, classes at 0.0000). Use 16-bit activations or split the head.
  The repo's `yolov8_det_w8a8.dlc` (AI Hub) is built differently; it is not in the repo and needs an AI Hub token.
- **fp16 or fp32 graphs.** An fp32 graph failed to finalize (a 160x160x48 concat needs 9.8 MB against 8 MB of VTCM). An fp16 graph compiled
  and ran, but its output did not depend on the input (identical bytes for zeros, ones and a photo), so it is unusable; the cause was not found.
- **More calibration data helps.** With 6 samples from 3 images the NPU said "cat 0.40" for the dog; with 16 samples from 4 images it says "dog 0.31".
  Use real camera frames from the target scene for a deployment.

## Real PPE model (optional)
PPE (helmet/vest) is not available in COCO, so it needs a PPE-trained model.

If you have a PPE YOLOv8 ONNX model, you can enable the PPE checker:
- `export VSAAS_PPE_CHECKER=onnx_ppe`
- `export VSAAS_PPE_ONNX_PATH=/path/to/ppe.onnx`
- `export VSAAS_PPE_LABELS='person,helmet,vest'` (must match the model’s class order)
- `export VSAAS_PPE_REQUIRED='helmet,vest'`

The edge agent will then emit `ppe_violation` events when required items are missing.

## Quick start (IQ8)
1. Start the local cloud API:
   - `./scripts/run_cloud.sh`
2. Run edge camera agent (edge AI enabled by default in the script):
   - `./scripts/run_edge_camera.sh`
3. View events:
   - `curl -s http://127.0.0.1:9000/events?limit=10 | jq .`

## Optional: Hydra/AIC100 LLM summaries (Qwen)
To enable LLM-backed summaries for `/query` (no secrets in notes; export in your shell only):
- `export VSAAS_LLM_BASE_URL="https://dev.apigwx-op.qualcomm.com/aips/sparq/api/v1"`
- `export VSAAS_LLM_MODEL="qwen3_vl_32b_instruct"`
- `export QAIC_API_KEY="Stored in password manager"`
- `export APIGEE_TOKEN="Stored in password manager"`
- `export VSAAS_LLM_DEBUG=1`


## Mocking for demos
Force a PPE violation:
  - `export VSAAS_MOCK_PPE_VIOLATION=1`
Provide explicit detections (normalized bboxes):
  - `export VSAAS_MOCK_DETECTIONS_JSON='[{"label":"person","score":0.9,"bbox":[0.65,0.15,0.85,0.65]}]'`

## Example

```bash
# ONNX YOLOv8 CPU smoke test (sample image)
export VSAAS_DETECTOR=onnx_yolov8
export VSAAS_YOLO_ONNX_PATH="$PWD/models/yolov8n.onnx"
python3 scripts/qnn_smoke_test.py /path/to/sample.jpg | jq .
```

```bash
# QNN YOLOv8 HTP/NPU smoke test
export VSAAS_DETECTOR=qnn_yolov8
export VSAAS_QNN_DLC_PATH="$PWD/models/yolov8_det_w8a8/yolov8_det_w8a8.dlc"
python3 scripts/qnn_smoke_test.py /path/to/sample.jpg | jq .
```
