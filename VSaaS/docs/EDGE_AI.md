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

## Optional: OpenAI-compatible LLM summaries (Qwen)
To enable LLM-backed summaries for `/query` (no secrets in notes; export in your shell only):
- `export VSAAS_LLM_BASE_URL="https://api.example.com/v1"`
- `export VSAAS_LLM_MODEL="qwen3_vl_32b_instruct"`
- `export VSAAS_LLM_API_KEY="Stored in password manager"`
- Optional custom gateway header: `export VSAAS_LLM_X_APIKEY="Stored in password manager"`
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
