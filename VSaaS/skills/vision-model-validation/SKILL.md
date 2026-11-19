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
