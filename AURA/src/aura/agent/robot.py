"""Safety-focused robot command seam with a ROS2 CLI adapter."""

from __future__ import annotations

import json
import math
import subprocess
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from threading import Lock
from typing import Any, Protocol

from aura.agent.tools import Tool
from aura.core.events import Event


class RobotSafetyError(ValueError):
    """Raised when a robot command violates the configured safety policy."""


class EmergencyStopActive(RobotSafetyError):
    """Raised when motion is requested while emergency stop is latched."""


class RobotTransport(Protocol):
    """Minimal transport interface used by the safety controller."""

    def publish_velocity(self, linear_x: float, angular_z: float) -> None: ...

    def stop(self) -> None: ...


class EventRecorder(Protocol):
    """Small memory seam implemented by ``MemoryStore`` and test fakes."""

    def add_event(self, event: Event) -> object: ...


# ── Physical emergency-stop GPIO seam ────────────────────────────────────────

class GpioReader(Protocol):
    """Read the current state of a single GPIO line (0 = low, 1 = high)."""

    def read(self) -> int: ...


class SysfsGpioReader:
    """Read a GPIO line via the Linux sysfs interface.

    Assumes the pin has already been exported and its direction set to ``in``
    (e.g. by the MCU side or a boot-time udev rule). The emergency-stop button
    wiring is active-low: the line is HIGH at rest and goes LOW when pressed.

    Args:
        pin: BCM / sysfs GPIO pin number (e.g. 17).
    """

    def __init__(self, pin: int) -> None:
        self._path = f"/sys/class/gpio/gpio{pin}/value"

    def read(self) -> int:
        with open(self._path) as fh:
            return int(fh.read().strip())


def watch_emergency_stop(
    controller: SafeRobotController,
    reader: GpioReader,
    *,
    poll_interval: float = 0.05,
    active_low: bool = True,
    stop_event: threading.Event | None = None,
) -> threading.Thread:
    """Start a daemon thread that polls *reader* and latches the e-stop.

    When the GPIO line reaches the active level (LOW by default for
    active-low wiring), :meth:`SafeRobotController.emergency_stop` is called
    once. Polling continues so the latch remains engaged even if the line
    bounces.

    Args:
        controller: The controller whose e-stop will be latched on trigger.
        reader: GPIO reader (e.g. :class:`SysfsGpioReader`).
        poll_interval: Seconds between GPIO reads (default 50 ms).
        active_low: If True (default), a LOW (0) signal triggers the stop.
        stop_event: Optional :class:`threading.Event`; set it to stop the thread.

    Returns:
        The started daemon thread (already running).
    """
    active_level = 0 if active_low else 1

    def _poll() -> None:
        triggered = False
        while stop_event is None or not stop_event.is_set():
            try:
                value = reader.read()
            except OSError:
                time.sleep(poll_interval)
                continue
            if value == active_level and not triggered:
                triggered = True
                if not controller.emergency_stop_latched:
                    controller.emergency_stop("physical emergency-stop button")
            elif value != active_level:
                triggered = False
            time.sleep(poll_interval)

    t = threading.Thread(target=_poll, daemon=True, name="aura-estop-watcher")
    t.start()
    return t


@dataclass(frozen=True)
class RobotSafetyPolicy:
    """Allowlisted motions and hard limits for one command invocation."""

    max_linear_speed: float = 0.25
    max_angular_speed: float = 0.75
    max_duration: float = 2.0
    allowed_directions: tuple[str, ...] = ("forward", "backward", "left", "right")


class Ros2CliTransport:
    """Publish velocity commands using the ``ros2 topic pub`` CLI."""

    def __init__(
        self,
        topic: str = "/cmd_vel",
        *,
        ros2_bin: str = "ros2",
        message_type: str = "geometry_msgs/msg/Twist",
        timeout: float = 10.0,
    ) -> None:
        self.topic = topic
        self.ros2_bin = ros2_bin
        self.message_type = message_type
        self.timeout = timeout

    def publish_velocity(self, linear_x: float, angular_z: float) -> None:
        payload = {
            "linear": {"x": linear_x, "y": 0.0, "z": 0.0},
            "angular": {"x": 0.0, "y": 0.0, "z": angular_z},
        }
        command = [
            self.ros2_bin,
            "topic",
            "pub",
            "--once",
            self.topic,
            self.message_type,
            json.dumps(payload, separators=(",", ":")),
        ]
        try:
            subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
        except FileNotFoundError as exc:
            raise RuntimeError("ros2 is not installed or is not available on PATH") from exc
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError(
                f"ROS2 publish timed out after {self.timeout:g} seconds on {self.topic}"
            ) from exc
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or exc.stdout or "unknown ROS2 error").strip()
            raise RuntimeError(f"ROS2 publish failed: {detail[:500]}") from exc

    def stop(self) -> None:
        self.publish_velocity(0.0, 0.0)


