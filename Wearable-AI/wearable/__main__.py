"""CLI: ``python -m wearable run --db wearable.db`` (needs AURA on PYTHONPATH)."""

from __future__ import annotations

import argparse
import json
import sys
import time

from aura.memory.store import MemoryStore

from .node import WearableNode
from .sensors import simulate


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="wearable")
    p.add_argument("--db", required=True, help="AURA memory db the context events are written to")
    p.add_argument("--seed", type=int, default=7)
    args = p.parse_args(argv)

    started = time.perf_counter()
    with MemoryStore(args.db).connect() as store:
        node = WearableNode(on_event=store.add_event,
                            on_burst=lambda e: print(f"BURST -> hub reasoning: {e}", flush=True))
        node.run(simulate(seed=args.seed))
    summary = node.summary()
    summary["wall_seconds"] = round(time.perf_counter() - started, 3)
    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
