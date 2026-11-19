# Whisper-tiny Streaming ASR — Architecture

## Overview

Real-time automatic speech recognition (ASR) application that transcribes
live microphone audio or WAV files using OpenAI's Whisper-tiny model,
optimized for Qualcomm Snapdragon X Elite. The encoder runs on the NPU
(Hexagon HTP) at INT8 precision for power-efficient mel-to-latent
conversion, while the autoregressive decoder runs on CPU via onnxruntime
for low-latency token generation.

Audio arrives as 16 kHz mono PCM, buffered into 5-second sliding windows
with 80 ms hops. A simple VAD (voice activity detector) flushes segments
on 250 ms of silence, producing streaming partial and final transcripts.

## System Diagram

```
                         ┌──────────────────────────────────┐
                         │       Whisper-tiny Pipeline       │
                         └──────────────────────────────────┘

 ┌─────────┐   80 ms    ┌──────────┐   5 s     ┌───────────────┐
 │   Mic   │──chunks──>│  Audio    │─window──>│     Mel        │
 │ (16kHz) │           │  Chunker  │          │  Spectrogram   │
 └─────────┘           └──────────┘          │  (80 x 3000)  │
                        VAD flush ↓           └───────┬───────┘
                                                      │
                              ┌────────────────────────┘
                              │
                     ┌────────▼────────┐
                     │    Encoder       │
                     │  (NPU / HTP)    │  ← INT8 QNN context binary
                     │  whisper-tiny   │     45 TOPS available
                     └────────┬────────┘
                              │
                     encoder_hidden_states (1, 1500, 384)
                              │
                     ┌────────▼────────┐
                     │    Decoder       │
                     │  (CPU / ORT)    │  ← INT8, autoregressive
                     │  greedy search  │     token-by-token
                     └────────┬────────┘
                              │
                         token IDs
                              │
                     ┌────────▼────────┐
                     │  Detokenizer    │
                     │  (transformers  │
                     │   or fallback)  │
                     └────────┬────────┘
                              │
                     ┌────────▼────────┐
                     │    Console      │
                     │  [...] partial  │
                     │  [final] text   │
                     └─────────────────┘
```

## Components

| Component | File | Description | Dependencies |
|-----------|------|-------------|-------------|
| Main pipeline | `run_whisper_asr.py` | Download, convert, benchmark, transcribe | fastmcp, numpy, scipy |
| Audio chunker | `run_whisper_asr.py:AudioChunker` | 80ms hop / 5s window / VAD endpoint | (stdlib) |
| Mel spectrogram | `run_whisper_asr.py:compute_mel_spectrogram` | Log-mel matching Whisper preprocessing | scipy, numpy |
| Mel filterbank | `run_whisper_asr.py:_mel_filterbank` | Triangular mel-scale filter matrix | numpy |
| DevRel MCP client | `run_whisper_asr.py:_call_convert` | Stdio transport to DevRel MCP server | fastmcp |
| Encoder bench | `run_whisper_asr.py:step3_benchmark` | CPU vs NPU encoder comparison | onnxruntime, qnn_utils |
| Decoder bench | `run_whisper_asr.py:_bench` | CPU timing with psutil power proxy | psutil |
| Greedy decoder | `run_whisper_asr.py:_decode_greedy` | Autoregressive token generation | onnxruntime |
| Detokenizer | `run_whisper_asr.py:_detokenize` | Token IDs to text (transformers or fallback) | transformers (optional) |
| Dependencies | `requirements.txt` | All Python deps with >= pins | — |
| Bootstrapper | `run.ps1` | uv-based venv + install | uv |

## Model Card

| Property | Encoder | Decoder |
|----------|---------|---------|
| Model | whisper-tiny encoder | whisper-tiny decoder |
| Source | Hugging Face onnx-community | Hugging Face onnx-community |
| Task | Audio → latent | Latent → tokens |
| Input shape | (1, 80, 3000) | (1, seq_len) + (1, 1500, 384) |
| Output shape | (1, 1500, 384) | (1, seq_len, 51865) |
| Quantization | INT8 (QNN) | INT8 (ORT) |
| Parameters | ~20M | ~19M |
| Total size | ~39M FP32, ~10M INT8 | — |

## Data Flow

1. **Audio capture**: 16 kHz mono PCM from microphone (`sounddevice`) or WAV file
2. **Chunking**: 80 ms PCM chunks pushed into 5-second sliding window buffer
3. **VAD**: Simple amplitude threshold; 250 ms silence triggers segment flush
4. **Mel spectrogram**: 400-sample FFT, 160-sample hop, 80 mel bands, log scale
5. **Pad/trim**: Audio padded or trimmed to 30 seconds (Whisper's native window)
6. **Encoder**: Mel (1, 80, 3000) → hidden states (1, 1500, 384)
7. **Decoder**: Greedy autoregressive — SOT + lang + task tokens → text tokens
8. **Detokenize**: Token IDs → string via Whisper tokenizer
9. **Output**: Streaming `[partial]` and `[final]` lines to console

## KPIs

| Metric | CPU | NPU | Target |
|--------|-----|-----|--------|
| Encoder avg latency | ~150 ms | ~15 ms | < 100 ms |
| Decoder avg latency | ~30 ms/step | N/A (CPU) | < 80 ms/step |
| First-word latency | ~180 ms | ~45 ms | < 200 ms |
| Encoder throughput | ~7 FPS | ~65 FPS | — |
| Est. package power | ~12 W | ~4.5 W | < 4.0 W |
| NPU speedup | 1.0x | ~10x | — |

*Values are estimates for Snapdragon X Elite X1E78100. Actual performance
depends on SDK version, thermal state, and system load.*
