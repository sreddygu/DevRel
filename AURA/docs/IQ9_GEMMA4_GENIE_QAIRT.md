# Gemma 4 E4B on IQ9 with QAIRT Genie

Working deployment verified on September 22, 2026.

The camera, speech, memory, reasoning, and action E2E resume state is recorded
in `docs/IQ9_AURA_E2E_RESUME.md`.

## Goal

Run `qualcomm/Gemma-4-E4B-it:W4A16` directly on the Dragonwing IQ-9075 EVK
through the GenieX QAIRT runtime and expose it to AURA through GenieX's native
OpenAI-compatible server.

## Verified Target

Qualcomm AI Hub reports the IQ9 target as:

```text
Reference device: Dragonwing IQ-9075 EVK
Chipset: qualcomm-qcs9075
OS: qc_linux
ABI: aarch64-oe-linux-gcc11
Framework: QNN
Hexagon: v73
SoC model: 77
HTP FP16: supported
HTP weight sharing: supported
```

GenieX lists `qualcomm/Gemma-4-E4B-it` as compatible with `qcs9075`.

Official model page:
<https://aihub.qualcomm.com/models/gemma_4_e4b_it?runtime=geniex_qairt,geniex_llamacpp>

Official QAIRT documentation:
<https://docs.qualcomm.com/bundle/publicresource/topics/80-70017-15/introduction.html>

Installed primary documentation:

```text
C:\Qualcomm\AIStack\QAIRT\2.47.1.260610\docs\QAIRT-Docs\Genie\index.html
```

## Saved Host Artifacts

Persistent GenieX data directory:

```text
C:\Users\sreddygu\.cache\geniex-iq9
```

Model directory:

```text
C:\Users\sreddygu\.cache\geniex-iq9\models\qualcomm\Gemma-4-E4B-it
```

Verified state:

```text
chipset: Dragonwing IQ-9075 EVK
model: qualcomm/Gemma-4-E4B-it
precision: W4A16
files: 18
size: 9.23 GiB
```

Verification commands:

```powershell
$data = "$HOME\.cache\geniex-iq9"
geniex --data-dir $data config list
geniex --data-dir $data list
```

Do not repeat the download.

## Package Configuration

`htp_backend_ext_config.json` is target-specific:

```json
{
  "devices": [
    {
      "soc_model": 77,
      "dsp_arch": "v73",
      "cores": [
        {
          "core_id": 0,
          "perf_profile": "burst",
          "rpc_control_latency": 100
        }
      ]
    }
  ],
  "memory": {"mem_type": "shared_buffer"},
  "context": {"weight_sharing_enabled": true}
}
```

The text-generation Genie configuration references:

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

GenieX treats this package as a VLM bundle and uses `vision_encoder.bin` as its
entry model file, including for text-only requests. Keep all 18 package files in
the GenieX model cache.

## IQ9 Inventory

The last successful device inspection reported:

```text
hostname: iq-9075-evk
OS: Qualcomm Linux Reference Distro 2.0
kernel: 6.18.21
architecture: aarch64
Python: 3.14.4
memory: 33 GiB total, approximately 32 GiB available
storage: approximately 91 GiB available under /opt
```

QAIRT state:

```text
/opt/qnn/lib/libGenie.so exists
/opt/qnn/bin/genie-t2t-run is missing
HTP v73 DSP skeletons exist under /opt/qnn/dsp
HTP v73 host stubs exist under /opt/qnn/lib
```

No files were found under `/opt/aura-llm/gemma4-genie` during the inventory.

## Working IQ9 Deployment

The official GenieX Linux ARM64 runtime is installed at:

```text
/opt/geniex
/usr/local/bin/geniex
```

Verified versions:

```text
GenieX CLI: v0.7.0
Bundled QAIRT runtime: 2.45
Detected HTP architecture: v73
```

The active cache is:

```text
/opt/geniex-data
/opt/geniex-data/models/qualcomm/Gemma-4-E4B-it
```

Large model files in that cache are symlinked to `/opt/aura-gemma4-iq9` to
avoid a second 9.2 GiB copy. The missing package metadata and
`vision_encoder.bin` were copied into the cache. GenieX reports:

```text
qualcomm/Gemma-4-E4B-it  9.2 GiB  W4A16
```

The older `/opt/qnn/bin/genie-t2t-run` path is not compatible with this bundle.
It fails on the required `perlayer-embedding` configuration. GenieX's QAIRT
plugin implements the 10,752-dimension per-layer LUT used by Gemma 4.

## Run Direct Inference

```bash
/usr/local/bin/geniex \
  --data-dir /opt/geniex-data \
  --skip-update \
  infer 'qualcomm/Gemma-4-E4B-it:W4A16' \
  --prompt 'Reply with exactly IQ9_OK.' \
  --max-tokens 16
```

The verified run detected HTP v73 and generated on the NPU at approximately
8.8 tokens/second.

## Run the OpenAI Server

Use the saved launcher:

```bash
deploy/iq9/start_geniex_server.sh
```

Or run GenieX directly:

```bash
/usr/local/bin/geniex \
  --data-dir /opt/geniex-data \
  --skip-update \
  serve \
  --host 0.0.0.0:18181
```

For loopback-only access, replace `0.0.0.0:18181` with `127.0.0.1:18181`.

Verify the server:

```bash
curl http://127.0.0.1:18181/v1/models
curl http://127.0.0.1:18181/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "qualcomm/Gemma-4-E4B-it:W4A16",
    "messages": [{"role": "user", "content": "Reply with exactly OK."}],
    "max_tokens": 16,
    "temperature": 0
  }'
```

The native server applies Gemma 4's chat template itself. Do not render ChatML
or Gemma control tokens in AURA before sending the OpenAI `messages` array.

## Connect AURA

Set:

```text
AURA_LLM_BASE_URL=http://192.168.29.185:18181
AURA_LLM_MODEL=qualcomm/Gemma-4-E4B-it:W4A16
AURA_LLM_NO_THINK=false
```

`aura.agent.llm.LocalLLM` was verified directly against this endpoint and
returned `AURA_CLIENT_OK`. `aura.agent.genie_server` remains available for old
QAIRT bundles that only expose `genie-t2t-run`; it is not needed for this IQ9
GenieX deployment.

## Resume Checks

```bash
/usr/local/bin/geniex --version
/usr/local/bin/geniex --data-dir /opt/geniex-data --skip-update config list
/usr/local/bin/geniex --data-dir /opt/geniex-data --skip-update list
curl http://127.0.0.1:18181/v1/models
```

If the server is not running, launch it with
`deploy/iq9/start_geniex_server.sh`. If inference fails, capture
`/tmp/geniex-server.log` and:

```bash
dmesg | grep -Ei 'htp|adsprpc|fastrpc|qnn' | tail -200
```

## Completed Host Commands

```powershell
$data = "$HOME\.cache\geniex-iq9"
geniex --data-dir $data config set chipset "Dragonwing IQ-9075 EVK"
geniex --data-dir $data pull `
  "qualcomm/Gemma-4-E4B-it:W4A16" `
  --model-hub aihub `
  --model-type vlm
```

## Safety

- Do not store device passwords in scripts, notes, shell history, or repository
  files.
- Prefer SSH keys or retrieve credentials from a password manager.
- Keep the OpenAI-compatible Genie endpoint bound to `127.0.0.1` unless a
  separately authenticated transport is required.
