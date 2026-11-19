# Author: Srinivas Reddy Gudala
# Email: sreddygu@qti.qualcomm.com
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
from pathlib import Path

from aura import __version__
from aura.config import load_settings
from aura.memory.store import MemoryStore


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="aura",
        description="AURA - Autonomous Understanding & Responsive Agent",
    )
    parser.add_argument("--version", action="version", version=f"aura {__version__}")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("config", help="print the resolved AURA_* settings")
    run = sub.add_parser("run", help="start the perceive-to-remember loop")
    run.add_argument("--location", default=None)
    ask = sub.add_parser("ask", help="[Milestone 4] ask a question about observed events")
    ask.add_argument("question", nargs="+", help="natural-language question")
    dashboard = sub.add_parser("dashboard", help="launch the FastAPI dashboard")
    dashboard.add_argument("--host", default=None)
    dashboard.add_argument("--port", type=int, default=None)
    sub.add_parser("health", help="check local storage and LLM configuration")
    learn = sub.add_parser("learn", help="index Markdown/text knowledge")
    learn.add_argument("path", nargs="?", default="docs")
    observe = sub.add_parser("observe", help="capture one frame and store detections")
    observe.add_argument("source", nargs="?", default=None)
    observe.add_argument("--location", default=None)
    sub.add_parser("demo", help="run the offline memory demo")

    args = parser.parse_args(argv)

    if args.command == "config":
        settings = load_settings()
        for k, v in vars(settings).items():
            print(f"AURA_{k.upper()}={v}")
        return 0

    if args.command == "health":
        settings = load_settings()
        checks = {"config": True, "database": False, "llm_endpoint": bool(settings.llm_base_url)}
        try:
            with MemoryStore(settings.db_path).connect():
                checks["database"] = True
        except Exception as exc:  # noqa: BLE001
            print(f"database: failed ({exc})", file=sys.stderr)
        for name, ok in checks.items():
            print(f"{name}: {'ok' if ok else 'not ready'}")
        return 0 if all(checks.values()) else 1

    if args.command == "run":
        from aura.core.pipeline import AuraPipeline
        from aura.vision.camera import Camera
        from aura.vision.detector import Detector
        settings = load_settings()
        detector = Detector(settings.yolo_model).load()
        with MemoryStore(settings.db_path).connect() as memory:
            with Camera(settings.camera) as camera:
                AuraPipeline(detector=detector, memory=memory).run(camera, location=args.location)
        return 0

    if args.command == "ask":
        from aura.agent.llm import LocalLLM
        settings = load_settings()
        question = " ".join(args.question)
        with MemoryStore(settings.db_path).connect() as memory:
            llm = LocalLLM(settings.llm_base_url, model=settings.llm_model,
                           no_think=settings.llm_no_think)
            print(llm.answer(question, memory.recall_context(question)))
        return 0

    if args.command == "learn":
        settings = load_settings()
        target = Path(args.path)
        files = [target] if target.is_file() else sorted(target.rglob("*.md"))
        if not files:
            print(f"No Markdown files found under {target}", file=sys.stderr)
            return 1
        with MemoryStore(settings.db_path).connect() as memory:
            total = 0
            for file in files:
                source = str(file).replace("\\", "/")
                total += memory.add_document(source, file.read_text(encoding="utf-8"))
        print(f"Indexed {total} knowledge chunks from {len(files)} file(s)")
        return 0

    if args.command == "observe":
        from aura.core.pipeline import AuraPipeline
        from aura.vision.camera import Camera
        from aura.vision.detector import Detector
        settings = load_settings()
        source = args.source or settings.camera
        detector = Detector(settings.yolo_model).load()
        with MemoryStore(settings.db_path).connect() as memory:
            with Camera(source, max_frames=1) as camera:
                pipeline = AuraPipeline(detector=detector, memory=memory)
                for frame in camera.frames():
                    for event in pipeline.perceive(frame, location=args.location):
                        print(event.to_json())
        return 0

    if args.command == "dashboard":
        import uvicorn

        from aura.agent.llm import LocalLLM
        from aura.dashboard.api import create_app
        settings = load_settings()
        memory = MemoryStore(settings.db_path).connect()
        llm = LocalLLM(settings.llm_base_url, model=settings.llm_model,
                       no_think=settings.llm_no_think)
        try:
            uvicorn.run(create_app(memory=memory, llm=llm),
                        host=args.host or settings.dashboard_host,
                        port=args.port or settings.dashboard_port)
        finally:
            memory.close()
        return 0

    if args.command == "demo":
        from aura.core.events import Event
        settings = load_settings()
        demo_db = Path(settings.db_path).with_name("aura_demo.db")
        demo_events = [
            Event(event="package delivered", entities=["package"], location="front door", source="vision"),
            Event(event="package left on table", entities=["package"], location="front table", source="vision"),
            Event(event="light turned off", type="action", entities=["light"], source="agent"),
        ]
        with MemoryStore(str(demo_db)).connect() as memory:
            for event in demo_events:
                memory.add_event(event)
            print(f"Stored {len(demo_events)} demo events in {demo_db}")
            for event in memory.recall("package"):
                print(event)
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
