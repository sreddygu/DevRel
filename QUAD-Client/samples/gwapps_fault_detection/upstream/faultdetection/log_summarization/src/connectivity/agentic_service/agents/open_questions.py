# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# All rights reserved.
# Confidential and Proprietary - Qualcomm Technologies, Inc.

"""
Open Questions Agent
Identifies missing data and suggests additional data collection
"""

from .base_agent import BaseAgent


class OpenQuestionsAgent(BaseAgent):
    """
    Identifies gaps in available data and suggests what additional
    information would help confirm or refute the root cause
    """

    def __init__(self, context, model: str = "qgenie"):
        super().__init__("OpenQuestions", context, model)

    def analyze(self) -> bool:
        """
        Identify open questions and missing data
        
        Returns:
            bool: True if analysis succeeded
        """
        self._log_debug("=== OpenQuestions Agent Analysis Starting ===")

        # Check if already cached
        if self.has_cached_data("open_questions"):
            self._log_info("Using cached open questions")
            return True

        # Gather context about what we have and what we analyzed
        anomaly_type = self.get_metadata("anomaly_type")
        root_causes = self.get_cached_data("root_causes") or []
        confidence_assessment = self.get_cached_data("confidence_assessment") or {}
        timeline = self.get_cached_data("timeline") or []
        kb_matches = self.get_cached_data("kb_matches") or []
        stats_analysis = self.get_cached_data("stats_analysis") or {}

        # Check what input data we have
        has_hostapd = len(timeline) > 0
        has_stats = len(stats_analysis.get("parsed_stats", {})) > 0
        has_kb_matches = len(kb_matches) > 0

        self._log_debug(f"Has hostapd: {has_hostapd}, Has stats: {has_stats}, Has KB matches: {has_kb_matches}")
        self._log_debug(f"Confidence level: {confidence_assessment.get('level', 'UNKNOWN')}")

        # Create context for LLM
        context_summary = self._create_context_for_questions(
            anomaly_type, root_causes, confidence_assessment,
            has_hostapd, has_stats, has_kb_matches, timeline, stats_analysis
        )

        # Generate open questions using LLM
        questions = self._generate_open_questions(context_summary)

        if not questions:
            self._log_warning("Failed to generate open questions")
            return False

        # Cache the questions
        self.cache_data("open_questions", questions)

        # Add as finding
        self.add_finding(
            finding_type="open_questions",
            content=questions
        )

        self._log_info(f"Identified {len(questions.get('missing_info', []))} missing information items")
        self._log_debug("=== OpenQuestions Agent Analysis Complete ===")
        return True

    def _create_context_for_questions(self,
                                     anomaly_type: str | None,
                                     root_causes: list[dict],
                                     confidence_assessment: dict,
                                     has_hostapd: bool,
                                     has_stats: bool,
                                     has_kb_matches: bool,
                                     timeline: list[dict],
                                     stats_analysis: dict) -> str:
        """Create context for LLM to identify gaps"""
        parts = []

        # Issue context
        parts.append("=== ANALYSIS CONTEXT ===")
        parts.append(f"Anomaly Type: {anomaly_type or 'Unknown'}")
        parts.append(f"Confidence Level: {confidence_assessment.get('level', 'UNKNOWN')}")
        parts.append("")

        # Data availability
        parts.append("=== AVAILABLE DATA ===")
        parts.append(f"Hostapd logs: {'Yes' if has_hostapd else 'No'}")
        if has_hostapd:
            parts.append(f"  - Events captured: {len(timeline)}")
            event_types = set(e.get('event_type', 'unknown') for e in timeline)
            parts.append(f"  - Event types: {', '.join(event_types)}")
        parts.append(f"WiFi stats: {'Yes' if has_stats else 'No'}")
        if has_stats:
            parts.append(f"  - Stats sections: {len(stats_analysis.get('parsed_stats', {}))}")
            parts.append(f"  - Anomalies found: {len(stats_analysis.get('anomalies', []))}")
        parts.append(f"KB matches: {'Yes' if has_kb_matches else 'No'}")
        parts.append("")

        # Root cause hypotheses
        if root_causes:
            parts.append("=== ROOT CAUSE HYPOTHESES ===")
            for i, rc in enumerate(root_causes[:2], 1):
                parts.append(f"{i}. {rc.get('description', 'N/A')[:150]}")
                parts.append(f"   Confidence: {rc.get('confidence', 'UNKNOWN')}")
            parts.append("")

        # Confidence reasoning
        if confidence_assessment.get('reasoning'):
            parts.append("=== CONFIDENCE REASONING ===")
            parts.append(confidence_assessment['reasoning'][:300])
            parts.append("")

        return "\n".join(parts)

    def _generate_open_questions(self, context: str) -> dict[str, list[str]] | None:
        """Use LLM to identify missing data and open questions"""

        prompt = f"""Based on the following WiFi connectivity issue analysis, identify what information is missing or unknown that would help confirm or refute the root cause.

{context}

Identify two categories:

1. MISSING INFORMATION: What data is not available in the current logs that would be valuable?
   Examples:
   - Client device details (model, OS, driver version)
   - Signal strength (RSSI) at time of disconnect
   - Prior connection history
   - Roaming context
   - Specific hostapd debug sections
   - Client-side logs (wpa_supplicant)
   - Environmental data (channel utilization, neighboring APs)

2. SUGGESTED DATA COLLECTION: What specific commands or actions would gather the missing data?
   Examples:
   - Enable enhanced debug: cfg80211tool mld0 link_id 2 dbgLVL 0x80c00000
   - Capture stats: wifistats wifi1 11 --mac <MAC>
   - Check configuration: cat /proc/wifi1/ic_config
   - Packet capture: tcpdump -i mld0 -w /tmp/capture.pcap

Format your response as:

MISSING_INFORMATION:
- <item 1>
- <item 2>
- <item 3>
...

SUGGESTED_DATA_COLLECTION:
- <command/action 1>
- <command/action 2>
- <command/action 3>
...
"""

        response = self.call_llm(prompt, call_type="hostapd")

        if not response:
            return None

        # Parse response
        questions = {
            'missing_info': [],
            'suggested_collection': []
        }

        # Extract missing information
        missing_section = re.search(
            r'MISSING_INFORMATION:(.*?)(?=SUGGESTED_DATA_COLLECTION:|$)',
            response,
            re.DOTALL | re.IGNORECASE
        )
        if missing_section:
            items = re.findall(r'[-•]\s*(.+)', missing_section.group(1))
            questions['missing_info'] = [item.strip() for item in items if item.strip()]

        # Extract suggested collection
        collection_section = re.search(
            r'SUGGESTED_DATA_COLLECTION:(.*?)$',
            response,
            re.DOTALL | re.IGNORECASE
        )
        if collection_section:
            items = re.findall(r'[-•]\s*(.+)', collection_section.group(1))
            questions['suggested_collection'] = [item.strip() for item in items if item.strip()]

        # Ensure we have at least some content
        if not questions['missing_info']:
            questions['missing_info'] = ["Additional debug logs would help confirm the root cause"]
        if not questions['suggested_collection']:
            questions['suggested_collection'] = ["Enable enhanced hostapd debug logging"]

        return questions


import re
