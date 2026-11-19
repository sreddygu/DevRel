# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# All rights reserved.
# Confidential and Proprietary - Qualcomm Technologies, Inc.

"""
Executive Summary Agent
Generates LLM-based executive summary synthesizing entire analysis
"""

from .base_agent import BaseAgent


class ExecutiveSummaryAgent(BaseAgent):
    """
    Generates executive summary by synthesizing all findings
    """

    def __init__(self, context, model: str = "qgenie"):
        super().__init__("ExecutiveSummary", context, model)

    def analyze(self) -> bool:
        """
        Generate executive summary
        
        Returns:
            bool: True if analysis succeeded
        """
        self._log_debug("=== ExecutiveSummary Agent Analysis Starting ===")

        # Check if already cached
        if self.has_cached_data("executive_summary"):
            self._log_info("Using cached executive summary")
            return True

        # Gather all findings and context
        anomaly_type = self.get_metadata("anomaly_type")
        mac_address = self.get_metadata("mac_address")

        # Get findings from other agents
        root_causes = self.get_cached_data("root_causes") or []
        confidence_assessment = self.get_cached_data("confidence_assessment") or {}
        timeline = self.get_cached_data("timeline") or []
        kb_matches = self.get_cached_data("kb_matches") or []
        stats_analysis = self.get_cached_data("stats_analysis") or {}

        self._log_debug(f"Anomaly: {anomaly_type}, MAC: {mac_address}")
        self._log_debug(f"Root causes: {len(root_causes)}, Timeline events: {len(timeline)}")

        # Create comprehensive context
        context_summary = self._create_context_for_summary(
            anomaly_type, mac_address, root_causes, confidence_assessment,
            timeline, kb_matches, stats_analysis
        )

        # Generate executive summary using LLM
        summary = self._generate_executive_summary(context_summary)

        if not summary:
            self._log_warning("Failed to generate executive summary")
            return False

        # Cache the summary
        self.cache_data("executive_summary", summary)

        # Add as finding
        self.add_finding(
            finding_type="executive_summary",
            content=summary,
            confidence=confidence_assessment.get("level", "UNKNOWN")
        )

        self._log_info("Generated executive summary")
        self._log_debug("=== ExecutiveSummary Agent Analysis Complete ===")
        return True

    def _create_context_for_summary(self,
                                   anomaly_type: str | None,
                                   mac_address: str | None,
                                   root_causes: list[dict],
                                   confidence_assessment: dict,
                                   timeline: list[dict],
                                   kb_matches: list[dict],
                                   stats_analysis: dict) -> str:
        """Create context for LLM to generate summary"""
        parts = []

        # Basic info
        parts.append("=== ISSUE OVERVIEW ===")
        if anomaly_type:
            parts.append(f"Anomaly Type: {anomaly_type}")
        if mac_address:
            parts.append(f"Station MAC: {mac_address}")
        parts.append("")

        # Root causes
        if root_causes:
            parts.append("=== ROOT CAUSES ===")
            for i, rc in enumerate(root_causes[:2], 1):  # Top 2
                parts.append(f"{i}. {rc.get('type', 'Unknown').upper()}: {rc.get('description', 'N/A')[:200]}")
                parts.append(f"   Confidence: {rc.get('confidence', 'UNKNOWN')}")
            parts.append("")

        # Confidence assessment
        if confidence_assessment:
            parts.append("=== CONFIDENCE ASSESSMENT ===")
            parts.append(f"Level: {confidence_assessment.get('level', 'UNKNOWN')}")
            parts.append(f"Reasoning: {confidence_assessment.get('reasoning', 'N/A')[:200]}")
            parts.append("")

        # Timeline summary
        if timeline:
            parts.append("=== TIMELINE SUMMARY ===")
            parts.append(f"Total events: {len(timeline)}")
            event_types = {}
            for event in timeline:
                et = event.get('event_type', 'unknown')
                event_types[et] = event_types.get(et, 0) + 1
            parts.append(f"Event distribution: {event_types}")
            parts.append("")

        # KB matches
        if kb_matches:
            parts.append("=== KB PATTERN MATCHES ===")
            for match in kb_matches[:2]:  # Top 2
                parts.append(f"- {match.get('section', 'Unknown')}")
            parts.append("")

        # Stats anomalies
        anomalies = stats_analysis.get("anomalies", [])
        if anomalies:
            parts.append("=== CRITICAL STATS ===")
            for anomaly in anomalies[:3]:  # Top 3
                parts.append(f"- {anomaly.get('stat', 'N/A')}: {anomaly.get('value', 'N/A')}")
            parts.append("")

        return "\n".join(parts)

    def _generate_executive_summary(self, context: str) -> dict[str, str] | None:
        """Use LLM to generate executive summary"""

        prompt = f"""Based on the following WiFi connectivity issue analysis, generate a concise executive summary.

{context}

Generate an executive summary with these exact fields:

1. Issue: One-line description of what happened (e.g., "STA xx:xx:xx:xx:xx:xx is experiencing DISCONNECT on WiFi")
2. Root Cause: Primary root cause in 5-10 words (e.g., "Client-Side Connectivity Issue" or "AP Inactivity Timer Timeout")
3. Severity: HIGH, MEDIUM, or LOW based on impact
4. Confidence: HIGH, MEDIUM, LOW, or UNKNOWN based on evidence quality

Format your response EXACTLY as:
ISSUE: <one-line description>
ROOT_CAUSE: <5-10 word cause>
SEVERITY: <HIGH/MEDIUM/LOW>
CONFIDENCE: <HIGH/MEDIUM/LOW/UNKNOWN>
"""

        response = self.call_llm(prompt, call_type="wifi")

        if not response:
            return None

        # Parse response
        summary = {}

        issue_match = re.search(r'ISSUE:\s*(.+?)(?=\n|ROOT_CAUSE:|$)', response, re.IGNORECASE)
        root_cause_match = re.search(r'ROOT_CAUSE:\s*(.+?)(?=\n|SEVERITY:|$)', response, re.IGNORECASE)
        severity_match = re.search(r'SEVERITY:\s*(HIGH|MEDIUM|LOW)', response, re.IGNORECASE)
        confidence_match = re.search(r'CONFIDENCE:\s*(HIGH|MEDIUM|LOW|UNKNOWN)', response, re.IGNORECASE)

        if issue_match:
            summary['issue'] = issue_match.group(1).strip()
        if root_cause_match:
            summary['root_cause'] = root_cause_match.group(1).strip()
        if severity_match:
            summary['severity'] = severity_match.group(1).upper()
        if confidence_match:
            summary['confidence'] = confidence_match.group(1).upper()

        # Provide defaults if parsing failed
        if not summary.get('issue'):
            summary['issue'] = "WiFi connectivity issue detected"
        if not summary.get('root_cause'):
            summary['root_cause'] = "Under investigation"
        if not summary.get('severity'):
            summary['severity'] = "MEDIUM"
        if not summary.get('confidence'):
            summary['confidence'] = "UNKNOWN"

        return summary


import re
