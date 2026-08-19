# Author: Srinivas Reddy Gudala
# Last Updated: 2026-08-17
# Version: 1.0
#
"""Minimal ``aura`` command-line entry point.

At v0.1 this reports version/config and points at the roadmap; the subcommands
(``run``, ``ask``, ``dashboard``) are wired as their milestones land.
"""

from __future__ import annotations

import argparse
import sys

from aura import __version__
from aura.config import load_settings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="aura",
        description="AURA — Autonomous Understanding & Responsive Agent",
    )
    parser.add_argument("--version", action="version", version=f"aura {__version__}")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("config", help="print the resolved AURA_* settings")
    sub.add_parser("run", help="[Milestone 1] start the perceive→remember loop")
    ask = sub.add_parser("ask", help="[Milestone 4] ask a question about observed events")
    ask.add_argument("question", nargs="+", help="natural-language question")
    sub.add_parser("dashboard", help="launch the FastAPI dashboard")

    args = parser.parse_args(argv)

    if args.command == "config":
        settings = load_settings()
        for k, v in vars(settings).items():
            print(f"AURA_{k.upper()}={v}")
        return 0

    if args.command in {"run", "ask", "dashboard"}:
        print(
            f"`aura {args.command}` is not implemented yet at v{__version__}.\n"
            "AURA is a scaffold — see docs/ROADMAP.md for the milestone plan.",
            file=sys.stderr,
        )
        return 2

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
