# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# All rights reserved.
# Confidential and Proprietary - Qualcomm Technologies, Inc.

"""
Known Issue Checker Agent
Checks for common known issues based on anomaly type
"""

import re

from .base_agent import BaseAgent


class KnownIssueCheckerAgent(BaseAgent):
    """
    Checks for specific known issues based on anomaly type.
    Only flags issues if evidence exists in logs.
    Remains unbiased - provides checks but doesn't force conclusions.
    """

    def __init__(self, context, model: str = "qgenie"):
        super().__init__("KnownIssueChecker", context, model)

        # Define known issue patterns
        self.known_patterns = {
            "BEACON_STUCK": {
                # high_cca_obss is detected from pre-computed stats anomalies
                # (populated by StatsAnalyzerAgent via cca_obss_percentage.py),
                # not from log text patterns.  The _check_beacon_stuck_issues()
                # method handles this anomaly type specially.
                "high_cca_obss": {
                    "patterns": [],   # no regex patterns — stats-based check
                    "description": (
                        "High CCA OBSS busy-time: neighboring AP transmissions are "
                        "occupying the channel, preventing the AP from accessing the "
                        "medium at TBTT and causing beacon delays / drops"
                    )
                }
            },
            "DATA_STALL": {
                # high_cca_obss is detected from pre-computed stats anomalies
                # (populated by StatsAnalyzerAgent via cca_obss_percentage.py).
                "high_cca_obss": {
                    "patterns": [],   # no regex patterns — stats-based check
                    "description": (
                        "High CCA OBSS busy-time: neighboring AP transmissions are "
                        "occupying the channel, causing channel access failures "
                        "and contributing to the data stall"
                    )
                },
                # low_rts_success_rate is detected from pre-computed stats anomalies
                # (populated by StatsAnalyzerAgent via rts_success_rate.py).
                "low_rts_success_rate": {
                    "patterns": [],   # no regex patterns — stats-based check
                    "description": (
                        "Low RTS success rate: channel access is severely impaired "
                        "by interference or congestion — the AP cannot obtain CTS "
                        "responses, causing transmission failures and data stalls"
                    )
                }
            },
            "DISCONNECT": {
                "ap_initiated": {
                    "patterns": [
                        r'DEL_STATION',
                        r'ap_sta_disconnect',
                        r'sending\s+DISASSOC',
                        r'reason[:\s=]+[45]',  # reason codes 4 or 5
                        r'station kicked out due to excessive retries',
                        r'Disassociated due to inactivity'
                    ],
                    "description": "AP-initiated disconnect"
                },
                "sta_initiated": {
                    "patterns": [
                        r'trying to deauthenticate.*not authenticated',
                        r'Received Deauth with reason',
                        r'reason[:\s=]+[13]',  # reason codes 1 or 3
                        r'station is leaving'
                    ],
                    "description": "STA-initiated disconnect"
                },
                "multiple_reassoc": {
                    "patterns": [
                        r'reassociation',
                        r'REASSOC'
                    ],
                    "description": "Multiple reassociation attempts",
                    "count_threshold": 3,
                    "time_window_sec": 10
                }
            },
            "FAIL_TO_CONNECT": {
                "mfp_sa_query": {
                    "patterns": [
                        r'SA Query',
                        r'fail after AP kickout',
                        r'Management frame protection'
                    ],
                    "description": "MFP SA Query blocking reconnection after AP kickout"
                },
                "wrong_password": {
                    "patterns": [
                        r'SAE:\s*Confirm mismatch',
                        r'invalid MIC in msg',
                        r'EAPOL.*M2.*fail',
                        r'4-Way Handshake.*fail'
                    ],
                    "description": "Wrong password (authentication failure)"
                }
            }
        }

    def analyze(self) -> bool:
        """
        Check for known issues based on anomaly type
        
        Returns:
            bool: True if analysis succeeded
        """
        # Check if already cached
        if self.has_cached_data("known_issues"):
            self._log_info("Using cached known issues")
            return True

        # Get anomaly type
        anomaly_type = self.get_metadata("anomaly_type")
        if not anomaly_type:
            self._log_warning("No anomaly type provided")
            return True

        self._log_info(f"Checking for known issues for anomaly type: {anomaly_type}")

        # Get relevant patterns for this anomaly type
        patterns = self.known_patterns.get(anomaly_type.upper(), {})
        if not patterns:
            self._log_info(f"No known issue patterns defined for {anomaly_type}")
            return True

        # Get logs and timeline
        hostapd_log = self.get_input_data("hostapd_log") or ""
        timeline = self.get_cached_data("timeline") or []

        # For BEACON_STUCK, supplement pattern checks with stats-based checks
        stats_analysis = self.get_cached_data("stats_analysis") or {}

        # Check each known issue pattern
        known_issues = []
        for issue_name, issue_config in patterns.items():
            self._log_debug(f"Checking for known issue: {issue_name}")

            # Stats-based checks (no log patterns — use pre-computed anomalies)
            if anomaly_type.upper() in ("BEACON_STUCK", "DATA_STALL") and issue_name == "high_cca_obss":
                evidence = self._check_cca_obss_issue(stats_analysis)
            elif anomaly_type.upper() == "DATA_STALL" and issue_name == "low_rts_success_rate":
                evidence = self._check_rts_success_rate_issue(stats_analysis)
            else:
                evidence = self._check_pattern(
                    issue_name,
                    issue_config,
                    hostapd_log,
                    timeline
                )

            if evidence:
                known_issues.append({
                    "issue_type": issue_name,
                    "description": issue_config["description"],
                    "evidence": evidence,
                    "confidence": self._calculate_confidence(evidence)
                })
                self._log_info(f"Found evidence for known issue: {issue_name}")

        # Cache results
        self.cache_data("known_issues", known_issues)

        # Add findings
        for issue in known_issues:
            self.add_finding(
                finding_type="known_issue",
                content=issue,
                confidence=issue["confidence"],
                metadata={"issue_type": issue["issue_type"]}
            )

        self._log_info(f"Identified {len(known_issues)} known issues")
        return True

    def _check_cca_obss_issue(self, stats_analysis: dict) -> list[dict]:
        """
        Check for high CCA OBSS busy-time using pre-computed anomalies from
        StatsAnalyzerAgent (populated by cca_obss_percentage.py).

        Returns evidence list if any channel has a HIGH or MEDIUM severity
        cca_obss anomaly, empty list otherwise.
        """
        evidence = []
        anomalies = stats_analysis.get("anomalies", [])
        for anomaly in anomalies:
            if anomaly.get("type") != "high_cca_obss":
                continue
            pct = anomaly.get("value", 0)
            sev = anomaly.get("severity", "LOW")
            chan = anomaly.get("chan_num", "?")
            if sev in ("HIGH", "MEDIUM"):
                evidence.append({
                    "type": "stats_anomaly",
                    "pattern": "cca_obss_pct",
                    "matched_text": (
                        f"cca_obss_pct = {pct:.2f}% on channel {chan} "
                        f"[severity: {sev}]"
                    ),
                    "context": anomaly.get("description", ""),
                    "chan_num": chan,
                    "cca_obss_pct": pct,
                    "severity": sev,
                })
        return evidence

    def _check_rts_success_rate_issue(self, stats_analysis: dict) -> list[dict]:
        """
        Check for low RTS success rate using pre-computed anomalies from
        StatsAnalyzerAgent (populated by rts_success_rate.py).

        Returns evidence list if any mac_id has a HIGH or MEDIUM severity
        low_rts_success_rate anomaly, empty list otherwise.
        """
        evidence = []
        anomalies = stats_analysis.get("anomalies", [])
        for anomaly in anomalies:
            if anomaly.get("type") != "low_rts_success_rate":
                continue
            rate = anomaly.get("value", 100)
            sev = anomaly.get("severity", "LOW")
            mac_id = anomaly.get("mac_id", "?")
            if sev in ("HIGH", "MEDIUM"):
                failure_rate = 100.0 - rate
                evidence.append({
                    "type": "stats_anomaly",
                    "pattern": "rts_success_rate_pct",
                    "matched_text": (
                        f"rts_success_rate = {rate:.2f}% on mac_id {mac_id} "
                        f"({failure_rate:.2f}% failure rate) "
                        f"[severity: {sev}]"
                    ),
                    "context": anomaly.get("description", ""),
                    "mac_id": mac_id,
                    "rts_success_rate_pct": rate,
                    "severity": sev,
                })
        return evidence

    def _check_pattern(self,
                      issue_name: str,
                      issue_config: dict,
                      hostapd_log: str,
                      timeline: list[dict]) -> list[dict]:
        """
        Check if pattern exists in logs
        
        Returns:
            List of evidence dictionaries if pattern found, empty list otherwise
        """
        evidence = []
        patterns = issue_config.get("patterns", [])

        # Check for pattern matches in hostapd log
        for pattern in patterns:
            matches = re.finditer(pattern, hostapd_log, re.IGNORECASE)
            for match in matches:
                # Get context around match (50 chars before and after)
                start = max(0, match.start() - 50)
                end = min(len(hostapd_log), match.end() + 50)
                context = hostapd_log[start:end]

                evidence.append({
                    "type": "log_match",
                    "pattern": pattern,
                    "matched_text": match.group(0),
                    "context": context.strip()
                })

        # Special handling for multiple reassoc (count-based)
        if issue_name == "multiple_reassoc":
            count_threshold = issue_config.get("count_threshold", 3)
            reassoc_events = [e for e in timeline if 'reassoc' in e.get('event_type', '').lower()]

            if len(reassoc_events) >= count_threshold:
                evidence.append({
                    "type": "count_threshold",
                    "pattern": "multiple_reassoc",
                    "matched_text": f"{len(reassoc_events)} reassociation attempts detected",
                    "context": f"Found {len(reassoc_events)} reassoc events (threshold: {count_threshold})"
                })

        return evidence

    def _calculate_confidence(self, evidence: list[dict]) -> str:
        """Calculate confidence level based on evidence strength"""
        if not evidence:
            return "LOW"

        # Stats-based anomalies carry their own severity — use it directly
        stats_anomalies = [e for e in evidence if e.get("type") == "stats_anomaly"]
        if stats_anomalies:
            # Use the highest severity found across all stats anomalies
            if any(e.get("severity") == "HIGH" for e in stats_anomalies):
                return "HIGH"
            if any(e.get("severity") == "MEDIUM" for e in stats_anomalies):
                return "MEDIUM"
            return "LOW"

        # Log / count-based evidence
        log_matches = len([e for e in evidence if e["type"] == "log_match"])
        count_matches = len([e for e in evidence if e["type"] == "count_threshold"])

        # High confidence: Multiple pieces of evidence
        if log_matches >= 3 or (log_matches >= 1 and count_matches >= 1):
            return "HIGH"
        # Medium confidence: Some evidence
        elif log_matches >= 1 or count_matches >= 1:
            return "MEDIUM"
        # Low confidence: Weak evidence
        else:
            return "LOW"
