"""Read-only, dependency-free DevRel tools for the portable local agent."""

from __future__ import annotations

import json
import os
from typing import Any

import agent
from devrel_local import detect_hardware, local_doctor, model_server_health


WORKFLOW = (
    "INTAKE",
    "DETECT",
    "DIAGNOSE",
    "SELECT_STACK",
    "PREPARE",
    "CONVERT",
    "DEPLOY",
    "RUN",
    "VALIDATE",
    "PROFILE",
    "RECOMMEND",
    "RUNBOOK",
)


def _envelope(
    *,
    step: str,
    status: str,
    evidence: list[Any] | None = None,
    next_step: str = "",
    commands: list[str] | None = None,
    artifacts: list[str] | None = None,
    requires_approval: bool = False,
    **extra: Any,
) -> dict[str, Any]:
    return {
        "step": step,
        "status": status,
        "evidence": evidence or [],
        "artifacts": artifacts or [],
        "commands": commands or [],
        "next_step": next_step,
        "requires_approval": requires_approval,
        **extra,
    }


def _dump(payload: dict[str, Any]) -> str:
    text = json.dumps(payload, ensure_ascii=True, default=str)
    if len(text) <= 9000:
        return text
    return json.dumps(
        {
            "step": payload.get("step"),
            "status": payload.get("status"),
            "next_step": payload.get("next_step"),
            "truncated": True,
            "top_level_keys": sorted(payload),
            "preview": text[:7000],
        },
        ensure_ascii=True,
    )


def tool_devrel_intake(args: dict[str, Any]) -> str:
    fields = {
        "goal": str(args.get("goal", "")).strip(),
        "model": str(args.get("model", "")).strip(),
        "model_format": str(args.get("model_format", "")).strip().lower(),
        "target": str(args.get("target", "")).strip(),
        "use_case": str(args.get("use_case", "")).strip().lower(),
        "constraints": str(args.get("constraints", "")).strip(),
    }
    missing = [name for name in ("goal", "model", "target", "use_case") if not fields[name]]
    return _dump(
        _envelope(
            step="INTAKE",
            status="warn" if missing else "pass",
            evidence=[{"captured": fields}],
            next_step="Ask only for the missing fields." if missing else "Run devrel_assess.",
            missing=missing,
            workflow=list(WORKFLOW),
        )
    )


def _doctor_payload(real_mode: bool) -> dict[str, Any]:
    checks = local_doctor(real_mode=real_mode)
    counts = {
        status: sum(1 for check in checks if check.get("status") == status)
        for status in ("pass", "warn", "fail")
    }
    findings = [check for check in checks if check.get("status") != "pass"]
    status = "fail" if counts["fail"] else "warn" if counts["warn"] else "pass"
    return _envelope(
        step="DIAGNOSE",
        status=status,
        evidence=findings,
        next_step=(
            "Resolve FAIL findings before model conversion or deployment."
            if counts["fail"]
            else "Review WARN findings, then select the runtime stack."
            if counts["warn"]
            else "Select the runtime stack and create a reference inference run."
        ),
        summary=counts,
        real_mode=real_mode,
    )


def tool_devrel_doctor(args: dict[str, Any]) -> str:
    return _dump(_doctor_payload(bool(args.get("real_mode", False))))


def tool_devrel_hardware_detect(_args: dict[str, Any]) -> str:
    hardware = detect_hardware()
    return _dump(
        _envelope(
            step="DETECT",
            status="pass" if hardware["cpu"] != "unknown" else "warn",
            evidence=[hardware],
            next_step="Run devrel_doctor, then select a candidate runtime stack.",
        )
    )


def tool_devrel_model_server(args: dict[str, Any]) -> str:
    base_url = str(args.get("base_url") or os.environ.get("DEVREL_MODEL_BASE_URL", "http://127.0.0.1:8080"))
    try:
        result = model_server_health(base_url)
    except ValueError as exc:
        result = {"status": "blocked", "base_url": base_url, "error": str(exc)}
    return _dump(
        _envelope(
            step="RUN",
            status=result["status"],
            evidence=[result],
            next_step=(
                "Use the reported local model endpoint for agent reasoning."
                if result["status"] == "pass"
                else "Start a local llama.cpp or Genie-compatible server on loopback and retry."
            ),
        )
    )


