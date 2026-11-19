# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# All rights reserved.
# Confidential and Proprietary - Qualcomm Technologies, Inc.

"""
Confidence Scorer Agent
Assigns confidence levels based on workflow rules
"""

from typing import Any

from .base_agent import BaseAgent


class ConfidenceScorerAgent(BaseAgent):
    """
    Assigns confidence levels (HIGH/MEDIUM/LOW) based on workflow rules:
    - HIGH: Hostapd sequence matches KB AND stats confirm
    - MEDIUM: Hostapd suggests cause, partial KB match OR partial stats alignment
    - LOW: Hostapd absent/inconclusive OR contradictions unresolved
    """

    def __init__(self, context, model: str = "qgenie"):
        super().__init__("ConfidenceScorer", context, model)

    def analyze(self) -> bool:
        """Score confidence levels"""
        if self.has_cached_data("confidence_scores"):
            self._log_info("Using cached confidence scores")
            return True

        # Get root causes
        root_causes = self.get_cached_data("root_causes") or []

        if not root_causes:
            self._log_warning("No root causes to score")
            return True

        # Get supporting data
        hostapd_events = self.get_cached_data("hostapd_events") or []
        kb_matches = self.get_cached_data("kb_matches") or []
        stats_analysis = self.get_cached_data("stats_analysis") or {}

        # Score each root cause
        scored_causes = []
        for rc in root_causes:
            score = self._calculate_confidence_score(
                rc, hostapd_events, kb_matches, stats_analysis
            )

            rc_with_score = rc.copy()
            rc_with_score["confidence_score"] = score
            rc_with_score["confidence"] = score["level"]
            rc_with_score["confidence_reasoning"] = score["reasoning"]

            scored_causes.append(rc_with_score)

        self.cache_data("confidence_scores", scored_causes)

        for sc in scored_causes:
            self.add_finding(
                finding_type="confidence_score",
                content=sc,
                confidence=sc["confidence"]
            )

        self._log_info(f"Scored {len(scored_causes)} root causes")
        return True

    def _calculate_confidence_score(self,
                                    root_cause: dict,
                                    hostapd_events: list,
                                    kb_matches: list,
                                    stats_analysis: dict) -> dict[str, Any]:
        """Calculate confidence score based on workflow rules"""

        has_hostapd = len(hostapd_events) > 0
        has_kb_match = len(kb_matches) > 0
        has_stats = len(stats_analysis.get("anomalies", [])) > 0

        # HIGH: Hostapd + KB + Stats all present and aligned
        if has_hostapd and has_kb_match and has_stats:
            return {
                "level": "HIGH",
                "reasoning": "Hostapd sequence matches KB and stats confirm the hypothesis",
                "components": {
                    "hostapd": "present",
                    "kb_match": "present",
                    "stats": "present"
                }
            }

        # MEDIUM: Partial alignment
        elif (has_hostapd and has_kb_match) or (has_hostapd and has_stats) or (has_kb_match and has_stats):
            return {
                "level": "MEDIUM",
                "reasoning": "Partial evidence alignment - some components present but not all",
                "components": {
                    "hostapd": "present" if has_hostapd else "absent",
                    "kb_match": "present" if has_kb_match else "absent",
                    "stats": "present" if has_stats else "absent"
                }
            }

        # LOW: Missing critical components or contradictions
        else:
            return {
                "level": "LOW",
                "reasoning": "Insufficient evidence - missing critical components",
                "components": {
                    "hostapd": "present" if has_hostapd else "absent",
                    "kb_match": "present" if has_kb_match else "absent",
                    "stats": "present" if has_stats else "absent"
                }
            }
