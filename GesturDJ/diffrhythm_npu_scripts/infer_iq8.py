"""Run DiffRhythm's stock infer.py, but send every DiT forward pass to the IQ8 NPU (HTP v75).

Runs inside WSL (where the PyTorch pipeline lives). On the first DiT call it starts `dit_server` on the board
through Windows plink.exe; the server keeps the four context binaries (seg0..3) loaded and chains them, and each
pass exchanges about 0.8 MB over the SSH pipe. No graph prepare is paid per pass.

Usage (cwd = DiffRhythm src dir): python infer_iq8.py <infer.py args...>
Env (required): IQ8_HOST, IQ8_HOSTKEY (SHA256:...), IQ8_PW (never stored in files).
Env (optional): DR_STEPS = sampler steps (default 32; the DiT runs 2 passes per step, minus one).
                DR_CTX_DIR = board directory holding seg0..3.bin (default "ctx"; e.g. "ctx_w8a16" for a quantized run), or four
                             comma-separated directories (one per segment) to mix precisions, e.g. "ctx,ctx_w8a16,ctx_w8a16,ctx".
                DR_SEED = fix the starting noise (integer) so two runs differ only in the setting under test.
                DR_CFG = classifier-free-guidance strength (stock 4.0); DR_SWAY = sway sampling coefficient (stock None; -1.0 spends
                         more of the few steps early in the trajectory, which usually helps at low step counts).
                DR_CALIB_DIR = if set, save every pass's DiT inputs there as raw files (calibration data for quantization).
                DR_FRAMES = sequence length of the NPU graphs (default 2048 = the stock 95 s song). A shorter song needs graphs
                            exported for that length (export_segments.py with the same DR_FRAMES); 960 frames = about 44.6 s
                            (21.5 frames per second). Run infer.py with --audio-length 95 as usual: this script shortens the song.
The unconditional CFG pass is the same graphs: DiT only zeroes `text` and `cond` when drop_text/drop_audio_cond are set.
"""
import os, subprocess, sys, time, runpy, threading
import numpy as np
import torch

PLINK = "/mnt/c/Program Files/PuTTY/plink.exe"
HOST = os.environ["IQ8_HOST"]
HOSTKEY = os.environ["IQ8_HOSTKEY"]          # SHA256:... pinned
PW = os.environ["IQ8_PW"]                    # never stored in notes/scripts
STATS = {"calls": 0, "npu_s": 0.0}
R = "/root/diffrhythm/qnn_rt"
_c = os.environ.get("DR_CTX_DIR", "ctx").split(",")
CTX = _c * 4 if len(_c) == 1 else _c          # one context dir per segment
assert len(CTX) == 4
CALIB = os.environ.get("DR_CALIB_DIR")
N = int(os.environ.get("DR_FRAMES", "2048"))   # frames per song; the graphs on the board must have been built for exactly this
REMOTE = (f"cd /root/diffrhythm && export LD_LIBRARY_PATH={R}/lib "
          f"ADSP_LIBRARY_PATH='{R}/lib/hexagon-v75/unsigned;/usr/lib/rfsa/adsp;/dsp' && "
          f"exec ./dit_server {R}/lib/libQnnHtp.so {R}/lib/libQnnSystem.so "
          + " ".join(f"{CTX[i]}/seg{i}.bin:seg{i}" for i in range(4)) + " 2>server.err")
_srv = None; _outbytes = 0; _inbytes = {}   # sizes the server reports; fp16 graphs take 2-byte floats, the int8 graphs have fp32 I/O

def _wait_board(max_s=900):
    """Block until the board answers SSH again after a reset (sshd can stall for minutes while ping stays up)."""
    t0 = time.time()
    while time.time() - t0 < max_s:
        try:
            r = subprocess.run([PLINK, "-ssh", "-batch", "-hostkey", HOSTKEY, "-pw", PW, f"root@{HOST}", "true"],
                               capture_output=True, timeout=30)
            if r.returncode == 0: return
        except subprocess.TimeoutExpired:
            pass
        time.sleep(10)
    raise RuntimeError(f"IQ8 did not come back within {max_s}s")

