# AURA on the Qualcomm NPU (IQ8 / VENTUNO Q) — Bring-up Runbook

AURA's `LocalLLM` speaks the OpenAI `/v1/chat/completions` protocol, but Genie
(QAIRT) ships only CLI runners — no HTTP server. `aura.agent.genie_server`
bridges the two: a stdlib-only shim that renders chat messages to the model's
ChatML prompt, runs `genie-t2t-run` on the NPU, and returns an OpenAI response.

This runbook covers pushing the runtime + a model bundle + the shim onto the
device and pointing AURA at it. The shim itself is already built and tested on
the PC (`tests/test_genie_server.py`); the steps below are the **hardware**
part, which needs a device and is done in a live session.

## Target device (verified 2026-08-06)

- **IQ8 EVK** `iq-8275-evk` @ `<device-ip>` (root / password; plink hostkey
  `<host-key>`, the SHA256 fingerprint shown on first connect).
- Qualcomm Linux Reference Distro **2.0**, aarch64, 8 cores, 10 GiB RAM.
- NPU: **HTP v75**, `/dev/fastrpc-cdsp` present. QNN libs already in `/opt/qnn`
  (incl. `libGenie.so`, `libQnnGenAiTransformer.so`, `libQnnHtpV75*.so`), but
  only `qnn-net-run` / `qnn-profile-viewer` binaries — **no Genie LLM runner**.
- Bare Python 3.14, **no pip / no dnf repos / no compiler**. Direct internet OK.

## SDK source (on the PC)

`C:\Qualcomm\AIStack\QAIRT\2.47.1.260610` — use the **`aarch64-oe-linux-gcc11.2`**
target (matches the QLI 2.0 ABI):

- `bin/aarch64-oe-linux-gcc11.2/genie-t2t-run`
- `lib/aarch64-oe-linux-gcc11.2/lib*.so` (incl. `libGenie.so`, `libQnnHtp*.so`,
  `libQnnGenAiTransformer*.so`)
- `lib/hexagon-v75/unsigned/libQnnHtpV75Skel.so`, `libQairtHtpV75Skel.so`

## ⚠️ Blocker: model bundle must be re-exported for v75

The ready bundle at `C:\genie_bundle\qwen3_4b_instruct_2507-genie-w4a16-…x_elite`
loads via **`ctx-bins`** (pre-compiled HTP context binaries) targeting
`soc_model 60 / dsp_arch v73` (X Elite), QAIRT 2.45. **Context binaries are
locked to the HTP arch** — they will *not* load on the IQ8's v75. A fresh v75
export is required first. Options:

1. **Qualcomm AI Hub** — export Qwen3-4B (or Gemma3-4B) for the IQ8 / QCS8275
   (v75) target; download the resulting Genie bundle.
2. **Local re-generation** — with the source DLC/graph, run
   `qnn-context-binary-generator` against the v75 backend
   (`libQnnHtpV75.so` + `htp_backend_ext_config.json` set to the QCS8275 SoC id
   and `dsp_arch: v75`).

Confirm `htp_backend_ext_config.json` in the new bundle reads roughly:
`{"devices":[{"dsp_arch":"v75", "soc_model":<QCS8275 id>, ...}]}`.

## Steps (once a v75 bundle exists)

1. **Push runtime + shim + bundle** to the device (`scp`/`pscp`):
   ```
   /opt/aura-llm/
     genie-t2t-run                # from bin/aarch64-oe-linux-gcc11.2
     lib/*.so                     # aarch64-oe libs
     hexagon-v75/*Skel.so
     bundle/                      # v75 model: *.bin, genie_config.json,
                                  #   tokenizer.json, text-generator.json, …
   ```
   Copy `src/aura/agent/genie_server.py` to the device too (or `pip`-less: just
   scp the single file).

2. **Set the library path** so Genie finds its .so's and the v75 skel:
   ```sh
   export LD_LIBRARY_PATH=/opt/aura-llm/lib:$LD_LIBRARY_PATH
   export ADSP_LIBRARY_PATH=/opt/aura-llm/hexagon-v75
   ```

3. **Smoke-test the CLI first** (prove the NPU generates before adding HTTP):
   ```sh
   cd /opt/aura-llm/bundle
   /opt/aura-llm/genie-t2t-run -c genie_config.json -p "$(cat sample_prompt.txt)"
   ```
   Expect a `[BEGIN]: … [END]` completion. If it errors on the HTP context,
   the bundle is still arch-mismatched — go back to the export step.

4. **Start the shim:**
   ```sh
   python3 genie_server.py \
     --genie-bin /opt/aura-llm/genie-t2t-run \
     --genie-config /opt/aura-llm/bundle/genie_config.json \
     --host 0.0.0.0 --port 8080 --model qwen3-4b-npu
   ```

5. **Point AURA at it** (on the PC or on-device), then run the demo:
   ```sh
   export AURA_LLM_BASE_URL=http://<device-ip>:8080
   export AURA_LLM_MODEL=qwen3-4b-npu
   python examples/ask_demo.py
   ```
   Expect a real, NPU-generated summary + grounded answers over the stored
   Events — the Milestone 4 definition of done, on Qualcomm silicon.

## Notes

