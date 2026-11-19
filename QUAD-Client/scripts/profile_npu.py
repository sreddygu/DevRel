import time

import numpy as np
import onnxruntime as ort
import onnxruntime_qnn

# Use the original ONNX — ORT QNN EP compiles it to HTP on first load
# (.bin cannot be loaded directly by ORT; needs wrapper ONNX + model_net.json)
MODEL = "quad_artifacts/mobilenetv2-12-static-qdq/mobilenetv2-12-static-qdq.onnx"

# ORT 1.27: register the QNN plugin EP library before creating any session
ort.register_execution_provider_library("QNN", onnxruntime_qnn.get_library_path())
htp_lib = onnxruntime_qnn.get_qnn_htp_path()
print(f"QNN HTP library  : {htp_lib}")

sess_opts = ort.SessionOptions()
sess_opts.enable_profiling = False

sess = ort.InferenceSession(
    MODEL,
    sess_options=sess_opts,
    providers=[("QNN", {"backend_path": htp_lib, "htp_performance_mode": "burst"})],
)

# Verify NPU is actually being used (provider name is "QNN" in ORT 1.27)
active = sess.get_providers()
print(f"Active providers : {active}")
if "QNN" not in active:
    print("WARNING: QNN EP not active — running on CPU fallback")

inp_name = sess.get_inputs()[0].name
inp_shape = [d if isinstance(d, int) else 1 for d in sess.get_inputs()[0].shape]
print(f"Input            : {inp_name} {inp_shape}")

dummy = np.random.randn(*inp_shape).astype(np.float32)
feeds = {inp_name: dummy}

# Warmup — let the HTP scheduler settle
print("Warming up (10 runs)...")
for _ in range(10):
    sess.run(None, feeds)

# Measure
N = 100
print(f"Measuring ({N} runs)...")
latencies = []
for _ in range(N):
    t0 = time.perf_counter()
    sess.run(None, feeds)
    latencies.append((time.perf_counter() - t0) * 1000)

arr = np.array(latencies)
print()
print("=" * 50)
print("  QUAD NPU PROFILE — Snapdragon X Elite / Hexagon HTP")
print("=" * 50)
print(f"  Model   : {MODEL}")
print("  Runtime : QNNExecutionProvider (QnnHtp.dll)")
print(f"  Runs    : {N}")
print()
print(f"  Mean    : {arr.mean():.2f} ms")
print(f"  p50     : {np.percentile(arr, 50):.2f} ms")
print(f"  p95     : {np.percentile(arr, 95):.2f} ms")
print(f"  p99     : {np.percentile(arr, 99):.2f} ms")
print(f"  Min     : {arr.min():.2f} ms")
print(f"  Max     : {arr.max():.2f} ms")
print(f"  FPS     : {1000 / arr.mean():.1f}")
print("=" * 50)
