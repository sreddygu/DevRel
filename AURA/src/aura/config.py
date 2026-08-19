# Author: Srinivas Reddy Gudala
# Last Updated: 2026-08-17
# Version: 1.0
#
"""Runtime configuration for AURA, loaded from environment / ``.env``.

Values mirror the keys in ``.env.example``. Loading is dependency-free: we
read ``os.environ`` and, if present, a local ``.env`` file (simple ``KEY=VALUE``
parser — no python-dotenv requirement, so this imports on a bare interpreter).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, fields
from pathlib import Path


def _load_dotenv(path: str | os.PathLike = ".env") -> None:
    """Populate ``os.environ`` from a ``.env`` file if it exists.

    Existing environment variables win over the file. Lines that are blank or
    start with ``#`` are ignored. Intentionally minimal.
    """
    p = Path(path)
    if not p.is_file():
        return
    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


@dataclass
class Settings:
    """Typed view over the ``AURA_*`` environment variables."""

    board_host: str = ""
    board_user: str = ""
    db_path: str = "./aura.db"
    vector_dir: str = "./.chroma"
    llm_base_url: str = "http://127.0.0.1:8080"
    llm_model: str = "gemma-2-2b-it"
    llm_no_think: bool = False
    camera: str = "0"
    yolo_model: str = "./models/yolov8n.onnx"
    whisper_model: str = "base"
    tts_voice: str = "EN-default"
    dashboard_host: str = "127.0.0.1"
    dashboard_port: int = 8000

    @classmethod
    def load(cls, *, dotenv: bool = True) -> Settings:
        """Build Settings from the environment (optionally loading ``.env``)."""
        if dotenv:
            _load_dotenv()

        def env(name: str, default: str) -> str:
            return os.environ.get(f"AURA_{name.upper()}", default)

        values: dict = {}
        for f in fields(cls):
            raw = env(f.name, str(f.default))
            if f.type == "int":
                values[f.name] = int(raw)
            elif f.type == "bool":
                values[f.name] = str(raw).strip().lower() in {"1", "true", "yes", "on"}
            else:
                values[f.name] = raw
        return cls(**values)


def load_settings() -> Settings:
    """Convenience wrapper — :meth:`Settings.load`."""
    return Settings.load()
