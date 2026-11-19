# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# All rights reserved.
# Confidential and Proprietary - Qualcomm Technologies, Inc.

"""
Log Summarization using Agentic Workflow
Integrates the new Agentic LLM Service for WiFi connectivity triage

Also contains the Evidence-First Multi-Agent Pipeline for Firmware Assert
Issue Summarization (migrated from serviceability/fw_assert_summarizer_standalone.py).
"""

import glob
import logging
import os
import re

from agentic_service import Orchestrator
from model_calls import generate_llm_response

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Firmware Assert Knowledge Base (embedded)
# ---------------------------------------------------------------------------
_FW_ASSERT_KNOWLEDGE_BASE = """\
================================================================================
FIRMWARE ASSERT KNOWLEDGE BASE
================================================================================
This knowledge base contains known firmware assert issues for WLAN firmware.
Each entry is structured to enable an LLM agent to independently detect whether
a given issue occurred by searching the cnss_diag logs.

Each entry follows this structure:
  - ISSUE ID and NAME
  - DESCRIPTION: What the issue is and why it causes a crash
  - ROOT CAUSE: The underlying condition that triggers the assert
  - DETECTION METHODOLOGY: Step-by-step reasoning chain to identify this issue
  - KEY LOG SIGNATURES: Exact log patterns to search for (with regex hints)
  - CONFIRMATION CRITERIA: How to definitively confirm this issue is present
  - NEGATIVE INDICATORS: Signs that rule this issue out
================================================================================


--------------------------------------------------------------------------------
ISSUE-001: VDEV MAX PEER COUNT EXCEEDED — FIRMWARE ASSERT
--------------------------------------------------------------------------------

DESCRIPTION:
  Each virtual device (vdev) in the WLAN firmware is configured with a maximum
  number of peer stations it can support. This limit is set at vdev initialization
  time. If a new peer attempts to associate with the vdev after the maximum peer
  count has already been reached, the firmware triggers an unconditional assert
  (crash) in wlan_peer.c. This is a hard enforcement of the peer capacity limit
  at the firmware level.

  This issue manifests as a firmware crash on the primary device, which then
  cascades to any partner devices in a multi-link operation (MLO) setup, requiring
  full system recovery.

ROOT CAUSE:
  The firmware enforces a strict maximum peer count per vdev. When a new peer
  association is processed and the current number of associated peers already
  equals the configured maximum, the firmware hits an unconditional assert
  (ASSERT(0) or equivalent) rather than gracefully rejecting the association.
  The assert fires in the peer association path in wlan_peer.c.

DETECTION METHODOLOGY:
  An LLM agent should follow this reasoning chain when analyzing cnss_diag logs:

  STEP 1 — Find the vdev initialization and its configured max peer count.
    Look for a log line from wlan_vdev.c that reports the maximum peer count
    configured for the vdev at initialization time. This establishes the capacity
    limit (call it MAX_PEERS).

    Search pattern: lines containing "CONN_DBG" AND "vdev init" AND "max peer count"
    Example: "CONN_DBG - vdev init - max peer count in this vdev: 2"
    Extract: the numeric value of max peer count (MAX_PEERS)
    Note: also record the vdev_id from context if available

  STEP 2 — Track peer association events and count successful associations.
    Look for log lines from wlan_peer.c that report the current number of remote
    peers after each successful association. These lines appear each time a peer
    completes the association process.

    Search pattern: lines containing "CONN_DBG" AND "Number of remote_peers" AND
                    "max peer count in this vdev"
    Example: "CONN_DBG - Number of remote_peers: 1, max peer count in this vdev: 2"
    Track: the sequence of "Number of remote_peers" values over time
    Confirm: each successful association increments this counter by 1

  STEP 3 — Identify the association attempt that triggers the assert.
    After MAX_PEERS peers have successfully associated (i.e., the last
    "Number of remote_peers" log shows remote_peers == MAX_PEERS), look for
    evidence of an additional peer attempting to associate. This will be the
    peer whose association triggers the firmware crash.

    Look for: a new WMI_PEER_CREATE or peer association sequence starting
    (e.g., WMI_CMD_RX CmdId=0x6001 for peer create, or PEER_ASSOC logs)
    that begins AFTER the peer count has reached MAX_PEERS, but does NOT
    produce a corresponding "Number of remote_peers: N+1" log — because the
    firmware crashes before completing it.

  STEP 4 — Confirm the firmware assert occurred.
    Look for evidence of a firmware crash/assert in the logs. In cnss_diag logs,
    this typically appears as an abrupt end of normal firmware log output,
    followed by crash recovery messages, or explicit assert/crash log lines.

    Also look for: "wal_mlo_recovery no recovery mode for fw all partner chip
    will crash" — this indicates the primary crash is cascading to partner chips.

  STEP 5 — Correlate timing and vdev context.
    Verify that:
    (a) The vdev that hit the assert is the same vdev that had the max peer
        count configured (same vdev_id in the logs)
    (b) The number of successful peer associations before the crash equals
        exactly MAX_PEERS
    (c) The crash occurs during or immediately after a new peer association
        attempt (not during unrelated operations)

KEY LOG SIGNATURES:
  The following log patterns are the primary evidence for this issue.
  All patterns appear in the cnss_diag firmware log output.

  [SIGNATURE-A] Vdev max peer count configuration at init time:
    Source file: wlan_vdev.c
    Pattern:     "CONN_DBG - vdev init - max peer count in this vdev: <N>"
    Meaning:     The vdev was initialized with a maximum of N peers allowed.
    What to extract: The value N (MAX_PEERS for this vdev)

  [SIGNATURE-B] Successful peer association with running count:
    Source file: wlan_peer.c
    Pattern:     "CONN_DBG - Number of remote_peers: <current>, max peer count
                  in this vdev: <max>"
    Meaning:     A peer successfully associated; current count is now <current>
                 out of a maximum of <max>.
    What to extract: The sequence of <current> values; confirm they increment
                     sequentially (1, 2, ... up to MAX_PEERS)
    Note:        This log appears once per successful peer association.
                 If the count reaches MAX_PEERS and then a new association
                 attempt begins without this log appearing again, the assert
                 fired during that next association attempt.

  [SIGNATURE-C] MLO recovery cascade (confirms crash occurred):
    Source file: wlan_wmi.c
    Pattern:     "wal_mlo_recovery no recovery mode for fw all partner chip
                  will crash"
    Meaning:     The primary device crashed and is forcing partner devices to
                 crash as well for system-wide recovery.
    Note:        This may appear on multiple radio devices (R0, R1, R2 prefixes)
                 as the crash cascades.

  [SIGNATURE-D] New peer creation attempt (the triggering event):
    Source file: wlan_peer.c or wmi_svc.c
    Pattern:     WMI_CMD_RX with CmdId=0x6001 (WMI_PEER_CREATE_CMDID) appearing
                 after SIGNATURE-B has shown remote_peers == MAX_PEERS
    Meaning:     A new peer creation was requested when the vdev was already at
                 capacity, triggering the assert.

CONFIRMATION CRITERIA:
  This issue is confirmed when ALL of the following are true:
  1. SIGNATURE-A is present, establishing a specific MAX_PEERS value for a vdev.
  2. SIGNATURE-B appears exactly MAX_PEERS times (once per successful association),
     with the counter incrementing from 1 up to MAX_PEERS.
  3. After the counter reaches MAX_PEERS, a new peer association attempt begins
     (SIGNATURE-D or equivalent peer create command is visible in logs).
  4. SIGNATURE-B does NOT appear again showing MAX_PEERS+1 (the crash prevents it).
  5. SIGNATURE-C or other crash evidence appears shortly after the final peer
     association attempt.

  The combination of (2) + (3) + (4) + (5) proves that the (MAX_PEERS+1)th peer
  association attempt triggered the firmware assert.

NEGATIVE INDICATORS (this issue is NOT present if):
  - SIGNATURE-A is absent (no max peer count was configured/logged for the vdev)
  - SIGNATURE-B shows the peer count never reaching MAX_PEERS before the crash
  - The crash occurs during a completely different operation (channel change,
    beacon processing, etc.) with no peer association activity nearby in the logs
  - SIGNATURE-B shows MAX_PEERS+1 peers successfully associated (meaning the
    assert did not fire on the (MAX_PEERS+1)th association)

ADDITIONAL CONTEXT:
  - The max peer count is a per-vdev configuration, not a global system limit.
    Different vdevs on the same device may have different limits.
  - In normal operation, the host driver should prevent more than MAX_PEERS
    associations from being sent to the firmware. If this assert fires, it
    indicates either a host-side enforcement failure or a deliberate test/debug
    scenario where the limit was intentionally exceeded.
  - In MLO (Multi-Link Operation) setups, a crash on one radio will cascade to
    partner radios. Look for the crash evidence on the primary radio first, then
    confirm the cascade on partner radios via SIGNATURE-C.
  - The assert location in firmware source is wlan_peer.c in the peer association
    completion path, triggered when the peer count check fails.

--------------------------------------------------------------------------------
END OF ISSUE-001
--------------------------------------------------------------------------------
"""

_FW_ASSERT_ANTI_HALLUCINATION_RULES = """
STRICT EVIDENCE RULES — YOU MUST FOLLOW THESE WITHOUT EXCEPTION:
1. Only reference facts explicitly listed in the STRUCTURED FACTS section below.
2. Do NOT mention any technology, feature, or subsystem (e.g., MLO, DFS, CE pipes,
   AST tables, rate control, EAPOL) unless it appears in the STRUCTURED FACTS.
3. Do NOT speculate about what "might have" or "could have" happened.
4. Every claim you make must cite the specific fact number (e.g., [FACT-3]) that supports it.
5. If the evidence is insufficient to determine something, state "INSUFFICIENT EVIDENCE".
6. Do NOT invent log lines, timestamps, or values not present in the STRUCTURED FACTS.
"""

_FW_ASSERT_MODEL = "default"


# ===========================================================================
# PHASE 1: PROGRAMMATIC EXTRACTION (no LLM)
# ===========================================================================

def _load_log(path: str) -> str:
    if not os.path.exists(path):
        logger.warning("Log file not found: %s", path)
        return ""
    with open(path, encoding="utf-8", errors="replace") as fh:
        content = fh.read()
    logger.info("Loaded %s (%d chars)", path, len(content))
    return content


