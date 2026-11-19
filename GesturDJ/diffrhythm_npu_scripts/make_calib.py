"""Build quantizer calibration lists for the four DiT segments from real DiT inputs.

Why: int8 quantization needs example data to choose each tensor's value range. Uniform random data would pick the wrong ranges,
so we use inputs the sampler really produced (saved by infer_iq8.py with DR_CALIB_DIR), spread across the whole denoising
trajectory and across both CFG passes (conditional and unconditional).

Run in WSL:  python make_calib.py <dump_dir> <seg_dir> <out_dir> [n_samples]
  dump_dir  raw inputs saved by infer_iq8.py: pNNN_<name>.raw (x, cond, time, style_prompt, start_time fp16; text int32).
            May contain one sub-folder per run (e.g. one per prompt); all of them are searched.
  seg_dir   directory with seg0..3.onnx (fp32 export from export_segments.py)
  out_dir   receives raw fp32 files and seg0_list.txt .. seg3_list.txt (one line per sample: "input:=file input:=file").

The segments are chained on the CPU in fp32 with onnxruntime, so segment 1-3 get the true intermediate tensors (h, c, text_embed)
that the previous segment would produce. Those are the inputs the quantizer sees for that segment.
"""
import sys, glob, os, json
import numpy as np
import onnxruntime as ort

dump, segdir, out = sys.argv[1:4]
n_want = int(sys.argv[4]) if len(sys.argv) > 4 else 16
os.makedirs(out, exist_ok=True)

found = sorted(glob.glob(os.path.join(dump, "**", "p*_x.raw"), recursive=True))
assert found, f"no p*_x.raw files under {dump}"
# DR_CALIB_FROM=0.5 keeps only the later part of every run (the detail-forming denoising steps, where int8 error hurts most).
frm = float(os.environ.get("DR_CALIB_FROM", "0"))
if frm > 0:
    by_dir = {}
    for f in found: by_dir.setdefault(os.path.dirname(f), []).append(f)
    found = [f for fs in by_dir.values() for f in fs[int(len(fs) * frm):]]
pick = [found[int(round(i))][:-len("_x.raw")] for i in np.linspace(0, len(found) - 1, min(n_want, len(found)))]
print(f"{len(found)} captured passes, using {len(pick)}")

io = json.load(open(os.path.join(segdir, "io.json")))
SEGS = ["seg0", "seg1", "seg2", "seg3"]

def load_input(meta, path):
    dt = np.int32 if "int" in meta.type else np.float16
    a = np.fromfile(path, dtype=dt)
    return a.reshape(meta.shape).astype(np.int64 if meta.type == "tensor(int64)" else (np.int32 if dt == np.int32 else np.float32))

# Process ONE segment at a time for all samples. Holding all four fp32 sessions plus their activation arenas at once used
# ~15 GB and made WSL thrash; the per-sample tensors passed between segments (h, c, text_embed) are small enough to keep.
opts = ort.SessionOptions(); opts.enable_cpu_mem_arena = False; opts.enable_mem_pattern = False
def open_session(s): return ort.InferenceSession(os.path.join(segdir, f"{s}.onnx"), opts, providers=["CPUExecutionProvider"])

sess = open_session("seg0")
meta = {i.name: i for i in sess.get_inputs()}
envs = [{name: load_input(meta[name], f"{stem}_{name}.raw") for name in io["seg0"]["in"]} for stem in pick]
for s in SEGS:
    if s != "seg0": sess = open_session(s)
    with open(os.path.join(out, f"{s}_list.txt"), "w") as lst:
        for n, env in enumerate(envs):
            names = io[s]["in"]; files = []
            for k in names:       # quantizer reads raw files in the DLC input dtype: fp32 for floats, int32 for the text tokens
                a = env[k]; a = a.astype(np.int32) if a.dtype in (np.int32, np.int64) else a.astype(np.float32)
                f = os.path.join(out, f"{s}_p{n:03d}_{k}.raw"); a.tofile(f); files.append(f"{k}:={os.path.abspath(f)}")
            lst.write(" ".join(files) + "\n")
            for k, v in zip(io[s]["out"], sess.run(None, {k: env[k] for k in names})): env[k] = v
            if "h_out" in env: env["h"] = env.pop("h_out")    # seg1/seg2 emit "h_out"; the next segment consumes it as "h"
            print(s, "sample", n, "done", flush=True)
    del sess
print("lists:", sorted(glob.glob(os.path.join(out, "seg*_list.txt"))))
