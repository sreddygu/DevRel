# Gemma 4 E4B on IQ8 with QAIRT Genie

Resume state captured on September 21, 2026.

Latest deployment checkpoint: September 22, 2026.

## Goal

Run `qualcomm/Gemma-4-E4B-it:W4A16` directly on the Arduino VENTUNO Q / IQ8
QCS8275 Hexagon HTP v75 through QAIRT Genie, then expose it to AURA through the
existing OpenAI-compatible `aura.agent.genie_server` seam.

## Verified

- Qualcomm AI Hub exposes `Arduino VENTUNO Q` as an Ubuntu QNN target with
  chipset `qualcomm-qcs8275`, HTP v75, SoC model 82, FP16 support, and weight
  sharing support.
- GenieX lists `qualcomm/Gemma-4-E4B-it` as compatible with `qcs8275`.
- The QCS8275-specific W4A16 package downloaded successfully from Qualcomm AI
  Hub and is preserved outside temporary storage.
- The package metadata identifies runtime `geniex_qairt`, model
  `Gemma-4-E4B-it`, and QAIRT tool version `2.45.0.260326154327`.
- The package's HTP configuration targets SoC model 82 and DSP architecture
  v75 with shared-buffer memory and weight sharing enabled.

Official model page:
<https://aihub.qualcomm.com/models/gemma_4_e4b_it?runtime=geniex_qairt,geniex_llamacpp>

Official QAIRT documentation:
<https://docs.qualcomm.com/bundle/publicresource/topics/80-70017-15/introduction.html>

Installed primary documentation is also available at:

```text
C:\Qualcomm\AIStack\QAIRT\2.47.1.260610\docs\QAIRT-Docs\Genie\index.html
```

## Saved Artifacts

Persistent GenieX data directory:

```text
C:\Users\sreddygu\.cache\geniex-iq8
```

Model directory:

```text
C:\Users\sreddygu\.cache\geniex-iq8\models\qualcomm\Gemma-4-E4B-it
```

Verification:

```powershell
geniex --data-dir "$HOME\.cache\geniex-iq8" config list
geniex --data-dir "$HOME\.cache\geniex-iq8" list
```

Expected target and model:

```text
chipset: Arduino VENTUNO Q
qualcomm/Gemma-4-E4B-it  W4A16  9.2 GiB
```

## Runtime Files

The text-generation Genie configuration references these package files:

```text
genie_config.json
htp_backend_ext_config.json
tokenizer.json
embedding_int16_lut.bin
embed_token_int16_lut.bin
part1_of_4.bin
part2_of_4.bin
part3_of_4.bin
part4_of_4.bin
```

`sample_prompt.txt` is useful for the first smoke test. `vision_encoder.bin` is
not referenced by the text dialog configuration and can be deferred until the
text path is validated.

The runtime configuration uses:

```text
backend: QnnHtp
context: 4096 tokens
SoC model: 82
DSP: v75
memory: shared_buffer
weight sharing: enabled
```

## Installed Host Toolchain

```text
GenieX CLI: 0.6.1
GenieX bundled QAIRT: 2.45
QAIRT SDK: C:\Qualcomm\AIStack\QAIRT\2.47.1.260610
Linux ABI: aarch64-oe-linux-gcc11.2
```

The host SDK contains:

```text
bin\aarch64-oe-linux-gcc11.2\genie-t2t-run
bin\aarch64-oe-linux-gcc11.2\genie-app
lib\aarch64-oe-linux-gcc11.2\libGenie.so
```

## Resume Checklist

1. Reconnect IQ8 and determine its current IP address.
2. Inspect `/opt/qnn` before copying anything:

   ```bash
   find /opt/qnn -maxdepth 2 -type f -iname '*version*' -o -iname 'sdk.yaml'
   ls -l /opt/qnn/bin/genie* /opt/qnn/lib/libGenie.so
   ls -l /opt/qnn/lib/*V75* /opt/qnn/dsp/*V75*
   df -h /opt
   free -h
   ```

3. Verify the device QAIRT runtime is compatible with the package's QAIRT 2.45
   build. The previous device inventory showed HTP v75 libraries, but the
   detailed version check was interrupted and must be repeated.
4. Create a device model directory, for example:

   ```bash
   mkdir -p /opt/aura-gemma4
   ```

