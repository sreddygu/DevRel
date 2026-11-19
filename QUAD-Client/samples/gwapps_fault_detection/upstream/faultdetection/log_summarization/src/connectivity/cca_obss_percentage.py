# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# All rights reserved.
# Confidential and Proprietary - Qualcomm Technologies, Inc.

"""
cca_obss_percentage.py
----------------------
Calculates the CCA OBSS busy-time percentage from the content of a
rate_of_change_wifistats.txt file.

Two parsing methods are attempted for WIFISTAT 19 sections that contain
collection_interval = 1000:

  Method 1 – table format
    HTT_PDEV_STATS_CCA_COUNTERS_TLV:(in usec)
    | col0 | col1 | ... | cnt | ... | cca_obss |
    | val0 | val1 | ... | <cnt_val> | ... | <cca_val> |

    Column indices (0-based):
      cnt      → index 5
      cca_obss → index 8

    cca_obss_pct = avg( (cca_obss / cnt) * 100  for each row )

  Method 2 – key-value format
    cca_obss_usec = <value>
    usec_cnt      = <value>

    cca_obss_pct = (cca_obss_usec / usec_cnt) * 100

Severity thresholds (as specified by the caller):
  >= 80 %  → HIGH
  >= 40 %  → MEDIUM
  <  40 %  → LOW
"""

import re


def calculate_cca_obss_percentage(wifistats_content: str) -> dict[int, float]:
    """
    Parse *wifistats_content* (the raw text of rate_of_change_wifistats.txt)
    and return the CCA OBSS busy-time percentage for every channel found in
    WIFISTAT 19 sections that have collection_interval = 1000.

    Args:
        wifistats_content: Full text of rate_of_change_wifistats.txt.

    Returns:
        dict mapping chan_num (int) → cca_obss percentage (float, 0–100).
        Returns an empty dict when no qualifying data is found.
    """
    cca_obss_data: dict[int, float] = {}

    if not wifistats_content:
        return cca_obss_data

    # Split on "WIFISTAT <N>" (handles both bare and === … === delimiters).
    # re.split with a capturing group interleaves [prefix, id, body, id, body, …]
    wifistat_sections = re.split(r'(?:===\s*)?WIFISTAT\s+(\d+)(?:\s*===)?', wifistats_content)

    for i in range(1, len(wifistat_sections), 2):
        wifistat_num = wifistat_sections[i]
        section_content = wifistat_sections[i + 1] if i + 1 < len(wifistat_sections) else ""

        # Only WIFISTAT 19 carries CCA counters
        if wifistat_num != '19':
            continue

        # Require collection_interval = 1000 (ms) so the denominator is known
        if 'collection_interval = 1000' not in section_content:
            continue

        # Extract the channel number for this section
        chan_match = re.search(r'chan_num\s*=\s*(\d+)', section_content)
        if not chan_match:
            continue
        chan_num = int(chan_match.group(1))

        # ------------------------------------------------------------------
        # Method 1: pipe-delimited table
        #   HTT_PDEV_STATS_CCA_COUNTERS_TLV:(in usec)
        #   | header0 | header1 | … |
        #   | value0  | value1  | … |
        #
        # Column layout (0-based):
        #   0: tx_frame  1: rx_frame  2: rx_clear  3: my_rx_frame
        #   4: pre_rx_frame  5: cnt  6: med_rx_idle  7: med_tx_idle_global
        #   8: cca_obss
        #
        # cca_obss_pct = avg( (cca_obss / cnt) * 100  for each row )
        # ------------------------------------------------------------------
        table_match = re.search(
            r'HTT_PDEV_STATS_CCA_COUNTERS_TLV:\(in usec\)\s*\n'
            r'\|[^\n]+\|\s*\n'                   # header row
            r'((?:\|[^\n]+\|\s*\n)+)',            # one or more data rows
            section_content
        )
        if table_match:
            table_lines = table_match.group(1).strip().split('\n')
            row_pcts = []
            for line in table_lines:
                parts = [p.strip() for p in line.split('|') if p.strip()]
                if len(parts) >= 9:
                    try:
                        cnt = int(parts[5])
                        cca_obss = int(parts[8])
                        if cnt > 0:
                            row_pcts.append((cca_obss / cnt) * 100)
                    except (ValueError, IndexError):
                        continue
            if row_pcts:
                cca_obss_pct = sum(row_pcts) / len(row_pcts)
                cca_obss_data[chan_num] = cca_obss_pct
                continue  # Method 1 succeeded; skip Method 2

        # ------------------------------------------------------------------
        # Method 2: key-value format
        #   collection_interval = 1000
        #   HTT_PDEV_STATS_CCA_COUNTERS_TLV:(in usec)
        #   cca_obss_usec = <value>
        #   usec_cnt      = <value>
        #
        # cca_obss_pct = (cca_obss_usec / usec_cnt) * 100
        # ------------------------------------------------------------------
        kv_pattern = (
            r'collection_interval\s*=\s*1000\s*\n'
            r'\s*HTT_PDEV_STATS_CCA_COUNTERS_TLV:\(in usec\)\s*\n'
            r'(.*?)(?:\n\n|\Z)'
        )
        kv_match = re.search(kv_pattern, section_content, re.DOTALL)
        if kv_match:
            stats_block = kv_match.group(1)
            cca_usec_m = re.search(r'cca_obss_usec\s*=\s*(\d+)', stats_block)
            usec_cnt_m = re.search(r'usec_cnt\s*=\s*(\d+)', stats_block)
            if cca_usec_m and usec_cnt_m:
                cca_obss_usec = int(cca_usec_m.group(1))
                usec_cnt = int(usec_cnt_m.group(1))
                if usec_cnt > 0:
                    cca_obss_pct = (cca_obss_usec / usec_cnt) * 100
                    cca_obss_data[chan_num] = cca_obss_pct

    return cca_obss_data


def get_cca_obss_severity(cca_obss_pct: float) -> str:
    """
    Return severity string for a given CCA OBSS percentage.

    Thresholds:
      >= 80 % → HIGH
      >= 40 % → MEDIUM
      <  40 % → LOW
    """
    if cca_obss_pct >= 80.0:
        return "HIGH"
    elif cca_obss_pct >= 40.0:
        return "MEDIUM"
    return "LOW"
