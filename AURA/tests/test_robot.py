"""Tests for the safety-focused robot command seam."""

from __future__ import annotations

import subprocess
import threading
import time

import pytest

from aura.agent.robot import (
    EmergencyStopActive,
    GpioReader,
    RobotSafetyError,
    RobotSafetyPolicy,
    Ros2CliTransport,
    SafeRobotController,
    SysfsGpioReader,
    robot_tools,
    watch_emergency_stop,
)


class FakeTransport:
    def __init__(self, failure: Exception | None = None) -> None:
        self.commands: list[tuple[float, float]] = []
        self.stop_count = 0
        self.failure = failure

    def publish_velocity(self, linear_x: float, angular_z: float) -> None:
        self.commands.append((linear_x, angular_z))
        if self.failure:
            raise self.failure

    def stop(self) -> None:
        self.stop_count += 1


def test_forward_motion_is_bounded_stopped_and_audited() -> None:
    transport = FakeTransport()
    events = []
    sleeps = []
    controller = SafeRobotController(
        transport,
        recorder=events.append,
        sleep=sleeps.append,
    )

    event = controller.move("forward", speed=0.2, duration=1.0)

    assert transport.commands == [(0.2, 0.0)]
    assert transport.stop_count == 1
    assert sleeps == [1.0]
    assert event.attributes["status"] == "completed"
    assert events == [event]


@pytest.mark.parametrize(
    ("direction", "speed", "duration"),
    [
        ("jump", 0.1, 1.0),
        ("forward", 0.3, 1.0),
        ("left", 0.8, 1.0),
        ("forward", 0.1, 3.0),
        ("forward", 0.0, 1.0),
    ],
)
def test_unsafe_motion_is_rejected_and_audited(
    direction: str,
    speed: float,
    duration: float,
) -> None:
    transport = FakeTransport()
    events = []
    controller = SafeRobotController(transport, recorder=events.append, sleep=lambda _: None)

    with pytest.raises(RobotSafetyError):
        controller.move(direction, speed, duration)

    assert transport.commands == []
    assert transport.stop_count == 1
    assert events[0].attributes["status"] == "failed"


def test_emergency_stop_latches_until_operator_reset() -> None:
    transport = FakeTransport()
    controller = SafeRobotController(transport, sleep=lambda _: None)

    stop_event = controller.emergency_stop("test")
    assert controller.emergency_stop_latched
    assert stop_event.attributes["status"] == "latched"

    with pytest.raises(EmergencyStopActive):
        controller.move("forward", 0.1, 0.5)
    with pytest.raises(RobotSafetyError):
        controller.reset_emergency_stop()

    controller.reset_emergency_stop(operator_confirmed=True)
    controller.move("right", 0.5, 0.5)
    assert transport.commands == [(0.0, -0.5)]


def test_emergency_stop_interrupts_an_active_motion() -> None:
    transport = FakeTransport()
    events = []
    controller = None

    def trigger_emergency_stop(_: float) -> None:
        assert controller is not None
        controller.emergency_stop("obstacle detected")

    controller = SafeRobotController(
        transport,
        recorder=events.append,
        sleep=trigger_emergency_stop,
    )

    with pytest.raises(EmergencyStopActive, match="interrupted"):
        controller.move("forward", 0.1, 0.5)

    assert transport.stop_count == 2
    assert [event.attributes["status"] for event in events] == ["latched", "failed"]


def test_transport_failure_attempts_stop_and_records_failure() -> None:
    transport = FakeTransport(RuntimeError("publisher unavailable"))
    events = []
    controller = SafeRobotController(transport, recorder=events.append, sleep=lambda _: None)

    with pytest.raises(RuntimeError, match="publisher unavailable"):
        controller.move("forward", 0.1, 0.5)

    assert transport.stop_count == 1
    assert events[0].attributes["status"] == "failed"
    assert events[0].attributes["error"] == "publisher unavailable"


def test_robot_tools_return_controller_events_without_double_wrapping() -> None:
    controller = SafeRobotController(FakeTransport(), sleep=lambda _: None)
    move_tool = next(tool for tool in robot_tools(controller) if tool.name == "move_robot")

    event = move_tool.invoke(direction="left", speed=0.5, duration=0.5)

    assert event.event == "move_robot: completed"
    assert event.attributes["args"]["direction"] == "left"


def test_ros2_transport_builds_a_non_shell_command(monkeypatch) -> None:
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    transport = Ros2CliTransport(topic="/robot/cmd_vel", timeout=3.0)

    transport.publish_velocity(0.2, -0.4)

    assert captured["command"][:5] == [
        "ros2",
        "topic",
        "pub",
        "--once",
        "/robot/cmd_vel",
    ]
    assert captured["kwargs"]["check"] is True
    assert captured["kwargs"]["timeout"] == 3.0


