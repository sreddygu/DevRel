# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# All rights reserved.
# Confidential and Proprietary - Qualcomm Technologies, Inc.

"""
Root Cause Agent
Formulates hypotheses based on hostapd + KB + stats alignment
"""

import re
from typing import Any

from .base_agent import BaseAgent


class RootCauseAgent(BaseAgent):
    """
    Formulates root cause hypotheses by synthesizing findings from:
    - Hostapd events and timeline
    - KB matches
    - Stats analysis
    """

    # ---------------------------------------------------------------------------
    # Maps anomaly type → frozenset of applicable prompt rule names.
    # Only rules present in this set are injected into the LLM prompt for that
    # anomaly type.  This ensures the LLM can only reason about evidence that is
    # relevant to the current anomaly category — it never sees patterns that
    # belong to a different category (e.g. wrong_password for DATA_STALL).
    # ---------------------------------------------------------------------------
    _ANOMALY_RULES: dict[str, frozenset[str]] = {
        "DATA_STALL": frozenset([
            "evidence", "examples", "confidence",
            "cca_obss", "rts_success_rate",
        ]),
        "BEACON_STUCK": frozenset([
            "evidence", "examples", "confidence",
            "cca_obss",
        ]),
        "DISCONNECT": frozenset([
            "evidence", "examples", "confidence",
            "disconnect_initiator", "log_evidence",
        ]),
        "FAIL_TO_CONNECT": frozenset([
            "evidence", "examples", "confidence",
            "disconnect_initiator", "log_evidence",
        ]),
    }

    def __init__(self, context, model: str = "qgenie"):
        super().__init__("RootCause", context, model)

    def analyze(self) -> bool:
        """
        Formulate root cause hypotheses

        Returns:
            bool: True if analysis succeeded
        """
        self._log_debug("=== RootCause Agent Analysis Starting ===")

        # Check if already cached
        if self.has_cached_data("root_causes"):
            self._log_info("Using cached root causes")
            return True

        # Gather all findings
        self._log_debug("Gathering findings from shared context...")
        timeline = self.get_cached_data("timeline") or []
        kb_matches = self.get_cached_data("kb_matches") or []
        stats_analysis = self.get_cached_data("stats_analysis") or {}
        disconnect_analysis = self.get_cached_data("disconnect_analysis") or {}
        known_issues = self.get_cached_data("known_issues") or []
        hostapd_pattern = self.get_findings(finding_type="hostapd_pattern_analysis")
        timing_analysis = self.get_findings(finding_type="timing_analysis")

        self._log_debug(f"Timeline events: {len(timeline)}")
        self._log_debug(f"KB matches: {len(kb_matches)}")
        self._log_debug(f"Stats analysis keys: {list(stats_analysis.keys())}")
        self._log_debug(f"Disconnect analysis: {disconnect_analysis.get('initiator', 'N/A')}")
        self._log_debug(f"Known issues: {len(known_issues)}")
        self._log_debug(f"Hostapd pattern findings: {len(hostapd_pattern)}")
        self._log_debug(f"Timing analysis findings: {len(timing_analysis)}")

        # Get metadata
        anomaly_type = self.get_metadata("anomaly_type")
        mac_address = self.get_metadata("mac_address")

        self._log_debug(f"Anomaly type: {anomaly_type}")
        self._log_debug(f"MAC address: {mac_address}")

        # Create comprehensive context for LLM
        self._log_debug("Creating context summary...")
        context_summary = self._create_context_summary(
            anomaly_type, mac_address, timeline, kb_matches,
            stats_analysis, disconnect_analysis, known_issues, hostapd_pattern, timing_analysis
        )

        self._log_debug(f"Context summary length: {len(context_summary)} characters")
        self._log_debug(f"Context summary preview (first 500 chars):\n{context_summary[:500]}")

        # Use LLM to formulate root causes
        self._log_debug("Calling LLM to formulate root causes...")
        root_causes = self._formulate_root_causes(context_summary, anomaly_type)

        self._log_debug(f"LLM returned {len(root_causes) if root_causes else 0} root causes")

        if not root_causes:
            self._log_warning("Failed to formulate root causes - LLM returned empty result")
            return False

        # Cache root causes
        self._log_debug("Caching root causes...")
        self.cache_data("root_causes", root_causes)

        # Add findings
        self._log_debug("Adding root cause findings to shared context...")
        for i, rc in enumerate(root_causes):
            self._log_debug(f"Root cause {i+1}: {rc.get('description', 'N/A')[:100]}")
            self.add_finding(
                finding_type="root_cause",
                content=rc,
                confidence=rc.get("confidence", "MEDIUM"),
                metadata={"priority": i + 1}
            )

        self._log_info(f"Formulated {len(root_causes)} root cause hypotheses")
        self._log_debug("=== RootCause Agent Analysis Complete ===")
        return True

    def _create_context_summary(self,
                                anomaly_type: str | None,
                                mac_address: str | None,
                                timeline: list[dict],
                                kb_matches: list[dict],
                                stats_analysis: dict,
                                disconnect_analysis: dict,
                                known_issues: list[dict],
                                hostapd_pattern: list,
                                timing_analysis: list) -> str:
        """Create comprehensive context summary"""
        summary_parts = []

        # Basic info
        summary_parts.append("=== ISSUE CONTEXT ===")
        if anomaly_type:
            summary_parts.append(f"Anomaly Type: {anomaly_type}")
        if mac_address:
            summary_parts.append(f"MAC Address: {mac_address}")
        summary_parts.append("")

        # Disconnect analysis (CRITICAL for determining initiator)
        if disconnect_analysis:
            summary_parts.append("=== DISCONNECT INITIATOR ANALYSIS (HIGH PRIORITY) ===")
            summary_parts.append(f"Initiator: {disconnect_analysis.get('initiator', 'UNKNOWN')}")
            summary_parts.append(f"Confidence: {disconnect_analysis.get('confidence', 'LOW')}")
            summary_parts.append(f"Explanation: {disconnect_analysis.get('explanation', '')}")

            # Add evidence details
            sta_evidence = disconnect_analysis.get('sta_evidence', [])
            if sta_evidence:
                summary_parts.append("STA Evidence:")
                for item in sta_evidence:
                    summary_parts.append(f"- {item.get('description', '')}")

            ap_evidence = disconnect_analysis.get('ap_evidence', [])
            if ap_evidence:
                summary_parts.append("AP Evidence:")
                for item in ap_evidence:
                    summary_parts.append(f"- {item.get('description', '')}")

            summary_parts.append("")

        # Known issues (if any detected)
        if known_issues:
            summary_parts.append("=== KNOWN ISSUE CHECKS ===")
            for issue in known_issues:
                summary_parts.append(f"Issue Type: {issue.get('issue_type', 'Unknown')}")
                summary_parts.append(f"Description: {issue.get('description', '')}")
                summary_parts.append(f"Confidence: {issue.get('confidence', 'UNKNOWN')}")
                evidence = issue.get('evidence', [])
                if evidence:
                    summary_parts.append("Evidence:")
                    for ev in evidence[:3]:  # Limit to 3 pieces of evidence per issue
                        summary_parts.append(f"- {ev.get('matched_text', '')}")
                summary_parts.append("")

        # Timeline summary with technical details
        if timeline:
            summary_parts.append("=== TIMELINE ANALYSIS ===")
            summary_parts.append(f"Total events: {len(timeline)}")
            event_types = {}
            specific_details = []

            for event in timeline:
                et = event.get('event_type', 'unknown')
                event_types[et] = event_types.get(et, 0) + 1

                # Collect specific technical details
                details = event.get('details', {})
                if isinstance(details, dict):
                    if 'reason_code' in details:
                        specific_details.append(f"Reason Code: {details['reason_code']}")
                    if 'status' in details:
                        specific_details.append(f"Status: {details['status']}")
                    if 'eapol_message' in details:
                        specific_details.append(f"EAPOL: {details['eapol_message']}")
                    if 'sae_state' in details:
                        specific_details.append(f"SAE State: {details['sae_state']}")

            summary_parts.append(f"Event types: {event_types}")

            # Add unique specific details to context
            if specific_details:
                unique_details = list(set(specific_details))
                summary_parts.append("Key Technical Indicators found in logs:")
                for detail in unique_details[:10]:  # Limit to top 10 unique details
                    summary_parts.append(f"- {detail}")

            # Add sequence snippet
            summary_parts.append("\nLog Sequence Snippet:")
            for event in timeline[:10]:
                ts = event.get('timestamp', '')
                et = event.get('event_type', '').upper()
                det = event.get('details', '')
                summary_parts.append(f"{ts}: {et} - {det}")
            summary_parts.append("")

        # Hostapd pattern analysis
        if hostapd_pattern:
            summary_parts.append("=== HOSTAPD PATTERN ANALYSIS ===")
            for finding in hostapd_pattern:
                summary_parts.append(finding.content.get("analysis", ""))
            summary_parts.append("")

        # Timing analysis
        if timing_analysis:
            summary_parts.append("=== TIMING ANALYSIS ===")
            for finding in timing_analysis[:1]:
                summary_parts.append(finding.content.get("analysis", "")[:500])
            summary_parts.append("")

        # KB matches
        if kb_matches:
            summary_parts.append("=== KB MATCHES ===")
            for match in kb_matches[:3]:  # Top 3
                summary_parts.append(f"- {match.get('section', 'Unknown')}")
                if match.get('relevance'):
                    summary_parts.append(f"  Relevance: {match['relevance'][:200]}")
            summary_parts.append("")

        # CCA OBSS data — always surface when present (not subject to top-5 limit)
        anomalies = stats_analysis.get("anomalies", [])
        cca_obss_anomalies = [a for a in anomalies if a.get('type') == 'high_cca_obss']
        if cca_obss_anomalies:
            summary_parts.append("=== CCA OBSS CHANNEL CONGESTION ===")
            for anomaly in cca_obss_anomalies:
                summary_parts.append(
                    f"- chan_num={anomaly.get('chan_num', 'N/A')}: "
                    f"cca_obss_pct = {anomaly.get('value', 'N/A')}% "
                    f"(severity={anomaly.get('severity', 'N/A')})"
                )
                summary_parts.append(f"  {anomaly.get('description', '')}")
            summary_parts.append("")

        # RTS success rate — always surface when present (not subject to top-5 limit)
        rts_anomalies = [a for a in anomalies if a.get('type') == 'low_rts_success_rate']
        if rts_anomalies:
            summary_parts.append("=== RTS SUCCESS RATE ===")
            for anomaly in rts_anomalies:
                success_rate = anomaly.get('value', 'N/A')
                failure_rate = round(100.0 - success_rate, 2) if isinstance(success_rate, (int, float)) else 'N/A'
                summary_parts.append(
                    f"- mac_id={anomaly.get('mac_id', 'N/A')}: "
                    f"rts_success_rate = {success_rate}% "
                    f"({failure_rate}% failure rate) "
                    f"(severity={anomaly.get('severity', 'N/A')})"
                )
                summary_parts.append(f"  {anomaly.get('description', '')}")
            summary_parts.append("")

        # Stats anomalies (general, excluding cca_obss and rts which have their own sections)
        non_dedicated_anomalies = [
            a for a in anomalies
            if a.get('type') not in ('high_cca_obss', 'low_rts_success_rate')
        ]
        if non_dedicated_anomalies:
            summary_parts.append("=== STATS ANOMALIES ===")
            for anomaly in non_dedicated_anomalies[:5]:  # Top 5
                summary_parts.append(
                    f"- {anomaly['type']}: {anomaly.get('stat', '')} = {anomaly.get('value', '')}"
                )
            summary_parts.append("")

        return "\n".join(summary_parts)

    def _formulate_root_causes(self, context_summary: str,
                               anomaly_type: str | None = None) -> list[dict[str, Any]]:
        """
        Use LLM to formulate root cause hypotheses.

        The prompt is built dynamically: only the rule blocks that are applicable
        to the current anomaly type (as defined in _ANOMALY_RULES) are included.
        This prevents the LLM from reasoning about evidence categories that are
        irrelevant to the anomaly being analyzed.
        """
        atype = (anomaly_type or "UNKNOWN").upper()
        applicable = self._ANOMALY_RULES.get(atype, frozenset(["evidence", "examples", "confidence"]))

        # ------------------------------------------------------------------
        # Define each rule block as a standalone string.
        # Blocks are appended in order and numbered sequentially so the LLM
        # always sees a clean 1-through-N list with no gaps.
        # ------------------------------------------------------------------

        rule_evidence = """\
EVIDENCE REQUIREMENT (MANDATORY):
   - You MUST cite SPECIFIC log lines, error messages, or stat values from the context above
   - Quote the EXACT text from logs (e.g., "SAE: Confirm mismatch", "reason_code=15")
   - Include timestamps or line identifiers when available
   - If you cannot find direct evidence in the logs, state "Insufficient evidence to determine root cause" rather than speculating"""

        rule_examples = """\
EXAMPLES OF GOOD vs BAD EXPLANATIONS:

   GOOD (Evidence-based):
   "Root Cause: Low RTS success rate causing data stall
   Evidence: Stats show rts_success_rate = 13.8% on mac_id 0 (86.2% failure rate)
   [severity: HIGH]. This indicates the AP cannot obtain CTS responses, severely
   impairing channel access and causing the data stall."

   GOOD (Evidence-based):
   "Root Cause: Wrong password
   Evidence: Log shows 'SAE: Confirm mismatch' at timestamp 1762305962.175731.
   This message definitively indicates that the WPA3-SAE authentication failed
   because the client's password hash does not match the AP's expected value."

   BAD (Speculative):
   "Root Cause: Possible MLO race condition
   Evidence: Multiple DEL_STATION events observed
   Explanation: The AP may have issues with MLO context mapping..."
   (This is bad because DEL_STATION alone doesn't prove MLO race condition —
   need specific MLO error messages)"""

        rule_disconnect_initiator = """\
DISCONNECT INITIATOR RESPECT:
   - If "DISCONNECT INITIATOR ANALYSIS" is present, you MUST respect its findings
   - If initiator is "STA", describe a STA-initiated scenario (e.g., "Client-initiated disconnect due to...")
   - If initiator is "AP", describe an AP-initiated scenario (e.g., "AP-initiated disconnect due to...")"""

        rule_log_evidence = """\
SPECIFIC EVIDENCE TO LOOK FOR:
   - Wrong password: "SAE: Confirm mismatch", "invalid MIC in msg", "EAPOL M2 failure"
   - AP kickout: "DEL_STATION", "ap_sta_disconnect", "sending DISASSOC", reason codes 4/5
   - STA disconnect: "trying to deauthenticate, but not authenticated", "Received Deauth", reason codes 1/3
   - MFP SA Query: "SA Query" + "fail after AP kickout"
   - EAPOL failures: "4-Way Handshake timeout", "Group Key Handshake timeout", specific EAPOL-Key msg failures
   - MLO issues: "MLD: Error in max simultaneous links", "MLD: Invalid MLD address", "MLO Assoc failure" """

        rule_confidence = """\
CONFIDENCE LEVELS:
   - HIGH: Direct error message found (e.g., "SAE: Confirm mismatch") + matches known pattern
   - MEDIUM: Indirect evidence (e.g., reason codes) + partial pattern match
   - LOW: Only circumstantial evidence or contradictions present"""

        rule_cca_obss = """\
CCA OBSS REQUIREMENT:
   - Thresholds: >= 80% → HIGH, >= 40% → MEDIUM, < 40% → LOW
   - If severity is HIGH or MEDIUM, you MUST explicitly state the cca_obss_pct value
     in the Evidence section and include it as a root cause.
   - If severity is LOW (< 40%), the CCA OBSS level is NOT a root cause. Do NOT
     list it as a suspected cause, even if a "CCA OBSS CHANNEL CONGESTION" section
     is present. A low cca_obss_pct means OBSS interference is negligible.
   - Example evidence line (HIGH): "Stats show cca_obss_pct = 95.9% on channel 2412,
     indicating the channel is occupied by OBSS traffic 95.9% of the time" """

        rule_rts_success_rate = """\
RTS SUCCESS RATE REQUIREMENT:
   - Thresholds: < 20% success rate → HIGH, < 50% → MEDIUM, >= 50% → LOW
   - If a "RTS SUCCESS RATE" section is present with HIGH severity (< 20% success rate),
     you MUST list it as a primary root cause and explicitly state the rts_success_rate
     value and failure rate in the Evidence section.
   - If severity is MEDIUM (20–49% success rate), include it as a contributing factor.
   - If severity is LOW (>= 50% success rate), it is NOT a root cause.
   - Example evidence line (HIGH): "Stats show rts_success_rate = 13.8% on mac_id 0
     (86.2% failure rate), indicating severe channel access impairment"
   - If a `low_rts_success_rate` known issue appears in "KNOWN ISSUE CHECKS" with
     HIGH or MEDIUM confidence, it MUST be reflected in the root cause analysis."""

        # Build the ordered list of applicable rule blocks
        ordered_blocks = [
            ("evidence",             rule_evidence),
            ("examples",             rule_examples),
            ("disconnect_initiator", rule_disconnect_initiator),
            ("log_evidence",         rule_log_evidence),
            ("confidence",           rule_confidence),
            ("cca_obss",             rule_cca_obss),
            ("rts_success_rate",     rule_rts_success_rate),
        ]

        rules_text_parts = []
        rule_num = 1
        for rule_name, rule_body in ordered_blocks:
            if rule_name in applicable:
                rules_text_parts.append(f"{rule_num}. {rule_body}")
                rule_num += 1

        rules_text = "\n\n".join(rules_text_parts)

        prompt = f"""Based on the following WiFi connectivity issue analysis:

{context_summary}

CRITICAL RULES FOR ROOT CAUSE ANALYSIS:

{rules_text}

Format your response exactly as follows:
PRIMARY HYPOTHESIS:
Description: [Specific technical root cause - must cite exact log messages]
Evidence: [Quote exact log lines with timestamps. Example: "syslog.txt shows 'SAE: Confirm mismatch' at 1762305962.175731"]
Explanation: [How this evidence proves the root cause]
Confidence: [HIGH/MEDIUM/LOW]
---
SECONDARY HYPOTHESIS:
Description: [Alternative root cause if evidence supports it]
Evidence: [Quote exact log lines with timestamps]
Explanation: [How this evidence supports this alternative]
Confidence: [HIGH/MEDIUM/LOW]
---

If you cannot find sufficient evidence for a secondary hypothesis, omit it entirely rather than speculating.
"""

        self._log_debug(f"LLM prompt length: {len(prompt)} characters")
        self._log_debug(f"Applicable rules for {atype}: {sorted(applicable)}")
        self._log_debug("Calling LLM with call_type='hostapd'...")

        response = self.call_llm(prompt, call_type="hostapd")

        self._log_debug(f"LLM response type: {type(response)}")
        self._log_debug(f"LLM response is None: {response is None}")

        if response:
            self._log_debug(f"LLM response length: {len(response)} characters")
            self._log_debug(f"LLM response preview (first 500 chars):\n{response[:500]}")
            self._log_debug("Parsing LLM response...")
            parsed = self._parse_root_cause_response(response)
            self._log_debug(f"Parsed {len(parsed)} root causes from response")
            return parsed
        else:
            self._log_warning("LLM returned None or empty response")

        return []

    def _parse_root_cause_response(self, response: str) -> list[dict[str, Any]]:
        """Parse LLM response to extract root causes"""
        root_causes = []

        # Split by separator
        hypotheses = response.split('---')

        for i, hypothesis in enumerate(hypotheses):
            if not hypothesis.strip():
                continue

            # Determine if primary or secondary
            is_primary = 'PRIMARY' in hypothesis.upper()

            # Extract fields
            desc_match = re.search(r'Description:\s*(.+?)(?=\nEvidence:|\nExplanation:|$)', hypothesis, re.IGNORECASE | re.DOTALL)
            evidence_match = re.search(r'Evidence:\s*(.+?)(?=\nExplanation:|\nConfidence:|$)', hypothesis, re.IGNORECASE | re.DOTALL)
            explanation_match = re.search(r'Explanation:\s*(.+?)(?=\nConfidence:|$)', hypothesis, re.IGNORECASE | re.DOTALL)
            conf_match = re.search(r'Confidence:\s*(HIGH|MEDIUM|LOW)', hypothesis, re.IGNORECASE)

            if desc_match:
                root_cause = {
                    "type": "primary" if is_primary else "secondary",
                    "description": desc_match.group(1).strip(),
                    "evidence": evidence_match.group(1).strip() if evidence_match else "",
                    "explanation": explanation_match.group(1).strip() if explanation_match else "",
                    "confidence": conf_match.group(1).upper() if conf_match else "MEDIUM",
                    "priority": 1 if is_primary else 2
                }
                root_causes.append(root_cause)

        return root_causes
