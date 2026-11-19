"""Run generic QLI audio, camera, logging, and storage workflows.

Audio workflows generate or process 16-bit PCM WAV files through ALSA tools.
Camera workflows use ``v4l2-ctl`` and configurable device nodes, dimensions,
and pixel formats. Storage workflows create only explicitly requested files;
log rotation remains plan-only until ``--execute`` is supplied.

Requirements may include ``aplay``, ``arecord``, and ``v4l2-ctl``. Verify the
selected audio and camera devices before running commands on shared hardware.

Examples::

    python3 qli_media_storage_apps.py beep --output beep.wav
    python3 qli_media_storage_apps.py camera-metadata --device /dev/video0
"""

import argparse
import json
import math
import shutil
import struct
import subprocess
import time
import wave
from datetime import datetime, timezone
from pathlib import Path


WORKFLOWS = (
    "Speaker Beep",
    "Multi Tone Generator",
    "Play WAV File",
    "Record Audio Sample",
    "Audio Loopback Test",
    "Capture Single Image",
    "Save Timestamped Photos",
    "Capture Burst Images",
    "Display Camera Metadata",
    "Motion Snapshot Trigger",
    "Create Log File",
    "Read Configuration File",
    "Store Photo to Disk",
    "Storage Capacity Reporter",
    "Rotate Log Files",
)


def run_command(command: list[str], timeout: int = 120) -> dict:
    """Run a media command and return its exit code and captured output."""
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout,
            check=False,
        )
        return {
            "command": command,
            "returncode": completed.returncode,
            "stdout": completed.stdout.strip(),
            "stderr": completed.stderr.strip(),
        }
    except FileNotFoundError:
        return {"command": command, "returncode": 127, "stdout": "", "stderr": "command not found"}


def emit(workflow: str, result) -> None:
    """Print a workflow result as formatted JSON."""
    print(json.dumps({"workflow": workflow, "result": result}, indent=2))


def write_tone(
    path: Path,
    frequencies: list[float],
    duration: float,
    rate: int,
    volume: float,
    channels: int,
) -> None:
    """Synthesize sine-wave frequencies into a PCM WAV with configurable channels."""
    frame_count = int(duration * rate)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(channels)
        stream.setsampwidth(2)
        stream.setframerate(rate)
        frames = bytearray()
        for index in range(frame_count):
            sample = sum(math.sin(2 * math.pi * frequency * index / rate) for frequency in frequencies)
            sample /= max(1, len(frequencies))
            packed_sample = struct.pack("<h", int(32767 * volume * sample))
            frames.extend(packed_sample * channels)
        stream.writeframes(frames)


def play_wav(path: Path, device: str | None) -> dict:
    """Play a WAV file with ALSA ``aplay`` on the optional output device."""
    command = ["aplay"]
    if device:
        command.extend(["-D", device])
    command.append(str(path))
    return run_command(command)


def handle_beep(args: argparse.Namespace) -> None:
    """Generate an optional-playback single-frequency speaker beep."""
    write_tone(
        args.output,
        [args.frequency],
        args.duration,
        args.rate,
        args.volume,
        args.channels,
    )
    result = {"wav": str(args.output), "frequency": args.frequency}
    if args.play:
        result["playback"] = play_wav(args.output, args.device)
    emit("Speaker Beep", result)


def handle_multi_tone(args: argparse.Namespace) -> None:
    """Generate an optional-playback WAV containing multiple simultaneous tones."""
    write_tone(
        args.output,
        args.frequencies,
        args.duration,
        args.rate,
        args.volume,
        args.channels,
    )
    result = {"wav": str(args.output), "frequencies": args.frequencies}
    if args.play:
        result["playback"] = play_wav(args.output, args.device)
    emit("Multi Tone Generator", result)


def handle_play(args: argparse.Namespace) -> None:
    """Play a user-supplied WAV file on the selected ALSA device."""
    emit("Play WAV File", play_wav(args.wav, args.device))


def record_audio(device: str, duration: int, output: Path, rate: int) -> dict:
    """Record mono PCM audio with ALSA ``arecord`` into the output path."""
    output.parent.mkdir(parents=True, exist_ok=True)
    return run_command(
        [
            "arecord",
            "-D",
            device,
            "-d",
            str(duration),
            "-f",
            "S16_LE",
            "-r",
            str(rate),
            "-c",
            "1",
            str(output),
        ],
        timeout=duration + 30,
    )