def _stop():
    global _srv
    if _srv is not None:
        try: _srv.kill()
        except OSError: pass
    _srv = None

PASS_TIMEOUT = int(os.environ.get("DR_PASS_TIMEOUT", "120"))   # a pass takes ~9 s; longer means a dead link or a hung NPU

def _read_timeout(n, timeout):
    """Read n bytes from the server, or raise TimeoutError. A board reset leaves plink's pipe half-open, so a bare read hangs."""
    box = []
    t = threading.Thread(target=lambda: box.append(_srv.stdout.read(n)), daemon=True)
    t.start(); t.join(timeout)
    if t.is_alive(): raise TimeoutError(f"no reply from dit_server in {timeout}s")
    return box[0]

def _server_alive_on_board():
    """True if dit_server still runs on the (reachable) board, i.e. the NPU call is hung rather than the board reset."""
    r = subprocess.run([PLINK, "-ssh", "-batch", "-hostkey", HOSTKEY, "-pw", PW, f"root@{HOST}", "pgrep -x dit_server"],
                       capture_output=True, timeout=60)
    return r.returncode == 0

def _start(attempts=4):
    """Start dit_server and wait for READY. A board reset while the graphs load (known memory fault) is retried."""
    global _srv, _outbytes
    for n in range(1, attempts + 1):
        _stop()
        try:
            _srv = subprocess.Popen([PLINK, "-ssh", "-batch", "-hostkey", HOSTKEY, "-pw", PW, f"root@{HOST}", REMOTE],
                                    stdin=subprocess.PIPE, stdout=subprocess.PIPE)
            while True:
                l = _srv.stdout.readline().decode().split()
                if not l: raise RuntimeError("IQ8 dit_server died at startup (see /root/diffrhythm/server.err)")
                if l[0] == "IN": _inbytes[l[1]] = int(l[2])
                if l[0] == "OUT": _outbytes = int(l[2])
                if l[0] == "READY": break
            print("[iq8] dit_server ready", flush=True)
            return
        except (RuntimeError, OSError) as e:
            print(f"[iq8] server start attempt {n}/{attempts} failed: {e}; waiting for the board", flush=True)
            _stop()
            if n == attempts: raise
            _wait_board()

def npu_forward(x, cond, text, time_, style_prompt, start_time, drop_text):
    t0 = time.time()
    if _srv is None: _start()   # normally already started eagerly below
    if drop_text:
        text = torch.zeros_like(text); cond = torch.zeros_like(cond)
    arrs = [("x", x.detach().float().numpy()), ("cond", cond.detach().float().numpy()), ("text", text.detach().numpy().astype(np.int32)),
            ("time", np.asarray([float(time_.reshape(-1)[0])])), ("style_prompt", style_prompt.detach().float().numpy()),
            ("start_time", start_time.detach().reshape(-1).float().numpy())]
    def enc(name, a, wide):   # int32 tokens as is; floats as fp32 if the graph input is 4 bytes per element, else fp16
        return a.tobytes() if name == "text" else a.astype(np.float32 if wide else np.float16).tobytes()
    buf = b"".join(enc(n, a, _inbytes[n] == a.size * 4) for n, a in arrs)
    if CALIB:   # calibration capture: x/cond/time/style as fp16, text as int32, one file per input per pass
        os.makedirs(CALIB, exist_ok=True)
        for name, a in arrs:
            with open(os.path.join(CALIB, f"p{STATS['calls']:03d}_{name}.raw"), "wb") as f: f.write(enc(name, a, False))
    for n in range(1, 4):
        # A pass is stateless, so after a dead pipe (board reset) restart the server and send it again.
        # Only a dead link is retried; if dit_server is still alive on the board the NPU is hung and we stop.
        try:
            _srv.stdin.write(buf); _srv.stdin.flush()
            raw = _read_timeout(_outbytes, PASS_TIMEOUT)
            if len(raw) != _outbytes: raise RuntimeError("short read from IQ8 dit_server")
            break
        except (OSError, RuntimeError, TimeoutError) as e:
            print(f"[iq8] pass failed ({e}); restarting dit_server (try {n}/3)", flush=True)
            if n == 3: raise
            _stop(); _wait_board()
            if _server_alive_on_board():
                raise RuntimeError("dit_server still running on the board: NPU call is hung. Reboot the board.")
            _start()
    v = np.frombuffer(raw, dtype=np.float32 if _outbytes == N * 64 * 4 else np.float16).astype(np.float32).reshape(1, N, 64)
    STATS["calls"] += 1; STATS["npu_s"] += time.time() - t0
    print(f"[iq8] pass {STATS['calls']} drop_text={drop_text} {time.time()-t0:.1f}s", flush=True)
    return torch.from_numpy(v.copy())