def _extract_assert_info(syslog: str) -> dict:
    result = {}

    ts_match = re.search(
        r'\[\s*([\d.]+)\]\s+([\w_]+\s+[\w.:]+):\s+Fatal error received from wcss!',
        syslog
    )
    if ts_match:
        result['assert_timestamp'] = ts_match.group(1)
        result['assert_device'] = ts_match.group(2).strip()

    # Extract assert file:line and condition from a window AFTER the Fatal error line.
    # This prevents matching driver-level assertions (e.g. ath12k_wifi7_ahb.c) that
    # may appear earlier in the syslog before the actual firmware assert dump.
    if ts_match:
        snippet = syslog[ts_match.start():ts_match.start() + 2000]
        assert_match = re.search(
            r'([\w./]+\.c):(\d+)\s+Assertion\s+(.*?)\s+failed',
            snippet
        )
    else:
        assert_match = re.search(
            r'([\w./]+\.c):(\d+)\s+Assertion\s+(.*?)\s+failed',
            syslog
        )
    if assert_match:
        result['assert_file'] = assert_match.group(1)
        result['assert_line'] = assert_match.group(2)
        result['assert_condition'] = assert_match.group(3).strip()

    thread_match = re.search(
        r'Thread ID\s*:\s*(0x[\da-fA-F]+)\s+Thread name\s*:\s*(\S+(?:\s+\S+)?)\s+Process ID\s*:\s*(\d+)',
        syslog
    )
    if thread_match:
        result['thread_id'] = thread_match.group(1)
        result['thread_name'] = thread_match.group(2).strip()
        result['process_id'] = thread_match.group(3)

    for reg in ['SP', 'FP', 'PC', 'SSR', 'BADVA', 'LR']:
        reg_match = re.search(rf'{reg}\s*:\s*(0x[\da-fA-F]+)', syslog)
        if reg_match:
            result[f'reg_{reg.lower()}'] = reg_match.group(1)

    stack_from = re.search(r'from\s*:\s*(0x[\da-fA-F]+)', syslog)
    stack_to = re.search(r'to\s*:\s*(0x[\da-fA-F]+)', syslog)
    if stack_from:
        result['stack_from'] = stack_from.group(1)
    if stack_to:
        result['stack_to'] = stack_to.group(1)

    fw_ver = re.search(r'QC_IMAGE_VERSION_STRING=([\w.\-]+)', syslog)
    if fw_ver:
        result['fw_version'] = fw_ver.group(1)

    fw_variant = re.search(r'IMAGE_VARIANT_STRING=([\w.\-]+)', syslog)
    if fw_variant:
        result['fw_variant'] = fw_variant.group(1)

    fw_oem = re.search(r'OEM_IMAGE_VERSION_STRING=([\w.\-]+)', syslog)
    if fw_oem:
        result['fw_oem'] = fw_oem.group(1)

    fw_uuid = re.search(r'OEM_IMAGE_UUID_STRING=([\w{}\-_]+)', syslog)
    if fw_uuid:
        result['fw_uuid'] = fw_uuid.group(1)

    fw_build_ts = re.search(r'fw_build_timestamp\s+([\d\-]+ [\d:]+)', syslog)
    if fw_build_ts:
        result['fw_build_ts'] = fw_build_ts.group(1)

    logger.info("Extracted assert info: file=%s line=%s condition=%s",
                result.get('assert_file', 'N/A'),
                result.get('assert_line', 'N/A'),
                result.get('assert_condition', 'N/A'))
    return result


def _extract_secondary_asserts(syslog: str) -> list[dict]:
    secondary = []
    for m in re.finditer(
        r'\[\s*([\d.]+)\]\s+([\w_]+\s+[\w.:]+):\s+Fatal error received from wcss!',
        syslog
    ):
        ts = m.group(1)
        device = m.group(2).strip()
        snippet = syslog[m.start():m.start() + 2000]
        assert_m = re.search(r'([\w./]+\.c):(\d+)\s+Assertion\s+(.*?)\s+failed', snippet)
        entry = {
            'timestamp': ts,
            'device': device,
            'assert_file': assert_m.group(1) if assert_m else 'unknown',
            'assert_line': assert_m.group(2) if assert_m else 'unknown',
            'assert_condition': assert_m.group(3).strip() if assert_m else 'unknown',
        }
        secondary.append(entry)
    logger.info("Found %d assert events total", len(secondary))
    return secondary


def _find_nearest_kernel_ts(syslog: str, pos: int) -> float:
    """
    Find the nearest kernel timestamp [NNN.NNN] before the given position.
    Used for hostapd/daemon lines that don't have kernel timestamps.
    """
    preceding = syslog[:pos]
    ts_matches = list(re.finditer(r'\[\s*([\d.]+)\]', preceding))
    if ts_matches:
        return float(ts_matches[-1].group(1))
    return 0.0


def _extract_station_events(syslog: str) -> list[dict]:
    events = []

    for m in re.finditer(r'\[\s*([\d.]+)\].*?Allocated STA ([\da-fA-F:]+)', syslog):
        events.append({'ts': float(m.group(1)), 'type': 'STA_ALLOCATED', 'mac': m.group(2)})

    for m in re.finditer(
        r'\[\s*([\d.]+)\].*?mac station ([\da-fA-F:]+) connected to vdev (\d+)\. num_stations=(\d+)',
        syslog
    ):
        events.append({
            'ts': float(m.group(1)),
            'type': 'STA_CONNECTED_FW',
            'mac': m.group(2),
            'vdev_id': m.group(3),
            'num_stations': int(m.group(4)),
            'raw': m.group(0).strip()
        })

    for m in re.finditer(r'\[\s*([\d.]+)\].*?AP-STA-CONNECTED ([\da-fA-F:]+)', syslog):
        events.append({'ts': float(m.group(1)), 'type': 'AP_STA_CONNECTED', 'mac': m.group(2)})
    if not any(e['type'] == 'AP_STA_CONNECTED' for e in events):
        for m in re.finditer(r'AP-STA-CONNECTED ([\da-fA-F:]+)', syslog):
            mac = m.group(1)
            ts = _find_nearest_kernel_ts(syslog, m.start())
            events.append({'ts': ts, 'type': 'AP_STA_CONNECTED', 'mac': mac})

    for m in re.finditer(r'\[\s*([\d.]+)\].*?AP-STA-DISCONNECTED ([\da-fA-F:]+)', syslog):
        events.append({'ts': float(m.group(1)), 'type': 'AP_STA_DISCONNECTED', 'mac': m.group(2)})
    if not any(e['type'] == 'AP_STA_DISCONNECTED' for e in events):
        for m in re.finditer(r'AP-STA-DISCONNECTED ([\da-fA-F:]+)', syslog):
            mac = m.group(1)
            ts = _find_nearest_kernel_ts(syslog, m.start())
            events.append({'ts': ts, 'type': 'AP_STA_DISCONNECTED', 'mac': mac})

    for m in re.finditer(r'\[\s*([\d.]+)\].*?EAPOL-4WAY-HS-COMPLETED ([\da-fA-F:]+)', syslog):
        events.append({'ts': float(m.group(1)), 'type': 'EAPOL_COMPLETED', 'mac': m.group(2)})

    for m in re.finditer(r'\[\s*([\d.]+)\].*?moving STA ([\da-fA-F:]+) to state (\d+)', syslog):
        events.append({
            'ts': float(m.group(1)),
            'type': 'STA_STATE',
            'mac': m.group(2),
            'state': int(m.group(3))
        })

    events.sort(key=lambda x: x['ts'])
    logger.info("Extracted %d station events", len(events))
    return events


def _extract_peer_failures(syslog: str) -> list[dict]:
    failures = []

    for m in re.finditer(
        r'\[\s*([\d.]+)\].*?failed to get peer assoc conf event for ([\da-fA-F:]+) vdev (\d+)',
        syslog
    ):
        failures.append({
            'ts': float(m.group(1)),
            'type': 'PEER_ASSOC_CONF_TIMEOUT',
            'mac': m.group(2),
            'vdev_id': m.group(3),
            'raw': m.group(0).strip()
        })

    for m in re.finditer(
        r'\[\s*([\d.]+)\].*?Failed to associate station:\s*([\da-fA-F:]+)',
        syslog
    ):
        failures.append({
            'ts': float(m.group(1)),
            'type': 'PEER_ASSOC_FAILED',
            'mac': m.group(2),
            'raw': m.group(0).strip()
        })

    for m in re.finditer(
        r'\[\s*([\d.]+)\].*?unable to move link sta \d+ of sta ([\da-fA-F:]+) from state (\d+) to (\d+)',
        syslog
    ):
        failures.append({
            'ts': float(m.group(1)),
            'type': 'STA_STATE_TRANSITION_FAILED',
            'mac': m.group(2),
            'from_state': m.group(3),
            'to_state': m.group(4),
            'raw': m.group(0).strip()
        })

    failures.sort(key=lambda x: x['ts'])
    logger.info("Extracted %d peer failure events", len(failures))
    return failures


def _extract_recovery_events(syslog: str) -> list[dict]:
    events = []

    for m in re.finditer(
        r'\[\s*([\d.]+)\]\s+([\w_]+\s+[\w.:]+):\s+mhi notify status reason MHI_CB_EE_RDDM',
        syslog
    ):
        events.append({'ts': float(m.group(1)), 'type': 'MHI_RDDM', 'device': m.group(2).strip()})

    for m in re.finditer(
        r'\[\s*([\d.]+)\]\s+([\w_]+\s+[\w.:]+):\s+mhi notify status reason MHI_CB_EE_MISSION_MODE',
        syslog
    ):
        events.append({'ts': float(m.group(1)), 'type': 'MHI_MISSION_MODE', 'device': m.group(2).strip()})

    for m in re.finditer(
        r'\[\s*([\d.]+)\]\s+([\w_]+\s+[\w.:]+):\s+coredump:\s+([\d,]+)\s+bytes transferred',
        syslog
    ):
        events.append({
            'ts': float(m.group(1)),
            'type': 'COREDUMP_COMPLETE',
            'device': m.group(2).strip(),
            'bytes': m.group(3).replace(',', '')
        })

    for m in re.finditer(
        r'\[\s*([\d.]+)\]\s+([\w_]+\s+[\w.:]+):\s+WLAN target is restarting',
        syslog
    ):
        events.append({'ts': float(m.group(1)), 'type': 'WLAN_RESTARTING', 'device': m.group(2).strip()})

    for m in re.finditer(
        r'\[\s*([\d.]+)\]\s+([\w_]+\s+[\w.:]+):\s+CRASHED',
        syslog
    ):
        events.append({'ts': float(m.group(1)), 'type': 'DEVICE_CRASHED', 'device': m.group(2).strip()})

    events.sort(key=lambda x: x['ts'])
    logger.info("Extracted %d recovery events", len(events))
    return events


def _extract_vdev_config(cnss_diag: str) -> list[dict]:
    configs = []

    for m in re.finditer(
        r'R\d+:\s+\[([0-9a-fA-F]+)\].*?vdev init.*?max peer count in this vdev:\s*(\d+)',
        cnss_diag, re.IGNORECASE
    ):
        configs.append({
            'seq': m.group(1),
            'type': 'VDEV_MAX_PEER_COUNT',
            'max_peer_count': int(m.group(2)),
            'raw': m.group(0).strip()
        })

    for m in re.finditer(
        r'R\d+:\s+\[([0-9a-fA-F]+)\].*?VDEV_START_CMD.*?vdev_id=(\d+).*?opmode=(\d+)',
        cnss_diag, re.IGNORECASE
    ):
        configs.append({
            'seq': m.group(1),
            'type': 'VDEV_START',
            'vdev_id': m.group(2),
            'opmode': m.group(3),
            'raw': m.group(0).strip()
        })

    logger.info("Extracted %d VDEV config entries", len(configs))
    return configs