def handle_record(args: argparse.Namespace) -> None:
    """Execute the Record Audio Sample workflow."""
    emit("Record Audio Sample", record_audio(args.device, args.duration, args.output, args.rate))


def handle_loopback(args: argparse.Namespace) -> None:
    """Record an audio sample and play it back when capture succeeds."""
    recorded = record_audio(args.capture_device, args.duration, args.output, args.rate)
    playback = None
    if recorded["returncode"] == 0:
        playback = play_wav(args.output, args.playback_device)
    emit("Audio Loopback Test", {"record": recorded, "playback": playback})


def capture_image(device: str, output: Path, width: int, height: int, pixel_format: str) -> dict:
    """Capture one camera frame with ``v4l2-ctl`` into the requested file."""
    output.parent.mkdir(parents=True, exist_ok=True)
    result = run_command(
        [
            "v4l2-ctl",
            "-d",
            device,
            f"--set-fmt-video=width={width},height={height},pixelformat={pixel_format}",
            "--stream-mmap=3",
            "--stream-count=1",
            "--stream-poll",
            f"--stream-to={output}",
        ]
    )
    size = output.stat().st_size if output.exists() else 0
    result["output"] = str(output)
    result["output_bytes"] = size
    if result["returncode"] == 0 and size == 0:
        result["returncode"] = 1
        message = "capture produced an empty output file"
        result["stderr"] = f"{result['stderr']}\n{message}".strip()
    return result


