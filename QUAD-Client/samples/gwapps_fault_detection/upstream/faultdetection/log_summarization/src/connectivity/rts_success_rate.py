# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# All rights reserved.
# Confidential and Proprietary - Qualcomm Technologies, Inc.

"""
rts_success_rate.py
-------------------
Calculates the RTS success rate percentage from the content of a
rate_of_change_wifistats.txt file.

Parsing method – key-value format in HTT_TX_PDEV_RATE_STATS_TLV sections
(WIFISTAT 9):

  mac_id       = <value>
  rts_cnt      = <value>
  rts_success  = <value>

  rts_success_rate_pct = (rts_success / rts_cnt) * 100

Sections where rts_cnt == 0 are skipped (no RTS was attempted).

Severity thresholds:
  <  20 %  → HIGH   (>80% failure rate — severe channel access impairment)
  <  50 %  → MEDIUM (>50% failure rate — significant channel access issues)
  >= 50 %  → LOW
"""

import re


def calculate_rts_success_rate(wifistats_content: str) -> dict[int, float]:
    """
    Parse *wifistats_content* (the raw text of rate_of_change_wifistats.txt)
    and return the RTS success rate percentage for every mac_id found in
    HTT_TX_PDEV_RATE_STATS_TLV sections.

    Args:
        wifistats_content: Full text of rate_of_change_wifistats.txt.

    Returns:
        dict mapping mac_id (int) → rts_success_rate percentage (float, 0–100).
        Returns an empty dict when no qualifying data is found (e.g. rts_cnt == 0).
    """
    rts_data: dict[int, float] = {}

    if not wifistats_content:
        return rts_data

    # Split on "WIFISTAT <N>" (handles both bare and === … === delimiters).
    # re.split with a capturing group interleaves [prefix, id, body, id, body, …]
    wifistat_sections = re.split(
        r'(?:===\s*)?WIFISTAT\s+(\d+)(?:\s*===)?', wifistats_content
    )

    for i in range(1, len(wifistat_sections), 2):
        section_content = wifistat_sections[i + 1] if i + 1 < len(wifistat_sections) else ""

        # Only process sections that contain HTT_TX_PDEV_RATE_STATS_TLV
        if 'HTT_TX_PDEV_RATE_STATS_TLV' not in section_content:
            continue

        # Find all HTT_TX_PDEV_RATE_STATS_TLV blocks within this section
        # (there may be multiple if the section contains several TLV blocks)
        tlv_blocks = re.split(r'HTT_TX_PDEV_RATE_STATS_TLV:', section_content)

        for block in tlv_blocks[1:]:  # skip the part before the first TLV header
            # Extract mac_id
            mac_match = re.search(r'mac_id\s*=\s*(\d+)', block)
            if not mac_match:
                continue
            mac_id = int(mac_match.group(1))

            # Extract rts_cnt and rts_success
            rts_cnt_match = re.search(r'\brts_cnt\s*=\s*(\d+)', block)
            rts_success_match = re.search(r'\brts_success\s*=\s*(\d+)', block)

            if not rts_cnt_match or not rts_success_match:
                continue

            rts_cnt = int(rts_cnt_match.group(1))
            rts_success = int(rts_success_match.group(1))

            # Skip if no RTS was attempted
            if rts_cnt == 0:
                continue

            success_rate_pct = (rts_success / rts_cnt) * 100

            # Keep the first occurrence per mac_id (WIFISTAT 9 is the primary source)
            if mac_id not in rts_data:
                rts_data[mac_id] = success_rate_pct

    return rts_data


def get_rts_success_severity(success_rate_pct: float) -> str:
    """
    Return severity string for a given RTS success rate percentage.

    A *lower* success rate means *more* failures, which is worse.

    Thresholds:
      <  20 % → HIGH   (>80% of RTS frames failed)
      <  50 % → MEDIUM (>50% of RTS frames failed)
      >= 50 % → LOW
    """
    if success_rate_pct < 20.0:
        return "HIGH"
    elif success_rate_pct < 50.0:
        return "MEDIUM"
    return "LOW"
