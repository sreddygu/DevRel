# Make a Song on the NPU in the Arduino Ventuno Q's Chip: The Build, Step by Step

This is the hands-on version, for the chip in the Arduino Ventuno Q, the Dragonwing IQ8. We built and measured everything here on a Dragonwing IQ8 development board, the chip inside the Ventuno Q; the Ventuno Q itself is untested (see the end). You will build four NPU graphs for DiffRhythm once, check them against a reference, then generate a 44.6 second song in about five minutes. The background and the reasoning are in the companion post. Here are the steps, the commands and the places we got stuck.

## What you need

A board with the Dragonwing IQ8 chip on your network (we used an IQ8 development board; the Arduino Ventuno Q has the same chip). A Windows PC with WSL (Ubuntu 22.04), a DiffRhythm install inside WSL, and the QAIRT SDK (we used 2.51). Keep 10 GB free on the Windows `C:` drive, because WSL lives there and crashes when it fills.

Credentials never go in a file. The scripts read `IQ8_HOST`, `IQ8_HOSTKEY` and `QLI_SSH_PASSWORD` from the environment, so set them in the terminal you launch the notebook from. Pin the host key after you check the fingerprint yourself.

The graphs are compiled for one fixed song length. A 44.6 second song is 960 latent frames, so set `DR_FRAMES=960`. The one-time build takes a few hours, mostly waiting. Finished steps are skipped on a re-run.

## 1. Split the model and export it

Run this from the DiffRhythm `src` folder in WSL.

```
DR_FRAMES=960 DR_SEGDIR=seg_45s python export_segments.py
```

The script splits the DiT into four ONNX graphs of four blocks each. It also writes a fixed test case and an fp32 reference output, and it asserts that chaining the four pieces reproduces the full forward pass before it writes anything. The reason for four pieces is that the full 16-block graph reset our board during HTP prepare.

Replace the stock Mish with `x * tanh(softplus(clamp(x, -10, 10)))` in the export. The stock version is wrong in fp16 on HTP v75 and gave a cosine of 0.06 against the reference. The script already does this.

## 2. Convert to fp16

```
qairt-converter --input_network seg0.onnx --float_bitwidth 16 --output_path seg0.dlc
```

Repeat for seg1, seg2 and seg3. A DLC is Qualcomm's model container. We ran the converter in a conda env with Python 3.12, numpy 1.26.4 and onnx 1.19.1.

## 3. Quantize the middle two

All four graphs at int8 fail the accuracy gate (cosine 0.76), so quantize only segments 1 and 2 and keep 0 and 3 at fp16.

First capture real inputs: run the fp16 graphs through DiffRhythm for a few different prompts with `DR_CALIB_DIR` set, then let `make_calib.py` pick passes spread across everything captured and push them through the fp32 ONNX segments on the CPU. The quantizer starts from a float model, so also convert fp32 DLCs (the same command without `--float_bitwidth 16`). Then:

```
qairt-quantizer --input_dlc seg1_fp32.dlc --output_dlc seg1.dlc \
  --input_list seg1_list.txt --weights_bitwidth 8 --act_bitwidth 16 \
  --bias_bitwidth 32 --float_bitwidth 16 --preserve_io_datatype \
  --use_per_channel_quantization
```

W8A16, int8 weights with 16-bit activations, is the only scheme that worked on this model. The quantizer needs a Windows x64 Python for its dependencies, so we used a separate venv for it.

## 4. Build context binaries on the board

Copy the DLCs to the board in checked chunks (we lost packets pushing large files over weak Wi-Fi, so the notebook copies in 16 MB pieces and verifies md5). Then compile each one once:

```
qnn-context-binary-generator --backend libQnnHtp.so --model libQnnModelDlc.so \
  --dlc_path seg0.dlc --binary_file seg0 --config_file cfg_seg0.json
```

The config needs `graph_names: ["seg0"]`, `vtcm_mb: 8`, `fp16_relaxed_precision: 1` and `htp_arch: 75`. The board needs the QAIRT runtime copied over; set `LD_LIBRARY_PATH` to its `lib` folder and `ADSP_LIBRARY_PATH` to the `hexagon-v75/unsigned` folder. Run `chmod +x` on the binaries after you extract them. Reloading a context binary takes seconds. Preparing the graph takes minutes, and you now do it once.

