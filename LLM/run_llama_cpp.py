from __future__ import annotations

import argparse
import os
import shlex
import subprocess
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run GGUF LLM inference via llama.cpp (llama-cli or llama-server).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--llama-cpp-dir",
        type=Path,
        default=Path(os.getenv("LLAMA_CPP_DIR", "~/llama.cpp")).expanduser(),
        help="Path to llama.cpp checkout (expects build/bin/*).",
    )
    parser.add_argument(
        "--model",
        type=Path,
        default=Path(os.getenv("LLM_GGUF", "models/gemma-4-12b-it-qat-q4_0.gguf")),
        help="Path to GGUF model file (relative to CWD or absolute).",
    )
    parser.add_argument("--prompt", default="Say hello in one sentence.", help="Prompt text.")
    parser.add_argument("--n-predict", type=int, default=128, help="Tokens to generate.")
    parser.add_argument(
        "--ctx-size",
        "--ctx",
        dest="ctx_size",
        type=int,
        default=512,
        help="Context length.",
    )
    parser.add_argument("--threads", type=int, default=0, help="CPU threads (0 = llama.cpp default).")
    parser.add_argument("--temp", type=float, default=0.7, help="Sampling temperature.")
    parser.add_argument("--top-p", type=float, default=0.95, help="Nucleus sampling top-p.")
    parser.add_argument(
        "--single-turn",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Exit after one response (llama-cli only).",
    )
    parser.add_argument(
        "--server",
        action="store_true",
        help="Run llama-server instead of llama-cli (serves HTTP on --host/--port).",
    )
    parser.add_argument("--host", default="127.0.0.1", help="llama-server bind host.")
    parser.add_argument("--port", type=int, default=8080, help="llama-server bind port.")
    parser.add_argument(
        "--extra",
        default="",
        help="Extra raw args passed to llama.cpp binary (string, appended as-is).",
    )
    return parser.parse_args()


def _resolve_bin(llama_cpp_dir: Path, *, server: bool) -> Path:
    candidates = [
        llama_cpp_dir / "build" / "bin" / ("llama-server" if server else "llama-cli"),
        llama_cpp_dir / "build" / ("llama-server" if server else "llama-cli"),
    ]
    for c in candidates:
        if c.exists():
            return c
    raise FileNotFoundError(
        f"Could not find llama.cpp binary under {llama_cpp_dir} (tried: {', '.join(str(x) for x in candidates)})"
    )


def main() -> None:
    args = parse_args()
    bin_path = _resolve_bin(args.llama_cpp_dir, server=bool(args.server))

    model_path = args.model
    if not model_path.is_absolute():
        model_path = (Path.cwd() / model_path).resolve()
    if not model_path.exists():
        raise FileNotFoundError(f"Missing GGUF model: {model_path}")

    cmd: list[str] = [str(bin_path), "-m", str(model_path), "-c", str(int(args.ctx_size))]
    if int(args.threads) > 0:
        cmd += ["-t", str(int(args.threads))]

    if args.server:
        cmd += ["--host", str(args.host), "--port", str(int(args.port))]
    else:
        cmd += [
            "-p",
            str(args.prompt),
            "-n",
            str(int(args.n_predict)),
            "--temp",
            str(float(args.temp)),
            "--top-p",
            str(float(args.top_p)),
        ]
        if bool(args.single_turn):
            cmd.append("--single-turn")

    if str(args.extra).strip():
        cmd += shlex.split(str(args.extra))

    print("Running:", " ".join(shlex.quote(x) for x in cmd))
    subprocess.check_call(cmd)


if __name__ == "__main__":
    main()
