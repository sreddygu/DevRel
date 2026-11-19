"""Vendored markdown formatters.

Source: ``DevRel/src/devrel/ui/formatters.py`` (commit 2485044 at sync time).
The functions here are deliberate copies; do not import from the DevRel
package since the client-light tier exists precisely to avoid that
dependency.

If DevRel updates these formatters in a meaningful way, re-sync.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any


def _icon(status: str) -> str:
    return {"pass": "[OK]", "warn": "[WARN]", "fail": "[FAIL]"}.get(status, "·")


def _format_table(
    headers: Sequence[str],
    rows: Sequence[Sequence[Any]],
    *,
    align: Sequence[str] | None = None,
) -> str:
    if not headers:
        return ""
    align = align or ["l"] * len(headers)
    align_map = {"l": ":---", "r": "---:", "c": ":---:"}
    sep_row = [align_map.get(a, ":---") for a in align]

    def _fmt_cell(c: Any) -> str:
        if isinstance(c, float):
            return f"{c:.2f}"
        return str(c)

    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(sep_row) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(_fmt_cell(c) for c in row) + " |")
    return "\n".join(lines)


def format_device(device: dict[str, Any]) -> str:
    """Render a DeviceProfile-shaped dict as markdown."""
    chipset = device.get("chipset", "unknown")
    platform = device.get("platform", "unknown")

    rows = [
        ["**CPU**", f"{device.get('cpu_cores', 0)} x {device.get('cpu_arch', '?')} @ {device.get('cpu_freq_ghz', 0)} GHz"],
        ["**GPU**", f"{device.get('gpu_model', '?')} ({device.get('gpu_tflops', 0)} TFLOPS)"],
        ["**NPU**", f"{device.get('npu_model', '?')} ({device.get('npu_tops', 0)} TOPS)"],
        ["**RAM**", f"{device.get('ram_gb', 0)} GB"],
    ]
    if device.get("storage_gb"):
        rows.append(["**Storage**", f"{device.get('storage_gb')} GB"])
    if device.get("os_version"):
        rows.append(["**OS**", str(device.get("os_version"))])
    rows += [
        ["**Runtimes**", ", ".join(device.get("available_runtimes", []) or ["--"])],
        ["**SDK**", f"{device.get('sdk_version', '?')} @ {device.get('sdk_path', '?') or '(not configured)'}"],
    ]
    return (
        f"### Hardware: {chipset}\n"
        f"_{platform.title()} platform_\n\n"
        + _format_table(["", "Detail"], rows)
    )


def format_doctor(checks: list[dict[str, str]]) -> str:
    """Render a list of CheckResult-shaped dicts as a markdown table."""
    parts: list[str] = ["### Doctor report\n"]
    rows = []
    pass_count = warn_count = fail_count = 0
    for check in checks:
        name = check.get("name", "?")
        status = check.get("status", "?")
        message = check.get("message", "")
        if status == "pass":
            pass_count += 1
        elif status == "warn":
            warn_count += 1
        elif status == "fail":
            fail_count += 1
        rows.append([_icon(status), name, message[:100]])

    parts.append(_format_table(["", "Check", "Detail"], rows, align=["c", "l", "l"]))
    parts.append("")
    parts.append(
        f"**Summary:** {pass_count} passed - {warn_count} warnings - {fail_count} errors"
    )
    return "\n".join(parts)


# Hardcoded subset of DevRel's tips for "detect" context. Avoids dragging the
# whole devrel.tips module across.
_DETECT_TIPS: tuple[str, ...] = (
    "`devrel-agent detect --json` re-probes locally without the DevRel MCP server.",
    "If `cpu_arch` shows 'AMD64' on a known Snapdragon laptop, you may be running an emulated shell. Try cmd.exe or pwsh.",
    "If `available_runtimes` is just ['cpu'] on a Snapdragon machine, install the QAIRT SDK and restart the shell so qnn-platform-validator becomes discoverable.",
    "On Windows, set `QAIRT_SDK_ROOT` to the unzipped QAIRT package root for `devrel-agent` to find SDK tools.",
    "TOPS/TFLOPS numbers are vendor-published peaks, not measured throughput. Use `devrel-agent profile` (server-side) for measured numbers.",
    "Mock-mode hardware figures live on the server. The local probe always reports real hardware.",
)


def tips_for(context: str, n: int = 2) -> list[str]:
    if context != "detect":
        return []
    return list(_DETECT_TIPS[:n])
