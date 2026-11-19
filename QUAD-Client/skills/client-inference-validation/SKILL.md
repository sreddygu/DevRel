# QUAD-Client Inference Validation

Validate a QNN inference workflow through QUAD-Client and retain evidence that
distinguishes local simulation from observed device execution.

1. Identify the model format, target SDK, backend, and target device or host.
2. Run `quad-client profile-device --model <path>` only with an approved model
   reference. If conversion is requested, add `--convert` only after explicit
   approval and record the source and generated artifact identifiers.
3. Use the relevant sample under `samples/` for the chosen workload and follow
   its documented command; do not substitute unreviewed model or converter
   options.
4. Run focused regression coverage before reporting an outcome:
   `python -m pytest tests/test_local/test_device_agent.py
   samples/mobilenetv2_npu_iq9075/tests/test_end_to_end.py -q`.
5. Record the model identifier, runtime/backend, target, provider verification,
   latency or throughput result, conversion state, command exit status, and
   exclusions. State whether the result was measured on-device.

Conversion, model transfer, remote execution, and benchmark runs can consume
device storage and compute; they require explicit approval. Never claim NPU
execution from host-only output, and never package restricted models or SDK
artifacts into public evidence.
