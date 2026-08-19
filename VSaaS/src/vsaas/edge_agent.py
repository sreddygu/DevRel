"""
VSaaS Edge Agent (prototype).

Two modes:
- `simulate`: emit synthetic events periodically
- `camera`: capture short clips from a video source and emit metadata events
- `camera` (optional edge AI): run detection/tracking/zones/PPE on-device and emit events (see `VSAAS_ENABLE_EDGE_AI`)

The agent posts events to the Cloud API `/events` endpoint. In camera mode it
writes clips to `VSAAS_RECORD_DIR` and includes the local `clip_path` in the
event payload. It does not upload video bytes.

Configuration (environment variables):
- `VSAAS_CLOUD_BASE_URL` (default: `http://127.0.0.1:9000`)
- `VSAAS_CAMERA_ID` (default: `iq8_cam_01`)
- `VSAAS_EMIT_INTERVAL_SEC` (default: `2.0` simulate, `5.0` via scripts)
- `VSAAS_VIDEO_SOURCE` (required for camera mode): `/dev/videoX` or `rtsp://...`
- `VSAAS_RECORD_DIR` (default: `data/recordings`)
- `VSAAS_CLIP_SECONDS` (default: `3.0`)
"""

from __future__ import annotations

import argparse
import json
import os
import random
import subprocess
import time
import urllib.request
import uuid

from .edge_vision import Detection, SimpleTracker, choose_detector, choose_ppe_checker, load_zones_from_env

EVENT_TYPES = [
    "objects_detected",
    "person_detected",
    "zone_entry",
    "dwell_time",
    "anomaly_motion",
    "ppe_violation",
]
SEVERITIES = ["low", "medium", "high"]


