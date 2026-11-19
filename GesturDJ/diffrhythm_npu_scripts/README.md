# diffrhythm_npu_scripts

Back to the [GesturDJ README](../README.md).

Helper scripts for running DiffRhythm's diffusion transformer (DiT) on a Qualcomm NPU. The maintained entry point for the IQ8 is [`../diffrhythm_iq8_npu_int8_45s.ipynb`](../diffrhythm_iq8_npu_int8_45s.ipynb), which calls these files; run them by hand only when you need to.

The exporter loads `cfm_model.pt` from [`ASLP-lab/DiffRhythm-1_2`](https://huggingface.co/ASLP-lab/DiffRhythm-1_2), not `DiffRhythm-base`; see [`export_segments.py`](export_segments.py).

## What is here

| File | Runs on | What it does |
| --- | --- | --- |
| [`export_segments.py`](export_segments.py) | WSL | Splits the DiT into four 4-block ONNX segments (with the fp16-safe `Mish`) and writes a fixed test case plus an fp32 reference output. Run from the DiffRhythm `src` dir. |
| [`dit_server.cpp`](dit_server.cpp) | board (aarch64) | Persistent runner. Loads the four context binaries once and chains them per request over stdin/stdout. Protocol and limits are documented in the file header. |
| [`build_dit_server.sh`](build_dit_server.sh) | WSL | Cross-compiles [`dit_server.cpp`](dit_server.cpp) for the board (`g++-aarch64-linux-gnu`; set `QAIRT_INCLUDE` to override the SDK header path). |
| [`infer_iq8.py`](infer_iq8.py) | WSL | Runs DiffRhythm's stock `infer.py` with `DiT.forward` replaced by a call to `dit_server` on the board (through Windows `plink.exe`). Also honours `DR_STEPS`. |
| [`make_calib.py`](make_calib.py) | WSL | Builds int8 quantizer calibration lists from real DiT inputs captured by [`infer_iq8.py`](infer_iq8.py) (`DR_CALIB_DIR`); used by [`../diffrhythm_iq8_npu_int8_45s.ipynb`](../diffrhythm_iq8_npu_int8_45s.ipynb). |
| [`gate_board.py`](gate_board.py) | board | Accuracy-gate runner: loads the given context dir(s) in `dit_server`, runs the test case twice. |
| [`make_fp32_case.py`](make_fp32_case.py) | board or PC | Widens the fp16 test case to fp32 so all-int8 graphs can be gated. |
| [`cosine_vs_ref.py`](cosine_vs_ref.py) | board or PC | Scores a gate output against the fp32 reference: cosine, max error, verdict. |
| [`evaluate_clip_library.py`](evaluate_clip_library.py) | PC | Objective checks on generated clips and on the set (length, clipping, silence, loudness spread, loop seam). |

## How the pieces fit (IQ8)

```
 PC (WSL)                                              IQ8 board
 --------                                              ---------
 export_segments.py -> seg0..3.onnx
 qairt-converter    -> seg0..3.dlc  ---- push ---->    seg/segN.dlc
                                                        qnn-context-binary-generator
                                                        -> ctx/segN.bin (compiled once)
 infer.py (text, MuQ style, VAE)
   DiT.forward  = infer_iq8.py  -- plink pipe -->      dit_server  (ctx/seg0..3.bin resident)
                  x, cond, text, time, ...  (0.8 MB)     seg0 -> seg1 -> seg2 -> seg3 on the HTP
                  <------ v (fp16 [1,frames,64]) ------
```

Per song: 2 x (STEPS - 1) DiT passes (classifier-free guidance doubles them): 30 at the default `STEPS = 16`, 62 at 32. `frames` is 960 for the 44.6 s demo and 2048 for the stock 95 s song.

## Environment variables

| Variable | Used by | Meaning |
| --- | --- | --- |
| `IQ8_HOST` | [`infer_iq8.py`](infer_iq8.py) | Board IP address. |
| `IQ8_HOSTKEY` | same | SSH host key fingerprint (`SHA256:...`); verify it yourself. |
| `IQ8_PW` | same | Board password. Never stored in any file; the notebook reads `QLI_SSH_PASSWORD` and passes it on. |
| `DR_CTX_DIR` | [`infer_iq8.py`](infer_iq8.py) | Board context-binary folder (default `ctx`), or four comma-separated folders to mix fp16 and int8 per segment. |
| `DR_CALIB_DIR` | [`infer_iq8.py`](infer_iq8.py) | If set, saves every pass's DiT inputs there (quantization calibration data). |
| `DR_FRAMES` | [`export_segments.py`](export_segments.py), [`infer_iq8.py`](infer_iq8.py) | Song length in latent frames (default 2048 = 95 s; the demo uses 960 = 44.6 s). Must match the exported graphs. |
| `DR_SEGDIR` | [`export_segments.py`](export_segments.py) | Output folder for the segments (default `seg`). |
| `DR_STEPS` | [`infer_iq8.py`](infer_iq8.py) | Sampler steps (default 32 in the scripts, 16 in the notebook). |
| `DR_WSL_ROOT` | [`infer_iq8.py`](infer_iq8.py) | DiffRhythm install in WSL (default `/home/ubuntu/diffrhythm_xelite`). |
| `QAIRT_INCLUDE` | [`build_dit_server.sh`](build_dit_server.sh) | QAIRT `include/QNN` directory for the build. |

## Gotchas

- `plink` must be called with `-ssh`; on some PCs PuTTY's default protocol is not SSH.
- [`infer_iq8.py`](infer_iq8.py) starts `dit_server` before the PC-side prep and retries (waiting for the board) if the graphs fail to load or the pipe dies mid-song. A hung NPU call is not retried.
- A hung NPU process cannot be killed and wedges the NPU until the board reboots.
- The board has an intermittent kernel memory fault that can reset it while the graphs load; see [`../DIFFRHYTHM_IQ8.md`](../DIFFRHYTHM_IQ8.md).
