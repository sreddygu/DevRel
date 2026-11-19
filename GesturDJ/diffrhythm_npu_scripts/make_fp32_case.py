"""Make an fp32 copy of a DiT test case, so graphs with fp32 inputs (all-int8) can be gated.

The fp16 case (x, cond, style_prompt, time, start_time) is widened to fp32 exactly; text.raw (int32) and ref_v.f32 are copied.
Run on the board (numpy only):  python3 make_fp32_case.py case_45s case_45s_fp32
"""

import os
import shutil
import sys

import numpy as np

src, dst = sys.argv[1:3]
os.makedirs(dst, exist_ok=True)
for n in ("x", "cond", "style_prompt", "time", "start_time"):
    a = np.fromfile(f"{src}/{n}.raw", dtype=np.float16).astype(np.float32)
    a.tofile(f"{dst}/{n}.raw")
    print(f"{n}: {a.size} values -> {a.nbytes} bytes")
shutil.copy(f"{src}/text.raw", f"{dst}/text.raw")
shutil.copy(f"{src}/ref_v.f32", f"{dst}/ref_v.f32")
print("text.raw and ref_v.f32 copied")