def post_events(base_url: str, events: list[dict]) -> None:
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/events",
        data=json.dumps({"events": events}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        r.read()


def _is_qmmf_source(source: str) -> bool:
    return source.strip().lower().startswith("qmmf://")


def _run_gst_qmmf_capture_clip(out_path: str, seconds: float) -> None:
    # Use timeout -s INT so -e can finalize MP4 cleanly. timeout returns 124 on timeout, which is expected.
    cmd = [
        "timeout", "-s", "INT", str(max(2, int(seconds) + 2)),
        "gst-launch-1.0", "-e",
        "qtiqmmfsrc", "name=qmmf",
        "qmmf.video_0", "!", "video/x-raw,format=NV12,width=1280,height=720,framerate=30/1", "!",
        "videoconvert", "!",
        "x264enc", "speed-preset=veryfast", "tune=zerolatency", "key-int-max=30", "bitrate=1200", "!",
        "h264parse", "!", "mp4mux", "!", f"filesink", f"location={out_path}", "sync=false",
    ]
    subprocess.run(cmd, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _run_gst_qmmf_capture_frame(out_path: str) -> None:
    # Capture a single JPEG frame from CSI via QMMF.
    cmd = [
        "timeout", "-s", "INT", "6",
        "gst-launch-1.0", "-e",
        "qtiqmmfsrc", "name=qmmf",
        "qmmf.video_0", "!", "video/x-raw,format=NV12,width=1280,height=720,framerate=30/1", "!",
        "videoconvert", "!", "jpegenc", "!", f"filesink", f"location={out_path}", "sync=false",
    ]
    subprocess.run(cmd, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _run_ffmpeg_capture(source: str, out_path: str, seconds: float) -> None:
    """Capture a short clip via ffmpeg."""
    if _is_qmmf_source(source):
        _run_gst_qmmf_capture_clip(out_path=out_path, seconds=seconds)
        # Treat as success if output exists and is non-empty.
        if not (os.path.exists(out_path) and os.path.getsize(out_path) > 0):
            raise subprocess.CalledProcessError(returncode=1, cmd=["gst-launch-1.0"], output=b"", stderr=b"")
        return

    cmd: list[str] = ["ffmpeg", "-y"]

    if source.startswith("rtsp://"):
        cmd += ["-rtsp_transport", "tcp", "-i", source]
    elif source.startswith("/dev/video"):
        if os.access(source, os.R_OK | os.W_OK):
            cmd = ["ffmpeg", "-y"]
        else:
            cmd = ["sudo", "-n", "ffmpeg", "-y"]
        cmd += ["-f", "v4l2", "-i", source]
    else:
        cmd += ["-i", source]

    cmd += [
        "-t",
        str(seconds),
        "-vf",
        "scale=640:-2,fps=15",
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-pix_fmt",
        "yuv420p",
        out_path,
    ]

    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def capture_clip(source: str, record_dir: str, seconds: float = 3.0) -> str | None:
    if not source:
        return None
    os.makedirs(record_dir, exist_ok=True)
    clip_id = str(uuid.uuid4())
    out_path = os.path.join(record_dir, f"clip_{clip_id}.mp4")

    try:
        _run_ffmpeg_capture(source=source, out_path=out_path, seconds=seconds)
        return out_path
    except (FileNotFoundError, subprocess.CalledProcessError):
        # ffmpeg capture failed or not available; try GStreamer fallback
        try:
            gst_cmd = [
                "gst-launch-1.0", "libcamerasrc", "!", "video/x-raw,width=1280,height=720,framerate=30/1",
                "!", "x264enc", "speed-preset=veryfast", "tune=zerolatency",
                "!", "mp4mux", "!", f"filesink location={out_path}"
            ]
            subprocess.run(gst_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return out_path
        except Exception:
            return None


def simulate_loop(base_url: str, camera_id: str, interval_sec: float) -> None:
    """Emit synthetic events forever."""
    while True:
        now_ms = int(time.time() * 1000)
        event_type = random.choice(EVENT_TYPES)
        severity = random.choices(SEVERITIES, weights=[0.65, 0.25, 0.10])[0]

        summary_by_type = {
            "objects_detected": "Objects detected",
            "person_detected": "Person detected",
            "zone_entry": "Zone entry detected",
            "dwell_time": "Dwell time threshold exceeded",
            "anomaly_motion": "Anomalous motion pattern",
            "ppe_violation": "Possible PPE violation",
        }

        event = {
            "id": str(uuid.uuid4()),
            "ts_ms": now_ms,
            "camera_id": camera_id,
            "event_type": event_type,
            "severity": severity,
            "summary": summary_by_type[event_type],
            "payload": {
                "source": "simulate",
                "camera_id": camera_id,
                "confidence": round(random.uniform(0.5, 0.99), 2),
            },
        }

        post_events(base_url, [event])
        time.sleep(interval_sec)


def camera_loop(
    base_url: str,
    camera_id: str,
    source: str,
    record_dir: str,
    clip_seconds: float,
    interval_sec: float,
) -> None:
    """Capture clips and emit camera events forever."""
    enable_edge_ai = os.environ.get("VSAAS_ENABLE_EDGE_AI", "").strip().lower() in {"1", "true", "yes"}
    if enable_edge_ai:
        _camera_edge_ai_loop(
            base_url=base_url,
            camera_id=camera_id,
            source=source,
            record_dir=record_dir,
            clip_seconds=clip_seconds,
            interval_sec=interval_sec,
        )
        return

    while True:
        now_ms = int(time.time() * 1000)
        event_type = "person_detected"
        severity = "low"

        clip_path = capture_clip(source=source, record_dir=record_dir, seconds=clip_seconds)
        payload = {
            "source": "camera",
            "camera_id": camera_id,
            "video_source": source,
            "clip_path": clip_path or "",
            "clip_seconds": clip_seconds,
        }
        summary = "Camera clip captured" if clip_path else "Camera capture failed"

        event = {
            "id": str(uuid.uuid4()),
            "ts_ms": now_ms,
            "camera_id": camera_id,
            "event_type": event_type,
            "severity": severity,
            "summary": summary,
            "payload": payload,
        }

        post_events(base_url, [event])
        time.sleep(interval_sec)


def _run_ffmpeg_capture_frame(source: str, out_path: str) -> None:

    if _is_qmmf_source(source):
        _run_gst_qmmf_capture_frame(out_path=out_path)
        if not (os.path.exists(out_path) and os.path.getsize(out_path) > 0):
            raise subprocess.CalledProcessError(returncode=1, cmd=["gst-launch-1.0"], output=b"", stderr=b"")
        return

    cmd: list[str] = ["ffmpeg", "-y"]

    if source.startswith("rtsp://"):
        cmd += ["-rtsp_transport", "tcp", "-i", source]
    elif source.startswith("/dev/video"):
        if os.access(source, os.R_OK | os.W_OK):
            cmd = ["ffmpeg", "-y"]
        else:
            cmd = ["sudo", "-n", "ffmpeg", "-y"]
        cmd += ["-f", "v4l2", "-i", source]
    else:
        cmd += ["-i", source]

    cmd += ["-frames:v", "1", "-q:v", "2", out_path]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def capture_frame(source: str, frame_dir: str) -> str | None:
    """Capture a single frame (JPEG) and return the file path, or `None` if capture fails."""
    if not source:
        return None
    os.makedirs(frame_dir, exist_ok=True)
    frame_id = str(uuid.uuid4())
    out_path = os.path.join(frame_dir, f"frame_{frame_id}.jpg")
    try:
        _run_ffmpeg_capture_frame(source=source, out_path=out_path)
        return out_path
    except (FileNotFoundError, subprocess.CalledProcessError):
        # ffmpeg frame capture failed; try GStreamer fallback
        try:
            gst_cmd = [
                "gst-launch-1.0", "libcamerasrc", "!", "video/x-raw,width=1280,height=720,framerate=30/1",
                "!", "jpegenc", "!", f"filesink location={out_path}"
            ]
            subprocess.run(gst_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return out_path
        except Exception:
            return None


def _camera_edge_ai_loop(
    base_url: str,
    camera_id: str,
    source: str,
    record_dir: str,
    clip_seconds: float,
    interval_sec: float,
) -> None:
    detector = choose_detector()
    ppe_checker = choose_ppe_checker()
    zones = load_zones_from_env()
    tracker = SimpleTracker()

    in_zone_since_ms: dict[tuple[int, str], int] = {}
    dwell_fired: set[tuple[int, str]] = set()

    frame_dir = os.environ.get("VSAAS_FRAME_DIR", "data/frames").strip()
    record_on_event = os.environ.get("VSAAS_RECORD_ON_EVENT", "").strip().lower() in {"1", "true", "yes"}
    det_top_k = int(os.environ.get("VSAAS_DET_TOPK", "5"))

    while True:
        ts_ms = int(time.time() * 1000)
        frame_path = capture_frame(source=source, frame_dir=frame_dir)

        events: list[dict] = []
        detections: list[Detection] = []
        if frame_path:
            try:
                detections = detector.detect(frame_path)
            except Exception:
                detections = []

        if detections:
            top = sorted(detections, key=lambda d: d.score, reverse=True)[: max(1, det_top_k)]
            events.append(
                {
                    "id": str(uuid.uuid4()),
                    "ts_ms": ts_ms,
                    "camera_id": camera_id,
                    "event_type": "objects_detected",
                    "severity": "low",
                    "summary": "Objects detected",
                    "payload": {
                        "source": "camera_ai",
                        "camera_id": camera_id,
                        "video_source": source,
                        "frame_path": frame_path or "",
                        "objects": [
                            {
                                "label": d.label,
                                "score": round(float(d.score), 3),
                                "bbox": [
                                    round(float(d.bbox.x1), 4),
                                    round(float(d.bbox.y1), 4),
                                    round(float(d.bbox.x2), 4),
                                    round(float(d.bbox.y2), 4),
                                ],
                            }
                            for d in top
                        ],
                    },
                }
            )
        elif frame_path:
            # Emit a small heartbeat event so E2E demos can verify the pipeline even when no detections fire.
            events.append(
                {
                    "id": str(uuid.uuid4()),
                    "ts_ms": ts_ms,
                    "camera_id": camera_id,
                    "event_type": "objects_detected",
                    "severity": "low",
                    "summary": "No objects detected",
                    "payload": {
                        "source": "camera_ai",
                        "camera_id": camera_id,
                        "video_source": source,
                        "frame_path": frame_path or "",
                        "objects": [],
                    },
                }
            )

        people = [d for d in detections if d.label == "person"]
        tracks = tracker.update(people, ts_ms=ts_ms)

        if people:
            events.append(
                {
                    "id": str(uuid.uuid4()),
                    "ts_ms": ts_ms,
                    "camera_id": camera_id,
                    "event_type": "person_detected",
                    "severity": "low",
                    "summary": f"People detected: {len(people)}",
                    "payload": {
                        "source": "camera_ai",
                        "camera_id": camera_id,
                        "video_source": source,
                        "frame_path": frame_path or "",
                        "people_count": len(people),
                    },
                }
            )

        for person in people:
            ppe = ppe_checker.check(person=person, frame_path=frame_path or "")
            if ppe.get("violation"):
                events.append(
                    {
                        "id": str(uuid.uuid4()),
                        "ts_ms": ts_ms,
                        "camera_id": camera_id,
                        "event_type": "ppe_violation",
                        "severity": "medium",
                        "summary": "Possible PPE violation",
                        "payload": {
                            "source": "camera_ai",
                            "camera_id": camera_id,
                            "video_source": source,
                            "frame_path": frame_path or "",
                            "ppe": ppe,
                        },
                    }
                )

        for trk in tracks:
            cx, cy = trk.center()
            for z in zones:
                key = (trk.track_id, z.zone_id)
                inside = z.contains_norm_point((cx, cy))

                if inside and key not in in_zone_since_ms:
                    in_zone_since_ms[key] = ts_ms
                    if z.kind == "restricted":
                        events.append(
                            {
                                "id": str(uuid.uuid4()),
                                "ts_ms": ts_ms,
                                "camera_id": camera_id,
                                "event_type": "zone_entry",
                                "severity": "high",
                                "summary": f"Intrusion: entered restricted zone {z.zone_id}",
                                "payload": {
                                    "source": "camera_ai",
                                    "camera_id": camera_id,
                                    "video_source": source,
                                    "frame_path": frame_path or "",
                                    "track_id": trk.track_id,
                                    "zone_id": z.zone_id,
                                    "zone_kind": z.kind,
                                },
                            }
                        )

                if inside and z.kind == "dwell":
                    enter = in_zone_since_ms.get(key, ts_ms)
                    dwell_ms = ts_ms - enter
                    if dwell_ms >= int(z.dwell_threshold_sec * 1000) and key not in dwell_fired:
                        dwell_fired.add(key)
                        events.append(
                            {
                                "id": str(uuid.uuid4()),
                                "ts_ms": ts_ms,
                                "camera_id": camera_id,
                                "event_type": "dwell_time",
                                "severity": "medium",
                                "summary": f"Dwell threshold exceeded in zone {z.zone_id}",
                                "payload": {
                                    "source": "camera_ai",
                                    "camera_id": camera_id,
                                    "video_source": source,
                                    "frame_path": frame_path or "",
                                    "track_id": trk.track_id,
                                    "zone_id": z.zone_id,
                                    "zone_kind": z.kind,
                                    "dwell_ms": dwell_ms,
                                    "dwell_threshold_ms": int(z.dwell_threshold_sec * 1000),
                                },
                            }
                        )

                if not inside and key in in_zone_since_ms:
                    in_zone_since_ms.pop(key, None)
                    dwell_fired.discard(key)

        actionable = any(e["event_type"] in {"zone_entry", "dwell_time", "ppe_violation"} for e in events)
        clip_path = None

        # Clip policy:
        # - If VSAAS_RECORD_ON_EVENT is enabled, only record when actionable events occur.
        # - Otherwise, record a clip every interval so E2E runs always have a fresh video artifact.
        if record_on_event:
            if actionable:
                clip_path = capture_clip(source=source, record_dir=record_dir, seconds=clip_seconds)
        else:
            clip_path = capture_clip(source=source, record_dir=record_dir, seconds=clip_seconds)

        if clip_path:
            for e in events:
                e["payload"]["clip_path"] = clip_path or ""
                e["payload"]["clip_seconds"] = clip_seconds

        if not frame_path and not clip_path:
            events = [
                {
                    "id": str(uuid.uuid4()),
                    "ts_ms": ts_ms,
                    "camera_id": camera_id,
                    "event_type": "person_detected",
                    "severity": "low",
                    "summary": "Camera capture failed",
                    "payload": {
                        "source": "camera_ai",
                        "camera_id": camera_id,
                        "video_source": source,
                        "frame_path": "",
                        "clip_path": "",
                        "clip_seconds": clip_seconds,
                    },
                }
            ]

        try:
            post_events(base_url, events)
        except Exception:
            pass
        time.sleep(interval_sec)


def main() -> None:
    parser = argparse.ArgumentParser(description="VSaaS Edge Agent")
    parser.add_argument("--mode", choices=["simulate", "camera"], default="simulate")
    args = parser.parse_args()

    base_url = os.environ.get("VSAAS_CLOUD_BASE_URL", "http://127.0.0.1:9000")
    camera_id = os.environ.get("VSAAS_CAMERA_ID", "iq8_cam_01")
    interval_sec = float(os.environ.get("VSAAS_EMIT_INTERVAL_SEC", "2.0"))
    video_source = os.environ.get("VSAAS_VIDEO_SOURCE", "").strip()
    record_dir = os.environ.get("VSAAS_RECORD_DIR", "data/recordings").strip()
    clip_seconds = float(os.environ.get("VSAAS_CLIP_SECONDS", "3.0"))

    if args.mode == "simulate":
        simulate_loop(base_url=base_url, camera_id=camera_id, interval_sec=interval_sec)
    elif args.mode == "camera":
        if not video_source:
            raise SystemExit("VSAAS_VIDEO_SOURCE is required for --mode camera (e.g. /dev/video0 or rtsp://...)")
        if (not video_source.startswith("rtsp://") and not video_source.startswith("qmmf://")) and not os.path.exists(video_source):
            raise SystemExit(f"VSAAS_VIDEO_SOURCE not found: {video_source}")
        camera_loop(
            base_url=base_url,
            camera_id=camera_id,
            source=video_source,
            record_dir=record_dir,
            clip_seconds=clip_seconds,
            interval_sec=interval_sec,
        )


if __name__ == "__main__":
    main()
