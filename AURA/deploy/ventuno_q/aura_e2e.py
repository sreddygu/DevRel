#!/usr/bin/env python3
# Author: Srinivas Reddy Gudala
# Email: sreddygu@qti.qualcomm.com
# Last Updated: 2026-10-21
# Version: 1.0
#
"""AURA full on-device loop for the VENTUNO Q: perceive -> remember -> reason -> act.

Wheel-free (stdlib + numpy/cv2 only), mirroring the IQ8 deploy script but with
the Milestone 5 Action seam wired properly: real SafeRobotController backed by
Ros2CliTransport, smart-home tools backed by a relay transport, and the
LocalLLM.act() tool-calling loop selecting which tool to invoke.

Stages:
  perceive  — vision on the Hexagon NPU + speech STT (whisper.cpp, CPU)
  remember  — MemoryStore (SQLite)
  reason    — LocalLLM.act() grounded on recalled events
  act       — SafeRobotController / SmartHomeRelay via tool-calling loop

Environment variables (all optional — see .env.example):
  AURA_LLM_BASE_URL           LLM endpoint (default http://127.0.0.1:8080)
  AURA_LLM_MODEL              Model id     (default qwen2.5-0.5b)
  AURA_LLM_NO_THINK           Set true for Qwen3 reasoning models
  AURA_ROBOT_TOPIC            ROS2 cmd_vel topic  (default /cmd_vel)
  AURA_ROBOT_MAX_LINEAR_SPEED Safety ceiling for linear motion (default 0.25)
  AURA_ROBOT_MAX_ANGULAR_SPEED Safety ceiling for turns (default 0.75)
  AURA_ROBOT_MAX_DURATION     Max single-command duration in seconds (default 2.0)
  AURA_ROBOT_EMERGENCY_GPIO   GPIO pin for physical e-stop button (default 0 = off)
  AURA_DB                     SQLite path  (default /opt/aura/aura_e2e.db)
  AURA_IMG                    Image to run vision on
  AURA_WAV                    WAV file to transcribe for speech context
  AURA_VISION_CONF            YOLO detection confidence threshold (default 0.75)
  AURA_COMMAND                Natural-language command for the act stage
                              (default: "Turn on the porch light")
"""
import json
import os
import sys
import threading
import urllib.request

sys.path.insert(0, "/opt/aura/src")
sys.path.insert(0, "/opt/aura-vision")
sys.path.insert(0, "/opt/aura-speech")

from aura.agent.robot import (  # noqa: E402
    Ros2CliTransport,
    SafeRobotController,
    RobotSafetyPolicy,
    SysfsGpioReader,
    watch_emergency_stop,
)
from aura.agent.tools import (  # noqa: E402
    MockSmartHomeTransport,
    SmartHomeTransport,
    Tool,
    smart_home_tools,
    default_tools,
)
from aura.core.events import Event  # noqa: E402
from aura.memory.store import MemoryStore  # noqa: E402

# ── Configuration ─────────────────────────────────────────────────────────────
LLM_URL    = os.environ.get("AURA_LLM_BASE_URL",   "http://127.0.0.1:8080")
LLM_MODEL  = os.environ.get("AURA_LLM_MODEL",      "qwen2.5-0.5b")
NO_THINK   = os.environ.get("AURA_LLM_NO_THINK",   "").lower() in {"1", "true", "yes"}
DB         = os.environ.get("AURA_DB",              "/opt/aura/aura_e2e.db")
IMG        = os.environ.get("AURA_IMG",             "/opt/aura-vision/data/bus.jpg")
WAV        = os.environ.get("AURA_WAV",             "/opt/aura-speech/jfk.wav")
VISION_CONF = float(os.environ.get("AURA_VISION_CONF", "0.75"))
COMMAND    = os.environ.get("AURA_COMMAND",         "Turn on the porch light")