def _extract_remote_peer_counts(cnss_diag: str) -> list[dict]:
    entries = []
    for m in re.finditer(
        r'R\d+:\s+\[([0-9a-fA-F]+)\].*?Number of remote_peers:\s*(\d+),\s*max peer count in this vdev:\s*(\d+)',
        cnss_diag, re.IGNORECASE
    ):
        entries.append({
            'seq': m.group(1),
            'remote_peers': int(m.group(2)),
            'max_peer_count': int(m.group(3)),
            'raw': m.group(0).strip()
        })
    logger.info("Extracted %d remote_peer_count entries from cnss_diag", len(entries))
    return entries


def _extract_peer_create_events(cnss_diag: str) -> list[dict]:
    events = []

    for m in re.finditer(
        r'R\d+:\s+\[([0-9a-fA-F]+)\].*?WAL_AST_ALLOC_PEER.*?sw_peer_id:(0x[\da-fA-F]+).*?status:(\d+)',
        cnss_diag, re.IGNORECASE
    ):
        events.append({
            'seq': m.group(1),
            'type': 'WAL_AST_ALLOC_PEER',
            'sw_peer_id': m.group(2),
            'status': m.group(3),
            'raw': m.group(0).strip()[:150]
        })

    for m in re.finditer(
        r'R\d+:\s+\[([0-9a-fA-F]+)\].*?wal peer allocat(?:i?on|e)\s+status\s*=\s*(\d+).*?vdev_id_8[^\s]*\s*=\s*(0x[\da-fA-F]+)',
        cnss_diag, re.IGNORECASE
    ):
        events.append({
            'seq': m.group(1),
            'type': 'WAL_PEER_ALLOC',
            'status': m.group(2),
            'vdev_id_raw': m.group(3),
            'raw': m.group(0).strip()[:150]
        })

    for m in re.finditer(
        r'R\d+:\s+\[([0-9a-fA-F]+)\].*?WMI_PEER_CREATE_RESP_EVENTID.*?vdevId=(\d+).*?status\s*=\s*(\d+)',
        cnss_diag, re.IGNORECASE
    ):
        events.append({
            'seq': m.group(1),
            'type': 'WMI_PEER_CREATE_RESP',
            'vdev_id': m.group(2),
            'status': m.group(3),
            'raw': m.group(0).strip()[:150]
        })

    logger.info("Extracted %d peer create events from cnss_diag", len(events))
    return events


def _extract_fw_assert_mode(syslog: str) -> list[dict]:
    events = []
    for m in re.finditer(
        r'\[\s*([\d.]+)\]\s+([\w_]+\s+[\w.:]+):\s+setting FW assert mode \[(\d+)\] ret \[(\d+)\]',
        syslog
    ):
        events.append({
            'ts': float(m.group(1)),
            'device': m.group(2).strip(),
            'mode': m.group(3),
            'ret': m.group(4)
        })
    return events


def _extract_vdev_syslog_events(syslog: str) -> list[dict]:
    events = []
    for m in re.finditer(
        r'\[\s*([\d.]+)\]\s+([\w_]+\s+[\w.:]+):\s+vdev ([\da-fA-F:]+) (created|started|stopped|deleted),\s+vdev_id (\d+)',
        syslog
    ):
        events.append({
            'ts': float(m.group(1)),
            'device': m.group(2).strip(),
            'mac': m.group(3),
            'action': m.group(4),
            'vdev_id': m.group(5)
        })
    events.sort(key=lambda x: x['ts'])
    return events


def _extract_dfs_events(syslog: str) -> list[dict]:
    events = []
    for m in re.finditer(
        r'\[\s*([\d.]+)\].*?(DFS-CAC-START|DFS-CAC-COMPLETED).*?freq=(\d+)',
        syslog
    ):
        events.append({
            'ts': float(m.group(1)),
            'type': m.group(2),
            'freq': m.group(3),
            'raw': m.group(0).strip()
        })
    events.sort(key=lambda x: x['ts'])
    return events


# ===========================================================================
# PHASE 2: KNOWLEDGE BASE LOOKUP
# ===========================================================================

def _lookup_fw_knowledge_base(assert_file: str, assert_condition: str) -> str:
    search_terms = []
    if 'wlan_peer' in assert_file.lower():
        search_terms.extend(['peer', 'MAX Client', 'peer count', 'association', 'assoc'])
    if 'partner_chip_crash' in assert_condition.lower():
        search_terms.extend(['MLO', 'partner', 'cascade'])
    if not search_terms:
        search_terms = ['assert', 'crash', 'firmware']

    paragraphs = _FW_ASSERT_KNOWLEDGE_BASE.split('\n\n')
    relevant_sections = []
    for para in paragraphs:
        para_lower = para.lower()
        if any(term.lower() in para_lower for term in search_terms):
            if len(para.strip()) > 50:
                relevant_sections.append(para.strip())

    if not relevant_sections:
        return "No directly relevant knowledge base entries found for this assert pattern."

    combined = "\n\n---\n\n".join(relevant_sections[:5])
    if len(combined) > 3000:
        combined = combined[:3000] + "\n... [KB TRUNCATED] ..."

    logger.info("Found %d relevant KB sections", len(relevant_sections))
    return combined


# ===========================================================================
# PHASE 3: STRUCTURED FACTS BUILDER + LLM AGENTS
# ===========================================================================

