#!/usr/bin/env python3
"""Send VSaaS events from `data/events.db` through the SparQ chat endpoint."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import textwrap
import time
from pathlib import Path
import urllib.error

# Ensure the VSaaS package is importable when the script lives under `scripts/`.
ROOT = Path(__file__).resolve().parent.parent
# `src/` contains the `vsaas` package.
SYS_PATH_ENTRY = str(ROOT / "src")
if SYS_PATH_ENTRY not in sys.path:
    sys.path.insert(0, SYS_PATH_ENTRY)

from vsaas.llm import LlmClient  # type: ignore[attr-defined]


def load_events(db_path: Path, limit: int | None = None) -> list[dict]:
    if not db_path.exists():
        raise FileNotFoundError(f"{db_path} not found")

    with sqlite3.connect(db_path) as con:
        con.row_factory = sqlite3.Row
        if limit is None:
            query = (
                "SELECT id, ts_ms, camera_id, event_type, severity, summary, payload_json "
                "FROM events ORDER BY ts_ms DESC"
            )
            params: tuple[int, ...] = ()
        else:
            query = (
                "SELECT id, ts_ms, camera_id, event_type, severity, summary, payload_json "
                "FROM events ORDER BY ts_ms DESC LIMIT ?"
            )
            params = (limit,)
        rows = con.execute(query, params).fetchall()

    events = []
    for row in reversed(rows):
        payload: dict | list | str | None = {}
        raw_payload = row["payload_json"]
        if raw_payload:
            try:
                payload = json.loads(raw_payload)
            except json.JSONDecodeError:
                payload = raw_payload
        events.append(
            {
                "id": row["id"],
                "ts_ms": row["ts_ms"],
                "camera_id": row["camera_id"],
                "event_type": row["event_type"],
                "severity": row["severity"],
                "summary": row["summary"],
                "payload": payload,
            }
        )
    return events


def build_messages(events: list[dict], chunk_idx: int | None = None, total_chunks: int | None = None) -> list[dict[str, str]]:
    event_blob = json.dumps(events, indent=2, ensure_ascii=False)
    system = textwrap.dedent(
        """\
        You are a telemetry relay for Qualcomm VSaaS. Your job is to
        receive VSaaS events and acknowledge that you captured them.
        Do not provide analysis; simply confirm receipt in the reply.
        """
    ).strip()
    chunk_label = ""
    if chunk_idx is not None and total_chunks is not None:
        chunk_label = f"Chunk {chunk_idx}/{total_chunks}: "
    user = (
        f"{chunk_label}Here are {len(events)} VSaaS events captured on IQ8 (chronological order):\n"
        f"{event_blob}"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def pick_credentials() -> tuple[str | None, str | None]:
    api_key = (
        os.environ.get("VSAAS_LLM_API_KEY")
        or os.environ.get("QAIC_API_KEY")
        or os.environ.get("QAIHUB_API_TOKEN")
    )
    x_apikey = (
        os.environ.get("VSAAS_LLM_X_APIKEY")
        or os.environ.get("APIGEE_TOKEN")
        or os.environ.get("QAIHUB_CLI_TOKEN")
    )
    return api_key, x_apikey


def parse_extra_headers(value: str | None) -> dict[str, str] | None:
    if not value:
        return None
    try:
        payload = json.loads(value)
        if isinstance(payload, dict):
            return {str(k): str(v) for k, v in payload.items()}
    except json.JSONDecodeError as exc:
        raise argparse.ArgumentTypeError(f"invalid JSON for extra headers: {exc}") from exc
    raise argparse.ArgumentTypeError("extra headers must be a JSON object")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Send recent VSaaS events to an OpenAI-style endpoint (SparQ)."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="how many of the most recent events to include (default: all)",
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("VSAAS_LLM_BASE_URL"),
        help="OpenAI-compatible base URL (default: VSAAS_LLM_BASE_URL or "
        "https://dev.apigwx-op.qualcomm.com/aips/sparq/api/v1)",
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("VSAAS_LLM_MODEL", "qwen3_vl_32b_instruct"),
        help="model name for the chat completion",
    )
    parser.add_argument(
        "--extra-headers",
        type=parse_extra_headers,
        help="JSON string of extra headers (e.g. '{\"X-Custom\": \"value\"}')",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=50,
        help="maximum number of events per SparQ request (default: 50)",
    )
    parser.add_argument(
        "--offset",
        type=int,
        default=0,
        help="skip the first N events (chronologically) before sending chunks",
    )
    parser.add_argument(
        "--max-chars",
        type=int,
        default=5000,
        help="approximate max characters per chunk payload (default: 5000)",
    )
    parser.add_argument(
        "--rate-retries",
        type=int,
        default=3,
        help="how many retries to attempt when SparQ rate-limits (default: 3)",
    )
    parser.add_argument(
        "--rate-sleep",
        type=float,
        default=10.0,
        help="seconds to wait between rate-limit retries (default: 10)",
    )
    parser.add_argument(
        "--chunk-delay",
        type=float,
        default=0.2,
        help="seconds to wait between completed chunk uploads (default: 0.2)",
    )
    args = parser.parse_args()

    base_url = args.base_url or "https://dev.apigwx-op.qualcomm.com/aips/sparq/api/v1"
    db_path = ROOT / "data" / "events.db"
    events = load_events(db_path=db_path, limit=args.limit)
    if not events:
        print("No events found in the database.", file=sys.stderr)
        sys.exit(0)
    offset = max(0, args.offset)
    if offset >= len(events):
        print("Offset is past the available events.", file=sys.stderr)
        sys.exit(0)
    if offset:
        events = events[offset:]

    api_key, x_apikey = pick_credentials()
    if not api_key and not x_apikey:
        raise RuntimeError(
            "Missing credentials for SparQ. Set QAIC_API_KEY / VSAAS_LLM_API_KEY or "
            "APIGEE_TOKEN / VSAAS_LLM_X_APIKEY in your environment."
        )

    client = LlmClient(
        base_url=base_url,
        model=args.model,
        api_key=api_key,
        x_apikey=x_apikey,
        extra_headers=args.extra_headers,
    )

    chunk_size = max(1, args.chunk_size)
    max_chars = max(1, args.max_chars)
    chunks = []
    current: list[dict] = []
    current_chars = 0

    for event in events:
        event_chars = len(json.dumps(event, ensure_ascii=False))
        if current and (
            len(current) >= chunk_size or current_chars + event_chars > max_chars
        ):
            chunks.append(current)
            current = []
            current_chars = 0
        current.append(event)
        current_chars += event_chars
    if current:
        chunks.append(current)
    for idx, chunk in enumerate(chunks, start=1):
        print(
            f"Sending chunk {idx}/{len(chunks)} ({len(chunk)} events) to {base_url} (model={args.model})..."
        )
        messages = build_messages(chunk, chunk_idx=idx, total_chunks=len(chunks))
        attempt = 0
        while True:
            try:
                reply = client.chat_messages(messages=messages, temperature=0.0, max_tokens=256)
                break
            except urllib.error.HTTPError as exc:
                body = exc.read().decode("utf-8", errors="replace")
                print("SparQ returned HTTP Error:", exc.code, exc.reason, file=sys.stderr)
                print("Response body:", body, file=sys.stderr)
                if exc.code == 429 and attempt < args.rate_retries:
                    attempt += 1
                    print(
                        f"Rate limited; retrying in {args.rate_sleep} seconds (attempt {attempt}/{args.rate_retries})...",
                        file=sys.stderr,
                    )
                    time.sleep(args.rate_sleep)
                    continue
                raise
        print("SparQ reply:")
        print(reply)
        if args.chunk_delay and chunk != chunks[-1]:
            time.sleep(args.chunk_delay)


if __name__ == "__main__":
    main()
