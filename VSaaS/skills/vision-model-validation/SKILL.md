---
name: vision-model-validation
description: "Validate an ONNX or QNN object detector (for example YOLOv8) used by VSaaS and record results labelled by backend and target."
version: 0.1.0
---

# VSaaS Vision Model Validation

Validate a selected detector using a known frame and label the evidence by
backend and target. Do not infer hardware acceleration from configuration alone.

1. Identify the detector mode, model identifier, backend, target, and approved
   test frame. Use a non-sensitive frame or an approved synthetic fixture.
2. For a QNN workflow, run `python3 scripts/qnn_smoke_test.py <frame>` with
   runtime-supplied QNN environment variables only after approval.
3. For the ONNX path, use the documented edge workflow and record the same
   detector/backend/target fields.
4. Record detection count, top labels/scores, command exit status, model and
   backend identifiers, and whether the execution was observed on-device.
5. Stop on missing model/backend dependencies. Do not download models, alter
   QNN libraries, or copy artifacts to a target without explicit approval.

This is a functional validation, not an accuracy certification. It does not
claim NPU execution without target-side evidence.

<!-- skills-hub:begin -->

## Compatibility

| Item | Details |
| --- | --- |
| Devkits | Dragonwing IQ-8275 EVK (`qcs8275-iq-8275-evk-pro`) |
| Target OS | No target OS constraint declared |
| Host OS | Any |
| Requirements | Python 3.12 and Linux (Ubuntu 24.04); ONNX Runtime or QNN YOLOv8 DLC for real perception |

References: [VSaaS README](https://github.com/sreddygu/DevRel/blob/main/VSaaS/README.md), [Edge AI notes](https://github.com/sreddygu/DevRel/blob/main/VSaaS/docs/EDGE_AI.md).

## Example prompts

- Validate my YOLOv8 ONNX detector
- Run the QNN YOLOv8 DLC on my IQ8 and record the result
- Compare ONNX CPU and QNN results on the same video frame
- Which backend and target produced this detection result?
- Did my detector really run on the NPU, or only on the CPU?
- Record detection count, top labels and scores for my test frame

<!-- skills-hub:end -->