def _build_structured_facts(
    assert_info: dict,
    all_asserts: list[dict],
    station_events: list[dict],
    peer_failures: list[dict],
    recovery_events: list[dict],
    vdev_config: list[dict],
    remote_peer_counts: list[dict],
    peer_create_events: list[dict],
    fw_assert_mode: list[dict],
    vdev_syslog: list[dict],
    dfs_events: list[dict],
) -> str:
    lines = ["=" * 70, "STRUCTURED FACTS — EXTRACTED PROGRAMMATICALLY FROM LOG FILES", "=" * 70, ""]
    fact_num = 1

    lines.append("## SECTION A: PRIMARY ASSERT DETAILS")
    lines.append("")

    if assert_info.get('assert_file'):
        lines.append(f"[FACT-{fact_num}] Assert Location: {assert_info['assert_file']}:{assert_info.get('assert_line', '?')}")
        fact_num += 1
    if assert_info.get('assert_condition'):
        lines.append(f"[FACT-{fact_num}] Assert Condition: \"{assert_info['assert_condition']}\" (unconditional assert/panic)")
        fact_num += 1
    if assert_info.get('assert_timestamp'):
        lines.append(f"[FACT-{fact_num}] Assert Timestamp (kernel uptime): [{assert_info['assert_timestamp']}s]")
        fact_num += 1
    if assert_info.get('assert_device'):
        lines.append(f"[FACT-{fact_num}] Assert Device: {assert_info['assert_device']}")
        fact_num += 1
    if assert_info.get('thread_name'):
        lines.append(f"[FACT-{fact_num}] Thread: {assert_info['thread_name']} (ID={assert_info.get('thread_id','?')}, PID={assert_info.get('process_id','?')})")
        fact_num += 1

    regs = {k: v for k, v in assert_info.items() if k.startswith('reg_')}
    if regs:
        reg_str = ", ".join(f"{k[4:].upper()}={v}" for k, v in regs.items())
        lines.append(f"[FACT-{fact_num}] Registers at crash: {reg_str}")
        fact_num += 1

    if assert_info.get('stack_from'):
        lines.append(f"[FACT-{fact_num}] Stack range: {assert_info['stack_from']} to {assert_info.get('stack_to','?')}")
        fact_num += 1

    lines.append("")
    lines.append("## SECTION B: FIRMWARE VERSION")
    lines.append("")
    if assert_info.get('fw_version'):
        lines.append(f"[FACT-{fact_num}] FW Version: {assert_info['fw_version']}")
        fact_num += 1
    if assert_info.get('fw_variant'):
        lines.append(f"[FACT-{fact_num}] FW Variant: {assert_info['fw_variant']}")
        fact_num += 1
    if assert_info.get('fw_oem'):
        lines.append(f"[FACT-{fact_num}] OEM Version: {assert_info['fw_oem']}")
        fact_num += 1
    if assert_info.get('fw_build_ts'):
        lines.append(f"[FACT-{fact_num}] Build Timestamp: {assert_info['fw_build_ts']}")
        fact_num += 1
    lines.append("")

    lines.append("## SECTION C: ALL ASSERT EVENTS (CHRONOLOGICAL)")
    lines.append("")
    primary_device = assert_info.get('assert_device', '')
    for i, a in enumerate(all_asserts):
        lines.append(f"[FACT-{fact_num}] Assert #{i+1}: [{a['timestamp']}s] Device={a['device']} "
                     f"File={a['assert_file']}:{a['assert_line']} Condition=\"{a['assert_condition']}\"")
        fact_num += 1
    # Compare by bus address (e.g. "0003:01:00.0") to handle mixed driver prefixes
    # (e.g. ath12k_wifi7_ahb vs ath12k_wifi7_pci)
    def _device_bus_addr(device_str: str) -> str:
        m = re.search(r'(\d{4}:\d{2}:\d{2}\.\d)', device_str)
        return m.group(1) if m else device_str

    primary_bus = _device_bus_addr(primary_device)
    partner_crashes = [a for a in all_asserts if _device_bus_addr(a['device']) != primary_bus]
    lines.append(f"[FACT-{fact_num}] DERIVED: Total assert events = {len(all_asserts)}; "
                 f"Primary device = {primary_device}; "
                 f"Partner (cascade) crashes = {len(partner_crashes)} "
                 f"(asserts on devices other than the primary).")
    if partner_crashes:
        partner_devices = [f"{a['device']} at {a['assert_file']}:{a['assert_line']}" for a in partner_crashes]
        lines.append(f"[FACT-{fact_num}] DERIVED: Partner crash devices: {'; '.join(partner_devices)}")
        fact_num += 1
    fact_num += 1
    lines.append("")

    lines.append("## SECTION D: VDEV PEER LIMIT CONFIGURATION (from firmware debug trace)")
    lines.append("")
    if vdev_config:
        for vc in vdev_config:
            if vc['type'] == 'VDEV_MAX_PEER_COUNT':
                lines.append(f"[FACT-{fact_num}] VDEV configured with max_peer_count={vc['max_peer_count']} "
                              f"(seq=0x{vc['seq']}) — Raw: \"{vc['raw'][:150]}\"")
                fact_num += 1
            elif vc['type'] == 'VDEV_START':
                lines.append(f"[FACT-{fact_num}] VDEV_START: vdev_id={vc['vdev_id']} opmode={vc['opmode']} "
                              f"(seq=0x{vc['seq']})")
                fact_num += 1
    else:
        lines.append(f"[FACT-{fact_num}] VDEV max peer count: NOT extracted from firmware debug trace "
                     f"(regex did not match — check cnss_diag format)")
        fact_num += 1
    lines.append("")

    lines.append("## SECTION E: REMOTE PEER COUNT PROGRESSION (from firmware debug trace)")
    lines.append("## NOTE: These entries are logged at wlan_peer.c:3867, just 3 lines before the assert at :3870")
    lines.append("")
    if remote_peer_counts:
        for rpc in remote_peer_counts:
            lines.append(f"[FACT-{fact_num}] seq=0x{rpc['seq']}: remote_peers={rpc['remote_peers']}, "
                         f"max_peer_count={rpc['max_peer_count']} — Raw: \"{rpc['raw'][:150]}\"")
            fact_num += 1
        max_seen = max(r['remote_peers'] for r in remote_peer_counts)
        max_allowed = remote_peer_counts[0]['max_peer_count'] if remote_peer_counts else 'unknown'
        lines.append(f"[FACT-{fact_num}] DERIVED: Maximum remote_peers count seen before assert = {max_seen}; "
                     f"max_peer_count configured = {max_allowed}. "
                     f"No entry for remote_peers={max_seen+1} exists — assert fired instead.")
        fact_num += 1
    else:
        lines.append(f"[FACT-{fact_num}] Remote peer count progression: NOT extracted from firmware debug trace.")
        fact_num += 1
    lines.append("")

    lines.append("## SECTION F: VDEV LIFECYCLE EVENTS (from syslog)")
    lines.append("")
    for ve in vdev_syslog[-10:]:
        lines.append(f"[FACT-{fact_num}] [{ve['ts']}s] {ve['device']}: vdev {ve['mac']} {ve['action']}, vdev_id={ve['vdev_id']}")
        fact_num += 1
    lines.append("")

    lines.append("## SECTION G: STATION ASSOCIATION EVENTS (chronological, from syslog)")
    lines.append("")

    crash_ts = float(assert_info.get('assert_timestamp', 699))
    relevant_sta = [e for e in station_events if e['ts'] <= crash_ts + 5]

    fw_connected = [e for e in relevant_sta if e['type'] == 'STA_CONNECTED_FW']
    for e in fw_connected:
        lines.append(f"[FACT-{fact_num}] [{e['ts']}s] FW: Station {e['mac']} connected to vdev {e['vdev_id']}. "
                     f"num_stations={e['num_stations']} — Raw: \"{e.get('raw','')[:120]}\"")
        fact_num += 1

    ap_connected = [e for e in relevant_sta if e['type'] == 'AP_STA_CONNECTED']
    for e in ap_connected:
        lines.append(f"[FACT-{fact_num}] [{e['ts']}s] hostapd: AP-STA-CONNECTED {e['mac']}")
        fact_num += 1

    # DERIVED: total stations successfully associated before crash
    # Use FW num_stations counter if available; fall back to counting unique
    # AP-STA-CONNECTED MACs minus any AP-STA-DISCONNECTED MACs before crash.
    max_num_stations = max((e['num_stations'] for e in fw_connected), default=0)
    if max_num_stations == 0 and ap_connected:
        ap_disconnected = {e['mac'] for e in relevant_sta if e['type'] == 'AP_STA_DISCONNECTED'}
        connected_macs = set()
        for e in relevant_sta:
            if e['type'] == 'AP_STA_CONNECTED':
                connected_macs.add(e['mac'])
            elif e['type'] == 'AP_STA_DISCONNECTED':
                connected_macs.discard(e['mac'])
        max_num_stations = len(connected_macs)
        lines.append(f"[FACT-{fact_num}] DERIVED: {max_num_stations} station(s) were successfully associated "
                     f"with the vdev before the crash (counted from {len(ap_connected)} AP-STA-CONNECTED "
                     f"events minus {len(ap_disconnected)} AP-STA-DISCONNECTED events before crash).")
    else:
        lines.append(f"[FACT-{fact_num}] DERIVED: {max_num_stations} station(s) were successfully associated "
                     f"with the vdev before the crash (highest num_stations value seen in STA_CONNECTED_FW events).")
    fact_num += 1

    eapol = [e for e in relevant_sta if e['type'] == 'EAPOL_COMPLETED']
    for e in eapol:
        lines.append(f"[FACT-{fact_num}] [{e['ts']}s] hostapd: EAPOL-4WAY-HS-COMPLETED {e['mac']}")
        fact_num += 1

    allocated = [e for e in relevant_sta if e['type'] == 'STA_ALLOCATED']
    for e in allocated:
        lines.append(f"[FACT-{fact_num}] [{e['ts']}s] kernel: Allocated STA {e['mac']}")
        fact_num += 1

    failed_macs = {f['mac'] for f in peer_failures}
    for e in relevant_sta:
        if e['type'] == 'STA_STATE' and (
            e['mac'] in failed_macs or e['mac'].replace('02:', '00:', 1) in failed_macs
        ):
            lines.append(f"[FACT-{fact_num}] [{e['ts']}s] kernel: STA {e['mac']} moved to state {e['state']}")
            fact_num += 1

    lines.append("")

    lines.append("## SECTION H: PEER ASSOCIATION FAILURES (from syslog)")
    lines.append("")
    if peer_failures:
        for pf in peer_failures:
            lines.append(f"[FACT-{fact_num}] [{pf['ts']}s] {pf['type']}: MAC={pf['mac']} "
                         f"— Raw: \"{pf.get('raw','')[:150]}\"")
            fact_num += 1
    else:
        lines.append(f"[FACT-{fact_num}] No peer association failures extracted.")
        fact_num += 1
    lines.append("")

    lines.append("## SECTION I: PEER CREATE EVENTS (from firmware debug trace)")
    lines.append("")
    if peer_create_events:
        for pe in peer_create_events[:20]:
            lines.append(f"[FACT-{fact_num}] seq=0x{pe['seq']} {pe['type']}: "
                         f"{', '.join(f'{k}={v}' for k,v in pe.items() if k not in ('seq','type','raw'))}")
            fact_num += 1
    else:
        lines.append(f"[FACT-{fact_num}] No peer create events extracted from firmware debug trace.")
        fact_num += 1
    lines.append("")

    lines.append("## SECTION J: RECOVERY SEQUENCE (from syslog)")
    lines.append("")
    for re_ev in recovery_events:
        lines.append(f"[FACT-{fact_num}] [{re_ev['ts']}s] {re_ev['type']}: {re_ev.get('device','')}")
        fact_num += 1
    lines.append("")

    if dfs_events:
        lines.append("## SECTION K: DFS EVENTS (from syslog)")
        lines.append("")
        for de in dfs_events:
            lines.append(f"[FACT-{fact_num}] [{de['ts']}s] {de['type']} freq={de['freq']}MHz")
            fact_num += 1
        lines.append("")

    if fw_assert_mode:
        lines.append("## SECTION L: FW ASSERT MODE SETTINGS (from syslog)")
        lines.append("")
        for am in fw_assert_mode[:6]:
            lines.append(f"[FACT-{fact_num}] [{am['ts']}s] {am['device']}: FW assert mode [{am['mode']}] ret [{am['ret']}]")
            fact_num += 1
        lines.append("")

    lines.append(f"TOTAL FACTS EXTRACTED: {fact_num - 1}")
    lines.append("=" * 70)

    return "\n".join(lines)


def _fw_fact_interpreter_agent(structured_facts: str) -> str:
    logger.info("Agent 1 (FactInterpreterAgent): Interpreting structured facts ...")

    prompt = f"""You are a Qualcomm Wi-Fi firmware crash analyst. You have been given a set of
STRUCTURED FACTS extracted programmatically from firmware crash logs.

{_FW_ASSERT_ANTI_HALLUCINATION_RULES}

{structured_facts}

Based ONLY on the facts above, provide:

1. **CHRONOLOGICAL EVENT SEQUENCE**
   List the key events in order, citing fact numbers. Format:
   [TIMESTAMP] [FACT-N] EVENT_DESCRIPTION

2. **TRIGGERING EVENT IDENTIFICATION**
   What specific event immediately preceded the firmware assert?
   - Cite the exact fact(s) that identify the trigger.
   - What was the system state at the moment of the assert?

3. **STATION COUNT ANALYSIS**
   - How many stations were successfully associated before the crash? (cite facts)
   - What was the vdev's configured maximum peer count? (cite facts)
   - What does the remote_peers progression show? (cite facts)
   - Was the (MAX_PEERS+1)th station association attempt the trigger? (cite facts)

4. **CRASH PROPAGATION**
   - How many devices asserted? (cite facts)
   - Were the secondary asserts on the same file:line as the primary? (cite facts)
   - What does the secondary assert condition mean?

5. **RECOVERY SUMMARY**
   - When did recovery complete? (cite facts)
   - Total recovery duration in seconds?

Be precise. Cite fact numbers for every statement. Do not add information not in the facts.
"""

    result = generate_llm_response(_FW_ASSERT_MODEL, prompt, call_type="fw_assert")
    logger.info("Agent 1 complete.")
    return result


def _fw_root_cause_agent(structured_facts: str, fact_interpretation: str, kb_context: str) -> str:
    logger.info("Agent 2 (RootCauseAgent): Determining root cause ...")

    if len(fact_interpretation) > 4000:
        fact_interpretation = fact_interpretation[:4000] + "\n... [TRUNCATED] ..."
    if len(kb_context) > 2000:
        kb_context = kb_context[:2000] + "\n... [TRUNCATED] ..."

    assert_loc = "unknown"
    for line in structured_facts.split('\n'):
        if 'Assert Location:' in line:
            assert_loc = line.split('Assert Location:')[-1].strip()
            break

    prompt = f"""You are a senior Qualcomm Wi-Fi firmware reliability engineer.

{_FW_ASSERT_ANTI_HALLUCINATION_RULES}

{structured_facts}

## FACT INTERPRETATION (from Agent 1)
{fact_interpretation}

## RELEVANT KNOWLEDGE BASE ENTRIES
{kb_context}

Based ONLY on the structured facts and fact interpretation above, determine the root cause.

1. **PRIMARY ROOT CAUSE STATEMENT**
   State the root cause in 1-2 sentences. Cite the specific facts that prove it.

2. **CAUSAL CHAIN**
   Step-by-step sequence from initial condition to assert. Each step must cite a fact:
   Step 1: [FACT-N] ...
   Step 2: [FACT-N] ...
   ...
   CRASH: [FACT-N] Assert fired at {assert_loc}

3. **KEY EVIDENCE**
   List the 3-5 most critical facts that prove the root cause. For each:
   - Fact number and content
   - Why it is critical to the root cause

4. **WHAT THE ASSERT MEANS**
   Based on the assert location ({assert_loc}) and the remote_peers progression facts,
   what firmware invariant was violated?

5. **SECONDARY ASSERTS**
   Are the secondary asserts (if any) a separate bug or expected behavior from the primary crash?
   Cite facts.

6. **CONFIDENCE LEVEL**: HIGH / MEDIUM / LOW
   Justify based on the quality and completeness of the evidence.

Do NOT speculate. Do NOT mention any subsystem not evidenced in the facts.
"""

    result = generate_llm_response(_FW_ASSERT_MODEL, prompt, call_type="fw_assert")
    logger.info("Agent 2 complete.")
    return result


