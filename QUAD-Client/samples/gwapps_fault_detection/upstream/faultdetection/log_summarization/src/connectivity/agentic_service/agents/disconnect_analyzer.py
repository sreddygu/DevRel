# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# All rights reserved.
# Confidential and Proprietary - Qualcomm Technologies, Inc.

"""
Disconnect Analyzer Agent
Specialized agent for determining whether a disconnect was AP-initiated or STA-initiated
"""

import re
from typing import Any

from .base_agent import BaseAgent


class DisconnectAnalyzerAgent(BaseAgent):
    """
    Analyzes disconnect events to determine the initiator (AP vs STA).
    This agent looks for specific evidence patterns in hostapd logs.
    """

    def __init__(self, context, model: str = "qgenie"):
        super().__init__("DisconnectAnalyzer", context, model)

    def analyze(self) -> bool:
        """
        Analyze disconnect events to determine initiator
        
        Returns:
            bool: True if analysis succeeded
        """
        # Check if already cached
        if self.has_cached_data("disconnect_analysis"):
            self._log_info("Using cached disconnect analysis")
            return True

        # Get anomaly type
        anomaly_type = self.get_metadata("anomaly_type")

        # Only run for DISCONNECT anomalies
        if anomaly_type != "DISCONNECT":
            self._log_info(f"Skipping disconnect analysis for {anomaly_type}")
            return True

        # Get hostapd events
        hostapd_events = self.get_cached_data("hostapd_events")
        if not hostapd_events:
            self._log_warning("No hostapd events available for disconnect analysis")
            return True

        # Get raw syslog for additional analysis
        syslog = self.get_input_data("hostapd_log")

        # Perform analysis
        analysis = self._analyze_disconnect_initiator(hostapd_events, syslog)

        # Cache the analysis
        self.cache_data("disconnect_analysis", analysis)

        # Add as finding
        self.add_finding(
            finding_type="disconnect_initiator_analysis",
            content=analysis,
            confidence=analysis.get("confidence", "MEDIUM")
        )

        self._log_info(f"Disconnect analysis complete: {analysis.get('initiator', 'UNKNOWN')} initiated")
        return True

    def _analyze_disconnect_initiator(self, hostapd_events: list[dict[str, Any]],
                                     syslog: str | None) -> dict[str, Any]:
        """
        Analyze events and logs to determine disconnect initiator
        
        CRITICAL LOGIC:
        1. First check for RX DEAUTH/DISASSOC frames from STA - this is the smoking gun
        2. DEL_STATION by itself is NOT proof of AP-initiated (it's often cleanup after STA deauth)
        3. Only consider AP-initiated if we see AP sending DEAUTH/DISASSOC without prior RX from STA
        
        Returns:
            Dict with initiator, confidence, and evidence
        """
        evidence = {
            "sta_evidence": [],
            "ap_evidence": [],
            "sta_score": 0,
            "ap_score": 0
        }

        # CRITICAL: Check for timing-based evidence
        found_rx_deauth_from_sta = False
        found_ap_sending_deauth = False
        found_deauth_after_disconnect = False  # NEW: STA deauth came AFTER AP already disconnected
        found_del_station_before_deauth = False  # NEW: DEL_STATION came before RX deauth

        # 1. Check raw syslog for SMOKING GUN: "trying to deauthenticate, but it is not authenticated"
        # This means STA sent deauth AFTER AP already kicked it out = AP-initiated!
        if syslog:
            if re.search(r'trying to deauthenticate, but it is not authenticated', syslog, re.IGNORECASE):
                found_deauth_after_disconnect = True
                evidence['ap_score'] += 90  # SMOKING GUN for AP-initiated
                evidence['ap_evidence'].append({
                    "type": "smoking_gun_ap_initiated",
                    "description": "STA tried to deauth but was already disconnected by AP - clear AP-initiated kickout",
                    "weight": 90
                })

            # Check for DEL_STATION followed by RX DEAUTH (timing matters!)
            # If DEL_STATION comes BEFORE RX DEAUTH, it's AP-initiated
            del_station_match = re.search(r'nl80211: Drv Event 20 \(NL80211_CMD_DEL_STATION\)', syslog)
            rx_deauth_match = re.search(r'(RX frame.*stype=12.*DEAUTH|deauthentication: STA=.*reason_code=)', syslog)

            if del_station_match and rx_deauth_match:
                # Check positions to determine order
                if del_station_match.start() < rx_deauth_match.start():
                    found_del_station_before_deauth = True
                    evidence['ap_score'] += 70
                    evidence['ap_evidence'].append({
                        "type": "del_station_before_rx_deauth",
                        "description": "AP issued DEL_STATION before receiving deauth from STA - AP initiated the disconnect",
                        "weight": 70
                    })
                else:
                    # RX deauth came BEFORE DEL_STATION = STA-initiated
                    found_rx_deauth_from_sta = True
                    evidence['sta_score'] += 80
                    evidence['sta_evidence'].append({
                        "type": "rx_deauth_before_del_station",
                        "description": "Received DEAUTH frame FROM STA before DEL_STATION - clear STA-initiated disconnect",
                        "weight": 80
                    })
            elif rx_deauth_match and not del_station_match:
                # Only RX deauth, no DEL_STATION = likely STA-initiated
                found_rx_deauth_from_sta = True
                evidence['sta_score'] += 75
                evidence['sta_evidence'].append({
                    "type": "rx_deauth_frame",
                    "description": "Received DEAUTH frame FROM STA - STA-initiated disconnect",
                    "weight": 75
                })

            # Check for AP sending DEAUTH (not receiving)
            # Pattern: "sending DISASSOC" or "CMD_FRAME.*DEAUTH"
            ap_send_pattern = r'(sending\s+(DISASSOC|DEAUTH)|CMD_FRAME.*c0\s+00)'
            if re.search(ap_send_pattern, syslog, re.IGNORECASE):
                found_ap_sending_deauth = True

        # 2. Check hostapd events for additional evidence
        for event in hostapd_events:
            details = event.get('details', {})
            event_type = event.get('type', '')

            # Check for RX frame direction (frame received FROM STA)
            if details.get('frame_direction') == 'RX':
                if details.get('frame_type') in ['DEAUTH', 'DISASSOC']:
                    if not found_rx_deauth_from_sta:  # Don't double-count
                        found_rx_deauth_from_sta = True
                        evidence['sta_score'] += 70
                        evidence['sta_evidence'].append({
                            "type": "rx_frame",
                            "description": f"RX {details.get('frame_type')} frame from STA",
                            "line": event.get('line_number'),
                            "weight": 70
                        })

            # SMOKING GUN: "trying to deauthenticate, but it is not authenticated"
            if details.get('initiator') == 'STA':
                if not found_rx_deauth_from_sta:  # Don't double-count
                    found_rx_deauth_from_sta = True
                    evidence['sta_score'] += 70
                    evidence['sta_evidence'].append({
                        "type": "smoking_gun",
                        "description": "Station sent deauth frame after already being disconnected",
                        "line": event.get('line_number'),
                        "weight": 70
                    })

        # 3. Check for reason codes (secondary evidence)
        reason_codes_found = []
        for event in hostapd_events:
            details = event.get('details', {})
            reason_code = details.get('reason_code')
            if reason_code:
                reason_codes_found.append(reason_code)

                # Reason code 1 (Unspecified) is often STA-initiated
                if reason_code == 1 and found_rx_deauth_from_sta:
                    evidence['sta_score'] += 10  # Supporting evidence
                    evidence['sta_evidence'].append({
                        "type": "reason_code",
                        "description": f"Reason code {reason_code} (Unspecified - typical of STA-initiated)",
                        "line": event.get('line_number'),
                        "weight": 10
                    })

                # Reason codes 4, 5 are typically AP-initiated (inactivity, capacity)
                elif reason_code in [4, 5] and found_ap_sending_deauth:
                    evidence['ap_score'] += 15
                    evidence['ap_evidence'].append({
                        "type": "reason_code",
                        "description": f"Reason code {reason_code} (AP-initiated: inactivity/capacity)",
                        "line": event.get('line_number'),
                        "weight": 15
                    })

        # 4. Check for AP-initiated patterns (only if NO RX deauth from STA)
        if not found_rx_deauth_from_sta:
            # Look for AP sending DEAUTH/DISASSOC
            if found_ap_sending_deauth:
                evidence['ap_score'] += 60
                evidence['ap_evidence'].append({
                    "type": "ap_sending_deauth",
                    "description": "AP sent DEAUTH/DISASSOC frame (no prior RX from STA)",
                    "weight": 60
                })

            # Check for DEL_STATION without RX deauth
            for event in hostapd_events:
                details = event.get('details', {})
                event_type = event.get('type', '')

                if event_type == 'del_station' or details.get('action') in ['del_station', 'delete_station']:
                    evidence['ap_score'] += 20
                    evidence['ap_evidence'].append({
                        "type": "del_station",
                        "description": "AP deleted station entry (no RX deauth from STA observed)",
                        "line": event.get('line_number'),
                        "weight": 20
                    })
                    break  # Only count once

        # 5. Determine initiator based on evidence
        # CRITICAL: Timing-based evidence takes precedence
        if found_deauth_after_disconnect or found_del_station_before_deauth:
            # SMOKING GUN: AP kicked out STA, then STA sent deauth as cleanup
            initiator = "AP"
            confidence = "HIGH"
            explanation = "AP initiated disconnect - DEL_STATION occurred before STA's deauth frame (STA's deauth was cleanup response)"
        elif found_rx_deauth_from_sta and not found_deauth_after_disconnect:
            # STA sent deauth BEFORE AP deleted station = STA-initiated
            initiator = "STA"
            confidence = "HIGH"
            explanation = "STA sent deauth/disassoc frame to AP before AP deleted station - clear STA-initiated disconnect"
        elif found_ap_sending_deauth and not found_rx_deauth_from_sta:
            initiator = "AP"
            confidence = "HIGH"
            explanation = "AP sent deauth/disassoc frame without prior RX from STA - clear AP-initiated disconnect"
        elif evidence['ap_score'] > evidence['sta_score'] * 1.5:
            initiator = "AP"
            confidence = "MEDIUM"
            explanation = f"Evidence suggests AP-initiated disconnect (score: {evidence['ap_score']} vs {evidence['sta_score']})"
        elif evidence['sta_score'] > evidence['ap_score'] * 1.5:
            initiator = "STA"
            confidence = "MEDIUM"
            explanation = f"Evidence suggests STA-initiated disconnect (score: {evidence['sta_score']} vs {evidence['ap_score']})"
        else:
            initiator = "UNCLEAR"
            confidence = "LOW"
            explanation = f"Mixed or insufficient evidence (STA: {evidence['sta_score']}, AP: {evidence['ap_score']})"

        return {
            "initiator": initiator,
            "confidence": confidence,
            "explanation": explanation,
            "sta_score": evidence['sta_score'],
            "ap_score": evidence['ap_score'],
            "sta_evidence": evidence['sta_evidence'],
            "ap_evidence": evidence['ap_evidence'],
            "reason_codes": reason_codes_found
        }