- The shim is one request → one `genie-t2t-run` process (no persistent context
  / KV reuse across requests). Fine for AURA's ask/summarize cadence; a
  persistent-process design is a later optimization. Because each request
  reloads the model, the first token can take a minute+ — `LocalLLM`'s default
  timeout is 300s for this reason.
- Prefer a smaller model (Gemma3-1B/4B) if Qwen3-4B is slow on the IQ8's NPU.
- Related PC-side context: the X Elite host already has a working Qwen3-4B NPU
  path (v73) — useful for a PC-hosted fallback endpoint while the v75 export is
  sorted.

## ✅ Verified working: PC (X Elite / v73) NPU run — 2026-08-06

The full AURA → shim → NPU path was validated on the **X Elite PC** (HTP v73),
which matches the existing `C:\genie_bundle\qwen3_4b…x_elite` bundle:

```sh
Q="/c/Qualcomm/AIStack/QAIRT/2.47.1.260610"
D="/c/genie_bundle/qwen3_4b_instruct_2507-genie-w4a16-qualcomm_snapdragon_x_elite"
export PATH="$Q/lib/aarch64-windows-msvc:$Q/bin/aarch64-windows-msvc:$PATH"
export ADSP_LIBRARY_PATH="$Q/lib/hexagon-v73/unsigned"   # <-- required, or load fails
python -m aura.agent.genie_server \
  --genie-bin genie-t2t-run.exe --genie-config "$D/genie_config.json" \
  --host 127.0.0.1 --port 8080 --model qwen3-4b-npu --timeout 600
# then:
AURA_LLM_BASE_URL=http://127.0.0.1:8080 AURA_LLM_MODEL=qwen3-4b-npu \
  python examples/ask_demo.py
```

Result — real NPU-generated, grounded answers (e.g. *"The package is on the
front table."*). Key gotcha: **`ADSP_LIBRARY_PATH` must point at the matching
`hexagon-v<arch>/unsigned` skel dir**, and the model load takes ~1 min per
cold request.

> **IQ8 (v75) is still pending** the v75 bundle — see the blocker above. Local
> AI Hub export needs **AIMET-ONNX (x86_64-only)**; this host is ARM64, so the
> v75 export must run on an x86_64 Linux machine.

## ✅ Alternative NPU path: GenieX CLI (no `genie_server` shim needed) — 2026-08-07

`GenieX CLI` (v0.3.14 tested) ships its own QAIRT 2.45 runtime **and a
llama.cpp Hexagon backend** — and, crucially,
its `serve` command already exposes an **OpenAI-compatible server**, so AURA's
`LocalLLM` can point straight at it with no `genie_server` shim.

```sh
export GENIEX_HOME="/c/Path/To/GenieX CLI"
cd "$GENIEX_HOME"
./geniex.exe serve --skip-update            # -> http://127.0.0.1:18181/
# then, from the AURA repo:
AURA_LLM_BASE_URL=http://127.0.0.1:18181 AURA_LLM_MODEL=qualcomm/Qwen3-8B \
  AURA_LLM_NO_THINK=true \
  ./.venv/Scripts/python.exe examples/ask_demo.py
```

Verified: `/v1/models` + `/v1/chat/completions` respond, and `ask_demo.py`
produced a correct grounded summary and "what happened while I was gone?"
answer on the PC NPU.

**Gotchas:**

- **Model id must be the bare name** `qualcomm/Qwen3-8B`. The `:W4A16` suffix
  that `geniex list` / `/v1/models` report back triggers
  `SDKError … quantization 'W4A16' not found`. Use the name without precision.
- **Disable thinking via `AURA_LLM_NO_THINK=true`.** Qwen3 defaults to reasoning
  mode; over HTTP neither `think:false` nor `chat_template_kwargs.enable_thinking`
  is honored, and long questions loop until `max_tokens`. `LocalLLM(no_think=True)`
  appends `/no_think` to the prompt (CLI equivalent: `--think=false`) and always
  strips any `<think>…</think>` block from the reply — turning a spiralling
  ~800-token answer into a crisp one-liner.
- **Still v73, not v75.** The cached `qualcomm/Qwen3-8B` is a QAIRT ctx-bins
  bundle with `htp_backend_ext_config.json` = `soc_model 60 / dsp_arch v73` —
  the same X-Elite arch lock, so this validated the PC again, **not** the IQ8.
  The real IQ8 lever is GenieX's bundled **llama.cpp** backend
  (`llama_cpp/ggml-hexagon.dll` + `libggml-htp-v75.so`, arch v68–v81): GGUF is
  not arch-locked, so a GGUF model run with `-c npu` should target v75. Untested
  next step — pull a GGUF LLM and run `geniex serve` on the IQ8 itself.

---

## Vision & Speech on the IQ8 — see `IQ8_DEPLOYMENT.md`

Milestones 1 (Eyes, on the **Hexagon NPU** via `qnn-net-run` + YOLOv8 DLC) and
2 (Ears/Voice, whisper.cpp + piper) are **verified on-device (2026-08-11)** and
documented separately in [`IQ8_DEPLOYMENT.md`](IQ8_DEPLOYMENT.md), with the
reproducible driver scripts under [`deploy/iq8/`](../deploy/iq8/). This file
tracks the remaining **LLM/Brain** NPU bring-up above.