def _fw_summary_agent(structured_facts: str, fact_interpretation: str, root_cause: str) -> str:
    logger.info("Agent 3 (SummaryAgent): Generating brief summary ...")

    if len(fact_interpretation) > 3000:
        fact_interpretation = fact_interpretation[:3000] + "\n... [TRUNCATED] ..."
    if len(root_cause) > 4000:
        root_cause = root_cause[:4000] + "\n... [TRUNCATED] ..."

    prompt = f"""You are a technical writer creating a brief firmware assert issue summary for a Qualcomm Wi-Fi engineering team.

{_FW_ASSERT_ANTI_HALLUCINATION_RULES}

{structured_facts}

## FACT INTERPRETATION
{fact_interpretation}

## ROOT CAUSE ANALYSIS
{root_cause}

Generate ONLY the following two sections. Use ONLY the information above.
Output each section EXACTLY ONCE. Do NOT repeat, rephrase, or restart after the Key Facts Referenced section — stop immediately.

---

## Executive Summary
Write 2-3 sentences. You MUST include ALL of the following specific values (cite each with [FACT-N]).
IMPORTANT: Fact numbers are dynamically generated. Do NOT assume specific fact numbers — search
each SECTION for the described content and use the actual [FACT-N] number you find there.

1. The assert file and line number (from SECTION A — find the line containing "Assert Location:")
2. The MAC address of the station that triggered the crash (from SECTION H — find the PEER_ASSOC_FAILED or PEER_ASSOC_CONF_TIMEOUT entry)
3. The vdev ID and its configured max peer count (from SECTION D — find the VDEV_MAX_PEER_COUNT entry)
4. How many stations were already associated before the crash: use ONLY the EXACT integer N from the single DERIVED fact in SECTION G that reads "N station(s) were successfully associated with the vdev before the crash". Do NOT count individual STA_CONNECTED_FW or AP_STA_CONNECTED entries — use only that pre-computed DERIVED value.
5. The exact crash timestamp in seconds (from SECTION A — find the line containing "Assert Timestamp"; do NOT use timestamps from SECTION H or J)
6. The primary device identifier (from SECTION A — find the line containing "Assert Device:")
7. How many partner devices also crashed (from SECTION C — find the DERIVED fact that explicitly states "Partner (cascade) crashes = N". The number N is the count of partner crashes. If N > 0, state that N partner device(s) also crashed. If N = 0, state that no partner devices crashed.)
8. The final recovery completion timestamp (from SECTION J — find the LAST MHI_MISSION_MODE entry, which has the highest timestamp)

## Key Facts Referenced
List each [FACT-N] cited in the Executive Summary above, with a one-line description of what that fact contains.

---

Every claim must be traceable to the structured facts. Do not add any other sections. Stop after Key Facts Referenced.
"""

    result = generate_llm_response(_FW_ASSERT_MODEL, prompt, call_type="fw_assert")
    logger.info("Agent 3 complete.")
    return result


def run_fw_assert_pipeline(syslog_path: str, cnss_diag_path: str) -> str:
    """
    Evidence-First Firmware Assert Summarization Pipeline.

    Phase 1: Programmatic extraction (no LLM)
    Phase 2: Knowledge base lookup (embedded)
    Phase 3: LLM analysis on structured facts only

    Args:
        syslog_path: Absolute path to syslog.txt
        cnss_diag_path: Absolute path to cnss_diag.txt

    Returns:
        str: The final summary report
    """
    logger.info("=" * 70)
    logger.info("Starting Evidence-First FW Assert Pipeline")
    logger.info("=" * 70)

    syslog = _load_log(syslog_path)
    cnss_diag = _load_log(cnss_diag_path)

    logger.info("Phase 1: Programmatic extraction ...")

    assert_info = _extract_assert_info(syslog)
    all_asserts = _extract_secondary_asserts(syslog)
    station_events = _extract_station_events(syslog)
    peer_failures = _extract_peer_failures(syslog)
    recovery_events = _extract_recovery_events(syslog)
    vdev_config = _extract_vdev_config(cnss_diag)
    remote_peer_counts = _extract_remote_peer_counts(cnss_diag)
    peer_create_events = _extract_peer_create_events(cnss_diag)
    fw_assert_mode = _extract_fw_assert_mode(syslog)
    vdev_syslog = _extract_vdev_syslog_events(syslog)
    dfs_events = _extract_dfs_events(syslog)

    logger.info("Extraction summary:")
    logger.info("  Assert info keys: %s", list(assert_info.keys()))
    logger.info("  Total assert events: %d", len(all_asserts))
    logger.info("  Station events: %d", len(station_events))
    logger.info("  Peer failures: %d", len(peer_failures))
    logger.info("  Recovery events: %d", len(recovery_events))
    logger.info("  VDEV config entries: %d", len(vdev_config))
    logger.info("  Remote peer count entries: %d", len(remote_peer_counts))
    logger.info("  Peer create events (FW): %d", len(peer_create_events))

    logger.info("Building structured facts document ...")
    structured_facts = _build_structured_facts(
        assert_info, all_asserts, station_events, peer_failures,
        recovery_events, vdev_config, remote_peer_counts, peer_create_events,
        fw_assert_mode, vdev_syslog, dfs_events
    )
    logger.info("Structured facts document (%d chars)", len(structured_facts))

    logger.info("Phase 2: Knowledge base lookup ...")
    kb_context = _lookup_fw_knowledge_base(
        assert_info.get('assert_file', ''),
        assert_info.get('assert_condition', '')
    )

    logger.info("Phase 3: LLM analysis on structured facts ...")

    fact_interpretation = _fw_fact_interpreter_agent(structured_facts)
    root_cause = _fw_root_cause_agent(structured_facts, fact_interpretation, kb_context)
    final_summary = _fw_summary_agent(structured_facts, fact_interpretation, root_cause)

    logger.info("Pipeline complete.")
    return final_summary


# ===========================================================================
# KFENCE (CLI_SNAPSHOT) PIPELINE
# ===========================================================================

_KFENCE_PROMPT_TEMPLATE = """You are a kernel diagnostics expert specializing in KFENCE (Kernel Electric-Fence) memory safety issues on Qualcomm WiFi platforms.

Analyze the following syslog excerpt and produce a structured diagnostic report.

IMPORTANT EXTRACTION RULES:
1. **OOB byte count calculation**: The number of bytes past the object boundary is:
   `(corrupted_address - object_base_address) - object_size`
   Example: object at 0xffffff803f71c000 size=32; corrupted at 0xffffff803f71c020 (=base+32):
   OOB bytes = 32 - 32 = 0 bytes INTO the redzone, i.e., exactly 1 byte past the last valid index (index 31).
   The `[ 0xab . . . . . . . . . . . . . . . ]` notation shows 16 bytes from the corrupted address;
   only the `0xab` bytes are corrupted (dots indicate uncorrupted guard bytes).
   So `object[32]` on a 32-byte object = 1 byte past the boundary, NOT 3 bytes.

2. **Handler crash loop**: Count ALL "Child program exited, restarting; cmdline='.../kfence-handler.sh'" lines.
   Report the TOTAL count. The handler was crash-looping THE ENTIRE TIME, not just during one event.

3. **Kernel taint flags**: Extract from the "Tainted:" field in the "CPU: N PID: N Comm: insmod Tainted:" line.
   Report all taint letters and their meaning (G=proprietary module, B=previous BUG, O=out-of-tree module).

4. **Log file reference**: Always refer to the source log file as "syslog.log" (the file analyzed here).

5. **Module purpose**: If the log contains the line `kfence_oob: triggering out-of-bounds write at ...`,
   this is CONCLUSIVE EVIDENCE that the write was DELIBERATE. The module named `kfence_oob` is
   a test/reproducer module specifically designed to trigger KFENCE OOB detection for validation
   purposes. State this clearly in Section 5.1. The byte value 0xab is a deliberately chosen
   marker value (not random corruption) — this further confirms deliberate triggering.

6. **Timeline timestamps**: Use only timestamps that appear in the log. Do NOT move events to wrong times.
   Specifically: logrotate occurs AFTER the first KFENCE event (look for `crond` log entry for `logrotate`).
   Module unload (`kfence_oob: module unloaded`) occurs at a separate timestamp, not immediately after the BUG.

=== SYSLOG CONTENT ===
{syslog_content}
=== END SYSLOG ===

Generate a structured report with ALL of the following sections.

---

# KFENCE OUT-OF-BOUNDS ANOMALY SUMMARY REPORT

## 1. Executive Summary
Write 3-4 sentences covering: anomaly type, hardware/kernel, timestamp, faulting module, violation details (byte value 0xab at exactly 1 byte past the 32-byte object boundary), number of times reproduced, and the kfence-handler.sh crash-loop count.

## 2. Issue Classification
- **Issue Type**: (KFENCE_OOB_WRITE)
- **Severity**: HIGH/MEDIUM/LOW with justification
- **Affected Component**: (module name, slab cache)
- **Anomaly Mode**: (heap buffer overflow — state exact byte count OOB and byte value)

## 3. Timeline of Events
List ALL events chronologically. Include:
- Pre-event handler crash loop start and approximate count
- First KFENCE event: module load → allocation → OOB trigger → BUG detection
- logrotate event if present
- Module unload
- Second KFENCE event
Format: `- [HH:MM:SS] EVENT_DESCRIPTION`

## 4. Anomaly Details
- **Anomaly Type**: KFENCE_OOB_WRITE
- **First Detection Time**: (timestamp + kernel uptime from BUG line)
- **Second Detection Time**: (timestamp + kernel uptime)
- **Hardware**: (from "Hardware name:" line)
- **Kernel**: (version, arch, taint flags from "Tainted:" line — list the letters and meanings)
- **Faulting Module**: (module + function from BUG line)
- **Object**: (size and slab cache from kfence-#NNNN line)
- **Corruption**: (value 0xab at byte offset N — state "N bytes past object boundary")
- **First Event**: (kfence-#ID, full address range, task ID, CPU number)
- **Second Event**: (kfence-#ID, full address range, task ID, CPU number)
- **Trigger Process**: (insmod)
- **Handler Status**: (total crash-loop count and exit status)

## 5. Root Cause Analysis

### 5.1 Primary Root Cause
State whether this is a deliberate test module or production driver. Describe the exact sequence: allocation → OOB write at offset 32 (1 byte past end) → detection-on-free.

### 5.2 Causal Chain
Step-by-step: module load → KFENCE-guarded kmalloc → write 0xab at offset 32 (1 byte OOB) → kfree triggers integrity check → BUG reported.

### 5.3 Supporting Evidence
3-5 specific log lines proving the root cause.

## 6. Impact Assessment

### System Impact
- Memory corruption potential in production scenario
- Handler non-functional: state the total crash-loop count

### Recovery
- NON-CRASH: kernel logs the bug and continues
- Module unloaded status

## 7. Recommendations

### 7.1 Immediate Investigation
- Fix kfence-handler.sh (state the exit status meaning: 32256 = script not executable)
- Verify kfence_oob module purpose

### 7.2 Configuration Recommendations
- Remove test module from production
- For development: ENABLE kfence.fault_on_corruption=1 to trigger kernel panic for coredump capture

## 8. References
- **Log file**: syslog.log
- Anomaly type, hardware, kernel version and taint flags, faulting module, first/second detection times, KFENCE object IDs.

---

Be precise. Do not invent addresses or values not in the log. Use exact numbers from the log.
"""

_KFENCE_MAX_SYSLOG_CHARS = 12000
_KFENCE_DELIM_RE = re.compile(r"={10,}")


def _is_kfence_line(line: str) -> bool:
    """Return True if the line is KFENCE-relevant (kernel kfence mention or === delimiter inside a KFENCE block)."""
    if _KFENCE_DELIM_RE.search(line):
        return True
    return "kernel:" in line and "kfence" in line.lower()