def tool_devrel_assess(args: dict[str, Any]) -> str:
    doctor = _doctor_payload(bool(args.get("real_mode", False)))
    hardware = detect_hardware()
    base_url = str(args.get("base_url") or os.environ.get("DEVREL_MODEL_BASE_URL", "http://127.0.0.1:8080"))
    try:
        server = model_server_health(base_url)
    except ValueError as exc:
        server = {"status": "blocked", "base_url": base_url, "error": str(exc)}

    statuses = {doctor["status"], server["status"]}
    status = "fail" if "fail" in statuses else "blocked" if "blocked" in statuses else "warn" if "warn" in statuses else "pass"
    return _dump(
        _envelope(
            step="DIAGNOSE",
            status=status,
            evidence=[
                {"hardware": hardware},
                {"local_doctor": doctor},
                {"local_model_server": server},
            ],
            next_step=(
                "Resolve local FAIL findings and start the loopback model server before changing the system."
                if status in {"fail", "blocked"}
                else "Select the runtime stack and prepare a reference inference run."
            ),
        )
    )


def tool_devrel_stack_recommend(args: dict[str, Any]) -> str:
    model_format = str(args.get("model_format", "")).strip().lower()
    workload = str(args.get("workload", "")).strip().lower()
    framework = str(args.get("framework", "")).strip().lower()
    target = str(args.get("target", "")).strip()

    if model_format == "gguf":
        primary = "llama.cpp"
        accelerator = "CPU reference path"
    elif model_format in {"pte", "executorch"} or framework == "pytorch":
        primary = "ExecuTorch with Qualcomm backend"
        accelerator = "QNN/HTP when supported"
    elif model_format == "onnx":
        primary = "ONNX Runtime with QNN Execution Provider"
        accelerator = "QNN/HTP with CPU reference comparison"
    elif model_format == "dlc":
        primary = "SNPE/QNN runtime matching the artifact and target SDK"
        accelerator = "DSP/HTP when the artifact is compatible"
    elif model_format in {"bin", "genie", "bundle"} and "llm" in workload:
        primary = "QAIRT Genie"
        accelerator = "Hexagon HTP"
    else:
        primary = "ONNX reference export, then ONNX Runtime QNN or ExecuTorch"
        accelerator = "CPU first; NPU only after compatibility checks"

    missing = [
        name
        for name, value in {
            "model_format": model_format,
            "workload": workload,
            "target": target,
        }.items()
        if not value
    ]
    return _dump(
        _envelope(
            step="SELECT_STACK",
            status="warn" if missing else "pass",
            evidence=[
                {
                    "candidate_runtime": primary,
                    "candidate_accelerator": accelerator,
                    "model_format": model_format or "unknown",
                    "framework": framework or "unknown",
                    "workload": workload or "unknown",
                    "target": target or "unknown",
                }
            ],
            next_step=(
                "Collect the missing facts before finalizing the runtime."
                if missing
                else "Run CPU/reference inference, validate outputs, then test accelerator coverage."
            ),
            missing=missing,
            caveat="Candidate stack only; verify compatibility and performance locally.",
        )
    )