## 5. Start the server and run the gate

`dit_server` is a C++ program you cross-build in WSL with `build_dit_server.sh`. It loads the four binaries, prints the input tensors it expects, prints `READY`, and then answers requests on stdin and stdout: you write the raw bytes of every input, it writes back the output. Do not send anything before `READY`.

Before you generate any audio, run the gate. It pushes the fixed test case through the four graphs and scores the result against the fp32 reference:

```
python3 gate_board.py ctx_45s,ctx_45s_w8a16,ctx_45s_w8a16,ctx_45s out.raw case_45s
python3 cosine_vs_ref.py out.raw case_45s/ref_v.f32 --frames 960
```

At least 0.99 is required to proceed. 0.999 or more counts as as good as fp16. Our mixed setup scores 0.99986 and the fp16 graphs score 0.99999. If your number is low, stop here: a bad graph wastes a five-minute song every time.

## 6. Make the song

The notebook hooks `DiT.forward` in DiffRhythm's own `infer.py` and sends each pass to `dit_server` over `plink`. Set a style prompt and timed lyrics, and run the song cell.

```
STYLE_PROMPT = "acoustic folk, guitar, warm, gentle, female vocal."
```

Lyrics are `[mm:ss.xx]` lines in ascending order. Two rules cost us time: every line needs text, because an empty line crashes the text step, and DiffRhythm does not sing the last line (it marks the end), so add a throwaway final line.

Expect 30 NPU passes at 16 steps. On our board that is 81 seconds of NPU time and four to six minutes in total.

## Where we got stuck

A hung NPU process cannot be killed. It stays in state `D` or defunct and every later run fails with `openSessionForPriority failed ... status=0x72`. Only a reboot clears it, so never start a second NPU run on top of a stuck one. The notebook stops with a reboot message if it finds a stale `dit_server`.

Some boards reset at graph load because of a kernel memory fault we could not attribute to the model. If your board resets while loading, count `external abort` in `dmesg` after it comes back, and try the shorter, mixed graphs before the big fp16 ones.

`pkill -f <pattern>` over SSH kills your own session, so kill by PID. During graph prepare, SSH can hang for minutes while ping still answers, so retry before you assume a crash.

fp16 on the board's CPU is unusable (hundreds of times slower than fp32), so keep all fp16 work on the NPU or the PC.

## What about the Arduino Ventuno Q

The Ventuno Q uses the same Dragonwing IQ8 family. In principle the context binaries for HTP v75 are the right starting point. We have not run any of this on a Ventuno Q, so we do not know its default login, how its memory behaves under the graph load, or whether the QAIRT runtime files copy over unchanged. It runs Ubuntu where our board runs Qualcomm Linux, so expect to adjust the runtime setup. Try the shortest graphs first and run the gate before you trust a song.

## License check before you demo

DiffRhythm is three licenses in one pipeline. Check each before you show it to anyone outside the team. This is a summary, not legal advice.

| Piece | License | What it means for a demo |
| --- | --- | --- |
| DiffRhythm code and DiT weights | Apache-2.0 | Free to use, modify and publish. |
| VAE (`DiffRhythm-vae`) | Stability AI Community License | Free for non-commercial use. Commercial use is gated by company revenue, so a large company needs an agreement with Stability. Check the current terms at stability.ai/license. |
| MuQ-MuLan style-encoder weights | CC-BY-NC-4.0 | Non-commercial only: evaluation, research, internal use. |

**Internal or closed-door demo** (team reviews, evaluation): go ahead.

**Public, customer-facing or event demo:** get legal sign-off first. A promotional demo can count as commercial use even when nothing is sold. Label it as an evaluation, not a product path.

**Do not redistribute the MuQ-MuLan or VAE weights.** Point readers to their original sources, which is how our notebook gets them.

**If legal says no:** swap the model (ACE-Step's code and weights are Apache-2.0; in our listening it fell short of what a demo needs), or ask the DiffRhythm authors (ASLP lab) for permission to use the style encoder commercially. Either costs time, so ask early if the demo has a date.

Label all generated output as AI-generated.

The notebook, the scripts and the gate are in the repo: [repo link].