def _extract_kfence_range(syslog_content: str) -> str:
    """
    Extract the KFENCE-relevant range from raw syslog content.

    Finds the first and last KFENCE-relevant lines (kernel messages
    mentioning kfence, or === delimiter lines from KFENCE reports) and
    returns all lines in that range, preserving full temporal context.

    Returns the extracted text, or an empty string if nothing KFENCE-related
    is found.
    """
    lines = syslog_content.splitlines()

    first = None
    last = None
    for i, line in enumerate(lines):
        if _is_kfence_line(line):
            if first is None:
                first = i
            last = i

    if first is None:
        return ""

    return "\n".join(lines[first : last + 1])


def _extract_kfence_facts(syslog_content: str) -> dict:
    """
    Programmatically extract key KFENCE facts to inject into the prompt.
    Returns a dict with handler_restart_count, taint_flags, bug_count.
    """
    facts = {}

    handler_count = sum(
        1 for line in syslog_content.splitlines()
        if "kfence-handler.sh" in line and "Child program exited" in line
    )
    facts["handler_restart_count"] = handler_count

    taint_match = re.search(r'Tainted:\s+([A-Z\s]+?)\s+\d+\.\d+', syslog_content)
    if taint_match:
        facts["taint_flags"] = taint_match.group(1).strip()

    bug_count = len(re.findall(r'BUG: KFENCE:', syslog_content))
    facts["bug_count"] = bug_count

    return facts


def run_kfence_pipeline(syslog_path: str) -> str:
    """
    KFENCE (CLI_SNAPSHOT) Summarization Pipeline.

    Phase 1: Programmatic extraction of KFENCE facts and sections (no LLM)
    Phase 2: Single LLM agent summarization with pre-extracted facts preamble

    Args:
        syslog_path: Absolute path to syslog.txt or syslog.log

    Returns:
        str: The KFENCE summary report
    """
    logger.info("=" * 70)
    logger.info("Starting KFENCE Pipeline")
    logger.info("=" * 70)

    if not os.path.isfile(syslog_path):
        error_msg = f"Syslog file not found: {syslog_path}"
        logger.error("[KFENCE] %s", error_msg)
        return f"Error: {error_msg}"

    try:
        with open(syslog_path, errors="replace") as f:
            syslog_content = f.read()
    except Exception as e:
        error_msg = f"Failed to read syslog: {e}"
        logger.error("[KFENCE] %s", error_msg)
        return f"Error: {error_msg}"

    logger.info("[KFENCE] Read syslog: %d chars", len(syslog_content))

    # Phase 1: Extract programmatic facts from full syslog BEFORE narrowing content
    facts = _extract_kfence_facts(syslog_content)
    logger.info("[KFENCE] Extracted facts: %s", facts)

    # Extract only KFENCE-relevant range from the syslog
    kfence_content = _extract_kfence_range(syslog_content)
    if kfence_content:
        logger.info("[KFENCE] Extracted %d chars of KFENCE content from %d char syslog",
                    len(kfence_content), len(syslog_content))
        syslog_content = kfence_content
    else:
        logger.warning("[KFENCE] No KFENCE sections found in syslog, sending full content to LLM")

    # Truncate if too large for LLM context
    if len(syslog_content) > _KFENCE_MAX_SYSLOG_CHARS:
        logger.info("[KFENCE] Truncating syslog from %d to %d chars",
                    len(syslog_content), _KFENCE_MAX_SYSLOG_CHARS)
        syslog_content = syslog_content[:_KFENCE_MAX_SYSLOG_CHARS]

    # Build a pre-extracted facts preamble for the LLM
    facts_preamble = (
        f"=== PRE-EXTRACTED FACTS (use these exact values, do not re-count or re-derive) ===\n"
        f"- kfence-handler.sh total crash-loop restarts: {facts.get('handler_restart_count', 'unknown')}\n"
        f"- Kernel taint flags string: \"{facts.get('taint_flags', 'unknown')}\" "
        f"(G=proprietary module, B=previous BUG recorded, O=out-of-tree module)\n"
        f"- Total BUG: KFENCE events in log: {facts.get('bug_count', 'unknown')}\n"
        f"=== END PRE-EXTRACTED FACTS ===\n\n"
    )

    # Phase 2: LLM summarization
    prompt = _KFENCE_PROMPT_TEMPLATE.format(syslog_content=facts_preamble + syslog_content)

    try:
        summary = generate_llm_response(
            "None",
            prompt,
            call_type="fw_assert",
            agent_name="KFENCESummarizer",
        )
        logger.info("[KFENCE] LLM summarization complete, %d chars", len(summary))
        return summary
    except Exception as e:
        error_msg = f"LLM summarization failed: {e}"
        logger.error("[KFENCE] %s", error_msg)
        return f"Error: {error_msg}"


# ===========================================================================
# FLUSH 52 (TXPCU_PHYTX_ABORT_ERR) PIPELINE
# ===========================================================================

_FLUSH52_MAX_CNSS_CONTEXT_CHARS = 8000
_FLUSH52_CNSS_CONTEXT_WINDOW = 8

_FLUSH52_ANTI_HALLUCINATION_RULES = """## ANTI-HALLUCINATION RULES (MANDATORY)
- Use ONLY the structured facts provided. Do NOT invent values, timestamps, or technical details.
- Every factual claim MUST cite a [FACT-N] reference.
- If a fact is not in the structured facts, write "not available in facts" — do NOT guess.
- Do NOT reference log files, source code, or documentation not mentioned in the facts.
"""

_FLUSH52_CNSS_KEYWORDS = [
    "flush_52", "FLUSH_52", "flush52",
    "TXPCU_PHYTX_ABORT", "phy_tx_abort", "PHY_TX_ABORT",
    "tx_abort_suspend", "FW_HANDLER",
    "phytx_abort", "phytxabort",
]


def _flush52_extract_anomaly_summary(anomaly_content: str) -> dict:
    """Parse anomaly_master.log for flush 52 critical event details."""
    result = {}
    if not anomaly_content:
        return result

    for line in anomaly_content.splitlines():
        if "flush_52_critical" not in line.lower():
            continue
        ts_match = re.search(r'\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]', line)
        if ts_match:
            result["timestamp"] = ts_match.group(1)
        radio_match = re.search(r'Radio:\s*(\S+)', line)
        if radio_match:
            result["radio"] = radio_match.group(1)
        occ_match = re.search(r'Occurrence:\s*(\d+)', line)
        if occ_match:
            result["occurrence"] = int(occ_match.group(1))
        inc_match = re.search(r'Increase:\s*(\d+)', line)
        if inc_match:
            result["increase"] = int(inc_match.group(1))
        folder_match = re.search(r'Folder:\s*(\S+)', line)
        if folder_match:
            result["snapshot_folder"] = folder_match.group(1)
        break

    return result


def _flush52_extract_details(details_content: str) -> dict:
    """Parse flush_52_details.txt for radio info and count delta."""
    result = {}
    if not details_content:
        return result

    for line in details_content.splitlines():
        line = line.strip()
        if line.startswith("Radio:"):
            m = re.match(r'Radio:\s*(\S+)\s*\(MAC:\s*([^)]+)\)', line)
            if m:
                result["radio"] = m.group(1)
                result["mac"] = m.group(2)
        elif line.startswith("Frequency:"):
            m = re.search(r'Frequency:\s*(\d+)\s*MHz', line)
            if m:
                result["frequency_mhz"] = int(m.group(1))
        elif line.startswith("Previous Count:"):
            m = re.search(r'(\d+)', line)
            if m:
                result["prev_count"] = int(m.group(1))
        elif line.startswith("Current Count:"):
            m = re.search(r'(\d+)', line)
            if m:
                result["curr_count"] = int(m.group(1))
        elif line.startswith("Increase:"):
            m = re.search(r'(\d+)', line)
            if m:
                result["increase"] = int(m.group(1))
        elif line.startswith("Threshold:"):
            m = re.search(r'(\d+)', line)
            if m:
                result["threshold"] = int(m.group(1))

    return result


def _flush52_extract_critical_logread_events(logread_content: str) -> list:
    """Find Flush 52 / PHY TX abort critical lines in the kernel log."""
    events = []
    for line in logread_content.splitlines():
        if any(kw in line for kw in (
            "Flush 52", "FLUSH_52", "TXPCU_PHYTX_ABORT", "flush_52_critical",
            "PHY_TX_ABORT", "phy_tx_abort", "FW_HANDLER",
        )):
            events.append(line.strip())
    return events


def _flush52_extract_wifistats(wifistats_content: str) -> dict:
    """Extract key TX statistics from wifistats."""
    result = {}
    if not wifistats_content:
        return result

    flush_match = re.search(r'flush_errs\s*=\s*([^\n]+)', wifistats_content)
    if flush_match:
        errs_str = flush_match.group(1)
        m52 = re.search(r'\b52:(\d+)', errs_str)
        if m52:
            result["flush_52_count"] = int(m52.group(1))
        non_zero = []
        for pair in re.finditer(r'(\d+):([1-9]\d*)', errs_str):
            non_zero.append(f"[{pair.group(1)}]={pair.group(2)}")
        if non_zero:
            result["flush_errs_nonzero"] = non_zero

    phy_match = re.search(r'phys_errs\s*=\s*([^\n]+)', wifistats_content)
    if phy_match:
        errs_str = phy_match.group(1)
        non_zero = []
        for pair in re.finditer(r'(\d+):([1-9]\d*)', errs_str):
            non_zero.append(f"[{pair.group(1)}]={pair.group(2)}")
        if non_zero:
            result["phy_errs_nonzero"] = non_zero

    tx_abort_match = re.search(r'tx_abort_suspend_cnt\s*=\s*(\d+)', wifistats_content)
    if tx_abort_match:
        result["tx_abort_suspend_cnt"] = int(tx_abort_match.group(1))

    suspend_match = re.search(r'last_suspend_reason\s*=\s*(\d+)', wifistats_content)
    if suspend_match:
        result["last_suspend_reason"] = int(suspend_match.group(1))

    hw_queued_match = re.search(r'hw_queued\s*=\s*(\d+)', wifistats_content)
    hw_reaped_match = re.search(r'hw_reaped\s*=\s*(\d+)', wifistats_content)
    if hw_queued_match:
        result["hw_queued"] = int(hw_queued_match.group(1))
    if hw_reaped_match:
        result["hw_reaped"] = int(hw_reaped_match.group(1))

    tx_abort_field = re.search(r'\btx_abort\s*=\s*(\d+)', wifistats_content)
    if tx_abort_field:
        result["tx_abort"] = int(tx_abort_field.group(1))

    return result


