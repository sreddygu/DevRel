#!/usr/bin/env python3
"""board_profile.py -- generalized multi-board SSH profiling for Qualcomm Linux boards.

Standalone from `devrel-agent unoq <cmd>` (src/devrel_client/local/board/commands.py)
on purpose: that CLI hardcodes Arduino UNO Q specifics (board/soc/hexagon/runtime/RAM
cap) into every command. This script keeps the same SSH plumbing
(`devrel_client.local.board.ssh`) but drives it from a swappable `BoardProfile`
registry, defaulting to the Dragonwing IQ-9075 EVK (SoC QCS9075, ~100 dense TOPS)
while remaining fully configurable for any other board via --board or --board-json.

Encodes lessons learned profiling MobileNetV2 on a Snapdragon X-Elite client
(see export_assets/mobilenet_v2/PROFILING_REPORT.md):

  1. Never rely on a remote MCP server for profiling -- it can be silently broken
     (permission-denied on its own SDK binary, on a host we don't control). This
     script profiles directly over SSH instead.
  2. Never trust a single self-reported arch/spec field -- cross-check multiple
     signals (uname -m, /proc/cpuinfo, /proc/device-tree) and diff against the
     board's declared profile instead of overwriting it silently.
  3. Check executable bits on SDK binaries *before* invoking them -- a permission
     error inside a benchmark run is a much worse debugging experience than a
     clear preflight message.
  4. Record exact onnxruntime version + which execution providers actually loaded
     -- EP behavior can differ across versions on the same graph (we hit this:
     ORT 1.27.0 rejected a graph on CPU/GPU EPs that ORT 1.22.1 and the NPU EP
     both loaded fine).
  5. Never assume int8 is smaller or faster than float -- always measure and
     report both, including on-disk model size.
  6. Capture remote output as text with errors="replace" and write reports as
     UTF-8 explicitly -- console encoding mismatches truncate/crash otherwise.
  7. Do not fabricate hardware specs. Only fields the user has actually
     confirmed are filled in a BoardProfile; everything else is None/"unconfirmed"
     and is populated by `detect` against the live device, never guessed.

IMPORTANT CAVEATS added after a critical review of the initial version (read
before trusting `profile`/`report` output on a new board):

  A. On-device Python + QNNExecutionProvider is UNVERIFIED on Linux ARM boards.
     `onnxruntime-qnn` does publish a `manylinux_2_34_aarch64` pip wheel, so
     `pip install` alone won't fail -- but this repo has no working precedent
     for it actually *loading* the NPU on a Linux device. Every documented,
     proven QNN pattern in this repo (`devrel-npu-prereqs.md`, `qnn_utils.py`)
     is Windows-arch-specific (DLL search paths, `onnxruntime_qnn.get_library_path()`
     pointing at .dll files, `platform.processor()` tricks for WoW64). None of
     that transfers to Linux .so loading as-is. Treat the Python/QNN-EP path
     in `_profile_via_python` as exploratory on a new Linux board -- the CLI
     fallback (`qnn-net-run`/`snpe-net-run`, native QAIRT binaries already on
     the device's rootfs) is the only *proven* on-device NPU path this repo
     has ever exercised. `detect` reports which path is actually viable
     instead of assuming Python succeeds.
  B. NPU inference needs a pre-compiled artifact, not raw .onnx. Per
     `qnn_utils.py` (`run_qnn_net_run` docstring) and `.claude/skills/devrel-convert.md`,
     `qnn-net-run` consumes a QNN **context binary** (`.bin`, produced by
     `mcp__devrel__convert_model(target_sdk="qnn")`) via `--retrieve_context`,
     and `snpe-net-run` consumes an SNPE **DLC** (`.dlc`, `target_sdk="snpe"`)
     via `--container`/`--dlc_path`. A raw `.onnx` on either CLI path will
     fail. This script does NOT automate that conversion (whether the MCP
     server's compiler can even target QCS9075's Hexagon version is itself
     unverified) -- `push`/`profile`/`report` all print an explicit reminder
     to convert first, and `detect` flags a raw-`.onnx` push against a
     CLI-only device as a predictable failure rather than letting it surface
     as a cryptic on-device error.
  C. The on-device QAIRT binary path in `detect`'s probe (`qnn_net_run` field)
     is a best-effort guess per board, NOT a fixed convention documented
     anywhere in this repo -- the only Qualcomm SDK path this codebase
     actually documents is SNPE's `/opt/snpe/` (`commands.py`). Do not
     trust a "missing" verdict for QNN as proof the SDK isn't installed;
     it may just be the wrong path for this board's image.
     `BoardProfile.qnn_bin_glob` makes the probed path configurable per
     board instead of hardcoding one guess for every board. CONFIRMED
     CASE IN POINT: the original guess for iq-9075
     (`/opt/qcom/aistack/qairt/*/bin/*/qnn-net-run`) was wrong -- a live
     `detect` run found the real path via the broader-search fallback
     (`/usr/bin/qnn-net-run`) and the profile below was corrected to
     match. Expect the same for any newly-added board until `detect` has
     actually run against it.
  D. `hexagon_version`, `npu_arch`, and `ram_mb` for QCS9075 (IQ-9075) were
     ALL informed defaults/unconfirmed placeholders as of this caveat's
     original writing, but have since been CONFIRMED via a live `detect`
     run (2026-07-05): on-device `dsp_skel` lists `libSnpeHtpV73Skel.so`
     (confirms hexagon_version=v73, npu_arch), and `free -m` reported the
     real RAM. All three are now in the iq-9075 profile's
     `confirmed_fields`. The general mechanism this caveat describes
     still matters for any OTHER board added to this registry: don't
     assume a value is real just because it looks specific -- check
     `confirmed_fields` before trusting it, and expect `detect` to
     upgrade placeholders to confirmed values (or contradict them) the
     first time it actually runs.
  E. `python_path_extra` (added after discovering `_profile_via_python`'s
     onnxruntime-presence probe never found onnxruntime on a board where
     it was manually installed to a non-standard, writable location
     instead of system site-packages -- iq-9075's `/usr` is read-only and
     has no pip/ensurepip, so onnxruntime lives at
     `/data/local/tmp/devrel/pylibs` there, not on the default Python path).
     Every `python3 -c "import onnxruntime"` probe in this script
     (`_build_detect_probe`, `cmd_profile`, `cmd_report`) and the actual
     benchmark invocation in `_profile_via_python` now prepend
     `PYTHONPATH=<profile.python_path_extra>` when the field is set.
     Without this, `profile`/`report` always fell back to the (working
     but less capable) CLI strategy even when a perfectly good Python
     path was available -- confirmed reproduced and fixed live against
     the board, not just inferred from reading the code.
  F. `--board auto` (added after RB5/Rubio Pi users hit a misleading
     "CONFLICT" when the required --board flag was guessed wrong or left
     at the default, silently degrading to the `generic` fallback profile
     -- see docs/debugging/Verification_Pass_SoC_Skel_SSH_Target.md).
     `detect --board auto <host>` inverts the normal "declare board, then
     probe" order: it probes with the generic profile first, reads the
     live `soc0` reading, and re-resolves to a real BOARD_PROFILES entry
     via `resolve_board_id_from_soc0()` (which reverse-looks-up by each
     profile's own declared `soc` field -- no second SoC->board mapping
     to keep in sync with capabilities.py). Falls back to the generic
     profile (with an honest note, not a silent guess) when soc0 is
     unreadable or no BoardProfile matches yet. `--board auto` is
     `detect`-only -- `configure`/`push`/`profile`/`report` all need a
     real, already-known profile up front (workspace paths, glob
     overrides) and reject `--board auto` with a pointer to run `detect`
     first. Registering a new SoC is one BoardProfile entry (see
     rb5/rubio-pi below for the pattern) plus a capabilities.py entry if
     you also want CPU/GPU/NPU spec enrichment on the client's `detect`
     command -- not a second detection mechanism.

TRANSPORT NOTE (updated 2026-07-20 -- see docs/debugging/IQ9075_adb_investigation.md):
SSH is now the primary, default transport for the IQ-9075 once it has WiFi
configured (`ssh root@<board-ip>`, see docs/IQ9075_SOPs.md) -- ~95% of
workflows go this way. ADB remains available (`--transport adb`) as a
secondary/bootstrap-only path for before WiFi is up on a freshly flashed
board: connecting via USB-C, Windows enumerates three interfaces (VID 05C6 =
Qualcomm) -- a DIAG interface (unusable on Windows without Qualcomm's own
driver -- expected, not a bug), a QDSS trace interface, and a WinUSB-bound
**ADB interface**. The ADB interface additionally requires
`android-tools-adbd.service` to be running on-device, which gates on the
marker file `/etc/usb-debugging-enabled` -- absent on every fresh
flash/reflash and must be recreated manually (`touch
/etc/usb-debugging-enabled && systemctl start android-tools-adbd.service`)
before `adb devices` will see the board again. Full RCA in
docs/debugging/IQ9075_adb_investigation.md. Over adb, the positional `host`
argument is the device **serial** (`adb devices`), or the literal string
`auto` to pick the single attached device automatically.


CONFIRMED VIA LIVE DETECTION (2026-07-05, adb, serial bdcd1f51): hostname
`qcs9075-iq-9075-evk`, device-tree model "Qualcomm Technologies, Inc. Addons
IQ 9075 EVK", compatible string `qcom,qcs9075-addons-iq-9075-evk qcom,qcs9075
qcom,sa8775p`, kernel `6.6.97-qli-1.6-ver.1.2.1-...` aarch64, OS "Qualcomm
Linux 1.6-ver.1.2.1" (qcom-wayland), RAM 35285 MB, root filesystem 107 GB
(4% used). This is the first time this script's `detect` has been run
against a live IQ-9075 -- see `BoardProfile.detect_verified` /
`detect_verified_via` on the `iq-9075` entry below.

Usage:
  python scripts/board_profile.py detect <host> [--board iq-9075] [--transport ssh|adb] [--user root] [--key PATH]
  python scripts/board_profile.py configure <host> [--board iq-9075] [--transport ssh|adb]
  python scripts/board_profile.py push <host> --model FLOAT.onnx [--model-int8 INT8.onnx] [--transport ssh|adb]
  python scripts/board_profile.py profile <host> --model FLOAT.onnx [--model-int8 INT8.onnx] [--transport ssh|adb]
  python scripts/board_profile.py report <host> --model FLOAT.onnx [--model-int8 INT8.onnx] --out report.md [--transport ssh|adb]

  # IQ-9075 over SSH (default, once the board has WiFi -- see docs/IQ9075_SOPs.md):
  python scripts/board_profile.py detect <board-ip> --board iq-9075

  # IQ-9075 over USB/adb (bootstrap-only, before WiFi is up):
  python scripts/board_profile.py detect auto --board iq-9075 --transport adb

  # Unknown/unconfirmed board over SSH -- resolve the board id from a live
  # probe instead of guessing --board (see caveat F):
  python scripts/board_profile.py detect <board-ip> --board auto --transport ssh

No third-party dependencies -- stdlib only, plus the repo's own SSH wrapper
and (for --transport adb) the OS `adb` binary.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from devrel_client.local.board.ssh import (  # noqa: E402
    CommandResult,
    SSHTarget,
    push_file,
    run_remote,
)
from devrel_client.local.capabilities import lookup_for_chipset  # noqa: E402

# ─────────────────────────────────────────────────────────────────────────
# 1. Board profile registry
# ─────────────────────────────────────────────────────────────────────────


@dataclass
class BoardProfile:
    board_id: str
    soc: str  # e.g. "qcs9075"
    aihub_chipset: str  # AI Hub catalog chipset id, e.g. "qualcomm-qcs9075"
    npu_arch: str  # architecture family, or "unconfirmed"
    npu_tops_dense: float | None  # confirmed spec only, else None -- never guessed
    ram_mb: int | None  # None = unconfirmed, filled in by `detect`
    hexagon_version: str | None
    preferred_runtime_order: list[str] = field(default_factory=lambda: ["qnn-htp", "snpe-dsp", "cpu"])
    workspace: str = "/data/local/tmp/devrel/"
    max_model_size_mb: int | None = None
    notes: str = ""
    # SDK binary glob patterns, per board -- QAIRT/QNN installs are NOT at a
    # single fixed path across device images (see caveat C in the module
    # docstring). Each board can override these; a "missing" verdict from
    # `detect` only means "not at this glob", not "not installed".
    snpe_bin_glob: str = "/opt/snpe/bin/*/snpe-net-run"
    qnn_bin_glob: str = "/opt/qcom/aistack/qairt/*/bin/*/qnn-net-run"
    # Which fields below are genuinely user/datasheet-confirmed, as opposed to
    # informed defaults or None placeholders. Drives honest diff/report output
    # instead of silently treating a default as ground truth. Valid entries:
    # "soc", "npu_tops_dense", "ram_mb", "hexagon_version", "npu_arch".
    confirmed_fields: tuple[str, ...] = field(default_factory=tuple)
    # True once a model artifact (.bin/.dlc) known-compatible with this board's
    # CLI NPU runtime has been used successfully -- otherwise `profile`/`report`
    # warn that raw .onnx will not run via qnn-net-run/snpe-net-run (caveat B).
    context_binary_required_for_npu: bool = True
    # Which transport actually reaches this board: "ssh" (default, e.g. UNO Q
    # over Ethernet) or "adb" (e.g. IQ-9075 over USB-C -- its DIAG interface
    # has no Windows driver, but its ADB interface works out of the box).
    # This is a DEFAULT for --transport, not a hard restriction -- the CLI
    # flag can still override it per invocation.
    default_transport: str = "ssh"
    # Flips to True (with detect_verified_via set) the first time `detect`
    # actually completes successfully against a real, live instance of this
    # board -- distinct from confirmed_fields, which tracks individual specs.
    # This tracks "has this script ever proven it can reach this board at
    # all", which is a lower, orthogonal bar.
    detect_verified: bool = False
    detect_verified_via: str = ""  # e.g. "adb serial bdcd1f51, 2026-07-05"
    # Extra on-device PYTHONPATH entry for a manually-installed onnxruntime,
    # when /usr (or wherever site-packages normally lives) is read-only and
    # pip/ensurepip are unavailable -- e.g. a wheel extracted locally and
    # pushed to a writable workspace dir (see the IQ-9075 investigation:
    # NPU_GPU_INVESTIGATION_IQ9075.md). Empty string = no extra path needed,
    # plain `python3 -c "import onnxruntime"` is expected to just work.
    python_path_extra: str = ""

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    def is_confirmed(self, field_name: str) -> bool:
        return field_name in self.confirmed_fields


BOARD_PROFILES: dict[str, BoardProfile] = {
    "iq-9075": BoardProfile(
        board_id="iq-9075",
        soc="qcs9075",
        aihub_chipset="qualcomm-qcs9075",
        npu_arch="Hexagon HTP V73",  # confirmed via live `detect`, 2026-07-05 -- was previously an unconfirmed guess
        npu_tops_dense=100.0,  # confirmed by user: "AI performance up to 100 dense TOPS"
        ram_mb=35285,  # confirmed via live `detect` over adb, 2026-07-05 (free -m on-device)
        hexagon_version="v73",  # confirmed via live `detect`, 2026-07-05: on-device dsp_skel is libSnpeHtpV73Skel.so
        preferred_runtime_order=["qnn-htp", "qnn-gpu", "snpe-dsp", "cpu"],
        confirmed_fields=("soc", "npu_tops_dense", "ram_mb", "hexagon_version", "npu_arch"),
        default_transport="ssh",  # SSH now covers ~95% of workflows once the board is on WiFi; ADB is a
        # bootstrap-only fallback for before WiFi is up (see docs/debugging/IQ9075_adb_investigation.md).
        # Override with --transport adb for that bootstrap case.
        qnn_bin_glob="/usr/bin/qnn-net-run",  # confirmed via live `detect`'s broader search, 2026-07-05 -- was a wrong guess before
        python_path_extra="/data/local/tmp/devrel/pylibs",  # /usr is read-only + no pip/ensurepip on-device -- onnxruntime manually extracted+pushed here (see NPU_GPU_INVESTIGATION_IQ9075.md sec 4.2 / PROFILING_REPORT_IQ9075_v2.md sec 2)
        detect_verified=True,
        detect_verified_via="adb serial bdcd1f51, 2026-07-05 -- hostname qcs9075-iq-9075-evk, kernel 6.6.97-qli-1.6-ver.1.2.1, Qualcomm Linux 1.6 (qcom-wayland), 107GB rootfs",
        notes=(
            "SoC (QCS9075), dense NPU TOPS (100), RAM (35285 MB), hexagon_version "
            "(v73), and npu_arch (Hexagon HTP V73) are all confirmed via a live "
            "`detect` run over adb (2026-07-05): on-device dsp_skel lists "
            "libSnpeHtpV73Skel.so, directly confirming the HTP v73 generation "
            "(previously only an informed guess from Snapdragon X Elite/8 Elite "
            "parity -- see src/devrel_client/local/capabilities.py). "
            "qnn_bin_glob was ALSO corrected by the same probe: the original "
            "/opt/qcom/aistack/qairt/... guess was wrong; the real on-device path "
            "is /usr/bin/qnn-net-run (found via detect's broader /opt,/usr "
            "search fallback -- see caveat C). snpe-net-run was NOT found at "
            "/opt/snpe/ on this device -- CPU/GPU details remain unconfirmed. "
            "Device-tree compatible string is "
            "'qcom,qcs9075-addons-iq-9075-evk qcom,qcs9075 qcom,sa8775p' -- "
            "QCS9075 shares a compatible-string lineage with the SA8775P "
            "automotive/industrial SoC family."
        ),
    ),
    "uno-q": BoardProfile(
        # Ported from src/devrel_client/local/board/commands.py::configure_template
        # for parity/reference -- these values ARE confirmed for that board.
        board_id="uno-q",
        soc="qcs2210",
        aihub_chipset="qualcomm-qcs2210",
        npu_arch="hexagon-v66",
        npu_tops_dense=1.0,
        ram_mb=2048,
        hexagon_version="v66",
        preferred_runtime_order=["snpe-dsp", "cpu"],
        max_model_size_mb=500,
        confirmed_fields=("soc", "npu_tops_dense", "ram_mb", "hexagon_version", "npu_arch"),
        notes="Reference board; UNO Q has no working DSP/GPU inference path -- CPU only in practice.",
    ),
    "rubio-pi": BoardProfile(
        # Rubio Pi / RB3 Gen 2 -- specs sourced from .claude/skills/devrel-app-builder
        # SKILL.md's target table + Target Profiles section (documented there,
        # not yet machine-registered until this entry). NOT marked confirmed --
        # unlike iq-9075/uno-q, no live `detect` has been run against this board
        # in this repo; a real run should promote fields into confirmed_fields
        # (or correct them) the same way IQ-9075's caveat D describes.
        board_id="rubio-pi",
        soc="qcs6490",
        aihub_chipset="qualcomm-qcs6490",
        npu_arch="Hexagon HTP V69",
        npu_tops_dense=12.0,
        ram_mb=8192,
        hexagon_version="v69",
        preferred_runtime_order=["qnn-htp", "snpe-dsp", "cpu"],
        max_model_size_mb=2000,
        notes=(
            "Specs from devrel-app-builder SKILL.md (not yet confirmed via a live "
            "`detect` run against a physical unit in this repo). Skel: "
            "libSnpeHtpV69Skel.so / libQnnHtpV69Skel.so. Cloud profiling available "
            "via AI Hub Models as 'QCS6490 (Proxy)'."
        ),
    ),
    "rb5": BoardProfile(
        # Robotics RB5 -- same sourcing/confirmation caveat as rubio-pi above.
        board_id="rb5",
        soc="qcs8250",
        aihub_chipset="qualcomm-qcs8250",
        npu_arch="Hexagon HTP V68",
        npu_tops_dense=15.0,
        ram_mb=8192,
        hexagon_version="v68",
        preferred_runtime_order=["qnn-htp", "snpe-dsp", "cpu"],
        max_model_size_mb=2000,
        notes=(
            "Specs from devrel-app-builder SKILL.md (not yet confirmed via a live "
            "`detect` run against a physical unit in this repo). Skel: "
            "libSnpeHtpV68Skel.so. GPU spec not documented anywhere in this repo."
        ),
    ),
    "generic": BoardProfile(
        board_id="generic",
        soc="unknown",
        aihub_chipset="",
        npu_arch="unconfirmed",
        npu_tops_dense=None,
        ram_mb=None,
        hexagon_version=None,
        preferred_runtime_order=["qnn-htp", "snpe-dsp", "cpu"],
        notes="Fallback profile for an unrecognized --board id. Everything unconfirmed.",
    ),
}

DEFAULT_BOARD = "iq-9075"


def _build_registry(board_json: Path | None, default_board_id: str) -> dict[str, BoardProfile]:
    """BOARD_PROFILES, optionally overlaid/extended from a user-supplied JSON
    file. Shared by resolve_profile() and cmd_detect()'s --board auto path --
    do not duplicate this logic inline; a second copy is a drift risk if one
    is edited without the other (caught in a critical review, see
    docs/debugging/Board_Auto_Detect_RB5_RubioPi.md)."""
    registry = dict(BOARD_PROFILES)
    if board_json is not None:
        with open(board_json, encoding="utf-8") as fh:
            extra = json.load(fh)
        # extra may be a single profile dict or {board_id: profile_dict, ...}
        entries = extra if _looks_like_registry(extra) else {extra.get("board_id", default_board_id): extra}
        for bid, data in entries.items():
            registry[bid] = BoardProfile(**data)
    return registry


def resolve_profile(board_id: str, board_json: Path | None) -> BoardProfile:
    """Resolve a BoardProfile by id, optionally overlaying/extending the
    registry from a user-supplied JSON file (real configurability, not a
    hardcoded per-board branch)."""
    registry = _build_registry(board_json, board_id)
    if board_id not in registry:
        print(f"[WARN] unknown --board '{board_id}' -- falling back to 'generic'", file=sys.stderr)
        return registry["generic"]
    return registry[board_id]


def _looks_like_registry(obj: dict) -> bool:
    return bool(obj) and all(isinstance(v, dict) for v in obj.values()) and "board_id" not in obj


def _reject_board_auto_outside_detect(args: argparse.Namespace, subcommand: str) -> str | None:
    """--board auto only makes sense for `detect` (it needs a live probe to
    resolve soc0 before anything else can proceed). configure/push/profile/
    report all need workspace paths, glob overrides, etc. from a real,
    already-known BoardProfile up front -- silently falling back to
    'generic' for them (resolve_profile's normal behavior for an unknown
    id) would be misleading here, since the user explicitly asked for
    auto-resolution, not a fallback. Returns an error message, or None if
    args.board is not 'auto'."""
    if args.board.strip().lower() == "auto":
        return (
            f"--board auto is only supported for `detect` (it resolves the profile from a live probe "
            f"before {subcommand} can use workspace paths / glob overrides from it). Run `detect --board "
            f"auto <host>` first to find the real board id, then pass that explicitly to `{subcommand}`."
        )
    return None


def resolve_board_id_from_soc0(soc0_machine: str, registry: dict[str, BoardProfile]) -> tuple[str | None, list[str]]:
    """Reverse-lookup a BOARD_PROFILES entry by its declared ``soc`` field.

    Used by ``--board auto`` (see caveat F) to pick a real profile from a
    live ``soc0`` reading instead of requiring the caller to already know
    which board they have. Deliberately keys off BoardProfile.soc (this
    registry's own field) rather than capabilities.py's chipset name, so
    there is exactly one source of truth for "which board_id does this SoC
    map to" -- no second mapping to keep in sync.

    Returns (board_id_or_None, all_matching_ids). A caller that only wants
    the single result should still check len(all_matching_ids) > 1 -- a
    --board-json overlay introducing a second entry with the same ``soc``
    as an existing one produces a genuine ambiguity that must be reported,
    not silently resolved by dict iteration order (caught in a critical
    review, see docs/debugging/Board_Auto_Detect_RB5_RubioPi.md). Returns
    (None, []) when nothing matches, so the caller can report an honest
    "no BoardProfile for this SoC yet" rather than silently picking a
    fallback that pretends to know the board.
    """
    needle = soc0_machine.strip().lower().replace("-", "").replace("_", "")
    matches = [
        board_id for board_id, profile in registry.items()
        if board_id != "generic" and profile.soc.lower().replace("-", "").replace("_", "") == needle
    ]
    if not matches:
        return None, []
    return matches[0], matches


# ─────────────────────────────────────────────────────────────────────────
# 2. Shared helpers -- transport abstraction (SSH or adb)
# ─────────────────────────────────────────────────────────────────────────
#
# Added after physically connecting a Dragonwing IQ-9075 EVK over USB-C: on
# Windows, its DIAG USB interface has no matching driver (Qualcomm's own DIAG
# driver isn't installed), but its ADB interface binds to WinUSB and works
# immediately -- `adb devices` sees it, `adb shell` reaches a root shell. SSH
# is not reachable at all over this USB link (no network interface is
# exposed). Rather than bolt adb-specific code into every cmd_* function,
# `run_remote`/`push_file` in this module wrap the repo's real SSH-only
# versions from devrel_client.local.board.ssh (used untouched when
# --transport ssh) or shell out to the OS `adb` binary (when --transport
# adb), and every call site in this script uses one BoardTarget regardless
# of which transport backs it.


@dataclass
class BoardTarget:
    """Transport-agnostic handle a cmd_* function passes to run_remote/push_file.

    Wraps either an SSHTarget (transport="ssh") or an adb device serial
    (transport="adb"). `host` for adb is the device serial from `adb
    devices`, or the literal string "auto" to auto-select when exactly one
    device is attached (mirrors the auto-select convenience of `devrel-detect`
    for USB boards).
    """

    transport: str  # "ssh" | "adb"
    host: str
    ssh: SSHTarget | None = None  # populated when transport == "ssh"
    adb_exe: str | None = None  # resolved adb.exe path, when transport == "adb"
    adb_serial: str | None = None  # resolved device serial, when transport == "adb"


def _find_adb() -> str | None:
    """Locate adb.exe: PATH first, then the two install locations documented
    in .claude/skills/devrel-detect.md (winget / Android Studio)."""
    import shutil

    exe = shutil.which("adb") or shutil.which("adb.exe")
    if exe:
        return exe
    candidates = [
        Path.home() / "AppData/Local/Microsoft/WinGet/Packages/Google.PlatformTools_Microsoft.Winget.Source_8wekyb3d8bbwe/platform-tools/adb.exe",
        Path.home() / "AppData/Local/Android/Sdk/platform-tools/adb.exe",
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    return None


def _adb_devices(adb_exe: str) -> list[str]:
    import subprocess

    r = subprocess.run([adb_exe, "devices"], capture_output=True, text=True, timeout=15)
    serials = []
    for line in r.stdout.splitlines()[1:]:
        line = line.strip()
        if line and "\tdevice" in line:
            serials.append(line.split("\t")[0])
    return serials


def resolve_target(host: str, user: str, port: int, key: str | None, transport: str) -> BoardTarget:
    if transport == "ssh":
        return BoardTarget(transport="ssh", host=host, ssh=_ssh_target(host, user, port, key))

    if transport == "adb":
        adb_exe = _find_adb()
        if adb_exe is None:
            raise RuntimeError(
                "adb not found on PATH or in the winget/Android-Studio default install dirs. "
                "Install with: winget install Google.PlatformTools"
            )
        if host == "auto":
            serials = _adb_devices(adb_exe)
            if len(serials) != 1:
                raise RuntimeError(
                    f"--transport adb with host='auto' requires exactly one attached device; "
                    f"found {len(serials)}: {serials}. Pass the serial explicitly instead."
                )
            serial = serials[0]
        else:
            serial = host
        return BoardTarget(transport="adb", host=host, adb_exe=adb_exe, adb_serial=serial)

    raise ValueError(f"unknown transport {transport!r} (expected 'ssh' or 'adb')")


def _ssh_target(host: str, user: str, port: int, key: str | None) -> SSHTarget:
    return SSHTarget(host=host, user=user, port=port, key=Path(key) if key else None)


def bp_run_remote(target: BoardTarget, remote_cmd: str, *, timeout_s: int = 30) -> CommandResult:
    """Transport-dispatching equivalent of devrel_client...ssh.run_remote."""
    if target.transport == "ssh":
        return run_remote(target.ssh, remote_cmd, timeout_s=timeout_s)

    import subprocess
    import time as _time

    start = _time.perf_counter()
    full = [target.adb_exe, "-s", target.adb_serial, "shell", remote_cmd]
    try:
        result = subprocess.run(full, capture_output=True, text=True, timeout=timeout_s, errors="replace")
    except subprocess.TimeoutExpired:
        elapsed = (_time.perf_counter() - start) * 1000
        return CommandResult(returncode=124, stdout="", stderr=f"timeout after {timeout_s}s", elapsed_ms=elapsed)
    elapsed = (_time.perf_counter() - start) * 1000
    # `adb shell` always exits 0 for the adb command itself even if the
    # remote command failed -- unlike ssh, it does not propagate the remote
    # exit code by default. We treat "produced no stderr and no obvious adb
    # error" as ok; callers that need the *remote* command's real exit code
    # should embed `; echo RC=$?` in remote_cmd and parse it themselves.
    adb_level_error = result.returncode != 0 or result.stderr.strip().startswith("adb: error")
    returncode = 1 if adb_level_error else result.returncode
    return CommandResult(returncode=returncode, stdout=result.stdout, stderr=result.stderr, elapsed_ms=elapsed)


def bp_push_file(target: BoardTarget, src: Path, dst: str, *, timeout_s: int = 120) -> CommandResult:
    """Transport-dispatching equivalent of devrel_client...ssh.push_file."""
    if target.transport == "ssh":
        return push_file(target.ssh, src, dst, timeout_s=timeout_s)

    import subprocess
    import time as _time

    start = _time.perf_counter()
    try:
        result = subprocess.run(
            [target.adb_exe, "-s", target.adb_serial, "push", str(src), dst],
            capture_output=True, text=True, timeout=timeout_s, errors="replace",
        )
    except subprocess.TimeoutExpired:
        elapsed = (_time.perf_counter() - start) * 1000
        return CommandResult(124, "", f"adb push timeout after {timeout_s}s", elapsed)
    elapsed = (_time.perf_counter() - start) * 1000
    return CommandResult(result.returncode, result.stdout, result.stderr, elapsed)


def _print_json(obj: Any) -> None:
    print(json.dumps(obj, indent=2, default=str, ensure_ascii=False))


REMOTE_BENCH_SCRIPT = r'''
import json, os, sys, time
import numpy as np
import onnxruntime as ort

MODEL_PATH = sys.argv[1]
WARMUP = int(sys.argv[2]) if len(sys.argv) > 2 else 5
ITERS = int(sys.argv[3]) if len(sys.argv) > 3 else 50

def get_input_feed(sess):
    inp = sess.get_inputs()[0]
    shape = [d if isinstance(d, int) else 1 for d in inp.shape]
    if "float" in inp.type:
        data = np.random.rand(*shape).astype(np.float32)
    else:
        data = np.random.randint(0, 255, size=shape, dtype=np.uint8)
    return {inp.name: data}

def bench(sess, feed):
    for _ in range(WARMUP):
        sess.run(None, feed)
    times = []
    for _ in range(ITERS):
        t0 = time.perf_counter()
        sess.run(None, feed)
        times.append((time.perf_counter() - t0) * 1000)
    times = np.array(times)
    return {
        "mean_ms": float(times.mean()),
        "p50_ms": float(np.percentile(times, 50)),
        "p95_ms": float(np.percentile(times, 95)),
        "fps": float(1000.0 / times.mean()),
    }

def try_provider(name):
    try:
        sess = ort.InferenceSession(MODEL_PATH, providers=[name])
        feed = get_input_feed(sess)
        return {"ok": True, **bench(sess, feed)}
    except Exception as e:
        return {"ok": False, "error": str(e)}

results = {"onnxruntime_version": ort.__version__, "available_providers": ort.get_available_providers()}
for provider in ["CPUExecutionProvider", "QNNExecutionProvider", "OpenVINOExecutionProvider"]:
    if provider in ort.get_available_providers():
        results[provider] = try_provider(provider)

print(json.dumps(results))
'''


def _quote(remote_path: str) -> str:
    return f"'{remote_path}'"


# ─────────────────────────────────────────────────────────────────────────
# 3. detect -- live device probe, cross-checked against the profile
# ─────────────────────────────────────────────────────────────────────────

# NOTE on snpe_exec/qnn_exec probes below: the glob paths come from the
# resolved BoardProfile (snpe_bin_glob / qnn_bin_glob), NOT a fixed convention
# -- this repo only documents /opt/snpe/ as an actual on-device path
# (src/devrel_client/local/board/commands.py); the QAIRT/QNN path is a
# best-effort default (see caveat C in the module docstring) and is very
# likely to need correcting per device image. A "missing" verdict here means
# "not found at the configured glob" -- it does NOT prove the SDK isn't
# installed. If `detect` reports "missing" but you know QAIRT is on the
# device, find the real path (`find / -name 'qnn-net-run' 2>/dev/null`) and
# pass it via --board-json's qnn_bin_glob for this board.
def _python_prefix(profile: BoardProfile) -> str:
    """Shell prefix that puts profile.python_path_extra on PYTHONPATH, if set.
    Needed for boards (e.g. iq-9075) where onnxruntime was manually extracted
    to a writable workspace dir instead of the (read-only) system
    site-packages -- without this, every `python3 -c "import onnxruntime"`
    probe in this script would report MISSING even when a working install
    exists, and `profile`/`report` would always fall back to the CLI
    strategy instead of the (working) Python strategy."""
    if not profile.python_path_extra:
        return ""
    return f"PYTHONPATH={profile.python_path_extra} "


def _detect_profiling_strategy(probe: CommandResult) -> tuple[str | None, str | None]:
    """Classify the on-device onnxruntime capability probe's result.

    Returns (strategy, error): strategy is "python" or "cli" on success,
    None if the probe result is ambiguous/untrustworthy (error is set in
    that case). The probe command is
    ``python3 -c "import onnxruntime; print('OK')" 2>/dev/null || echo MISSING``.

    The prior version of this check was a single boolean --
    ``probe.ok and "OK" in probe.stdout`` -- which conflates two completely
    different situations into the same False value:
      1. The device was unreachable (adb offline, ssh timeout/refused) --
         `probe.ok` is False because the TRANSPORT failed, stdout/stderr
         say nothing about onnxruntime at all.
      2. onnxruntime is genuinely not installed -- `probe.ok` is True (the
         shell command itself ran fine), stdout is literally "MISSING".
    Both collapsed to "fall back to the CLI strategy", which for a raw
    .onnx model produces a clean, plausible-looking "needs a .bin
    artifact" error from every CLI runtime -- indistinguishable from the
    genuine "onnxruntime not installed" case. A user re-running this
    command during a brief board-offline blip could easily read that
    result as "the model needs conversion now" rather than "the board was
    briefly unreachable." Confirmed live: this exact ambiguity was hit and
    diagnosed during a profiling re-validation pass -- see
    docs/debugging/7. CPU_Profiling_Revalidation_MobileNetV2_IQ9075.md §6.3.

    Fix: check `probe.ok` and the *content* separately. If the probe
    command itself failed to execute (transport/timeout error), return an
    explicit error instead of silently choosing a strategy -- the caller
    should surface this loudly, not degrade into a strategy pick that
    looks like a real profiling result.
    """
    if not probe.ok:
        return None, (
            f"could not determine profiling strategy -- the on-device capability probe itself failed "
            f"(is the board still reachable? check `adb devices` / re-test the SSH connection): "
            f"{probe.stderr.strip()[:300] or f'exit {probe.returncode}'}"
        )
    if "OK" in probe.stdout:
        return "python", None
    return "cli", None


def _build_detect_probe(profile: BoardProfile) -> str:
    py = _python_prefix(profile)
    return f"""
echo "===alive==="; echo ALIVE
echo "===uname==="; uname -a
echo "===cpuinfo==="; (grep -m4 -E 'model name|Hardware|CPU implementer|CPU part' /proc/cpuinfo 2>/dev/null || echo none)
echo "===devicetree==="; (cat /proc/device-tree/model 2>/dev/null; echo; cat /proc/device-tree/compatible 2>/dev/null | tr '\\0' ' '; echo)
echo "===soc0==="; (cat /sys/devices/soc0/machine 2>/dev/null; cat /sys/devices/soc0/soc_id 2>/dev/null) || echo none
echo "===os==="; cat /etc/os-release 2>/dev/null | head -8
echo "===mem==="; free -m | head -2
echo "===disk==="; df -h / 2>/dev/null | tail -1
echo "===fastrpc==="; ls /dev/fastrpc-* 2>/dev/null || echo none
echo "===dsp_skel==="; ls /usr/lib/rfsa/adsp/libSnpe*Skel*.so /vendor/lib*/libSnpe*Skel*.so 2>/dev/null | head -5 || echo none
echo "===dsp_skel_qcom_share==="; (find /usr/share/qcom -maxdepth 6 -iname '*Skel*.so' 2>/dev/null | head -200) || echo none
echo "===gpu==="; ls /sys/class/drm/ 2>/dev/null | head -5; clinfo 2>/dev/null | grep -E 'Platform Name|Platform Vendor' | head -3
echo "===snpe_exec==="; (test -x {profile.snpe_bin_glob} 2>/dev/null && echo executable) || (test -f {profile.snpe_bin_glob} 2>/dev/null && echo "found-not-executable") || echo "missing-at-configured-path"
echo "===qnn_exec==="; (test -x {profile.qnn_bin_glob} 2>/dev/null && echo executable) || (test -f {profile.qnn_bin_glob} 2>/dev/null && echo "found-not-executable") || echo "missing-at-configured-path"
echo "===qnn_search==="; (find /opt /usr -maxdepth 6 -iname 'qnn-net-run' 2>/dev/null | head -3) || echo none
echo "===python==="; python3 --version 2>&1
echo "===onnxruntime==="; {py}python3 -c "import onnxruntime; print(onnxruntime.__version__); print(','.join(onnxruntime.get_available_providers()))" 2>&1 || echo "not-installed"
"""


def _parse_sections(stdout: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current = None
    for line in stdout.splitlines():
        if line.startswith("===") and line.endswith("==="):
            current = line.strip("=")
            sections[current] = []
        elif current is not None:
            sections[current].append(line)
    return {k: "\n".join(v).strip() for k, v in sections.items()}


def _filter_skel_by_soc0(dsp_skel_qcom_share: str, soc0: str) -> tuple[str, str | None]:
    """Filter a /usr/share/qcom skel search by the soc0-resolved HTP version.

    Returns (filtered_text, warning_or_None). Never hardcodes an HTP version
    (e.g. "V73") -- derives it dynamically from the soc0-resolved chipset via
    capabilities.py's registry, since a hardcoded version is only correct for
    the one board already seen and silently wrong on any other SoC a
    multi-SoC reference-distro BSP might host. Falls back to returning the
    unfiltered input (with a warning, not a silent failure) when soc0 is
    unreadable, the registry has no entry, or the filter matches nothing --
    see docs/debugging/SoC_Identity_DSP_Skel_False_Positive.md.
    """
    dsp_skel_qcom_share = (dsp_skel_qcom_share or "").strip()
    soc0 = (soc0 or "").strip()
    if not dsp_skel_qcom_share or dsp_skel_qcom_share.lower() == "none" or not soc0 or soc0.lower() == "none":
        return dsp_skel_qcom_share, None

    cap = lookup_for_chipset(soc0.splitlines()[0].strip())
    htp_match = re.search(r"v(\d+)", (cap or {}).get("npu_model", ""), re.IGNORECASE) if cap else None
    if not htp_match:
        return dsp_skel_qcom_share, (
            f"soc0 resolved to {soc0.splitlines()[0].strip()!r} but capabilities.py's registry has no "
            "entry (or no parseable HTP version) for it -- showing the unfiltered /usr/share/qcom skel "
            "list rather than guessing a version filter; consider adding this SoC to the registry"
        )

    arch_ver = htp_match.group(1)
    filtered_lines = [
        line for line in dsp_skel_qcom_share.splitlines()
        # (?!\d) rejects a longer version number (v730 must not match v73).
        # Does not reject a lowercase-letter suffix (e.g. a hypothetical
        # v73b) -- no such filename has been observed on this BSP's actual
        # skel tree (checked live: every V73 hit here is immediately
        # followed by "Skel", never a letter), so this is a known, narrow
        # residual gap, not a live bug. A same-day attempt to also exclude
        # letter suffixes via (?![0-9a-z]) was REVERTED: under re.IGNORECASE,
        # [a-z] in a lookahead also matches uppercase, so it rejected the
        # real "V73Skel" pattern too and broke the filter -- verified broken
        # by re-running _filter_skel_by_soc0 before shipping it. See
        # docs/debugging/Verification_Pass_SoC_Skel_SSH_Target.md.
        if re.search(rf"v{arch_ver}(?!\d)", line, re.IGNORECASE)
    ]
    if filtered_lines:
        return "\n".join(filtered_lines), None
    return dsp_skel_qcom_share, (
        f"soc0-resolved HTP version is v{arch_ver} ({cap['npu_model']!r}), but none of the "
        f"/usr/share/qcom skel hits matched 'v{arch_ver}' -- showing the unfiltered list instead; "
        "this SoC's skel may live under a variant folder that doesn't name its HTP version, "
        "or the registry entry may be stale"
    )


def cmd_detect(args: argparse.Namespace) -> int:
    auto = args.board.strip().lower() == "auto"
    # --board auto: probe first with the generic (everything-unconfirmed)
    # profile, then re-resolve to a real BoardProfile from the live soc0
    # reading -- inverts the normal "declare board, then probe" order so
    # RB5/Rubio Pi-class users don't have to already know their board id
    # (or silently degrade to a generic-profile "CONFLICT" if they guess
    # wrong). See caveat F in this script's module docstring.
    profile = resolve_profile("generic", args.board_json) if auto else resolve_profile(args.board, args.board_json)
    # Capture the glob values actually embedded into the probe BEFORE any
    # --board auto re-resolution below reassigns `profile` -- the snpe_exec/
    # qnn_exec sections in this probe's output were checked against these
    # exact globs, not whatever profile.snpe_bin_glob/qnn_bin_glob end up
    # being after resolution. Using the post-resolution values in the diff
    # message would report the WRONG glob as "not found" (it was never
    # checked) and could even print the resolved board's correct path as if
    # it were the missing one. See caveat F.
    probed_snpe_bin_glob = profile.snpe_bin_glob
    probed_qnn_bin_glob = profile.qnn_bin_glob
    transport = args.transport or profile.default_transport
    try:
        target = resolve_target(args.host, args.user, args.port, args.key, transport)
    except (RuntimeError, ValueError) as e:
        _print_json({"ok": False, "board_id": profile.board_id, "host": args.host, "transport": transport, "error": str(e)})
        return 1

    t0 = time.perf_counter()
    r = bp_run_remote(target, _build_detect_probe(profile), timeout_s=30)
    elapsed_ms = (time.perf_counter() - t0) * 1000

    if not r.ok:
        result = {
            "ok": False,
            "board_id": profile.board_id,
            "host": args.host,
            "transport": transport,
            "error": f"probe failed (exit {r.returncode}): {r.stderr.strip()[:400]}",
            "elapsed_ms": elapsed_ms,
        }
        _print_json(result)
        return 1

    sections = _parse_sections(r.stdout)
    auto_resolution_note = None

    if auto:
        soc0_raw = sections.get("soc0", "").strip()
        soc0_machine = soc0_raw.splitlines()[0].strip() if soc0_raw and soc0_raw.lower() != "none" else ""
        registry = _build_registry(args.board_json, "auto")
        resolved_board_id, all_matches = resolve_board_id_from_soc0(soc0_machine, registry) if soc0_machine else (None, [])
        if resolved_board_id and len(all_matches) > 1:
            profile = registry[resolved_board_id]
            auto_resolution_note = (
                f"--board auto found AMBIGUOUS matches for soc0={soc0_machine!r}: {all_matches!r} -- "
                f"picked {resolved_board_id!r} (first by iteration order, NOT a reliable tie-break). "
                "This means two BoardProfile entries (likely one from --board-json) declare the same "
                "soc -- fix the overlay so only one profile claims this SoC."
            )
        elif resolved_board_id:
            profile = registry[resolved_board_id]
            auto_resolution_note = f"--board auto resolved to {resolved_board_id!r} from soc0={soc0_machine!r}"
        elif soc0_machine:
            auto_resolution_note = (
                f"--board auto could not resolve soc0={soc0_machine!r} to any registered BoardProfile -- "
                "staying on the generic/unconfirmed profile. Add a BoardProfile entry for this SoC (see "
                "rb5/rubio-pi for the pattern) to get real defaults instead of this fallback."
            )
        else:
            auto_resolution_note = (
                "--board auto could not read soc0/machine on this device -- staying on the generic/"
                "unconfirmed profile. Pass --board <id> explicitly if you know which board this is."
            )
        # qnn_bin_glob/snpe_bin_glob checks above already ran against the
        # generic profile's default globs (which are themselves fallback-only
        # values -- see caveat C); a resolved profile's globs are re-checked
        # by simply re-running `detect --board <resolved_id>` if the operator
        # wants a glob-exact check. Re-probing automatically here would double
        # the round-trip for a check that caveat C's own broader search
        # already covers. This is a deliberate scope limit, not an oversight.

    # Cross-check live signals against the declared profile -- diff, don't
    # silently overwrite. Only fields already in profile.confirmed_fields are
    # treated as ground truth; everything else is an informed default or
    # unconfirmed placeholder, and a diff here is a *prompt to update the
    # registry*, not evidence the script is wrong.
    mem_line = sections.get("mem", "")
    detected_ram_mb = None
    for line in mem_line.splitlines():
        if line.strip().lower().startswith("mem:"):
            parts = line.split()
            if len(parts) > 1 and parts[1].isdigit():
                detected_ram_mb = int(parts[1])
            break

    diffs = []
    if auto_resolution_note:
        diffs.append(auto_resolution_note)
    if detected_ram_mb is not None:
        if profile.is_confirmed("ram_mb") and profile.ram_mb != detected_ram_mb:
            diffs.append(f"CONFLICT: profile.ram_mb={profile.ram_mb} (confirmed) but device reports {detected_ram_mb} MB")
        elif not profile.is_confirmed("ram_mb"):
            diffs.append(f"profile.ram_mb is unconfirmed ({profile.ram_mb!r}); device reports {detected_ram_mb} MB -- update BOARD_PROFILES and add 'ram_mb' to confirmed_fields")

    if not profile.is_confirmed("hexagon_version"):
        diffs.append(
            f"profile.hexagon_version={profile.hexagon_version!r} is an informed default, NOT user-confirmed "
            "-- cross-check against on-device QAIRT/SNPE version output (e.g. `qnn-net-run --version`, "
            "SDK release notes) once the SDK path below resolves, then add 'hexagon_version' to confirmed_fields"
        )

    # SoC identity: /sys/devices/soc0/machine is fused/firmware identity and
    # does NOT change across a reflash; /proc/device-tree/compatible can be a
    # shared platform/family string on a multi-SoC reference-distro BSP (e.g.
    # QLI 2.0+) rather than a per-SKU identifier -- confirmed live on an
    # IQ-9075 (QCS9075) reporting `compatible = qcom,lemans-evk qcom,qcs9100
    # qcom,sa8775p` post-reflash while soc0/machine correctly said QCS9075.
    # Treat a soc0 vs. profile.soc mismatch as the real signal; a
    # devicetree-only difference is expected on these BSPs and not a conflict.
    # See docs/debugging/SoC_Identity_DSP_Skel_False_Positive.md.
    soc0 = sections.get("soc0", "").strip()
    devicetree = sections.get("devicetree", "").strip()
    if soc0 and soc0.lower() != "none":
        soc0_machine = soc0.splitlines()[0].strip()
        if profile.soc.lower() == "unknown":
            # profile.soc="unknown" means --board resolved to the generic
            # fallback (unregistered board id, e.g. rb5/rubio-pi have no
            # BoardProfile entry yet) -- soc0 disagreeing with a placeholder
            # is not a real conflict, just useful discovery. Report it as
            # such rather than the CONFLICT wording below.
            diffs.append(
                f"soc0 reports real SoC {soc0_machine!r}, but --board={profile.board_id!r} has no "
                f"registered BoardProfile (using the generic/unconfirmed fallback) -- consider adding a "
                f"BoardProfile entry for {soc0_machine!r} so future runs get real defaults instead of this fallback"
            )
        elif soc0_machine.lower().replace("-", "").replace("_", "") != profile.soc.lower().replace("-", "").replace("_", ""):
            diffs.append(
                f"CONFLICT: /sys/devices/soc0/machine reports {soc0_machine!r} but profile.soc={profile.soc!r} "
                "-- soc0 is fused/firmware identity and is authoritative here, NOT the devicetree compatible "
                "string above (which can be a shared platform/family label on a multi-SoC reference-distro BSP)"
            )
    elif devicetree:
        diffs.append(
            "/sys/devices/soc0/machine was not readable on this device -- SoC identity below relies on "
            "/proc/device-tree/compatible alone, which can be a shared platform/family string (not a "
            "per-SKU identifier) on a multi-SoC reference-distro BSP; treat it as informational, not confirmed"
        )

    snpe_exec = sections.get("snpe_exec", "missing-at-configured-path")
    qnn_exec = sections.get("qnn_exec", "missing-at-configured-path")
    qnn_search_hits = sections.get("qnn_search", "").strip()
    if snpe_exec == "found-not-executable":
        diffs.append("snpe-net-run found on device but NOT executable -- fix permissions before calling `profile` (this is exactly the failure mode hit on the remote MCP server's dgx host)")
    if qnn_exec == "found-not-executable":
        diffs.append("qnn-net-run found on device but NOT executable -- fix permissions before calling `profile`")
    if qnn_exec == "missing-at-configured-path" and qnn_search_hits and qnn_search_hits != "none":
        diffs.append(
            f"qnn-net-run NOT found at {probed_qnn_bin_glob!r} (the glob actually probed"
            + (" -- generic profile default, since --board auto resolves after probing" if auto else "")
            + f"), but a broader search found: {qnn_search_hits!r} -- update qnn_bin_glob via --board-json "
            "to the real path (see caveat C in this script's module docstring; this repo has no confirmed "
            "QAIRT-on-Linux path convention)"
        )
    elif qnn_exec == "missing-at-configured-path":
        diffs.append(
            "qnn-net-run not found at the configured glob NOR via a broader /opt,/usr search -- QAIRT for Linux "
            "may not be installed on this device yet, or lives outside both search roots"
        )

    # dsp_skel: /usr/lib/rfsa/adsp/ is the standard SNPE skel location, but a
    # multi-SoC reference-distro BSP (QLI 2.0+) can file the real skel under
    # /usr/share/qcom/<soc-variant>/.../dsp/cdsp/ instead -- confirmed live on
    # an IQ-9075 where the standard glob was empty but libQnnHtpV73Skel.so was
    # found under /usr/share/qcom/sa8775p/.../dsp/cdsp/. Same diff pattern as
    # qnn_exec/qnn_search above: an empty standard-glob result is "not found
    # there yet", never "not installed", if the broader search has hits.
    #
    # The broader search itself can return 50+ hits across every SoC variant
    # bundled on the rootfs, and the match for THIS device is not guaranteed
    # to sort near the top of a capped `head` -- confirmed live: an IQ-9075's
    # real v73 skel sorted after several other boards' entries and was cut
    # off by an earlier, smaller cap. Never hardcode the expected HTP version
    # (e.g. "V73") to filter this list -- that only matches the one board
    # already seen and silently returns nothing on any other SoC. Instead,
    # derive it dynamically from the soc0-resolved chipset via this repo's
    # own capabilities registry (same registry local `detect` uses for
    # TOPS/HTP-arch enrichment) -- see docs/debugging/SoC_Identity_DSP_Skel_False_Positive.md.
    dsp_skel = sections.get("dsp_skel", "").strip()
    dsp_skel_qcom_share = sections.get("dsp_skel_qcom_share", "").strip()
    dsp_skel_qcom_share_filtered, skel_filter_warning = _filter_skel_by_soc0(dsp_skel_qcom_share, soc0)
    if skel_filter_warning:
        diffs.append(skel_filter_warning)
    if (not dsp_skel or dsp_skel.lower() == "none") and dsp_skel_qcom_share_filtered and dsp_skel_qcom_share_filtered.lower() != "none":
        diffs.append(
            f"No skel found at the standard /usr/lib/rfsa/adsp/ path, but a broader /usr/share/qcom search "
            f"found: {dsp_skel_qcom_share_filtered!r} -- this BSP files skels under a SoC-variant subdirectory "
            "instead of the standard path; do not report the NPU/DSP as missing based on the standard glob alone"
        )
    elif (not dsp_skel or dsp_skel.lower() == "none") and (not dsp_skel_qcom_share or dsp_skel_qcom_share.lower() == "none"):
        diffs.append(
            "No skel found at the standard /usr/lib/rfsa/adsp/ path NOR via the broader /usr/share/qcom search "
            "-- the DSP skel library may genuinely not be installed on this device"
        )

    ort_section = sections.get("onnxruntime", "not-installed")
    onnxruntime_version = ort_section.splitlines()[0] if ort_section and "not-installed" not in ort_section else None
    available_providers = (
        ort_section.splitlines()[1].split(",") if onnxruntime_version and len(ort_section.splitlines()) > 1 else []
    )
    qnn_ep_listed = "QNNExecutionProvider" in available_providers
    if onnxruntime_version and not qnn_ep_listed:
        diffs.append(
            "onnxruntime is installed on-device but QNNExecutionProvider is NOT in get_available_providers() "
            "-- per this script's caveat A, on-device Linux QNN EP via pip onnxruntime-qnn is unverified in this "
            "repo; treat the CLI path (qnn-net-run/snpe-net-run against a pre-converted .bin/.dlc) as primary"
        )

    alive = sections.get("alive", "").strip() == "ALIVE"

    result = {
        "ok": True,
        "detection_successful": alive,  # True iff the probe round-tripped and the device answered "ALIVE"
        "board_id": profile.board_id,
        "declared_profile": profile.to_dict(),
        "host": args.host,
        "transport": transport,
        "elapsed_ms": elapsed_ms,
        "raw": {
            "uname": sections.get("uname", ""),
            "cpuinfo": sections.get("cpuinfo", ""),
            "devicetree": sections.get("devicetree", ""),
            "soc0": soc0 or "none",
            "os_release": sections.get("os", ""),
            "mem": mem_line,
            "disk": sections.get("disk", ""),
            "fastrpc": sections.get("fastrpc", "none"),
            "dsp_skel": sections.get("dsp_skel", "none"),
            "dsp_skel_qcom_share": dsp_skel_qcom_share or "none",
            "dsp_skel_qcom_share_filtered": dsp_skel_qcom_share_filtered or "none",
            "gpu": sections.get("gpu", ""),
        },
        "sdk": {
            "snpe_net_run": snpe_exec,
            "qnn_net_run": qnn_exec,
            "qnn_net_run_broader_search": qnn_search_hits or "none",
            "python": sections.get("python", ""),
            "onnxruntime_version": onnxruntime_version,
            "onnxruntime_providers": available_providers,
        },
        "detected_ram_mb": detected_ram_mb,
        "diffs_vs_profile": diffs,
    }
    if alive and not profile.detect_verified:
        result["note"] = (
            f"First successful `detect` recorded for board_id={profile.board_id!r} via {transport} -- "
            "consider setting BoardProfile.detect_verified=True and detect_verified_via=... in BOARD_PROFILES."
        )
    _print_json(result)
    return 0


# ─────────────────────────────────────────────────────────────────────────
# 4. configure -- emit a generalized [target.<board_id>] devrel.toml stanza
# ─────────────────────────────────────────────────────────────────────────


def cmd_configure(args: argparse.Namespace) -> int:
    if (err := _reject_board_auto_outside_detect(args, "configure")) is not None:
        print(f"[ERROR] {err}", file=sys.stderr)
        return 2
    profile = resolve_profile(args.board, args.board_json)
    transport = args.transport or profile.default_transport
    hexagon_display = profile.hexagon_version or "unconfirmed"
    hexagon_comment = "" if profile.is_confirmed("hexagon_version") else "  # informed default, not user-confirmed -- see caveat D"
    # qnn_bin_glob is only trustworthy once a `detect` run has actually found
    # a binary there (or via its broader-search fallback) -- detect_verified
    # is the closest proxy this script has for "this glob was checked against
    # a real device", short of storing per-field provenance for path strings.
    qnn_glob_comment = (
        "  # verified against a live device by `detect`"
        if profile.detect_verified
        else "  # best-effort guess, not a repo-verified convention -- see caveat C"
    )
    detect_status = (
        f"detect_verified = true  # {profile.detect_verified_via}" if profile.detect_verified
        else "detect_verified = false  # run `detect` against the live board to confirm"
    )
    if transport == "adb":
        connectivity = f"""[target.{profile.board_id}.adb]
serial = "{args.host}"
note = "reached over USB -- this board's SSH/network interface is not exposed on this transport; see the module docstring's TRANSPORT NOTE"
"""
    else:
        connectivity = f"""[target.{profile.board_id}.ssh]
host = "{args.host}"
user = "{args.user}"
key = "~/.ssh/id_rsa"
port = {args.port}
"""
    toml = f"""[target.{profile.board_id}]
type = "linux-{transport}"
board = "{profile.board_id}"
soc = "{profile.soc}"
aihub_chipset = "{profile.aihub_chipset}"
npu_arch = "{profile.npu_arch}"
hexagon_version = "{hexagon_display}"{hexagon_comment}
{detect_status}

{connectivity}
[target.{profile.board_id}.paths]
workspace = "{profile.workspace}"
models = "{profile.workspace}models/"
logs = "{profile.workspace}logs/"
snpe_bin_glob = "{profile.snpe_bin_glob}"
qnn_bin_glob = "{profile.qnn_bin_glob}"{qnn_glob_comment}

[target.{profile.board_id}.constraints]
max_ram_mb = {profile.ram_mb if profile.ram_mb is not None else "0  # unconfirmed -- run `detect` and fill in"}
max_model_size_mb = {profile.max_model_size_mb if profile.max_model_size_mb is not None else "0  # unconfirmed"}
preferred_runtime_order = {json.dumps(profile.preferred_runtime_order)}
confirmed_fields = {json.dumps(list(profile.confirmed_fields))}

# {profile.notes}
# NPU inference requires a pre-compiled artifact (.bin QNN context binary or
# .dlc SNPE DLC), NOT a raw .onnx -- see caveat B in scripts/board_profile.py.
"""
    print(toml)
    return 0


# ─────────────────────────────────────────────────────────────────────────
# 5. push -- pre-flight + scp one or more model precision variants
# ─────────────────────────────────────────────────────────────────────────


def cmd_push(args: argparse.Namespace) -> int:
    if (err := _reject_board_auto_outside_detect(args, "push")) is not None:
        print(f"[ERROR] {err}", file=sys.stderr)
        return 2
    profile = resolve_profile(args.board, args.board_json)
    transport = args.transport or profile.default_transport
    try:
        target = resolve_target(args.host, args.user, args.port, args.key, transport)
    except (RuntimeError, ValueError) as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 1
    workspace = profile.workspace

    models: list[tuple[str, Path]] = []
    if args.model:
        models.append(("float", Path(args.model)))
    if args.model_int8:
        models.append(("int8", Path(args.model_int8)))
    if not models:
        print("[ERROR] pass at least --model", file=sys.stderr)
        return 2

    for _, p in models:
        if not p.exists():
            print(f"[ERROR] model path missing: {p}", file=sys.stderr)
            return 2
        if p.suffix.lower() == ".onnx":
            print(
                f"[WARN] {p.name} is a raw .onnx -- fine for the on-device Python path (if "
                "onnxruntime is installed there), but qnn-net-run/snpe-net-run (the CLI/NPU "
                "path) need a pre-compiled .bin (QNN context binary) or .dlc (SNPE DLC) "
                "instead. Convert first with mcp__devrel__convert_model if you intend to "
                "profile the NPU via the CLI path -- see caveat B in this script's module "
                "docstring. This script does not do that conversion for you.",
                file=sys.stderr,
            )

    pre = bp_run_remote(target, f"mkdir -p {workspace}models && df -h {workspace}", timeout_s=15)
    if not pre.ok:
        print(f"[ERROR] pre-flight failed: {pre.stderr.strip()[:300]}", file=sys.stderr)
        return 1
    print(f"[OK] pre-flight ({workspace}):\n{pre.stdout.strip()}")

    pushed = {}
    for precision, p in models:
        remote_dst = f"{workspace}models/{p.name}"
        r = bp_push_file(target, p, remote_dst, timeout_s=300)
        if not r.ok:
            print(f"[ERROR] push failed for {precision} ({p.name}): {r.stderr.strip()[:300]}", file=sys.stderr)
            return 1
        size_mb = p.stat().st_size / 1e6
        pushed[precision] = {"local": str(p), "remote": remote_dst, "size_mb": round(size_mb, 2)}
        print(f"[OK] pushed {precision}: {p.name} ({size_mb:.2f} MB) -> {remote_dst}")

    _print_json({"ok": True, "board_id": profile.board_id, "transport": transport, "pushed": pushed})
    return 0


# ─────────────────────────────────────────────────────────────────────────
# 6. profile -- run the benchmark, Python path preferred, CLI fallback
# ─────────────────────────────────────────────────────────────────────────

ORT_EP_TO_LABEL = {
    "CPUExecutionProvider": "cpu",
    "QNNExecutionProvider": "npu/gpu (qnn, backend depends on device config)",
    "OpenVINOExecutionProvider": "openvino",
}


def _profile_via_python(target: BoardTarget, workspace: str, remote_model: str, iters: int, warmup: int, python_path_extra: str = "") -> dict[str, Any]:
    """Push and run REMOTE_BENCH_SCRIPT on-device via plain `python3` + pip
    `onnxruntime`. Per caveat A in the module docstring: this repo has NO
    verified precedent for QNNExecutionProvider actually loading the Hexagon
    NPU on a Linux ARM device (only the Windows arch-specific plugin-EP path
    in qnn_utils.py / devrel-npu-prereqs.md is proven). REMOTE_BENCH_SCRIPT
    itself already tries CPUExecutionProvider/QNNExecutionProvider/
    OpenVINOExecutionProvider independently and reports per-provider
    ok/error rather than assuming any of them work -- but callers should
    still treat a result where only CPUExecutionProvider succeeded as the
    *expected* outcome on a new board, not a bug, until proven otherwise.

    python_path_extra: profile.python_path_extra, if the board's onnxruntime
    was manually installed to a non-standard, writable location (e.g. a
    read-only /usr with no pip) rather than plain site-packages.
    """
    remote_script = f"{workspace}board_profile_bench.py"
    # Write the embedded benchmark script to a local temp file, then push it.
    import tempfile

    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as tf:
        tf.write(REMOTE_BENCH_SCRIPT)
        local_tmp = Path(tf.name)
    try:
        push = bp_push_file(target, local_tmp, remote_script, timeout_s=30)
        if not push.ok:
            return {"strategy": "python", "ok": False, "error": f"failed to push bench script: {push.stderr.strip()[:300]}"}
        py_prefix = f"PYTHONPATH={python_path_extra} " if python_path_extra else ""
        cmd = f"{py_prefix}python3 {_quote(remote_script)} {_quote(remote_model)} {warmup} {iters}"
        r = bp_run_remote(target, cmd, timeout_s=max(60, iters * 2))
        if not r.ok:
            return {"strategy": "python", "ok": False, "error": r.stderr.strip()[:500] or f"exit {r.returncode}"}
        try:
            parsed = json.loads(r.stdout.strip().splitlines()[-1])
        except (json.JSONDecodeError, IndexError) as e:
            return {"strategy": "python", "ok": False, "error": f"could not parse bench output: {e}; raw={r.stdout[:500]}"}
        qnn_result = parsed.get("QNNExecutionProvider")
        if qnn_result is not None and not qnn_result.get("ok"):
            parsed["_note"] = (
                "QNNExecutionProvider was available but failed to run (see its 'error') -- expected per "
                "caveat A: this repo has no verified on-device Linux QNN-EP path. Use the CLI strategy "
                "(qnn-net-run against a converted .bin) as the primary NPU path instead."
            )
        return {"strategy": "python", "ok": True, **parsed}
    finally:
        local_tmp.unlink(missing_ok=True)


_CLI_REQUIRED_EXT = {
    "snpe-dsp": ".dlc", "snpe-gpu": ".dlc", "snpe-cpu": ".dlc",
    "qnn-htp": ".bin", "qnn-gpu": ".bin",
}


def _check_cli_model_format(remote_model: str, runtime: str) -> str | None:
    """Return an error string if remote_model's extension is wrong for this
    CLI runtime, else None. Per caveat B: qnn-net-run needs a QNN context
    binary (.bin, produced by `mcp__devrel__convert_model(target_sdk="qnn")`
    via --retrieve_context) and snpe-net-run needs an SNPE DLC (.dlc,
    target_sdk="snpe"). A raw .onnx works with NEITHER CLI tool -- this repo
    has no on-device conversion step, so catch it here with an actionable
    message instead of letting the remote command fail cryptically.
    """
    required = _CLI_REQUIRED_EXT.get(runtime)
    if required is None:
        return f"no CLI runtime mapping for '{runtime}'"
    if not remote_model.lower().endswith(required):
        return (
            f"runtime '{runtime}' needs a {required} artifact, but got {remote_model!r}. "
            f"Raw .onnx will NOT run via qnn-net-run/snpe-net-run -- convert first via "
            f"mcp__devrel__convert_model(target_sdk={'qnn' if required == '.bin' else 'snpe'!r}) "
            "on the client, then push the converted artifact (see caveat B in this script's "
            "module docstring; conversion is NOT automated here since QCS9075 Hexagon-version "
            "compiler support is unverified)."
        )
    return None


def _profile_via_cli(target: BoardTarget, remote_model: str, runtime: str, duration_s: int) -> dict[str, Any]:
    fmt_error = _check_cli_model_format(remote_model, runtime)
    if fmt_error is not None:
        return {"strategy": "cli", "ok": False, "runtime": runtime, "error": fmt_error}

    if runtime.startswith("snpe-"):
        runtime_flag = {"snpe-dsp": "--use_dsp", "snpe-gpu": "--use_gpu", "snpe-cpu": "--use_cpu"}[runtime]
        cmd = (
            f"snpe-net-run --container {_quote(remote_model)} {runtime_flag} "
            f"--perf_profile burst --duration {duration_s} --debug 2>&1 "
            f"| grep -E 'Total Inference|Init Time' || true"
        )
    elif runtime.startswith("qnn-"):
        backend_flag = {"qnn-htp": "libQnnHtp.so", "qnn-gpu": "libQnnGpu.so"}[runtime]
        # --retrieve_context loads a pre-compiled QNN context binary (.bin) --
        # qnn-net-run cannot compile a graph on the fly the way snpe-net-run can.
        cmd = (
            f"qnn-net-run --retrieve_context {_quote(remote_model)} --backend {backend_flag} "
            f"--duration {duration_s} --debug 2>&1 "
            f"| grep -E 'Total Inference|Init Time' || true"
        )
    else:
        return {"strategy": "cli", "ok": False, "runtime": runtime, "error": f"unrecognized runtime family '{runtime}'"}

    r = bp_run_remote(target, cmd, timeout_s=duration_s + 30)
    return {"strategy": "cli", "ok": r.ok, "runtime": runtime, "stdout": r.stdout.strip()[:1000], "stderr": r.stderr.strip()[:300]}


def cmd_profile(args: argparse.Namespace) -> int:
    if (err := _reject_board_auto_outside_detect(args, "profile")) is not None:
        print(f"[ERROR] {err}", file=sys.stderr)
        return 2
    profile = resolve_profile(args.board, args.board_json)
    transport = args.transport or profile.default_transport
    try:
        target = resolve_target(args.host, args.user, args.port, args.key, transport)
    except (RuntimeError, ValueError) as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 1
    workspace = profile.workspace

    # Determine strategy from a quick capability probe (mirrors `detect`, kept
    # minimal here to avoid a full double-probe when the caller already ran
    # `detect` separately). Uses profile.python_path_extra so a manually
    # installed onnxruntime (e.g. iq-9075's /data/local/tmp/devrel/pylibs) is
    # actually found instead of always falling back to the CLI strategy.
    py = _python_prefix(profile)
    probe = bp_run_remote(target, f"{py}python3 -c \"import onnxruntime; print('OK')\" 2>/dev/null || echo MISSING", timeout_s=15)
    strategy, strategy_error = _detect_profiling_strategy(probe)
    if strategy is None:
        print(f"[ERROR] {strategy_error}", file=sys.stderr)
        return 1
    has_python_ort = strategy == "python"

    variants: list[tuple[str, str]] = []
    if args.model:
        variants.append(("float", f"{workspace}models/{Path(args.model).name}"))
    if args.model_int8:
        variants.append(("int8", f"{workspace}models/{Path(args.model_int8).name}"))
    if not variants:
        print("[ERROR] pass at least --model (assumes it was already pushed via `push`)", file=sys.stderr)
        return 2

    results: dict[str, Any] = {"board_id": profile.board_id, "transport": transport, "strategy": strategy, "variants": {}}

    for precision, remote_model in variants:
        if has_python_ort:
            r = _profile_via_python(target, workspace, remote_model, args.iters, args.warmup, profile.python_path_extra)
            results["variants"][precision] = r
        else:
            per_runtime = {}
            for runtime in profile.preferred_runtime_order:
                if runtime == "cpu":
                    continue  # snpe-net-run CPU fallback rarely meaningful; python path preferred for CPU
                per_runtime[runtime] = _profile_via_cli(target, remote_model, runtime, args.duration)
            results["variants"][precision] = {"strategy": "cli", "by_runtime": per_runtime}

    _print_json(results)
    return 0


# ─────────────────────────────────────────────────────────────────────────
# 7. report -- detect + profile, rendered as a markdown report
# ─────────────────────────────────────────────────────────────────────────


def cmd_report(args: argparse.Namespace) -> int:
    if (err := _reject_board_auto_outside_detect(args, "report")) is not None:
        print(f"[ERROR] {err}", file=sys.stderr)
        return 2
    profile = resolve_profile(args.board, args.board_json)
    transport = args.transport or profile.default_transport
    try:
        target = resolve_target(args.host, args.user, args.port, args.key, transport)
    except (RuntimeError, ValueError) as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 1
    r = bp_run_remote(target, _build_detect_probe(profile), timeout_s=30)
    sections = _parse_sections(r.stdout) if r.ok else {}
    detection_successful = r.ok and sections.get("alive", "").strip() == "ALIVE"

    issues: list[str] = []
    if not r.ok:
        issues.append(f"detect probe failed over {transport}: {r.stderr.strip()[:300]}")

    variants: list[tuple[str, Path]] = []
    if args.model:
        variants.append(("float", Path(args.model)))
    if args.model_int8:
        variants.append(("int8", Path(args.model_int8)))

    # push + profile each variant
    profile_results: dict[str, Any] = {}
    if variants:
        for precision, p in variants:
            if not p.exists():
                issues.append(f"model path missing for {precision}: {p}")
                continue
            if p.suffix.lower() == ".onnx":
                issues.append(
                    f"{precision} model {p.name} is a raw .onnx -- the CLI/NPU path "
                    "(qnn-net-run/snpe-net-run) needs a pre-compiled .bin/.dlc instead "
                    "(see caveat B); only the on-device Python path can use it as-is, "
                    "and that path's QNN EP is itself unverified on Linux (caveat A)."
                )
            pf = bp_push_file(target, p, f"{profile.workspace}models/{p.name}", timeout_s=300)
            if not pf.ok:
                issues.append(f"push failed for {precision}: {pf.stderr.strip()[:300]}")

        py = _python_prefix(profile)
        probe = bp_run_remote(target, f"{py}python3 -c \"import onnxruntime; print('OK')\" 2>/dev/null || echo MISSING", timeout_s=15)
        strategy, strategy_error = _detect_profiling_strategy(probe)
        if strategy is None:
            # Same ambiguity _detect_profiling_strategy exists to prevent
            # (see its docstring / caveat) -- but cmd_report is a best-effort
            # multi-section generator, not a hard-fail command (it already
            # tolerates a failed `detect` probe above), so record this as an
            # issue and skip profiling rather than aborting the whole report.
            issues.append(f"could not profile -- {strategy_error}")
            has_python_ort = False
            variants = []  # skip the profiling loop below entirely
        else:
            has_python_ort = strategy == "python"
        for precision, p in variants:
            remote_model = f"{profile.workspace}models/{p.name}"
            if has_python_ort:
                res = _profile_via_python(target, profile.workspace, remote_model, args.iters, args.warmup, profile.python_path_extra)
            else:
                res = {"strategy": "cli", "by_runtime": {
                    rt: _profile_via_cli(target, remote_model, rt, args.duration)
                    for rt in profile.preferred_runtime_order if rt != "cpu"
                }}
            if not res.get("ok", True) and "error" in res:
                issues.append(f"{precision} profiling issue: {res['error']}")
            for rt, rt_res in res.get("by_runtime", {}).items():
                if not rt_res.get("ok", True) and "error" in rt_res:
                    issues.append(f"{precision}/{rt} profiling issue: {rt_res['error']}")
            size_mb = p.stat().st_size / 1e6
            profile_results[precision] = {"result": res, "size_mb": round(size_mb, 2)}

    # Cross-check
    mem_line = sections.get("mem", "")
    detected_ram_mb = None
    for line in mem_line.splitlines():
        if line.strip().lower().startswith("mem:"):
            parts = line.split()
            if len(parts) > 1 and parts[1].isdigit():
                detected_ram_mb = int(parts[1])
            break
    if detected_ram_mb is not None:
        if profile.is_confirmed("ram_mb") and profile.ram_mb != detected_ram_mb:
            issues.append(f"CONFLICT: profile.ram_mb={profile.ram_mb} (confirmed) but device reports {detected_ram_mb} MB")
        elif not profile.is_confirmed("ram_mb"):
            issues.append(f"profile.ram_mb was unconfirmed; device reports {detected_ram_mb} MB -- update BOARD_PROFILES")

    # Filter the /usr/share/qcom skel search by the soc0-resolved HTP version
    # before rendering -- same rationale as cmd_detect (see _filter_skel_by_soc0):
    # the unfiltered list can have 50+ hits across every SoC variant bundled
    # on a multi-SoC reference-distro BSP.
    dsp_skel_qcom_share_filtered, skel_filter_warning = _filter_skel_by_soc0(
        sections.get("dsp_skel_qcom_share", ""), sections.get("soc0", "")
    )
    if skel_filter_warning:
        issues.append(skel_filter_warning)
    sections = {**sections, "dsp_skel_qcom_share": dsp_skel_qcom_share_filtered}

    md = _render_report_md(profile, args.host, transport, detection_successful, sections, profile_results, issues, detected_ram_mb)

    out_path = Path(args.out) if args.out else REPO_ROOT / f"board_profile_report_{profile.board_id}.md"
    out_path.write_text(md, encoding="utf-8")
    print(f"[OK] report written to {out_path}")
    return 0


def _render_report_md(
    profile: BoardProfile,
    host: str,
    transport: str,
    detection_successful: bool,
    sections: dict[str, str],
    profile_results: dict[str, Any],
    issues: list[str],
    detected_ram_mb: int | None,
) -> str:
    detect_badge = "✅ SUCCESSFUL" if detection_successful else "❌ FAILED"
    lines = [
        f"# {profile.board_id} — Board Profiling Report",
        "",
        f"**Detection:** {detect_badge} (transport: {transport})  ",
        f"**SoC:** {profile.soc}  ",
        f"**Declared NPU:** {profile.npu_arch}, {profile.npu_tops_dense if profile.npu_tops_dense is not None else 'unconfirmed'} dense TOPS  ",
        f"**Host:** {host}  ",
        f"**Detected RAM:** {detected_ram_mb if detected_ram_mb is not None else f'unconfirmed ({transport} probe unavailable)'} MB  ",
        "",
        "---",
        "",
        "## 1. Device probe",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| uname | {sections.get('uname', 'n/a')} |",
        f"| cpuinfo | {sections.get('cpuinfo', 'n/a').replace(chr(10), '; ')} |",
        f"| device-tree model | {sections.get('devicetree', 'n/a')} |",
        f"| soc0 (authoritative SoC ID) | {sections.get('soc0', 'n/a')} |",
        f"| OS release | {sections.get('os', 'n/a').replace(chr(10), '; ')} |",
        f"| Memory | {sections.get('mem', 'n/a').replace(chr(10), '; ')} |",
        f"| Disk (/) | {sections.get('disk', 'n/a')} |",
        f"| fastrpc | {sections.get('fastrpc', 'n/a')} |",
        f"| DSP skel libs (standard path) | {sections.get('dsp_skel', 'n/a')} |",
        f"| DSP skel libs (/usr/share/qcom fallback, soc0-filtered) | {sections.get('dsp_skel_qcom_share', 'n/a')} |",
        f"| GPU | {sections.get('gpu', 'n/a').replace(chr(10), '; ')} |",
        f"| snpe-net-run | {sections.get('snpe_exec', 'n/a')} |",
        f"| qnn-net-run | {sections.get('qnn_exec', 'n/a')} |",
        f"| Python | {sections.get('python', 'n/a')} |",
        f"| onnxruntime | {sections.get('onnxruntime', 'n/a').replace(chr(10), '; ')} |",
        "",
        "---",
        "",
        "## 2. Profiling results",
        "",
    ]
    if not profile_results:
        lines.append("_No model provided — pass `--model` (and optionally `--model-int8`) to profile._")
    else:
        lines.append("| Precision | Size (MB) | Strategy | Result |")
        lines.append("|---|---|---|---|")
        for precision, data in profile_results.items():
            res = data["result"]
            strategy = res.get("strategy", "n/a")
            if strategy == "python" and res.get("ok"):
                # _profile_via_python nests per-provider stats (e.g.
                # res["CPUExecutionProvider"]["mean_ms"]) rather than flat
                # top-level keys -- pick the first provider entry that
                # actually ran successfully to summarize.
                provider_stats = next(
                    (v for v in res.values() if isinstance(v, dict) and v.get("ok") and "mean_ms" in v),
                    None,
                )
                if provider_stats is not None:
                    summary = (
                        f"mean={provider_stats['mean_ms']:.3f}ms p50={provider_stats['p50_ms']:.3f}ms "
                        f"p95={provider_stats['p95_ms']:.3f}ms fps={provider_stats['fps']:.1f}"
                    )
                else:
                    summary = f"no provider reported success: {json.dumps(res, default=str)[:300]}"
            elif strategy == "python" and not res.get("ok"):
                summary = f"ERROR: {res.get('error', 'unknown')}"
            else:
                summary = json.dumps(res.get("by_runtime", res), default=str)[:300]
            lines.append(f"| {precision} | {data['size_mb']} | {strategy} | {summary} |")
    lines += [
        "",
        "---",
        "",
        "## 3. Issues encountered",
        "",
    ]
    if issues:
        for i in issues:
            lines.append(f"- {i}")
    else:
        lines.append("_None._")
    lines += [
        "",
        "---",
        "",
        "## 4. Declared board profile (for reference)",
        "",
        "```json",
        json.dumps(profile.to_dict(), indent=2),
        "```",
        "",
        f"_Generated by `scripts/board_profile.py report`. {profile.notes}_",
    ]
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────
# 8. CLI wiring
# ─────────────────────────────────────────────────────────────────────────


def _add_common_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("host", help="Board IP/hostname (ssh transport) or adb device serial / 'auto' (adb transport)")
    p.add_argument(
        "--board", default=DEFAULT_BOARD,
        help=f"Board profile id (default: {DEFAULT_BOARD}). Pass 'auto' (detect subcommand only) to "
        "probe first and resolve the profile from a live soc0 reading instead of declaring it upfront -- "
        "see caveat F in this script's module docstring. Not the same 'auto' as the host positional arg above.",
    )
    p.add_argument("--board-json", type=Path, default=None, help="JSON file with extra/override BoardProfile entries")
    p.add_argument(
        "--transport", choices=["ssh", "adb"], default=None,
        help="Connection transport. Defaults to the board profile's default_transport "
        "(iq-9075 -> ssh, ~95% of workflows; use --transport adb as a bootstrap-only "
        "fallback before WiFi is up -- see docs/debugging/IQ9075_adb_investigation.md; "
        "every other board -> ssh).",
    )
    p.add_argument("--user", default="root", help="SSH user (ignored for --transport adb)")
    p.add_argument("--port", type=int, default=22, help="SSH port (ignored for --transport adb)")
    p.add_argument("--key", default=None, help="SSH private key path (ignored for --transport adb)")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_detect = sub.add_parser("detect", help="Probe the board and diff against its declared profile")
    _add_common_args(p_detect)
    p_detect.set_defaults(func=cmd_detect)

    p_configure = sub.add_parser("configure", help="Emit a [target.<board_id>] devrel.toml stanza")
    _add_common_args(p_configure)
    p_configure.set_defaults(func=cmd_configure)

    p_push = sub.add_parser("push", help="Push model artifact(s) to the board")
    _add_common_args(p_push)
    p_push.add_argument("--model", help="Path to float/baseline model")
    p_push.add_argument("--model-int8", help="Path to int8-quantized model")
    p_push.set_defaults(func=cmd_push)

    p_profile = sub.add_parser("profile", help="Benchmark already-pushed model(s) on-device")
    _add_common_args(p_profile)
    p_profile.add_argument("--model", help="Path to float/baseline model (must already be pushed)")
    p_profile.add_argument("--model-int8", help="Path to int8-quantized model (must already be pushed)")
    p_profile.add_argument("--iters", type=int, default=50)
    p_profile.add_argument("--warmup", type=int, default=5)
    p_profile.add_argument("--duration", type=int, default=30, help="Duration (s) for CLI fallback (snpe-net-run)")
    p_profile.set_defaults(func=cmd_profile)

    p_report = sub.add_parser("report", help="detect + push + profile, rendered as a markdown report")
    _add_common_args(p_report)
    p_report.add_argument("--model", help="Path to float/baseline model")
    p_report.add_argument("--model-int8", help="Path to int8-quantized model")
    p_report.add_argument("--iters", type=int, default=50)
    p_report.add_argument("--warmup", type=int, default=5)
    p_report.add_argument("--duration", type=int, default=30)
    p_report.add_argument("--out", default=None, help="Output markdown path (default: board_profile_report_<board_id>.md)")
    p_report.set_defaults(func=cmd_report)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
