"""Split the DiffRhythm DiT into four 4-block ONNX segments for the IQ8 NPU, and write a reference test case.

Why: preparing the whole 16-block graph on HTP v75 resets the IQ8; four 4-block graphs prepare fine (about 3 min each).
Run:  from the DiffRhythm `src` directory, with the diffrhythm_xelite WSL env, after the weights are in `pretrained/`.
      HF_HUB_OFFLINE=1 python export_segments.py       (needs about 10 GB RAM; a few minutes)

Segments (inputs -> outputs; text fusion only applies to the first 8 blocks):
  seg0  input layers + blocks 0-3     x, cond, text, time, style_prompt, start_time -> h, c, text_embed
  seg1  blocks 4-7                    h, text_embed                                  -> h_out
  seg2  blocks 8-11                   h                                              -> h_out
  seg3  blocks 12-15 + norm_out/proj  h, c                                           -> v

Also fixes the fp16 `Mish` problem: HTP v75 computes Softplus wrongly for large negative inputs (the stock Mish gave
cosine 0.06 against PyTorch), so Mish is replaced by x * tanh(softplus(clamp(x, -10, 10))), which is the same function
(tanh(softplus(x)) is already 0 or 1 beyond +-10).

Outputs in ./seg:  seg0..3.onnx, io.json (tensor names), case/*.raw (fp16/int32 inputs of a fixed random case) and
case/ref_v.f32 (fp32 output of the FULL model for that case). The script asserts that the chained segments equal the full
forward pass (max abs error < 1e-3) before exporting, so a bad split cannot be exported silently.
"""
import json, sys, types, os, numpy as np, torch
sys.path.insert(0, ".")
_pkg = types.ModuleType("model"); _pkg.__path__ = ["model"]; sys.modules["model"] = _pkg
import torch.nn as nn, torch.nn.functional as Fn
def safe_mish(x, inplace=False):
    return x * torch.tanh(Fn.softplus(x.clamp(min=-10.0, max=10.0)))   # HTP fp16 Softplus is wrong for large |x|
nn.Mish.forward = lambda self, x: safe_mish(x)
Fn.mish = safe_mish
from huggingface_hub import hf_hub_download
import model.dit as D
from model.dit import DiT, _prepare_decoder_attention_mask
from model.cfm import CFM
cfg = json.load(open("config/diffrhythm-1b.json"))["model"]; F = 2048      # F: what the model was trained with (do not change)
# N: sequence length of the exported graphs. 2048 frames = the stock 95 s song; a shorter song needs fewer frames
# (21.5 frames per second): DR_FRAMES=960 gives about 44.6 s. SEGD: output folder, so a short-song export never overwrites the stock one.
N = int(os.environ.get("DR_FRAMES", "2048")); SEGD = os.environ.get("DR_SEGDIR", "seg")
assert 0 < N <= F, "DR_FRAMES must be between 1 and 2048"
cfm = CFM(transformer=DiT(**cfg, max_frames=F), num_channels=cfg["mel_dim"], max_frames=F)
ck = torch.load(hf_hub_download("ASLP-lab/DiffRhythm-1_2", "cfm_model.pt", cache_dir="pretrained"), map_location="cpu", weights_only=True)
cfm.load_state_dict(ck["model_state_dict"], strict=False)
dit = cfm.transformer.float().eval()
DEPTH = dit.depth; print("depth", DEPTH, "blocks", len(dit.transformer_blocks), "long_skip", dit.long_skip_connection is not None)

class Seg(nn.Module):   # base: a slice [lo, hi) of the transformer blocks plus the shared rotary/mask setup
    def __init__(self, d, lo, hi): super().__init__(); self.dit = d; self.lo = lo; self.hi = hi
    def rope(self, x):
        pos = torch.arange(x.shape[1]).unsqueeze(0).repeat(x.shape[0], 1)
        return self.dit.rotary_emb(x, pos), _prepare_decoder_attention_mask(torch.ones((x.shape[0], x.shape[1]), dtype=torch.bool), (x.shape[0], x.shape[1]), x)
    def run_blocks(self, x, text_embed):
        rot, mask = self.rope(x)
        for i in range(self.lo, self.hi):
            x, *_ = self.dit.transformer_blocks[i](x, attention_mask=mask, position_embeddings=rot)
            if i < DEPTH // 2: x = x + self.dit.text_fusion_linears[i](text_embed)
        return x