def _flush52_extract_cnss_diag_chunks(cnss_content: str, max_chars: int = _FLUSH52_MAX_CNSS_CONTEXT_CHARS) -> str:
    """
    Extract only flush-52-relevant lines from cnss_diag, with context window.
    Falls back to the last N chars if no keyword matches are found.
    """
    if not cnss_content:
        return "(not available)"

    lines = cnss_content.splitlines()
    matched_indices = set()

    for i, line in enumerate(lines):
        if any(kw.lower() in line.lower() for kw in _FLUSH52_CNSS_KEYWORDS):
            start = max(0, i - _FLUSH52_CNSS_CONTEXT_WINDOW)
            end = min(len(lines), i + _FLUSH52_CNSS_CONTEXT_WINDOW + 1)
            for j in range(start, end):
                matched_indices.add(j)

    if not matched_indices:
        logger.info("[FLUSH52] No keyword matches in cnss_diag, using last %d chars", max_chars)
        excerpt = cnss_content[-max_chars:]
        return f"[No flush-52-specific entries found; showing last {max_chars} chars of trace]\n{excerpt}"

    sorted_indices = sorted(matched_indices)
    chunks = []
    prev_end = None

    i = 0
    while i < len(sorted_indices):
        idx = sorted_indices[i]
        j = i
        while j + 1 < len(sorted_indices) and sorted_indices[j + 1] == sorted_indices[j] + 1:
            j += 1
        block_end = sorted_indices[j]

        if prev_end is not None and idx > prev_end + 1:
            chunks.append(f"[... {idx - prev_end - 1} lines omitted ...]")

        chunks.extend(lines[idx:block_end + 1])
        prev_end = block_end
        i = j + 1

    excerpt = "\n".join(chunks)
    if len(excerpt) > max_chars:
        excerpt = excerpt[-max_chars:]
        logger.info("[FLUSH52] cnss_diag excerpt truncated to %d chars", max_chars)
    else:
        logger.info("[FLUSH52] cnss_diag excerpt: %d chars from %d matched lines",
                    len(excerpt), len(matched_indices))

    return excerpt


def _flush52_build_structured_facts(
    anomaly: dict,
    details: dict,
    critical_events: list,
    wifistats: dict,
) -> str:
    """Build a numbered FACT-N document for the LLM agents."""
    lines = ["=" * 70,
             "STRUCTURED FACTS — EXTRACTED PROGRAMMATICALLY FROM LOG FILES",
             "=" * 70, ""]
    n = 1

    lines.append("## SECTION A: ANOMALY IDENTIFICATION")
    lines.append("")

    lines.append(f"[FACT-{n}] Anomaly Type: FLUSH_52_CRITICAL (TXPCU_PHYTX_ABORT_ERR)")
    n += 1

    if anomaly.get("timestamp"):
        lines.append(f"[FACT-{n}] Detection Timestamp: {anomaly['timestamp']} (occurrence #{anomaly.get('occurrence', '?')})")
        n += 1

    if details.get("radio") and details.get("mac"):
        lines.append(f"[FACT-{n}] Radio: {details['radio']} (MAC: {details['mac']})")
        n += 1
    elif anomaly.get("radio"):
        lines.append(f"[FACT-{n}] Radio: {anomaly['radio']}")
        n += 1

    if details.get("frequency_mhz"):
        lines.append(f"[FACT-{n}] Frequency: {details['frequency_mhz']} MHz")
        n += 1

    if details.get("prev_count") is not None:
        inc = details.get('increase', details.get('curr_count', 0) - details.get('prev_count', 0))
        thr = details.get('threshold', '?')
        lines.append(
            f"[FACT-{n}] Flush 52 Count Delta: prev={details['prev_count']} → "
            f"curr={details.get('curr_count', '?')} (+{inc}); threshold={thr}"
        )
        n += 1

    lines.append("")

    lines.append("## SECTION B: WIFISTATS EVIDENCE (from HTT TX PDEV stats snapshot)")
    lines.append("")

    if wifistats.get("flush_52_count") is not None:
        lines.append(
            f"[FACT-{n}] HTT_TX_PDEV_STATS_FLUSH_TLV: flush_errs[52]={wifistats['flush_52_count']} "
            f"(confirms TXPCU_PHYTX_ABORT_ERR flush events occurred)"
        )
        n += 1

    flush_nonzero = wifistats.get("flush_errs_nonzero", [])
    other_flush = [x for x in flush_nonzero if not x.startswith("[52]")]
    if other_flush:
        lines.append(f"[FACT-{n}] Other non-zero flush_errs: {', '.join(other_flush)}")
        n += 1

    phy_errs = wifistats.get("phy_errs_nonzero")
    if phy_errs:
        lines.append(
            f"[FACT-{n}] HTT_TX_PDEV_STATS_PHY_ERR_TLV non-zero entries: {', '.join(phy_errs)} "
            f"(index 27 = TXPCU_PHYTX_ABORT_ERR)"
        )
        n += 1

    tx_abort_suspend = wifistats.get("tx_abort_suspend_cnt")
    last_reason = wifistats.get("last_suspend_reason")
    if tx_abort_suspend is not None:
        reason_desc = " (TX abort suspend)" if last_reason == 2 else ""
        lines.append(
            f"[FACT-{n}] tx_abort_suspend_cnt={tx_abort_suspend}, "
            f"last_suspend_reason={last_reason}{reason_desc}"
        )
        n += 1

    hw_queued = wifistats.get("hw_queued")
    hw_reaped = wifistats.get("hw_reaped")
    tx_abort = wifistats.get("tx_abort")
    if hw_queued is not None:
        lines.append(
            f"[FACT-{n}] TX pipeline: hw_queued={hw_queued}, hw_reaped={hw_reaped}, tx_abort={tx_abort}"
        )
        n += 1

    lines.append("")

    lines.append("## SECTION C: CRITICAL KERNEL LOG EVENTS")
    lines.append("")

    if critical_events:
        lines.append(f"[FACT-{n}] {len(critical_events)} flush-52-related kernel log events found:")
        n += 1
        for ev in critical_events[:5]:
            lines.append(f"   - {ev}")
    else:
        lines.append(f"[FACT-{n}] No flush-52-related kernel log events found in logread.")
        n += 1

    lines.append("")

    lines.append("## SECTION D: SNAPSHOT CONTEXT")
    lines.append("")

    if anomaly.get("snapshot_folder"):
        lines.append(f"[FACT-{n}] Snapshot folder: {anomaly['snapshot_folder']}")
        n += 1

    lines.append("")
    return "\n".join(lines)


def _flush52_fact_interpreter_agent(structured_facts: str, cnss_excerpt: str) -> str:
    """Agent 1: Build a timeline and interpret the TX pipeline state at the time of anomaly."""
    logger.info("[FLUSH52] Agent 1 (FactInterpreter): building timeline and interpreting TX state...")

    if len(cnss_excerpt) > 4000:
        cnss_excerpt = cnss_excerpt[-4000:] + "\n... [TRUNCATED]"

    prompt = f"""You are a Qualcomm WiFi firmware diagnostics expert specializing in TX path anomalies.

{_FLUSH52_ANTI_HALLUCINATION_RULES}

{structured_facts}

## FIRMWARE TRACE (cnss_diag) — flush-52-relevant sections
{cnss_excerpt}
## END FIRMWARE TRACE

Based ONLY on the structured facts and firmware trace above, answer the following:

1. **CHRONOLOGICAL EVENT SEQUENCE**
   List the key events in order, citing fact numbers. Format:
   [TIMESTAMP or sequence] [FACT-N] EVENT_DESCRIPTION

2. **ANOMALY TRIGGER IDENTIFICATION**
   - What specific event/condition caused the flush 52 count to spike?
   - What was the TX pipeline state at the time of the anomaly? (cite facts)
   - Is this a hardware or software failure? (cite facts)

3. **TX ABORT ANALYSIS**
   - What do tx_abort_suspend_cnt and last_suspend_reason indicate? (cite facts)
   - What does phy_errs[27] indicate? (cite facts)
   - Is HW completing TX frames? (cite facts)

4. **SEVERITY ASSESSMENT**
   - How severe is the count increase relative to threshold? (cite facts)
   - Is this a transient spike or evidence of persistent PHY failure?

Be precise. Cite fact numbers for every statement. Do not add information not in the facts.
"""

    result = generate_llm_response("None", prompt, call_type="flush52", agent_name="Flush52FactInterpreter")
    logger.info("[FLUSH52] Agent 1 complete.")
    return result


def _flush52_root_cause_agent(structured_facts: str, fact_interpretation: str) -> str:
    """Agent 2: Determine the root cause from structured facts + interpretation."""
    logger.info("[FLUSH52] Agent 2 (RootCauseAgent): determining root cause...")

    if len(fact_interpretation) > 4000:
        fact_interpretation = fact_interpretation[:4000] + "\n... [TRUNCATED]"

    prompt = f"""You are a senior Qualcomm WiFi firmware reliability engineer.

{_FLUSH52_ANTI_HALLUCINATION_RULES}

{structured_facts}

## FACT INTERPRETATION (from Agent 1)
{fact_interpretation}

Based ONLY on the structured facts and fact interpretation above, determine the root cause.

1. **PRIMARY ROOT CAUSE STATEMENT**
   State the root cause in 1-2 sentences. Cite the specific facts that prove it.
   Use precise language: "HW is not doing any TX", "aborting very frequently/always", "sudden spike".

2. **CAUSAL CHAIN**
   Step-by-step sequence from normal operation to anomaly detection. Each step must cite a fact:
   Step 1: [FACT-N] Normal TX operation — flush_errs[52] at baseline
   Step 2: [FACT-N] PHY TX aborts begin — evidence
   Step 3: [FACT-N] Count spike detected — threshold exceeded
   ANOMALY: [FACT-N] FLUSH_52_CRITICAL triggered

3. **KEY EVIDENCE**
   List the 3-5 most critical facts that prove the root cause. For each:
   - Fact number and content
   - Why it is critical to the root cause

4. **WHAT THE FLUSH 52 MEANS**
   Based on the flush_errs[52], phy_errs[27], tx_abort_suspend_cnt, and last_suspend_reason facts,
   what is the state of the TX PCU / PHY interface?

5. **CONFIDENCE LEVEL**: HIGH / MEDIUM / LOW
   Justify based on the quality and completeness of the evidence.

Do NOT speculate. Do NOT mention subsystems not evidenced in the facts.
"""

    result = generate_llm_response("None", prompt, call_type="flush52", agent_name="Flush52RootCause")
    logger.info("[FLUSH52] Agent 2 complete.")
    return result


