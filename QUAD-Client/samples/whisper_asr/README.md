# Whisper-tiny Streaming ASR on Snapdragon X Elite

Real-time speech-to-text using Whisper-tiny with NPU-accelerated encoder
and CPU decoder on Qualcomm Snapdragon X Elite.

## Architecture

```
Microphone/WAV --> 80ms chunks --> 5s sliding window --> Mel spectrogram (CPU)
    --> Encoder (NPU INT8) --> Decoder (CPU INT8) --> Streaming text --> Console
```

| Component | Runtime | Quantization | Target |
|-----------|---------|-------------|--------|
| Mel frontend | CPU | float32 | scipy filterbank |
| Encoder | NPU (HTP) | INT8 | < 100 ms |
| Decoder | CPU | INT8 | < 80 ms/step |

## Prerequisites

- Windows 11 on Snapdragon X Elite (or any x86/ARM64 Windows for CPU-only mode)
- Python 3.10+
- QUAD platform installed (for NPU conversion/inference)
- Microphone (for live mode) or WAV/FLAC files

## Quick Start

```powershell
# 1. Install dependencies
.\run.ps1

# 2. Run with test audio (downloads models automatically)
.venv\Scripts\python.exe run_whisper_asr.py

# 3. Live microphone transcription
.venv\Scripts\python.exe run_whisper_asr.py --input none

# 4. Transcribe a specific file
.venv\Scripts\python.exe run_whisper_asr.py --input recording.wav
```

## CLI Options

| Flag | Default | Description |
|------|---------|-------------|
| `--encoder-model` | `whisper_tiny_encoder.onnx` | Path to encoder ONNX |
| `--decoder-model` | `whisper_tiny_decoder.onnx` | Path to decoder ONNX |
| `--skip-download` | false | Skip model download |
| `--output-dir` | `output` | Directory for converted models |
| `--adapter-mode` | `real` | `mock` or `real` (QUAD adapter) |
| `--warmup` | 2 | Benchmark warmup runs |
| `--runs` | 5 | Benchmark timed runs |
| `--input` | (auto) | Audio file path, or omit for microphone |
| `--max-duration` | 30.0 | Max mic recording duration (seconds) |
| `--skip-transcribe` | false | Benchmark only, no transcription |

## What It Does

1. **Downloads** Whisper-tiny encoder + decoder ONNX from Hugging Face
2. **Converts** both to INT8 QNN via QUAD MCP server
3. **Benchmarks** encoder (NPU vs CPU) and decoder (CPU)
4. **Transcribes** from microphone or audio file with streaming output

## Performance Targets

| Metric | Target | Notes |
|--------|--------|-------|
| First-word latency | < 200 ms | Encoder + first decoder step |
| Partial p95 | < 80 ms | Per-chunk decoder latency |
| Sustained power | < 4.0 W | NPU encoder + CPU decoder duty cycle |

## Troubleshooting

- **"onnxruntime not installed"**: Run `.\run.ps1` to set up dependencies
- **"sounddevice not installed"**: Already in requirements.txt; run `.\run.ps1`
- **"QNN_SDK_ROOT not set"**: Install QAIRT SDK or set the env var
- **NPU benchmark skipped**: Expected in mock mode; use `--adapter-mode real` with SDK
- **No microphone detected**: Use `--input recording.wav` for file mode
- **Garbled output**: Install `transformers` for proper Whisper detokenization:
  `.venv\Scripts\pip.exe install transformers`