ROBOT_TOPIC      = os.environ.get("AURA_ROBOT_TOPIC",            "/cmd_vel")
MAX_LINEAR       = float(os.environ.get("AURA_ROBOT_MAX_LINEAR_SPEED",  "0.25"))
MAX_ANGULAR      = float(os.environ.get("AURA_ROBOT_MAX_ANGULAR_SPEED", "0.75"))
MAX_DURATION     = float(os.environ.get("AURA_ROBOT_MAX_DURATION",      "2.0"))
EMERGENCY_GPIO   = int(os.environ.get("AURA_ROBOT_EMERGENCY_GPIO",      "0"))


# ── Minimal LibreHTTP LocalLLM (no httpx on-device) ───────────────────────────
class _UrllibLLM:
    """Stdlib-only equivalent of LocalLLM for use on a bare device image."""

    def __init__(self, base_url: str, model: str, *, no_think: bool = False, timeout: int = 120) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.no_think = no_think
        self.timeout = timeout

    def _post(self, payload: dict) -> dict:
        body = json.dumps(payload).encode()
        req = urllib.request.Request(
            self.base_url + "/v1/chat/completions",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            return json.load(r)

    def act(self, command: str, tools: list[Tool], context=None, *, max_rounds: int = 5):
        """Tool-calling loop mirroring LocalLLM.act() without httpx."""
        import re
        _THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)

        tool_map = {t.name: t for t in tools}
        tool_specs = [t.to_openai_spec() for t in tools]

        system_content = (
            "You are AURA, a privacy-first physical-AI agent. "
            "Use the available tools to carry out the user's command. "
            "Only use the tools provided; do not invent tool names."
        )
        if context:
            system_content += "\n\nRecent observations:\n" + "\n".join(f"- {e}" for e in context)

        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": command + (" /no_think" if self.no_think else "")},
        ]

        action_events: list[Event] = []

        for _ in range(max_rounds):
            data = self._post({
                "model": self.model,
                "messages": messages,
                "tools": tool_specs,
                "tool_choice": "auto",
                "max_tokens": 256,
            })
            choice = data["choices"][0]
            assistant_msg = choice["message"]
            finish = choice.get("finish_reason", "stop")
            messages.append(assistant_msg)

            if finish != "tool_calls" or not assistant_msg.get("tool_calls"):
                content = _THINK_RE.sub("", assistant_msg.get("content") or "").strip()
                return content, action_events

            for tc in assistant_msg["tool_calls"]:
                fn = tc["function"]
                name = fn["name"]
                try:
                    args = json.loads(fn.get("arguments", "{}"))
                except json.JSONDecodeError:
                    args = {}
                if name not in tool_map:
                    result_text = f"Error: unknown tool '{name}'"
                else:
                    ev = tool_map[name].invoke(**args)
                    result_text = ev.event
                    action_events.append(ev)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.get("id", name),
                    "content": result_text,
                })

        return "", action_events


# ── Smart-home relay transport (VENTUNO Q MCU serial relay) ───────────────────
class SerialRelayTransport:
    """Drive a relay board connected to the VENTUNO Q real-time MCU via serial.

    Writes simple ASCII commands to /dev/ttyACM0 (or AURA_RELAY_DEV).
    Expected command format: "RELAY:<name>:<STATE>\\n"

    Replace with your actual MCU protocol or MQTT gateway as needed.
    """

    def __init__(self, device: str | None = None) -> None:
        self._dev = device or os.environ.get("AURA_RELAY_DEV", "/dev/ttyACM0")
        self._lock = threading.Lock()

    def _send(self, cmd: str) -> None:
        with self._lock:
            with open(self._dev, "w") as fh:
                fh.write(cmd + "\n")
                fh.flush()

    def set_light(self, name: str, state: str) -> str:
        self._send(f"RELAY:{name}:{state.upper()}")
        return f"{name} turned {state}"

    def run_scene(self, name: str) -> str:
        self._send(f"SCENE:{name}")
        return f"scene '{name}' activated"