class Seg0(Seg):      # input layers + first blocks
    def forward(self, x, cond, text, time, style_prompt, start_time):
        d = self.dit
        c = d.time_embed(time) + d.start_time_embed(start_time) + torch.zeros_like(d.start_time_embed(start_time))
        te = d.text_embed(text, x.shape[1], drop_text=False)
        h = d.input_embed(x, cond, te, style_prompt, c, drop_audio_cond=False)
        return self.run_blocks(h, te), c, te          # h, c, text_embed
class SegMid(Seg):    # blocks that still add text fusion
    def forward(self, h, text_embed): return self.run_blocks(h, text_embed)
class SegPlain(Seg):  # blocks with no text fusion
    def forward(self, h): return self.run_blocks(h, None)
class SegLast(Seg):   # last blocks + output layers
    def forward(self, h, c):
        x = self.run_blocks(h, None)
        assert self.dit.long_skip_connection is None
        return self.dit.proj_out(self.dit.norm_out(x, c))
# Cut the blocks into four equal slices. The text-fusion linears run for the first DEPTH//2 blocks, so the cut must
# fall exactly on the boundary between segment 1 and 2 (asserted below).
NB = len(dit.transformer_blocks); q = NB // 4
segs = [Seg0(dit, 0, q), SegMid(dit, q, 2 * q), SegPlain(dit, 2 * q, 3 * q), SegLast(dit, 3 * q, NB)]
assert DEPTH // 2 == 2 * q, "text fusion must end exactly at segment 1"

# Reference case: random but fixed inputs, the full-model output (same safe Mish) and the chained segments. Shapes follow
# the real pipeline: x/cond [1,N,64], text int [1,N], time/start_time [1], style_prompt [1,512].
torch.manual_seed(0)
inp = {"x": torch.randn(1, N, 64), "cond": torch.randn(1, N, 64), "text": torch.randint(0, 100, (1, N), dtype=torch.long),
       "time": torch.tensor([0.5]), "style_prompt": torch.randn(1, 512), "start_time": torch.tensor([0.0])}
with torch.inference_mode():
    ref = dit(inp["x"], inp["cond"], inp["text"], inp["time"], drop_audio_cond=False, drop_text=False,
              style_prompt=inp["style_prompt"], start_time=inp["start_time"])
    h, c, te = segs[0](inp["x"], inp["cond"], inp["text"], inp["time"], inp["style_prompt"], inp["start_time"])
    h1 = segs[1](h, te); h2 = segs[2](h1); v = segs[3](h2, c)
err = (v - ref).abs().max().item(); cos = float((v.flatten() @ ref.flatten()) / (v.norm() * ref.norm()))
print("segments chained vs full PyTorch forward: max_abs_err %.2e cos %.8f" % (err, cos))
assert err < 1e-3, "split is not faithful"

os.makedirs(SEGD, exist_ok=True)
# raw inputs (fp16, int32 text) + fp32 reference, for the on-board gate
os.makedirs(f"{SEGD}/case", exist_ok=True)
for k, dt in [("x", np.float16), ("cond", np.float16), ("time", np.float16), ("style_prompt", np.float16), ("start_time", np.float16)]:
    inp[k].numpy().astype(dt).tofile(f"{SEGD}/case/{k}.raw")
inp["text"].numpy().astype(np.int32).tofile(f"{SEGD}/case/text.raw")
ref.float().numpy().astype(np.float32).tofile(f"{SEGD}/case/ref_v.f32")
h, c, te, h1, h2 = [t.clone() for t in (h, c, te, h1, h2)]
# (name, module, example inputs, input names, output names) for torch.onnx.export; names must match what dit_server chains.
specs = [
 ("seg0", segs[0], (inp["x"], inp["cond"], inp["text"], inp["time"], inp["style_prompt"], inp["start_time"]), ["x","cond","text","time","style_prompt","start_time"], ["h","c","text_embed"]),
 ("seg1", segs[1], (h, te), ["h","text_embed"], ["h_out"]),
 ("seg2", segs[2], (h1,), ["h"], ["h_out"]),
 ("seg3", segs[3], (h2, c), ["h","c"], ["v"]),
]
for name, mod, ins, inn, outn in specs:
    torch.onnx.export(mod, ins, f"{SEGD}/{name}.onnx", input_names=inn, output_names=outn, opset_version=17, dynamo=False)
    print(name, "exported", os.path.getsize(f"{SEGD}/{name}.onnx") // 2**20, "MB")
json.dump({n: {"in": i, "out": o} for n, _, _, i, o in specs}, open(f"{SEGD}/io.json", "w"), indent=1)