def register_devrel_tools() -> None:
    additions = [
        agent.Tool(
            "devrel_intake",
            "capture goal, model, target, use case, and constraints before recommending changes.",
            tool_devrel_intake,
            {
                "goal": "developer's desired outcome",
                "model": "model name or path",
                "model_format": "onnx, pytorch, gguf, pte, dlc, or bundle",
                "target": "device or chipset",
                "use_case": "realtime, interactive, batch, or development",
                "constraints": "latency, power, accuracy, memory, or security constraints",
            },
            {
                "goal": "run image classification on the NPU",
                "model": "mobilenetv2.onnx",
                "model_format": "onnx",
                "target": "Snapdragon X Elite",
                "use_case": "interactive",
                "constraints": "preserve accuracy",
            },
        ),
        agent.Tool(
            "devrel_hardware_detect",
            "inspect local CPU, RAM, architecture, GPU, and Qualcomm markers without external services.",
            tool_devrel_hardware_detect,
        ),
        agent.Tool(
            "devrel_doctor",
            "run dependency-free local Qualcomm SDK, tools, Python, and runtime diagnostics.",
            tool_devrel_doctor,
            {"real_mode": "true to treat missing real-hardware prerequisites as failures"},
            {"real_mode": True},
        ),
        agent.Tool(
            "devrel_model_server",
            "check a loopback OpenAI-compatible model server and list its local models.",
            tool_devrel_model_server,
            {"base_url": "optional local URL; defaults to the agent model endpoint"},
            {"base_url": "http://127.0.0.1:8080"},
        ),
        agent.Tool(
            "devrel_assess",
            "combine local hardware, diagnostics, and loopback model-server health into a readiness gate.",
            tool_devrel_assess,
            {
                "real_mode": "true for strict real-hardware readiness",
                "base_url": "optional loopback model-server URL",
            },
            {"real_mode": True, "base_url": "http://127.0.0.1:8080"},
        ),
        agent.Tool(
            "devrel_stack_recommend",
            "select a candidate runtime without making unmeasured performance claims.",
            tool_devrel_stack_recommend,
            {
                "model_format": "onnx, pytorch, gguf, pte, dlc, or bundle",
                "workload": "vision, audio, llm, multimodal, or other",
                "framework": "optional source framework",
                "target": "detected device or chipset",
            },
            {
                "model_format": "onnx",
                "workload": "vision",
                "framework": "pytorch",
                "target": "Snapdragon X Elite",
            },
        ),
    ]
    agent.TOOLS.clear()
    agent.TOOLS.update({tool.name: tool for tool in additions})


def route_devrel_prompt(prompt: str) -> str:
    text = prompt.lower()
    tool = ""
    if ("model server" in text or "model endpoint" in text) and any(
        word in text for word in ("check", "health", "running", "list")
    ):
        tool = "devrel_model_server"
    elif any(word in text for word in ("runtime", "stack")) and any(
        word in text for word in ("recommend", "select", "candidate", "path")
    ):
        tool = "devrel_stack_recommend"
    elif "assess" in text or "readiness assessment" in text or "blockers" in text:
        tool = "devrel_assess"
    elif any(phrase in text for phrase in ("ready for", "setup failure", "development machine is ready")):
        tool = "devrel_doctor"
    elif "hardware" in text or sum(
        word in text for word in ("cpu", "ram", "architecture", "gpu", "qualcomm markers")
    ) >= 2:
        tool = "devrel_hardware_detect"
    elif any(phrase in text for phrase in ("not said which", "which model", "which board", "which target")):
        tool = "devrel_intake"
    if not tool:
        return prompt
    return f"{prompt}\n\nRouting requirement: your first action must call {tool}."


DEVREL_PROMPT = """

DevRel bring-up policy:
- Use only the local OpenAI-compatible model endpoint configured for this process.
- For DevRel and Qualcomm bring-up requests, prefer the devrel_* tools over generic
  tools such as sys_info, read_file, or run_shell.
- Route underspecified model or board requests to devrel_intake first.
- Route local hardware inspection to devrel_hardware_detect.
- Route setup readiness checks to devrel_doctor; use devrel_assess when the user asks
  for a full readiness assessment or blockers.
- Route local model endpoint checks to devrel_model_server.
- Route runtime or stack selection to devrel_stack_recommend.
- Do not answer these routed requests from memory without calling the matching tool.
- Follow INTAKE -> DETECT -> DIAGNOSE -> SELECT_STACK before proposing installation,
  conversion, deployment, flashing, or service exposure.
- Use tools for facts. Never guess hardware, SDK readiness, accelerator coverage, or
  measured performance.
- Current DevRel tools are read-only. System-changing next steps require explicit approval.
- Never claim NPU execution until local runtime/provider evidence confirms it.
- Finish with blockers, evidence, the safest next step, and rollback guidance when relevant.
"""