def _build_relay_transport() -> SmartHomeTransport:
    dev = os.environ.get("AURA_RELAY_DEV", "")
    if dev:
        print(f"  relay transport: {dev}")
        return SerialRelayTransport(dev)
    print("  relay transport: MockSmartHomeTransport (AURA_RELAY_DEV not set)")
    return MockSmartHomeTransport()


def main() -> int:
    print("=" * 60)
    print("AURA VENTUNO Q — perceive -> remember -> reason -> act")
    print("=" * 60)

    store = MemoryStore(DB).connect()

    # ── Build robot controller ────────────────────────────────────────────────
    ros2_transport = Ros2CliTransport(topic=ROBOT_TOPIC)
    policy = RobotSafetyPolicy(
        max_linear_speed=MAX_LINEAR,
        max_angular_speed=MAX_ANGULAR,
        max_duration=MAX_DURATION,
    )
    controller = SafeRobotController(
        ros2_transport,
        policy=policy,
        recorder=store,
    )

    # Wire the physical emergency-stop GPIO if configured.
    estop_thread = None
    if EMERGENCY_GPIO:
        print(f"\n[SETUP] physical emergency-stop watcher on GPIO {EMERGENCY_GPIO}")
        reader = SysfsGpioReader(EMERGENCY_GPIO)
        estop_thread = watch_emergency_stop(controller, reader)
        print(f"  watcher thread: {estop_thread.name} (daemon, polling every 50 ms)")

    # ── Build tool list ───────────────────────────────────────────────────────
    relay = _build_relay_transport()
    tools = default_tools(smart_home=relay, robot=controller)
    print(f"\n[SETUP] tools registered: {[t.name for t in tools]}")

    # ── 1. PERCEIVE: vision (Hexagon NPU) ─────────────────────────────────────
    print("\n[1/4 PERCEIVE] vision on Hexagon NPU ...")
    import aura_npu_detect as vision  # noqa: PLC0415
    vevents = vision.detect(IMG, conf=VISION_CONF, location="living room")
    counts: dict[str, int] = {}
    for e in vevents:
        counts[e["entities"][0]] = counts.get(e["entities"][0], 0) + 1
    scene = ", ".join(f"{n} {label}" for label, n in counts.items()) or "nothing"
    print(f"  scene: {scene}")
    for e in vevents:
        store.add_event(Event(
            event=e["event"], type="detection", source="vision",
            entities=e["entities"], location=e["location"], confidence=e["confidence"],
        ))

    # ── 1b. PERCEIVE: speech STT (CPU) ────────────────────────────────────────
    print("\n[1/4 PERCEIVE] speech STT (whisper.cpp, CPU) ...")
    import aura_stt as stt  # noqa: PLC0415
    spoken = stt.transcribe(WAV)
    print(f"  heard: {spoken[:70]}{'...' if len(spoken) > 70 else ''}")
    store.add_event(Event(event=spoken, type="speech", source="speech"))

    # ── 2. REMEMBER ───────────────────────────────────────────────────────────
    print("\n[2/4 REMEMBER] events persisted to SQLite ...")
    all_events = store.query()
    print(f"  {len(all_events)} events in memory")

    # ── 3/4. REASON + ACT via tool-calling loop ───────────────────────────────
    print(f"\n[3-4/4 REASON+ACT] LLM tool-calling loop ...")
    print(f"  command: {COMMAND}")

    context = [e.event for e in store.query()]
    llm = _UrllibLLM(LLM_URL, LLM_MODEL, no_think=NO_THINK)
    answer, action_events = llm.act(COMMAND, tools, context)

    print(f"\n  LLM answer: {answer}")
    print(f"  actions taken ({len(action_events)}):")
    for ev in action_events:
        store.add_event(ev)
        print(f"    • {ev.event}")

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("LOOP COMPLETE — action Events in memory:")
    for ev in store.query(type="action"):
        print(f"  • {ev.event}")
    store.close()
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
