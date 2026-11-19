# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# All rights reserved.
# Confidential and Proprietary - Qualcomm Technologies, Inc.

"""
Evidence Collector Agent
Gathers supporting evidence with file references and line numbers
"""

from .base_agent import BaseAgent


class EvidenceCollectorAgent(BaseAgent):
    """Collects and organizes evidence supporting root cause hypotheses"""

    def __init__(self, context, model: str = "qgenie"):
        super().__init__("EvidenceCollector", context, model)

    def analyze(self) -> bool:
        """Collect evidence"""
        if self.has_cached_data("evidence"):
            self._log_info("Using cached evidence")
            return True

        # Gather all findings
        timeline = self.get_cached_data("timeline") or []
        kb_matches = self.get_cached_data("kb_matches") or []
        stats_analysis = self.get_cached_data("stats_analysis") or {}
        root_causes = self.get_cached_data("root_causes") or []

        # Collect evidence for each root cause
        evidence_collection = []

        for rc in root_causes:
            evidence = {
                "root_cause": rc.get("description", ""),
                "supporting_evidence": []
            }

            # Timeline evidence
            if timeline:
                evidence["supporting_evidence"].append({
                    "type": "timeline",
                    "source": "syslog.txt",
                    "description": f"{len(timeline)} events analyzed",
                    "key_events": [e.get("raw_line", "")[:100] for e in timeline[:3]]
                })

            # KB evidence
            for kb_match in kb_matches[:2]:
                evidence["supporting_evidence"].append({
                    "type": "knowledge_base",
                    "source": "knowledge_base.txt",
                    "section": kb_match.get("section", ""),
                    "relevance": kb_match.get("relevance", "")[:200]
                })

            # Stats evidence
            anomalies = stats_analysis.get("anomalies", [])
            if anomalies:
                evidence["supporting_evidence"].append({
                    "type": "statistics",
                    "source": "rate_of_change_wifistats.txt",
                    "anomalies": [f"{a['stat']}={a['value']}" for a in anomalies[:3]]
                })

            evidence_collection.append(evidence)

        self.cache_data("evidence", evidence_collection)

        for ev in evidence_collection:
            self.add_finding(
                finding_type="evidence",
                content=ev,
                confidence="HIGH"
            )

        self._log_info(f"Collected evidence for {len(evidence_collection)} root causes")
        return True
