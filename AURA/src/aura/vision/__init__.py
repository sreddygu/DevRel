# Author: Srinivas Reddy Gudala
# Last Updated: 2026-08-17
# Version: 1.0
#
"""👁️ Vision — cameras + YOLO/VLM → Events (Milestone 1, "Eyes").

Turns camera frames into :class:`aura.core.events.Event` records:

    camera ─▶ Detector (YOLO ONNX) ─▶ scene description ─▶ Event

Heavy deps (``opencv-python``, ``onnxruntime``) are declared in the ``vision``
optional-dependency group and imported lazily inside methods, so importing
this package never requires them.
"""

from __future__ import annotations

from aura.vision.camera import Camera
from aura.vision.detector import Detection, Detector

__all__ = ["Camera", "Detector", "Detection"]