5. Copy `genie-t2t-run` only if it is missing. Prefer the device's existing
   `/opt/qnn` libraries; do not overwrite the runtime until compatibility has
   been checked.
6. Copy the nine text-runtime files listed above plus `sample_prompt.txt` into
   `/opt/aura-gemma4/`. Use an SSH key or password manager; do not put device
   credentials in scripts or documentation.
7. Run the native Genie smoke test from the model directory:

   ```bash
   cd /opt/aura-gemma4
   export LD_LIBRARY_PATH=/opt/qnn/lib
   export ADSP_LIBRARY_PATH=/opt/qnn/dsp
   /opt/qnn/bin/genie-t2t-run \
     -c /opt/aura-gemma4/genie_config.json \
     -p "$(cat /opt/aura-gemma4/sample_prompt.txt)"
   ```

8. If the runner fails, capture its complete stderr plus `dmesg` HTP/adsprpc
   messages before changing libraries.
9. Add a Gemma 4 prompt renderer to `src/aura/agent/genie_server.py`. The
   current server renders Qwen ChatML, while this package's sample prompt uses:

   ```text
   <bos><|turn>system
   ...<turn|>
   <|turn>user
   ...<turn|>
   <|turn>model
   ```

10. Keep the existing OpenAI-compatible HTTP seam and make prompt format a
    runner/server configuration option rather than adding a second server.
11. Add unit tests for Gemma prompt rendering and then deploy the updated AURA
    source to `/opt/aura/src`.
12. Start the loopback-only server and test `/v1/models` and
    `/v1/chat/completions` before running `aura_e2e.py`.

## Known Risks

- The model package was generated with QAIRT 2.45 while the available host SDK
  is QAIRT 2.47.1. Runtime compatibility must be verified on IQ8 before copying
  or replacing libraries.
- The package is approximately 9.2 GiB. Transfer individual files and verify
  sizes or hashes so an interrupted copy can resume without retransferring the
  entire bundle.
- The two embedding LUTs consume most of the package size and host memory.
  Measure available memory and model initialization behavior before enabling
  AURA's full perception pipeline concurrently.
- `aura.agent.genie_server` launches `genie-t2t-run` once per request. This is
  correct for the first smoke test but may reload the model each time. After
  correctness is established, evaluate a persistent Genie dialog process or
  in-process `libGenie` adapter for lower latency.

## September 22 Deployment Checkpoint

The IQ8 runtime was inspected and had the correct QNN HTP v75 libraries, but it
did not contain `libGenie.so` or `genie-t2t-run`.

The following QAIRT 2.47.1 files were copied successfully:

```text
/opt/qnn/bin/genie-t2t-run
/opt/qnn/lib/libGenie.so
```

`genie-t2t-run --help` executed successfully with
`LD_LIBRARY_PATH=/opt/qnn/lib`, confirming that the runner starts against the
staged runtime. The device image does not provide `ldd`, so dependency
validation used actual runner startup instead.

The following model files reported successful SCP completion under
`/opt/aura-gemma4/`:

```text
genie_config.json
htp_backend_ext_config.json
tokenizer.json
embedding_int16_lut.bin
embed_token_int16_lut.bin
part1_of_4.bin
part2_of_4.bin
```

The connection aborted while copying `part3_of_4.bin`. Its remote state is
unknown and must be checked by file size before resuming. `part4_of_4.bin` and
`sample_prompt.txt` were not attempted during that transfer.

Expected remaining local sizes:

```text
part3_of_4.bin  444112896
part4_of_4.bin  342663168
sample_prompt.txt  107
```

On reconnect, resume with:

```bash
find /opt/aura-gemma4 -maxdepth 1 -type f -printf '%f %s\n' | sort
```

Delete or overwrite `part3_of_4.bin` if its size is not exactly `444112896`,
then transfer only the incomplete or missing files. After all file sizes match,
continue with the native Genie smoke test in the Resume Checklist.

## Completed Commands

```powershell
$data = "$HOME\.cache\geniex-iq8"
geniex --data-dir $data config set chipset "Arduino VENTUNO Q"
geniex --data-dir $data model list
geniex --data-dir $data pull `
  "qualcomm/Gemma-4-E4B-it:W4A16" `
  --model-hub aihub `
  --model-type vlm
```

Do not repeat the download. Resume from the persistent data directory above.
