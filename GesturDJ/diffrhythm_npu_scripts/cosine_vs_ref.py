"""Accuracy gate score: cosine similarity and max abs error of an NPU output against the fp32 PyTorch reference.

    python3 cosine_vs_ref.py <npu_output.raw> <ref_v.f32> [--frames 960] [--min_cos 0.99]

The NPU output is fp16 or fp32 (told apart by file size: frames * 64 values). Exit code 1 if the cosine is below --min_cos.
Same arithmetic as the gate in the notebook; runs on the board or on a PC (numpy only).
"""
import argparse
import json
import sys

import numpy as np

p = argparse.ArgumentParser()
p.add_argument("npu_output")
p.add_argument("reference")
p.add_argument("--frames", type=int, default=960)
p.add_argument("--min_cos", type=float, default=0.99)
a = p.parse_args()

raw = np.fromfile(a.npu_output, dtype=np.uint8)
n = a.frames * 64
dtype = np.float32 if raw.size == n * 4 else np.float16
out = np.frombuffer(raw.tobytes(), dtype=dtype).astype(np.float64)
ref = np.fromfile(a.reference, dtype=np.float32).astype(np.float64)
if out.size != ref.size:
    sys.exit(f"output has {out.size} values, reference {ref.size}: graphs and test case disagree on the song length")
cos = float(out @ ref / np.sqrt((out @ out) * (ref @ ref)))
err = float(np.abs(out - ref).max())
verdict = "as good as fp16" if cos >= 0.999 else "usable, check by ear" if cos >= a.min_cos else "too lossy: do not generate a song"
print(json.dumps({"output_dtype": dtype.__name__, "cosine": round(cos, 5), "max_abs_err": round(err, 3), "min_cos": a.min_cos, "verdict": verdict, "ok": cos >= a.min_cos}))
sys.exit(0 if cos >= a.min_cos else 1)