sys.path.insert(0, os.path.join(os.getcwd(), "infer"))
sys.path.insert(0, os.getcwd())
import types
if "model" not in sys.modules:
    pkg = types.ModuleType("model"); pkg.__path__ = [os.path.join(os.getcwd(), "model")]
    sys.modules["model"] = pkg
from model.dit import DiT
from model.cfm import CFM
sys.modules['model'].DiT = DiT; sys.modules['model'].CFM = CFM

if N != 2048:
    # Shorter song. DiffRhythm's 95 s model always builds 2048 frames of lyric tokens and an empty 2048-frame latent prompt,
    # so cut both to N frames and tell the sampler the song is N frames long. Everything downstream (noise, the DiT passes,
    # the VAE decode) then follows from that length. The model itself is the same; only the sequence is shorter.
    import infer_utils as _iu
    _orig_lrc, _orig_ref = _iu.get_lrc_token, _iu.get_reference_latent
    def _lrc_short(max_frames, text, tokenizer, max_secs, device):
        lrc_emb, start_time, _end_frame, song_duration = _orig_lrc(max_frames, text, tokenizer, max_secs, device)
        return lrc_emb[:, :N], start_time, N, song_duration
    def _ref_short(device, max_frames, edit, pred_segments, ref_song, vae_model):
        assert not edit, "editing a reference song is not supported for short songs"
        return torch.zeros(1, N, 64).to(device), [(0, N)]
    _iu.get_lrc_token, _iu.get_reference_latent = _lrc_short, _ref_short
    print(f"[iq8] short song: {N} frames = {N * 2048 / 44100:.1f} s", flush=True)

_orig_sample = CFM.sample
def _sample(self, *a, **kw):
    kw["steps"] = int(os.environ.get("DR_STEPS", kw.get("steps", 32)))   # fewer Euler steps = fewer DiT passes (2 per step)
    if os.environ.get("DR_SEED"): kw["seed"] = int(os.environ["DR_SEED"])
    if os.environ.get("DR_CFG"): kw["cfg_strength"] = float(os.environ["DR_CFG"])
    if os.environ.get("DR_SWAY"): kw["sway_sampling_coef"] = float(os.environ["DR_SWAY"])
    print(f"[iq8] sampler steps={kw['steps']} seed={kw.get('seed')} cfg={kw.get('cfg_strength')} sway={kw.get('sway_sampling_coef')}", flush=True)
    return _orig_sample(self, *a, **kw)
CFM.sample = _sample

_orig = DiT.forward
def forward(self, x, cond, text, time, drop_audio_cond, drop_text, drop_prompt=False, style_prompt=None,
            start_time=None, duration=None, **kw):
    assert x.shape == (1, N, 64), f"NPU graph is fixed to [1,{N},64], got {tuple(x.shape)}"
    assert not drop_prompt and drop_audio_cond == drop_text
    return npu_forward(x, cond, text, time, style_prompt, start_time, drop_text)
DiT.forward = forward

# Start the server now, before the ~8 min of text/style work on the PC, so a board that fails to load the graphs
# is found (and retried) up front instead of after the prep.
_start()

sys.argv = ["infer.py"] + sys.argv[1:]
t_all = time.time()
try:
    runpy.run_path(os.path.join(os.getcwd(), "infer", "infer.py"), run_name="__main__")
finally:
    _stop()
    print(f"[iq8] total passes={STATS['calls']} npu_wall={STATS['npu_s']:.1f}s total={time.time()-t_all:.1f}s", flush=True)