class SafeRobotController:
    """Validate, execute, stop, and audit a small allowlist of robot motions."""

    def __init__(
        self,
        transport: RobotTransport,
        *,
        policy: RobotSafetyPolicy | None = None,
        recorder: EventRecorder | Callable[[Event], object] | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.transport = transport
        self.policy = policy or RobotSafetyPolicy()
        self.recorder = recorder
        self._sleep = sleep
        self._emergency_stop_latched = False
        self._motion_lock = Lock()

    @property
    def emergency_stop_latched(self) -> bool:
        return self._emergency_stop_latched

    def move(self, direction: str, speed: float, duration: float) -> Event:
        with self._motion_lock:
            normalized_direction = direction.strip().lower()
            requested = {
                "direction": normalized_direction,
                "speed": speed,
                "duration": duration,
            }
            try:
                linear_x, angular_z = self._validate_motion(
                    normalized_direction,
                    speed,
                    duration,
                )
                self.transport.publish_velocity(linear_x, angular_z)
                self._sleep(duration)
                if self._emergency_stop_latched:
                    raise EmergencyStopActive("motion interrupted by emergency stop")
                self.transport.stop()
            except Exception as exc:
                try:
                    self.transport.stop()
                except Exception:
                    pass
                self._record(self._event("move_robot", "failed", requested, error=str(exc)))
                raise

            event = self._event("move_robot", "completed", requested)
            self._record(event)
            return event

    def emergency_stop(self, reason: str = "operator request") -> Event:
        self._emergency_stop_latched = True
        self.transport.stop()
        event = self._event("emergency_stop", "latched", {"reason": reason})
        self._record(event)
        return event

    def reset_emergency_stop(self, *, operator_confirmed: bool = False) -> Event:
        if not operator_confirmed:
            raise RobotSafetyError("operator_confirmed=true is required to reset emergency stop")
        self.transport.stop()
        self._emergency_stop_latched = False
        event = self._event("reset_emergency_stop", "completed", {})
        self._record(event)
        return event

    def _validate_motion(
        self,
        direction: str,
        speed: float,
        duration: float,
    ) -> tuple[float, float]:
        if self._emergency_stop_latched:
            raise EmergencyStopActive("emergency stop is latched")
        if direction not in self.policy.allowed_directions:
            allowed = ", ".join(self.policy.allowed_directions)
            raise RobotSafetyError(f"direction must be one of: {allowed}")
        if (
            isinstance(speed, bool)
            or not isinstance(speed, (int, float))
            or not math.isfinite(speed)
            or speed <= 0
        ):
            raise RobotSafetyError("speed must be a positive number")
        if (
            isinstance(duration, bool)
            or not isinstance(duration, (int, float))
            or not math.isfinite(duration)
            or duration <= 0
        ):
            raise RobotSafetyError("duration must be a positive number")
        if duration > self.policy.max_duration:
            raise RobotSafetyError(
                f"duration exceeds the {self.policy.max_duration:g} second safety limit"
            )

        if direction in {"forward", "backward"}:
            if speed > self.policy.max_linear_speed:
                raise RobotSafetyError(
                    f"speed exceeds the {self.policy.max_linear_speed:g} linear safety limit"
                )
            return (speed if direction == "forward" else -speed), 0.0

        if speed > self.policy.max_angular_speed:
            raise RobotSafetyError(
                f"speed exceeds the {self.policy.max_angular_speed:g} angular safety limit"
            )
        return 0.0, (speed if direction == "left" else -speed)

    def _event(
        self,
        command: str,
        status: str,
        arguments: dict[str, Any],
        *,
        error: str | None = None,
    ) -> Event:
        attributes: dict[str, Any] = {
            "tool": command,
            "status": status,
            "args": arguments,
            "emergency_stop_latched": self._emergency_stop_latched,
        }
        if error:
            attributes["error"] = error
        return Event(
            event=f"{command}: {status}",
            type="action",
            source="agent",
            entities=["robot"],
            attributes=attributes,
        )

    def _record(self, event: Event) -> None:
        if self.recorder is None:
            return
        if callable(self.recorder):
            self.recorder(event)
        else:
            self.recorder.add_event(event)


def robot_tools(controller: SafeRobotController) -> list[Tool]:
    """Expose the safe controller through the existing AURA ``Tool`` interface."""
    return [
        Tool(
            "move_robot",
            "Move the robot using an allowlisted direction, bounded speed, and bounded duration.",
            controller.move,
        ),
        Tool(
            "emergency_stop",
            "Immediately stop the robot and latch motion off until an operator resets it.",
            controller.emergency_stop,
        ),
    ]
