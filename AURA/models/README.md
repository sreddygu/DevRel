# Model Artifacts

Model files are **not checked into git** (they're large and are fetched or
exported on demand). This directory is a placeholder; populate it locally.

The defaults in `aura.config.Settings` and `README.md` expect:

| File | Used by | Default path |
|---|---|---|
| `yolov8n.onnx` | Milestone 1 (Eyes) — `aura.vision.detector.Detector` | `AURA_YOLO_MODEL=./models/yolov8n.onnx` |
| `bus.jpg` | demo / test fixture for `examples/eyes_demo.py` | `./models/bus.jpg` |

## Fetch `yolov8n.onnx`

Export the stock YOLOv8-nano detector to ONNX with Ultralytics:

```bash
pip install ultralytics
yolo export model=yolov8n.pt format=onnx imgsz=640
mv yolov8n.onnx models/
```

Or download a prebuilt `yolov8n.onnx` (COCO-80, 640×640 input) from the
[Ultralytics releases](https://github.com/ultralytics/assets/releases) and place
it here.

## Fetch `bus.jpg`

The canonical Ultralytics sample image:

```bash
curl -L -o models/bus.jpg https://ultralytics.com/images/bus.jpg
```

## On-device (IQ8 / Hexagon NPU)

The device path uses a quantized **DLC** (`yolov8_det_w8a8.dlc`) run via
`qnn-net-run`, not the ONNX file above — see
[`../docs/IQ8_DEPLOYMENT.md`](../docs/IQ8_DEPLOYMENT.md).
