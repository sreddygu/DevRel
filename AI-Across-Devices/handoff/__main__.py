"""CLI: ``python -m handoff serve|pull``. The token is read from HANDOFF_TOKEN, never argv."""

from __future__ import annotations

import argparse
import json
import os
import sys

from aura.memory.store import MemoryStore

from .ask import ask
from .transport import catch_up, make_server


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="handoff")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("serve", help="serve this node's memory (hub)")
    s.add_argument("--db", required=True)
    s.add_argument("--host", default="127.0.0.1", help="default loopback; use an SSH tunnel")
    s.add_argument("--port", type=int, default=8765)
    g = sub.add_parser("pull", help="pull a hub's context into this node")
    g.add_argument("--db", required=True)
    g.add_argument("--url", required=True)
    g.add_argument("--since")
    a = sub.add_parser("ask", help="answer a question from the local store with an OpenAI-compatible model")
    a.add_argument("--db", required=True)
    a.add_argument("--base-url", required=True, help="e.g. http://127.0.0.1:11434/v1")
    a.add_argument("--model", required=True)
    a.add_argument("--since")
    a.add_argument("question")
    args = p.parse_args(argv)

    if args.cmd == "ask":  # no handoff token needed: purely local store + model endpoint
        with MemoryStore(args.db).connect() as store:
            print(json.dumps(ask(args.question, store, base_url=args.base_url, model=args.model, since=args.since)))
        return 0

    token = os.environ.get("HANDOFF_TOKEN", "")
    if not token:
        print("set HANDOFF_TOKEN", file=sys.stderr)
        return 2
    if args.cmd == "serve":
        server = make_server(args.db, token, host=args.host, port=args.port)
        print(f"serving on {args.host}:{args.port}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        return 0
    with MemoryStore(args.db).connect() as store:
        print(json.dumps(catch_up(store, args.url, token, since=args.since)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