def test_custom_policy_changes_limits() -> None:
    controller = SafeRobotController(
        FakeTransport(),
        policy=RobotSafetyPolicy(max_linear_speed=0.1, max_duration=0.25),
        sleep=lambda _: None,
    )

    with pytest.raises(RobotSafetyError, match="linear safety limit"):
        controller.move("forward", 0.2, 0.2)
    with pytest.raises(RobotSafetyError, match="second safety limit"):
        controller.move("forward", 0.1, 0.5)


@pytest.mark.parametrize("unsafe_value", [float("nan"), float("inf")])
def test_non_finite_motion_values_are_rejected(unsafe_value: float) -> None:
    controller = SafeRobotController(FakeTransport(), sleep=lambda _: None)

    with pytest.raises(RobotSafetyError):
        controller.move("forward", unsafe_value, 0.5)
    with pytest.raises(RobotSafetyError):
        controller.move("forward", 0.1, unsafe_value)


# ── Emergency-stop watcher ────────────────────────────────────────────────────

class _FakeGpioReader:
    """Toggle-able fake GPIO reader for testing the watcher thread."""

    def __init__(self, initial_value: int = 1) -> None:  # 1 = released (active-low)
        self._value = initial_value

    @property
    def value(self) -> int:
        return self._value

    @value.setter
    def value(self, v: int) -> None:
        self._value = v

    def read(self) -> int:
        return self._value


def test_watch_emergency_stop_triggers_on_active_level() -> None:
    transport = FakeTransport()
    controller = SafeRobotController(transport, sleep=lambda _: None)
    reader = _FakeGpioReader(initial_value=1)  # button released
    stop = threading.Event()

    watch_emergency_stop(controller, reader, poll_interval=0.005, stop_event=stop)
    assert not controller.emergency_stop_latched

    reader.value = 0  # simulate button press (active-low)
    deadline = time.monotonic() + 1.0
    while not controller.emergency_stop_latched and time.monotonic() < deadline:
        time.sleep(0.01)

    stop.set()
    assert controller.emergency_stop_latched


def test_watch_emergency_stop_does_not_trigger_when_inactive() -> None:
    transport = FakeTransport()
    controller = SafeRobotController(transport, sleep=lambda _: None)
    reader = _FakeGpioReader(initial_value=1)  # always released
    stop = threading.Event()

    watch_emergency_stop(controller, reader, poll_interval=0.005, stop_event=stop)
    time.sleep(0.05)
    stop.set()
    assert not controller.emergency_stop_latched


def test_watch_emergency_stop_does_not_double_trigger() -> None:
    transport = FakeTransport()
    events: list = []
    controller = SafeRobotController(transport, recorder=events.append, sleep=lambda _: None)
    reader = _FakeGpioReader(initial_value=0)  # already pressed at start
    stop = threading.Event()

    watch_emergency_stop(controller, reader, poll_interval=0.005, stop_event=stop)
    deadline = time.monotonic() + 0.5
    while not controller.emergency_stop_latched and time.monotonic() < deadline:
        time.sleep(0.01)
    time.sleep(0.05)  # let watcher poll a few more times while still pressed
    stop.set()

    estop_events = [e for e in events if "emergency_stop" in e.event]
    assert len(estop_events) == 1  # only one latch call, not repeated


def test_sysfs_gpio_reader_interface() -> None:
    """SysfsGpioReader composes the correct path — no filesystem access needed."""
    r = SysfsGpioReader(17)
    assert r._path == "/sys/class/gpio/gpio17/value"


# ── Config float fields ───────────────────────────────────────────────────────

def test_settings_robot_defaults() -> None:
    """Robot settings load with the correct default values and types."""
    import os
    from aura.config import Settings

    # Ensure env is clean for these keys.
    for key in ("AURA_ROBOT_TOPIC", "AURA_ROBOT_MAX_LINEAR_SPEED",
                "AURA_ROBOT_MAX_ANGULAR_SPEED", "AURA_ROBOT_MAX_DURATION",
                "AURA_ROBOT_EMERGENCY_GPIO"):
        os.environ.pop(key, None)

    s = Settings.load(dotenv=False)
    assert s.robot_topic == "/cmd_vel"
    assert s.robot_max_linear_speed == pytest.approx(0.25)
    assert s.robot_max_angular_speed == pytest.approx(0.75)
    assert s.robot_max_duration == pytest.approx(2.0)
    assert s.robot_emergency_gpio == 0


def test_settings_robot_overridable_from_env(monkeypatch) -> None:
    monkeypatch.setenv("AURA_ROBOT_TOPIC", "/robot/cmd_vel")
    monkeypatch.setenv("AURA_ROBOT_MAX_LINEAR_SPEED", "0.5")
    monkeypatch.setenv("AURA_ROBOT_MAX_DURATION", "3.0")
    monkeypatch.setenv("AURA_ROBOT_EMERGENCY_GPIO", "17")

    from aura.config import Settings
    s = Settings.load(dotenv=False)
    assert s.robot_topic == "/robot/cmd_vel"
    assert s.robot_max_linear_speed == pytest.approx(0.5)
    assert s.robot_max_duration == pytest.approx(3.0)
    assert s.robot_emergency_gpio == 17
