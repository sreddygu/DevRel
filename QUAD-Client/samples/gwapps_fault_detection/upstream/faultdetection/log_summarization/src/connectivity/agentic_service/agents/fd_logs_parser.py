# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# All rights reserved.
# Confidential and Proprietary - Qualcomm Technologies, Inc.

"""
FD Logs Parser Agent
Extracts anomaly-specific metrics from fault detection logs
"""

import re
from typing import Any

from .base_agent import BaseAgent


class FDLogsParserAgent(BaseAgent):
    """
    Parses fault detection logs to extract anomaly-specific metrics.
    
    Supports:
    - DATA STALL: data_retry_pct, rssi_in_dbm (and rssi_mgmt, rssi_data, rssi_comb)
    - BEACON STUCK: beacon_fail_rate
    """

    def __init__(self, context, model: str = "qgenie"):
        super().__init__("FDLogsParser", context, model)

    def analyze(self) -> bool:
        """
        Parse FD logs based on anomaly type
        
        Returns:
            bool: True if parsing succeeded
        """
        # Check if already cached
        if self.has_cached_data("fd_logs_metrics"):
            self._log_info("Using cached FD logs metrics")
            return True

        # Get anomaly type
        anomaly_type = self.get_metadata("anomaly_type")

        # Get FD logs
        fd_logs = self.get_input_data("fd_logs")
        if not fd_logs:
            self._log_warning("No FD logs available")
            return True

        # Parse based on anomaly type
        metrics = {}

        if anomaly_type == "DATA_STALL":
            metrics = self._parse_data_stall_metrics(fd_logs)
            self._log_info(f"Parsed DATA STALL metrics: data_retry_pct={metrics.get('data_retry_pct')}, rssi_in_dbm={metrics.get('rssi_in_dbm')}")

        elif anomaly_type == "BEACON_STUCK":
            metrics = self._parse_beacon_stuck_metrics(fd_logs)
            self._log_info(f"Parsed BEACON STUCK metrics: beacon_fail_rate={metrics.get('beacon_fail_rate')}")

        else:
            # Not a DATA_STALL or BEACON_STUCK anomaly - skip parsing
            self._log_info(f"Skipping FD logs parsing for {anomaly_type}")
            return True

        # Cache the metrics
        self.cache_data("fd_logs_metrics", metrics)

        # Add as finding
        if metrics:
            self.add_finding(
                finding_type="fd_logs_metrics",
                content=metrics,
                confidence="HIGH"
            )

        return True

    def _parse_data_stall_metrics(self, fd_logs: str) -> dict[str, Any]:
        """
        Parse DATA STALL specific metrics from FD logs

        Extracts:
        - data_retry_pct: Data retry percentage
        - anomaly_band: Band on which the anomaly was detected (e.g. "6G")
        - rssi_mgmt: RSSI management values (index 46) for the anomaly band only
        - rssi_data: RSSI data values (index 47) for the anomaly band only
        - rssi_comb: RSSI combined values (index 48) for the anomaly band only
        - rssi_in_dbm: RSSI in dBm values (index 49) for the anomaly band only

        The file contains N iterations (N can vary from 1 to ~10).  Each
        iteration has one "Radio Band X:" line per active radio.  Only the
        line whose band number matches the anomaly band is used.

        Returns:
            Dict with extracted metrics
        """
        metrics = {
            "data_retry_pct": None,
            "anomaly_band": None,
            "rssi_mgmt": [],
            "rssi_data": [],
            "rssi_comb": [],
            "rssi_in_dbm": []
        }

        lines = fd_logs.split('\n')

        # ------------------------------------------------------------------ #
        # Step 1: determine the anomaly band number from the header section.  #
        # "Anomaly detected on band: 6G"  →  band_number = "6"               #
        # ------------------------------------------------------------------ #
        anomaly_band_number: str | None = None
        for line in lines:
            m = re.search(r'Anomaly detected on band:\s*(\d+)G', line, re.IGNORECASE)
            if m:
                anomaly_band_number = m.group(1)
                metrics["anomaly_band"] = m.group(1) + "G"
                break

        # ------------------------------------------------------------------ #
        # Step 2: iterate over all lines and collect metrics.                 #
        # For Radio Band lines, only process the line whose band number       #
        # matches anomaly_band_number (across all iterations).                #
        # ------------------------------------------------------------------ #
        for line in lines:
            # Extract data retry percentage
            if 'Data retry PCT:' in line:
                m = re.search(r'Data retry PCT:\s*([0-9.]+)', line)
                if m:
                    metrics["data_retry_pct"] = float(m.group(1))

            # Extract Radio Band data (format: "Radio Band X: 0:value 1:value ...")
            rb_match = re.match(r'Radio Band (\d+):', line.strip())
            if rb_match:
                band_num = rb_match.group(1)

                # Skip bands that are not the anomaly band
                if anomaly_band_number is not None and band_num != anomaly_band_number:
                    continue

                # Parse all key:value pairs in the line
                values = dict(re.findall(r'(\d+):([-+]?[0-9]*\.?[0-9]+)', line))

                if '46' in values:
                    metrics["rssi_mgmt"].append(float(values['46']))
                if '47' in values:
                    metrics["rssi_data"].append(float(values['47']))
                if '48' in values:
                    metrics["rssi_comb"].append(float(values['48']))
                if '49' in values:
                    metrics["rssi_in_dbm"].append(float(values['49']))

        # ------------------------------------------------------------------ #
        # Step 3: compute per-list statistics (avg / min / max).              #
        # ------------------------------------------------------------------ #
        for key in ["rssi_mgmt", "rssi_data", "rssi_comb", "rssi_in_dbm"]:
            values = [v for v in metrics[key] if v != 0.0]
            if values:
                metrics[f"{key}_avg"] = sum(values) / len(values)
                metrics[f"{key}_min"] = min(values)
                metrics[f"{key}_max"] = max(values)

        return metrics

    def _parse_beacon_stuck_metrics(self, fd_logs: str) -> dict[str, Any]:
        """
        Parse BEACON STUCK specific metrics from FD logs
        
        Extracts:
        - beacon_fail_rate: Beacon failure rate
        
        Returns:
            Dict with extracted metrics
        """
        metrics = {
            "beacon_fail_rate": None
        }

        lines = fd_logs.split('\n')

        for line in lines:
            # Extract beacon fail rate
            if 'Beacon fail rate:' in line:
                match = re.search(r'Beacon fail rate:\s*([0-9.]+)', line)
                if match:
                    metrics["beacon_fail_rate"] = float(match.group(1))
                    break

        return metrics