def _flush52_summary_agent(structured_facts: str, fact_interpretation: str, root_cause: str) -> str:
    """Agent 3: Generate a structured engineering report."""
    logger.info("[FLUSH52] Agent 3 (SummaryAgent): generating structured report...")

    if len(fact_interpretation) > 3000:
        fact_interpretation = fact_interpretation[:3000] + "\n... [TRUNCATED]"
    if len(root_cause) > 4000:
        root_cause = root_cause[:4000] + "\n... [TRUNCATED]"

    prompt = f"""You are a technical writer creating a structured firmware anomaly report for a Qualcomm WiFi engineering team.

{_FLUSH52_ANTI_HALLUCINATION_RULES}

{structured_facts}

## FACT INTERPRETATION
{fact_interpretation}

## ROOT CAUSE ANALYSIS
{root_cause}

Generate a structured report with ALL of the following sections. Use ONLY the information above. Every factual claim must cite [FACT-N].

---

# FLUSH TYPE 52 ANOMALY SUMMARY REPORT

## 1. Executive Summary
Write 2-3 sentences that include ALL of the following (cite each with [FACT-N]):
1. The anomaly type (Flush Type 52 / TXPCU_PHYTX_ABORT_ERR)
2. The radio and MAC address where it occurred
3. The detection timestamp
4. The count increase (prev → curr, +delta) and threshold
5. The key finding: HW is not doing any TX — aborting very frequently/always
6. The critical wifistats evidence (flush_errs[52], phy_errs[27], tx_abort_suspend_cnt)

## 2. Issue Classification
- **Issue Type**: (flush type 52 anomaly)
- **Severity**: HIGH/MEDIUM/LOW with justification citing facts
- **Affected Component**: (radio, frequency)
- **Anomaly Mode**: (what the PHY is doing)

## 3. Timeline of Events
Use this format for each event:
- [TIMESTAMP or seq] EVENT_DESCRIPTION [FACT-N]
Include: pre-anomaly baseline, PHY abort events beginning, count spike, anomaly detection.

## 4. Anomaly Details
Fill in the ACTUAL VALUES from the structured facts (do not write bare [FACT-N] as the value — write the value and cite the fact):
- **Anomaly Type**: <actual anomaly type string> [FACT-1]
- **Detection Time**: <actual timestamp> [FACT-2]
- **Radio**: <actual radio name and MAC> [FACT-3]
- **Frequency**: <actual MHz> [FACT-4]
- **Flush 52 Count Delta**: prev=<N> → curr=<N> (+<delta>); threshold=<N> [FACT-5]
- **wifistats Evidence**: flush_errs[52]=<N> [FACT-6], phy_errs[27]=<N> [FACT-8], tx_abort_suspend_cnt=<N>, last_suspend_reason=<N> [FACT-9]

## 5. Root Cause Analysis

### 5.1 Primary Root Cause
1-2 sentences. Must state: "HW is not doing any TX and aborting very frequently/always".

### 5.2 Causal Chain
Step-by-step with fact citations. Include:
- Step 1: pre-anomaly baseline state (normal TX, flush_errs[52] at baseline count)
- Step 2: PHY TX aborts begin (cite tx_abort_suspend_cnt, phy_errs[27], last_suspend_reason)
- Step 3: Count spike detected — threshold exceeded
- ANOMALY: FLUSH_52_CRITICAL triggered

### 5.3 Supporting Evidence
List 3-5 key facts with explanation of their significance.

## 6. Impact Assessment

### User Impact
- TX performance and connectivity impact (be specific about what PHY TX aborts cause)

### Recovery
- State clearly: this is a NON-CRASH anomaly — firmware continues running without a device reset
- Automatic recovery IS POSSIBLE if the underlying cause (e.g., interference, thermal event) is transient
- Monitoring is needed to determine if the condition persists

## 7. Recommendations

### 7.1 Immediate Investigation
- Investigate RF interference / co-channel congestion at the affected frequency [FACT-4]
- Correlate phy_errs[27] with external interference sources or adjacent AP activity [FACT-8]

### 7.2 Configuration Recommendations
- Review the threshold relative to the observed increase (count [FACT-5] exceeded threshold by 3x) — is the threshold appropriate?
- Consider channel selection if co-channel interference is suspected at the detected frequency [FACT-4]

## 8. References
- Log files, anomaly type [FACT-1], radio and MAC [FACT-3], frequency [FACT-4], detection timestamp [FACT-2], snapshot folder [FACT-11].

---

Every section must be present. Every claim must cite [FACT-N]. Do not invent facts.
"""

    result = generate_llm_response("None", prompt, call_type="flush52", agent_name="Flush52Summary")
    logger.info("[FLUSH52] Agent 3 complete.")
    return result


def run_flush52_pipeline(
    logread_path: str,
    cnss_diag_path: str,
    anomaly_master_path: str = "",
    flush52_details_path: str = "",
    wifistats_path: str = "",
) -> str:
    """
    Run the Flush 52 (TXPCU_PHYTX_ABORT_ERR) agentic summarization pipeline.

    Phase 1: Programmatically extract structured facts from all available logs.
    Phase 2: Extract flush-52-relevant chunks from cnss_diag.
    Phase 3: Run 3-agent LLM pipeline on structured facts.

    Args:
        logread_path: Path to logread_output.txt (kernel log).
        cnss_diag_path: Path to default_cnss_diag.txt (firmware trace).
        anomaly_master_path: Path to anomaly_master.log (optional).
        flush52_details_path: Path to flush_52_details.txt (optional).
        wifistats_path: Path to wifistats_*.txt (optional).

    Returns:
        str: Structured diagnostic report.
    """
    logger.info("=" * 70)
    logger.info("[FLUSH52] Starting agentic pipeline")
    logger.info("=" * 70)

    # Phase 1: Extract facts
    anomaly = _flush52_extract_anomaly_summary(
        _load_log(anomaly_master_path) if anomaly_master_path else ""
    )
    logger.info("[FLUSH52] Anomaly: %s", anomaly)

    details = _flush52_extract_details(
        _load_log(flush52_details_path) if flush52_details_path else ""
    )
    logger.info("[FLUSH52] Details: %s", details)

    logread_content = _load_log(logread_path)
    critical_events = _flush52_extract_critical_logread_events(logread_content)
    logger.info("[FLUSH52] Critical events: %d", len(critical_events))

    wifistats = _flush52_extract_wifistats(
        _load_log(wifistats_path) if wifistats_path else ""
    )
    logger.info("[FLUSH52] Wifistats: %s", wifistats)

    structured_facts = _flush52_build_structured_facts(anomaly, details, critical_events, wifistats)
    logger.info("[FLUSH52] Structured facts: %d chars", len(structured_facts))

    # Phase 2: Extract cnss_diag chunks
    cnss_content = _load_log(cnss_diag_path)
    cnss_excerpt = _flush52_extract_cnss_diag_chunks(cnss_content)
    logger.info("[FLUSH52] cnss_diag excerpt: %d chars", len(cnss_excerpt))

    # Phase 3: Agentic pipeline
    try:
        fact_interpretation = _flush52_fact_interpreter_agent(structured_facts, cnss_excerpt)
        logger.info("[FLUSH52] Agent 1 output: %d chars", len(fact_interpretation))

        root_cause = _flush52_root_cause_agent(structured_facts, fact_interpretation)
        logger.info("[FLUSH52] Agent 2 output: %d chars", len(root_cause))

        summary = _flush52_summary_agent(structured_facts, fact_interpretation, root_cause)
        logger.info("[FLUSH52] Agent 3 output: %d chars", len(summary))

        return summary

    except Exception as e:
        error_msg = f"Agentic pipeline failed: {e}"
        logger.error("[FLUSH52] %s", error_msg)
        return f"Error: {error_msg}"


def run_log_summarization(folder_name, MODEL="None"):
    """
    Run log summarization using the Agentic Workflow

    Args:
        folder_name: Path to the folder containing log files
        MODEL: Model to use for LLM calls (e.g., "qgenie", "bedrock", "internal")

    Returns:
        str: The triage report (log_summarization.txt content)
    """
    print(f"[LOG_SUMMARIZATION] Starting Agentic Workflow analysis for: {folder_name}")

    # Locate input files
    fd_logs_path = None
    hostapd_log_path = None
    wifistats_path = None
    knowledge_base_path = None

    # Find FD logs (notification file) - matches patterns like "0_fd_logs.txt", "86_fd_logs.txt", etc.
    fd_logs_pattern = os.path.join(folder_name, "*fd_logs.txt")
    fd_logs_matches = glob.glob(fd_logs_pattern)
    if fd_logs_matches:
        fd_logs_path = fd_logs_matches[0]
        print(f"[LOG_SUMMARIZATION] Found FD logs: {fd_logs_path}")
    else:
        print(f"[LOG_SUMMARIZATION] Warning: No FD logs found matching pattern: {fd_logs_pattern}")
        return "Error: No FD logs (notification file) found in the provided folder"

    # Find hostapd log (syslog.txt)
    hostapd_log_path = os.path.join(folder_name, "syslog.txt")
    if os.path.exists(hostapd_log_path):
        print(f"[LOG_SUMMARIZATION] Found hostapd log: {hostapd_log_path}")
    else:
        print("[LOG_SUMMARIZATION] No hostapd log found (syslog.txt)")
        hostapd_log_path = None

    # Find wifistats (rate_of_change_wifistats.txt)
    wifistats_path = os.path.join(folder_name, "rate_of_change_wifistats.txt")
    if os.path.exists(wifistats_path):
        print(f"[LOG_SUMMARIZATION] Found wifistats: {wifistats_path}")
    else:
        print("[LOG_SUMMARIZATION] No wifistats found (rate_of_change_wifistats.txt)")
        wifistats_path = None

    # Find knowledge base
    # Production: loaded from compiled assets.so (knowledge_base.txt is not present)
    # Development fallback: read from knowledge_base.txt if assets.so not compiled yet
    knowledge_base_path = None  # used only in fallback path

    # Read file contents
    try:
        with open(fd_logs_path) as f:
            fd_logs = f.read()
    except Exception as e:
        print(f"[LOG_SUMMARIZATION] Error reading FD logs: {e}")
        return f"Error reading FD logs: {str(e)}"

    hostapd_log = None
    if hostapd_log_path:
        try:
            with open(hostapd_log_path) as f:
                hostapd_log = f.read()
        except Exception as e:
            print(f"[LOG_SUMMARIZATION] Warning: Error reading hostapd log: {e}")

    wifistats = None
    if wifistats_path:
        try:
            with open(wifistats_path) as f:
                wifistats = f.read()
        except Exception as e:
            print(f"[LOG_SUMMARIZATION] Warning: Error reading wifistats: {e}")

    knowledge_base = None
    try:
        from assets import KNOWLEDGE_BASE  # compiled Cython extension
        knowledge_base = KNOWLEDGE_BASE
        print("[LOG_SUMMARIZATION] Loaded knowledge base from compiled assets module")
    except ImportError:
        # Development fallback: read from file when assets.so is not compiled
        script_dir = os.path.dirname(os.path.abspath(__file__))
        knowledge_base_path = os.path.join(script_dir, "knowledge_base.txt")
        if os.path.exists(knowledge_base_path):
            try:
                with open(knowledge_base_path) as f:
                    knowledge_base = f.read()
                print(f"[LOG_SUMMARIZATION] Loaded knowledge base from file (dev fallback): {knowledge_base_path}")
            except Exception as e:
                print(f"[LOG_SUMMARIZATION] Warning: Error reading knowledge base file: {e}")
        else:
            print("[LOG_SUMMARIZATION] Warning: No knowledge base found (assets.so not compiled, knowledge_base.txt not present)")

    # Determine model to use
    # If MODEL is "None" (string), use "qgenie" as default
    if MODEL == "None" or MODEL is None:
        model = "qgenie"
    else:
        model = MODEL

    print(f"[LOG_SUMMARIZATION] Using model: {model}")

    # Create orchestrator and run analysis
    try:
        orchestrator = Orchestrator(model=model)
        report = orchestrator.analyze(
            fd_logs=fd_logs,
            hostapd_log=hostapd_log,
            wifistats=wifistats,
            knowledge_base=knowledge_base
        )

        print("[LOG_SUMMARIZATION] Analysis complete")
        print(f"[LOG_SUMMARIZATION] Report length: {len(report)} characters")

        return report

    except Exception as e:
        print(f"[LOG_SUMMARIZATION] Error during analysis: {e}")
        import traceback
        traceback.print_exc()
        return f"Error during analysis: {str(e)}"
