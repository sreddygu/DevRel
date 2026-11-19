# DiffRhythm on the IQ8 NPU: background

Back to the [GesturDJ README](README.md).

The demo is [`diffrhythm_iq8_npu_int8_45s.ipynb`](diffrhythm_iq8_npu_int8_45s.ipynb); measured results and status are in [`PROJECT_CONTEXT.md`](PROJECT_CONTEXT.md). No credentials are stored here; scripts read them from environment variables.

DiffRhythm (Apache-2.0 code; MuQ-MuLan weights are CC-BY-NC-4.0, evaluation only) generates a song from a style prompt and timed lyrics: latent frames (21.5 per second) and diffusion steps with classifier-free guidance, so 2 x (steps - 1) passes of its transformer (DiT). The DiT runs on the IQ8 NPU; the text/style encoders and the audio decoder (VAE) run on a PC. The demo exports [`ASLP-lab/DiffRhythm-1_2`](https://huggingface.co/ASLP-lab/DiffRhythm-1_2)'s `cfm_model.pt` checkpoint (not `DiffRhythm-base`), builds the graphs for 960 frames (44.6 s), and uses 2048 frames for the stock 95 s song.

## How the IQ8 NPU run works

The full 16-block graph resets the board during HTP prepare (about 6 min in), so the DiT is split into four 4-block graphs.

1. **Export** (WSL, [`diffrhythm_npu_scripts/export_segments.py`](diffrhythm_npu_scripts/export_segments.py), run from the DiffRhythm `src` dir; `DR_FRAMES` sets the song length): `seg0..3.onnx`, plus a fixed random test case and an fp32 reference output for the accuracy gate. seg0 = input layers + blocks 0-3 (outputs `h`, `c`, `text_embed`); seg1 = blocks 4-7 (inputs `h`, `text_embed`); seg2 = blocks 8-11 (input `h`); seg3 = blocks 12-15 + norm_out/proj_out (inputs `h`, `c`; output `v`). Text fusion applies to the first 8 blocks only. The script asserts the chain matches the full forward pass.
2. **Convert** with QAIRT 2.51.40.260930 (`qairt-converter --float_bitwidth 16`, conda env `qairt312`: Python 3.12, numpy 1.26.4, onnx 1.19.1) to `seg0..3.dlc`. Mish must be exported as `x * tanh(softplus(clamp(x, -10, 10)))`: fp16 Softplus is wrong for large negative inputs on HTP v75 and the stock Mish gave cosine 0.06.
3. **Quantize** segments 1 and 2 to W8A16 int8 with calibration inputs captured from real runs ([`make_calib.py`](diffrhythm_npu_scripts/make_calib.py)). Segments 0 and 3 stay fp16: all-int8 fails the accuracy gate (cosine 0.61), the mix passes.
4. **Context binaries** on the board: `qnn-context-binary-generator --backend libQnnHtp.so --model libQnnModelDlc.so --dlc_path segN.dlc --binary_file segN --config_file cfg_segN.json` into `ctx*/segN.bin`. The config needs `graph_names:["segN"]`, `vtcm_mb:8`, `fp16_relaxed_precision:1`, `htp_arch:75`. Reloading a context binary takes seconds instead of minutes.
5. **`dit_server`** (C++, [`diffrhythm_npu_scripts/dit_server.cpp`](diffrhythm_npu_scripts/dit_server.cpp), cross-built in WSL with `aarch64-linux-gnu-g++` via [`build_dit_server.sh`](diffrhythm_npu_scripts/build_dit_server.sh)): loads the four contexts once and chains them by tensor name over stdin/stdout. Input per request: fp16 `x`, `cond`, int32 `text`, fp16 `time`, `style_prompt`, `start_time`; output fp16 `v` `[1, frames, 64]`. The unconditional CFG pass reuses the same graphs.
6. **Song**: the notebook runs [`infer_iq8.py`](diffrhythm_npu_scripts/infer_iq8.py) in WSL, which hooks `DiT.forward` and talks to the server through Windows `plink.exe`. Needs `IQ8_PW`, `IQ8_HOSTKEY`, `IQ8_HOST`; optional `DR_STEPS`, `DR_FRAMES`, `DR_CTX_DIR`.
7. **Accuracy gate**: cosine of the chain's output vs the fp32 PyTorch reference. At least 0.99 is required; 0.999 counts as "as good as fp16".

Runtime environment on the board: `R=/root/diffrhythm/qnn_rt`, `LD_LIBRARY_PATH=$R/lib`, `ADSP_LIBRARY_PATH="$R/lib/hexagon-v75/unsigned;/usr/lib/rfsa/adsp;/dsp"`. Run `chmod +x` on `qnn_rt/bin/*` after extracting `qnn_rt.tar`. Quote profiler execute time for NPU speed claims; wall-clock adds about 0.5 s HTP init per process.

## Board and platform

- IQ8 runs Qualcomm Linux 2.0 (aarch64, 8 cores, 11 GB RAM, no swap, no compiler or git). The same board answers at an office and a home IP with the same host key; pin the key with `plink -hostkey` after checking the fingerprint.
- Use the on-device espeak-ng at `/opt/aura-speech/piper`. QNN 2.47.1 is at `/opt/qnn`; QAIRT 2.51 is staged at `/opt/qnn-2.51.40.260930`.
- Big copies over weak Wi-Fi caused packet loss: push in md5-checked 16 MB chunks (the notebook's `push()`).
- sshd can hang for minutes during graph prepare while ping stays up; retry before assuming a crash.
- Audio: PipeWire sink "Built-in Audio Speaker playback"; a speaker must be on the jack to hear anything.

## IQ8 memory-abort resets (open issue)

Board hangs and resets are kernel memory faults, not memory pressure.

- Signature: `Internal error: synchronous external abort: 0000000096000010` (taint `S`, `M`) in `clear_page` / `copy_page` / `memset` on a newly allocated page, then RCU starvation, SSH death, reboot.
- Faulting physical pages: `0x91a88000`, `0x91ab1000`, `0xB0000000`. A 12 GB swap file did nothing, and retiring pages with `hard_offline_page` only moved the crash.
- Reproducer on a clean reflash: `stress-ng --vm 4 --vm-bytes 9G --vm-method walk-1d --verify --timeout 600s` crashes the board in about 4 min, so it is independent of DiffRhythm: bad or inaccessible RAM handed to the kernel. Not proven.
- Load test: the stock 95 s fp16 graphs (2.3 GB) reset the board 2 of 2 loads; 45 s mixed, 45 s fp16 and 95 s mixed loaded 6 times each with no reset. This does not show whether int8 or the shorter length is the reason.
- **Wedged NPU:** a hung `dit_server` / `qnn-net-run` stays in state `D` or `<defunct>` and cannot be killed; every later run then fails with `openSessionForPriority failed ... status=0x72`. Only a board reboot clears it. Never start another NPU run on top of a hung one; the notebook's gate stops with a reboot message if it finds a stale `dit_server`.
- After a reset, sshd can come up without shells; a power cycle fixes it.

**Next:** escalate to the EVK/BSP owners with the fault addresses and `/proc/iomem`, or try another board. Until then expect occasional resets; files survive reboot.

## Other findings

- **Empty lyric line crashes g2p.** Every line needs text. DiffRhythm also does not sing the last lyric line (it marks the end), so add a throwaway final line.
- **fp16 on CPU is unusable**: DiffRhythm calls `model.half()` (`infer/infer_utils.py`); fp16/bf16 matmuls on the IQ8 CPU are hundreds of times slower than fp32.
- **C: full / WSL**: the WSL disk lives on C:; when C: filled, WSL crashed with `E_UNEXPECTED`. Keep 10 GB free.
- **Install friction**: pin `py3langid==0.2.2`; set `PIP_DEFAULT_TIMEOUT=120 PIP_RETRIES=10`; send shell scripts to plink as bytes (CRLF breaks bash); ONNX export needs the `model` package stubbed (it imports `wandb`) and external data consolidated into one file.
- **WSL/Git Bash**: `\\wsl.localhost\...` paths and `$VAR` inside `wsl -- bash -c '...'` get mangled, so write a `.sh` and run it (or set `MSYS_NO_PATHCONV=1`); background jobs started inside a `wsl.exe` call die when it returns; no sudo, so use the `espeakng-loader` pip package (`PHONEMIZER_ESPEAK_LIBRARY`, `ESPEAK_DATA_PATH`).
- **plink**: `pkill -f <pattern>` over SSH kills your own session; kill by PID. In Git Bash use forward slashes in `plink -m` paths.

## Files

- WSL `/home/ubuntu/diffrhythm_xelite`: `env/`, `src/` (with the segment folders after export), `runs/` (songs).
- PC `C:\dr_iq8\`: staging (`qnn_rt.tar`, segment and quantizer folders).
- Board `/root/diffrhythm/`: `seg*/` DLCs, `ctx*/` context binaries, `case*/` test cases, `qnn_rt/`, `dit_server`.

## Resume

1. Power-cycle the board if it is down; check `dmesg | grep -c 'external abort'`.
2. Set `IQ8_HOST`, `IQ8_HOSTKEY`, `QLI_SSH_PASSWORD` and run [`diffrhythm_iq8_npu_int8_45s.ipynb`](diffrhythm_iq8_npu_int8_45s.ipynb); finished steps are skipped.
3. Listen to the mixed and fp16 songs in `diffrhythm_outputs/` and compare.