def timestamped_path(directory: Path, prefix: str, suffix: str) -> Path:
    """Create a UTC timestamped path for a generated photo or snapshot."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return directory / f"{prefix}_{stamp}{suffix}"


def handle_capture(args: argparse.Namespace) -> None:
    """Capture a single image using configured V4L2 settings."""
    emit(
        "Capture Single Image",
        capture_image(args.device, args.output, args.width, args.height, args.pixel_format),
    )


def handle_timestamped(args: argparse.Namespace) -> None:
    """Capture one image into a timestamped destination filename."""
    output = timestamped_path(args.directory, args.prefix, args.suffix)
    emit(
        "Save Timestamped Photos",
        {"output": str(output), "capture": capture_image(args.device, output, args.width, args.height, args.pixel_format)},
    )


def handle_burst(args: argparse.Namespace) -> None:
    """Capture a timed sequence of timestamped camera images."""
    captures = []
    for index in range(args.count):
        output = timestamped_path(args.directory, f"{args.prefix}_{index + 1:03d}", args.suffix)
        captures.append(capture_image(args.device, output, args.width, args.height, args.pixel_format))
        if index + 1 < args.count:
            time.sleep(args.interval)
    emit("Capture Burst Images", captures)


def handle_metadata(args: argparse.Namespace) -> None:
    """Report camera capabilities, formats, and controls from ``v4l2-ctl``."""
    emit(
        "Display Camera Metadata",
        {
            "all": run_command(["v4l2-ctl", "-d", args.device, "--all"]),
            "formats": run_command(["v4l2-ctl", "-d", args.device, "--list-formats-ext"]),
            "controls": run_command(["v4l2-ctl", "-d", args.device, "--list-ctrls"]),
        },
    )


def file_difference(first: Path, second: Path) -> float:
    """Return the byte-level difference ratio between two captured files."""
    first_bytes = first.read_bytes()
    second_bytes = second.read_bytes()
    compared = min(len(first_bytes), len(second_bytes))
    if compared == 0:
        return 0.0
    changed = sum(a != b for a, b in zip(first_bytes[:compared], second_bytes[:compared]))
    changed += abs(len(first_bytes) - len(second_bytes))
    return changed / max(len(first_bytes), len(second_bytes))


def handle_motion(args: argparse.Namespace) -> None:
    """Capture samples and preserve frames whose byte difference exceeds a threshold."""
    args.directory.mkdir(parents=True, exist_ok=True)
    previous = args.directory / ".motion_previous.mjpg"
    current = args.directory / ".motion_current.mjpg"
    snapshots = []
    initial_capture = capture_image(args.device, previous, args.width, args.height, args.pixel_format)
    if initial_capture["returncode"] != 0:
        previous.unlink(missing_ok=True)
        emit("Motion Snapshot Trigger", [{"capture": initial_capture}])
        return
    for _ in range(args.samples):
        time.sleep(args.interval)
        capture = capture_image(args.device, current, args.width, args.height, args.pixel_format)
        if capture["returncode"] != 0:
            snapshots.append({"capture": capture})
            continue
        difference = file_difference(previous, current)
        if difference >= args.threshold:
            output = timestamped_path(args.directory, "motion", args.suffix)
            shutil.copy2(current, output)
            snapshots.append({"difference": difference, "output": str(output)})
        current.replace(previous)
    previous.unlink(missing_ok=True)
    current.unlink(missing_ok=True)
    emit("Motion Snapshot Trigger", snapshots)


def handle_create_log(args: argparse.Namespace) -> None:
    """Append a UTC timestamped message to a requested log file."""
    args.path.parent.mkdir(parents=True, exist_ok=True)
    entry = f"{datetime.now(timezone.utc).isoformat()} {args.message}\n"
    with args.path.open("a", encoding="utf-8") as stream:
        stream.write(entry)
    emit("Create Log File", {"path": str(args.path), "entry": entry.rstrip()})


def handle_read_config(args: argparse.Namespace) -> None:
    """Read a text or JSON configuration file and emit its content."""
    text = args.path.read_text(encoding="utf-8")
    if args.path.suffix.lower() == ".json":
        content = json.loads(text)
    else:
        content = text
    emit("Read Configuration File", {"path": str(args.path), "content": content})


def handle_store_photo(args: argparse.Namespace) -> None:
    """Copy a source photo to an explicitly requested destination path."""
    args.destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(args.source, args.destination)
    emit("Store Photo to Disk", {"source": str(args.source), "destination": str(args.destination)})


def handle_capacity(args: argparse.Namespace) -> None:
    """Report total, used, free, and percentage-used storage values."""
    usage = shutil.disk_usage(args.path)
    emit(
        "Storage Capacity Reporter",
        {
            "path": str(args.path),
            "total_bytes": usage.total,
            "used_bytes": usage.used,
            "free_bytes": usage.free,
            "percent_used": round(usage.used / usage.total * 100, 2),
        },
    )


def handle_rotate(args: argparse.Namespace) -> None:
    """Plan or perform numbered log rotation while retaining a configured count."""
    if not args.path.exists():
        emit("Rotate Log Files", {"status": "skipped", "reason": "log does not exist"})
        return
    if not args.execute:
        emit("Rotate Log Files", {"status": "planned", "path": str(args.path), "keep": args.keep})
        return
    # Remove every rotated file at or beyond the retention limit, not just the oldest slot.
    prefix = f"{args.path.name}."
    for rotated in args.path.parent.glob(f"{args.path.name}.*"):
        suffix = rotated.name[len(prefix):]
        if suffix.isdigit() and int(suffix) >= args.keep:
            rotated.unlink(missing_ok=True)
    for index in range(args.keep - 1, 0, -1):
        source = args.path.with_name(f"{args.path.name}.{index}")
        if source.exists():
            source.replace(args.path.with_name(f"{args.path.name}.{index + 1}"))
    args.path.replace(args.path.with_name(f"{args.path.name}.1"))
    args.path.touch()
    emit("Rotate Log Files", {"status": "rotated", "path": str(args.path), "keep": args.keep})


def add_tone_arguments(parser: argparse.ArgumentParser) -> None:
    """Add common tone-generation and optional playback arguments."""
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--duration", type=float, default=1.0)
    parser.add_argument("--rate", type=int, default=48000)
    parser.add_argument("--volume", type=float, default=0.25)
    parser.add_argument("--channels", type=int, choices=(1, 2), default=2)
    parser.add_argument("--play", action="store_true")
    parser.add_argument("--device")


def add_camera_arguments(parser: argparse.ArgumentParser) -> None:
    """Add common V4L2 device, resolution, and pixel-format arguments."""
    parser.add_argument("--device", default="/dev/video0")
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--pixel-format", default="MJPG")


def build_parser() -> argparse.ArgumentParser:
    """Construct the media and storage command-line parser."""
    parser = argparse.ArgumentParser(description="Generic QLI audio, camera, and storage apps.")
    parser.add_argument("--list-workflows", action="store_true")
    subparsers = parser.add_subparsers(dest="app")

    beep = subparsers.add_parser("beep", help=WORKFLOWS[0])
    add_tone_arguments(beep)
    beep.add_argument("--frequency", type=float, default=880.0)
    beep.set_defaults(handler=handle_beep)

    tones = subparsers.add_parser("multi-tone", help=WORKFLOWS[1])
    add_tone_arguments(tones)
    tones.add_argument("--frequencies", type=float, nargs="+", default=[440.0, 660.0, 880.0])
    tones.set_defaults(handler=handle_multi_tone)

    play = subparsers.add_parser("play-wav", help=WORKFLOWS[2])
    play.add_argument("--wav", type=Path, required=True)
    play.add_argument("--device")
    play.set_defaults(handler=handle_play)

    record = subparsers.add_parser("record-audio", help=WORKFLOWS[3])
    record.add_argument("--device", default="default")
    record.add_argument("--duration", type=int, default=3)
    record.add_argument("--rate", type=int, default=48000)
    record.add_argument("--output", type=Path, required=True)
    record.set_defaults(handler=handle_record)

    loopback = subparsers.add_parser("audio-loopback", help=WORKFLOWS[4])
    loopback.add_argument("--capture-device", default="default")
    loopback.add_argument("--playback-device")
    loopback.add_argument("--duration", type=int, default=3)
    loopback.add_argument("--rate", type=int, default=48000)
    loopback.add_argument("--output", type=Path, required=True)
    loopback.set_defaults(handler=handle_loopback)

    capture = subparsers.add_parser("capture-image", help=WORKFLOWS[5])
    add_camera_arguments(capture)
    capture.add_argument("--output", type=Path, required=True)
    capture.set_defaults(handler=handle_capture)

    timestamped = subparsers.add_parser("timestamped-photo", help=WORKFLOWS[6])
    add_camera_arguments(timestamped)
    timestamped.add_argument("--directory", type=Path, required=True)
    timestamped.add_argument("--prefix", default="photo")
    timestamped.add_argument("--suffix", default=".mjpg")
    timestamped.set_defaults(handler=handle_timestamped)

    burst = subparsers.add_parser("burst", help=WORKFLOWS[7])
    add_camera_arguments(burst)
    burst.add_argument("--directory", type=Path, required=True)
    burst.add_argument("--prefix", default="burst")
    burst.add_argument("--suffix", default=".mjpg")
    burst.add_argument("--count", type=int, default=5)
    burst.add_argument("--interval", type=float, default=1.0)
    burst.set_defaults(handler=handle_burst)

    metadata = subparsers.add_parser("camera-metadata", help=WORKFLOWS[8])
    metadata.add_argument("--device", default="/dev/video0")
    metadata.set_defaults(handler=handle_metadata)

    motion = subparsers.add_parser("motion-snapshot", help=WORKFLOWS[9])
    add_camera_arguments(motion)
    motion.add_argument("--directory", type=Path, required=True)
    motion.add_argument("--samples", type=int, default=10)
    motion.add_argument("--interval", type=float, default=1.0)
    motion.add_argument("--threshold", type=float, default=0.05)
    motion.add_argument("--suffix", default=".mjpg")
    motion.set_defaults(handler=handle_motion)

    create_log = subparsers.add_parser("create-log", help=WORKFLOWS[10])
    create_log.add_argument("--path", type=Path, required=True)
    create_log.add_argument("--message", required=True)
    create_log.set_defaults(handler=handle_create_log)

    read_config = subparsers.add_parser("read-config", help=WORKFLOWS[11])
    read_config.add_argument("--path", type=Path, required=True)
    read_config.set_defaults(handler=handle_read_config)

    store_photo = subparsers.add_parser("store-photo", help=WORKFLOWS[12])
    store_photo.add_argument("--source", type=Path, required=True)
    store_photo.add_argument("--destination", type=Path, required=True)
    store_photo.set_defaults(handler=handle_store_photo)

    capacity = subparsers.add_parser("storage-capacity", help=WORKFLOWS[13])
    capacity.add_argument("--path", type=Path, default=Path("/"))
    capacity.set_defaults(handler=handle_capacity)

    rotate = subparsers.add_parser("rotate-logs", help=WORKFLOWS[14])
    rotate.add_argument("--path", type=Path, required=True)
    rotate.add_argument("--keep", type=int, default=5)
    rotate.add_argument("--execute", action="store_true")
    rotate.set_defaults(handler=handle_rotate)

    return parser


def main() -> None:
    """Dispatch the selected media or storage workflow."""
    parser = build_parser()
    args = parser.parse_args()
    if args.list_workflows:
        print("\n".join(WORKFLOWS))
        return
    if not hasattr(args, "handler"):
        parser.print_help()
        raise SystemExit(2)
    args.handler(args)


if __name__ == "__main__":
    main()
