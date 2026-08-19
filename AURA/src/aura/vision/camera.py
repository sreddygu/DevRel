# Author: Srinivas Reddy Gudala
# Last Updated: 2026-08-17
# Version: 1.0
#
"""Camera frame source (Milestone 1).

Wraps a webcam / CSI camera / RTSP stream as an iterator of frames. Backed by
OpenCV (or GStreamer on the VENTUNO Q). ``cv2`` is imported lazily so this
module imports without the ``vision`` extra installed.

For hardware-free testing there is also an *image mode*: point :class:`Camera`
at a single image file or a directory of images and it yields those as frames.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from typing import Any

_IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".bmp", ".webp")


class Camera:
    """A frame source identified by an index (``0``), device path, or URL.

    Example::

        with Camera(0) as cam:
            for frame in cam.frames():
                ...

    ``source`` may be:

    - an ``int`` (or digit string) — a webcam / capture index;
    - an RTSP/HTTP URL — a network stream;
    - a path to an image file or a directory of images — *image mode*, which
      needs no camera and is handy for tests and demos.

    Args:
        source: Frame source (see above).
        max_frames: Optional cap on how many frames :meth:`frames` yields
            (``None`` = unbounded for live sources).
    """

    def __init__(self, source: int | str = 0, *, max_frames: int | None = None) -> None:
        self.source = source
        self.max_frames = max_frames
        self._capture: Any = None
        self._images: list[str] | None = None  # populated in image mode

    # -- mode detection -----------------------------------------------------
    def _image_paths(self) -> list[str] | None:
        """Return a sorted list of image paths if ``source`` is image mode, else None."""
        src = self.source
        if isinstance(src, int) or (isinstance(src, str) and src.isdigit()):
            return None
        if isinstance(src, str):
            if os.path.isdir(src):
                files = [
                    os.path.join(src, f)
                    for f in sorted(os.listdir(src))
                    if f.lower().endswith(_IMAGE_EXTS)
                ]
                return files
            if os.path.isfile(src) and src.lower().endswith(_IMAGE_EXTS):
                return [src]
        return None

    def open(self) -> Camera:
        """Open the underlying capture device (or prepare image mode)."""
        images = self._image_paths()
        if images is not None:
            if not images:
                raise FileNotFoundError(f"No images found for source: {self.source!r}")
            self._images = images
            return self

        import cv2  # noqa: PLC0415 — lazy heavy import

        src: int | str = int(self.source) if str(self.source).isdigit() else self.source
        cap = cv2.VideoCapture(src)
        if not cap.isOpened():
            raise RuntimeError(f"Could not open camera source: {self.source!r}")
        self._capture = cap
        return self

    def read(self):
        """Grab a single frame as an ``np.ndarray`` (BGR), or ``None`` if exhausted."""
        if self._images is not None:
            import numpy as np  # noqa: PLC0415

            if not self._images:
                return None
            path = self._images.pop(0)
            try:
                import cv2  # noqa: PLC0415

                return cv2.imread(path)
            except Exception:  # pragma: no cover — cv2-less fallback via PIL
                from PIL import Image  # noqa: PLC0415

                return np.asarray(Image.open(path).convert("RGB"))[:, :, ::-1]

        if self._capture is None:
            self.open()
        ok, frame = self._capture.read()
        return frame if ok else None

    def frames(self) -> Iterator[Any]:
        """Yield frames continuously until the source is exhausted/closed."""
        if self._capture is None and self._images is None:
            self.open()
        count = 0
        while True:
            if self.max_frames is not None and count >= self.max_frames:
                return
            frame = self.read()
            if frame is None:
                return
            count += 1
            yield frame

    def close(self) -> None:
        """Release the capture device."""
        if self._capture is not None:
            try:
                self._capture.release()
            except Exception:  # pragma: no cover
                pass
            self._capture = None
        self._images = None

    def __enter__(self) -> Camera:
        return self.open()

    def __exit__(self, *exc: object) -> None:
        self.close()
