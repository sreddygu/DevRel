# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# All rights reserved.
# Confidential and Proprietary - Qualcomm Technologies, Inc.

"""
Report Generator Agent
Produces structured output matching LogiQ format
"""

from .base_agent import BaseAgent


class ReportGeneratorAgent(BaseAgent):
    """
    Generates final triage report in LogiQ format with:
    - Executive Summary
    - Timeline Analysis
    - Critical Findings
    - Configuration Details
    - Root Cause Hypothesis
    - Recommended Actions
    - Evidence Summary Table
    """

    def __init__(self, context, model: str = "qgenie"):
        super().__init__("ReportGenerator", context, model)

    def analyze(self) -> bool:
        """Generate final report"""
        if self.has_cached_data("final_report"):
            self._log_info("Using cached report")
            return True

        # Gather all analysis results
        timeline = self.get_cached_data("timeline") or []
        root_causes = self.get_cached_data("confidence_scores") or self.get_cached_data("root_causes") or []
        evidence = self.get_cached_data("evidence") or []
        mitigations = self.get_cached_data("mitigations") or []
        kb_matches = self.get_cached_data("kb_matches") or []
        stats_analysis = self.get_cached_data("stats_analysis") or {}

        # Get metadata
        anomaly_type = self.get_metadata("anomaly_type")
        mac_address = self.get_metadata("mac_address")

        # Generate report sections
        report = {
            "executive_summary": self._generate_executive_summary(anomaly_type, mac_address, root_causes),
            "timeline_analysis": self._generate_timeline_analysis(timeline),
            "critical_findings": self._generate_critical_findings(timeline, kb_matches, stats_analysis),
            "configuration_details": self._generate_configuration_details(mac_address),
            "root_cause_hypothesis": self._generate_root_cause_section(root_causes),
            "recommended_actions": self._generate_recommended_actions(mitigations),
            "evidence_summary": self._generate_evidence_summary(evidence, kb_matches, stats_analysis)
        }

        # Format as text report
        formatted_report = self._format_report(report)

        self.cache_data("final_report", formatted_report)

        self.add_finding(
            finding_type="final_report",
            content={"report": formatted_report},
            confidence="HIGH"
        )

        self._log_info("Generated final triage report")
        return True

    def _generate_executive_summary(self, anomaly_type: str, mac_address: str, root_causes: list[dict]) -> dict:
        """Generate executive summary section"""
        primary_rc = root_causes[0] if root_causes else {}

        return {
            "issue": f"STA {mac_address} is experiencing {anomaly_type} on WiFi",
            "root_cause": primary_rc.get("description", "Under investigation"),
            "severity": "High" if primary_rc.get("confidence") == "HIGH" else "Medium",
            "confidence": primary_rc.get("confidence", "UNKNOWN")
        }

    def _generate_timeline_analysis(self, timeline: list[dict]) -> list[dict]:
        """Generate timeline analysis section"""
        timeline_entries = []

        for entry in timeline[:20]:  # Limit to 20 events
            timeline_entries.append({
                "timestamp": entry.get("timestamp", ""),
                "delta": f"+{entry.get('delta_ms', 0):.1f}ms" if entry.get('delta_ms') else "-",
                "event": entry.get("event_type", "").upper(),
                "source": entry.get("source", ""),
                "details": str(entry.get("details", ""))
            })

        return timeline_entries

    def _generate_critical_findings(self, timeline: list[dict], kb_matches: list[dict], stats_analysis: dict) -> list[dict]:
        """Generate critical findings section"""
        findings = []
        finding_num = 1

        # Finding from timeline patterns
        if timeline:
            event_types = {}
            for event in timeline:
                et = event.get('event_type', 'unknown')
                event_types[et] = event_types.get(et, 0) + 1

            if event_types.get('disassoc', 0) > 3 or event_types.get('deauth', 0) > 3:
                findings.append({
                    "number": finding_num,
                    "title": "Repeated Disconnection Events",
                    "description": f"Multiple disconnect events observed: {event_types}",
                    "evidence": f"Timeline shows {len(timeline)} events"
                })
                finding_num += 1

        # Finding from stats
        anomalies = stats_analysis.get("anomalies", [])
        if anomalies:
            high_severity = [a for a in anomalies if a.get('severity') == 'HIGH']
            if high_severity:
                findings.append({
                    "number": finding_num,
                    "title": "High Severity Statistics Anomalies",
                    "description": f"Found {len(high_severity)} high-severity stat anomalies",
                    "evidence": ", ".join([f"{a['stat']}={a['value']}" for a in high_severity[:3]])
                })
                finding_num += 1

        # Finding from KB matches
        if kb_matches:
            findings.append({
                "number": finding_num,
                "title": "Knowledge Base Pattern Match",
                "description": f"Issue matches {len(kb_matches)} KB patterns",
                "evidence": f"Top match: {kb_matches[0].get('section', 'Unknown')}"
            })

        return findings

    def _generate_configuration_details(self, mac_address: str) -> dict:
        """Generate configuration details section"""
        return {
            "sta_mac": mac_address or "Unknown",
            "interface": "Detected from logs",
            "band": "Detected from logs",
            "authentication": "Detected from logs"
        }

    def _generate_root_cause_section(self, root_causes: list[dict]) -> dict:
        """Generate root cause hypothesis section"""
        primary = root_causes[0] if root_causes else {}
        secondary = root_causes[1] if len(root_causes) > 1 else {}

        return {
            "primary": {
                "description": primary.get("description", "Under investigation"),
                "evidence": primary.get("evidence", ""),
                "explanation": primary.get("explanation", ""),
                "confidence": primary.get("confidence", "UNKNOWN")
            },
            "secondary": {
                "description": secondary.get("description", "No secondary hypothesis"),
                "evidence": secondary.get("evidence", ""),
                "explanation": secondary.get("explanation", ""),
                "confidence": secondary.get("confidence", "UNKNOWN")
            } if secondary else None
        }

    def _generate_recommended_actions(self, mitigations: list[dict]) -> dict:
        """Generate recommended actions section"""
        actions = {
            "high_priority": [],
            "medium_priority": [],
            "low_priority": []
        }

        for mitigation in mitigations:
            priority = mitigation.get("priority", "MEDIUM")
            action_type = mitigation.get("type", "unknown")
            action = mitigation.get("action", "")

            action_entry = f"[{action_type.upper()}] {action}"

            if priority == "HIGH":
                actions["high_priority"].append(action_entry)
            elif priority == "MEDIUM":
                actions["medium_priority"].append(action_entry)
            else:
                actions["low_priority"].append(action_entry)

        return actions

    def _generate_evidence_summary(self, evidence: list[dict], kb_matches: list[dict], stats_analysis: dict) -> list[dict]:
        """Generate evidence summary table"""
        summary = []

        # Timeline evidence
        summary.append({
            "source": "syslog.txt",
            "key_evidence": "Hostapd event sequence analyzed",
            "reference": "Multiple line references"
        })

        # KB evidence
        for kb in kb_matches[:2]:
            summary.append({
                "source": "knowledge_base.txt",
                "key_evidence": kb.get("section", ""),
                "reference": kb.get("section", "")
            })

        # Stats evidence
        if stats_analysis.get("anomalies"):
            summary.append({
                "source": "rate_of_change_wifistats.txt",
                "key_evidence": f"{len(stats_analysis['anomalies'])} anomalies detected",
                "reference": "Various wifistat sections"
            })

        return summary

    def _format_simple_report(self, report: dict) -> str:
        """Format a simplified customer-facing report with only Title, What Happened, and Root Cause Analysis"""
        lines = []

        # Title
        lines.append("WiFi Connectivity Issue Triage Report")
        lines.append("")

        # 1. What Happened - Observed Symptom only
        lines.append("1. What Happened")
        lines.append("")
        lines.append("Observed Symptom")
        exec_sum = report["executive_summary"]
        lines.append(f"• {exec_sum['issue']}")
        lines.append("")

        # 2. Root Cause Analysis - Primary Suspected Causes only
        lines.append("2. Root Cause Analysis")
        lines.append("")
        lines.append("Primary Suspected Causes (Ranked by Likelihood)")

        rc = report["root_cause_hypothesis"]
        lines.append(f"{rc['primary']['confidence']} Likelihood: {rc['primary']['description']}")
        if rc['primary']['explanation']:
            lines.append(f"• {rc['primary']['explanation']}")
        if rc['primary']['evidence']:
            lines.append(f"• Evidence: {rc['primary']['evidence']}")

        if rc.get("secondary"):
            lines.append(f"{rc['secondary']['confidence']} Likelihood: {rc['secondary']['description']}")
            if rc['secondary']['explanation']:
                lines.append(f"• {rc['secondary']['explanation']}")
            if rc['secondary']['evidence']:
                lines.append(f"• Evidence: {rc['secondary']['evidence']}")

        lines.append("")

        return "\n".join(lines)

    def _format_report(self, report: dict) -> str:
        """Format report as text matching ground truth structure"""
        return self._format_simple_report(report)

    def _format_full_report(self, report: dict) -> str:
        """Format full report as text matching ground truth structure"""
        lines = []

        # Title
        lines.append("WiFi Connectivity Issue Triage Report")
        lines.append("")

        # 1. What Happened (instead of Executive Summary)
        lines.append("1. What Happened")
        lines.append("")
        lines.append("Observed Symptom")
        exec_sum = report["executive_summary"]
        lines.append(f"• {exec_sum['issue']}")

        # Add context from timeline if available
        timeline = report.get("timeline_analysis", [])
        if timeline:
            mac_address = self.get_metadata("mac_address") or "Unknown"
            lines.append(f"• Station MAC: {mac_address}")
            anomaly_type = self.get_metadata("anomaly_type") or "UNKNOWN"
            lines.append(f"• Issue detected as \"{anomaly_type}\" anomaly")

        lines.append("")
        lines.append("Supporting Log Evidence")
        # Add key timeline events as evidence
        for entry in timeline[:5]:
            if entry.get('timestamp'):
                details = entry.get('details', '')
                if isinstance(details, dict):
                    # Convert dict to readable string
                    details_str = ', '.join([f"{k}={v}" for k, v in details.items() if v])
                    if not details_str:
                        details_str = entry.get('event_type', 'Unknown event')
                else:
                    details_str = str(details) if details else entry.get('event_type', 'Unknown event')
                lines.append(f"{entry['timestamp']}: {details_str}")

        lines.append("")
        lines.append("Context")
        config = report.get("configuration_details", {})
        lines.append(f"• Band: {config.get('band', 'Detected from logs')}")
        lines.append(f"• Role: {config.get('interface', 'AP mode')}")
        lines.append(f"• Security: {config.get('authentication', 'Detected from logs')}")
        lines.append("")

        # 2. Root Cause Analysis (instead of Timeline Analysis)
        lines.append("2. Root Cause Analysis")
        lines.append("")
        lines.append("Primary Suspected Causes (Ranked by Likelihood)")

        rc = report["root_cause_hypothesis"]
        lines.append(f"{rc['primary']['confidence']} Likelihood: {rc['primary']['description']}")
        if rc['primary']['explanation']:
            lines.append(f"• {rc['primary']['explanation']}")
        if rc['primary']['evidence']:
            lines.append(f"• Evidence: {rc['primary']['evidence']}")

        if rc.get("secondary"):
            lines.append(f"{rc['secondary']['confidence']} Likelihood: {rc['secondary']['description']}")
            if rc['secondary']['explanation']:
                lines.append(f"• {rc['secondary']['explanation']}")
            if rc['secondary']['evidence']:
                lines.append(f"• Evidence: {rc['secondary']['evidence']}")

        # Add KB pattern match analysis
        kb_matches = self.get_cached_data("kb_matches") or []
        if kb_matches:
            lines.append("")
            lines.append("KB Pattern Match Analysis")
            for kb in kb_matches[:2]:
                lines.append(f"Pattern: \"{kb.get('section', 'Unknown')}\"")
                if kb.get('context'):
                    lines.append(f"• {kb['context'][:200]}...")
        lines.append("")

        # 3. Why This Root Cause Fits (instead of Critical Findings)
        lines.append("3. Why This Root Cause Fits")
        lines.append("")
        lines.append("Evidence Chain")

        # Add timeline as evidence chain
        lines.append("1. Hostapd Timeline (primary evidence):")
        for i, entry in enumerate(timeline[:5], 1):
            if entry.get('timestamp'):
                details = entry.get('details', '')
                if isinstance(details, dict):
                    # Convert dict to readable string
                    details_str = ', '.join([f"{k}={v}" for k, v in details.items() if v])
                    if not details_str:
                        details_str = entry.get('event_type', 'Unknown event')
                else:
                    details_str = str(details) if details else entry.get('event_type', 'Unknown event')
                lines.append(f"{entry['timestamp']}: {details_str}")

        # Add critical findings as evidence
        findings = report["critical_findings"]
        if findings:
            lines.append("")
            lines.append("2. Statistical Evidence:")
            for finding in findings[:2]:
                lines.append(f"• {finding['description']}")
                lines.append(f"  Evidence: {finding['evidence']}")

        lines.append("")
        lines.append(f"Confidence Level: {rc['primary']['confidence']} ({self._get_confidence_percentage(rc['primary']['confidence'])}%)")
        lines.append("")

        # 4. Mitigation / Next Steps (instead of Root Cause Hypothesis)
        lines.append("4. Mitigation / Next Steps")
        lines.append("")

        actions = report["recommended_actions"]
        if actions["high_priority"] or actions["medium_priority"]:
            lines.append("Immediate Actions")
            for i, action in enumerate(actions["high_priority"][:3], 1):
                lines.append(f"{i}. {action}")

            if actions["medium_priority"]:
                lines.append("")
                lines.append("Verification Steps")
                for i, action in enumerate(actions["medium_priority"][:3], 1):
                    lines.append(f"{i}. {action}")
        else:
            lines.append("No specific mitigations available - requires further investigation")
        lines.append("")

        # 5. Open Questions / Gaps (instead of Recommended Actions)
        lines.append("5. Open Questions / Gaps")
        lines.append("")
        lines.append("Missing Information")
        lines.append("• Client device details: Model, OS, driver version unknown")
        lines.append("• Signal strength: RSSI data missing at event time")
        lines.append("• Environmental factors: Channel utilization, interference unknown")
        lines.append("")
        lines.append("Suggested Additional Data Collection")
        lines.append("1. Extended Time Window:")
        lines.append("   Need logs from 5 minutes before event")
        lines.append("2. Client-Side Data:")
        lines.append("   wpa_supplicant logs if available")
        lines.append("3. Environmental Data:")
        lines.append("   Channel utilization: wifistats wifi1 19")
        lines.append("")

        # 6. References (instead of Evidence Summary)
        lines.append("6. References")
        lines.append("")
        lines.append("Knowledge Base References (knowledge.txt)")
        for kb in kb_matches[:3]:
            lines.append(f"• {kb.get('section', 'Unknown section')}")

        lines.append("")
        lines.append("Log Files Analyzed")
        for ev in report["evidence_summary"]:
            lines.append(f"• {ev['source']}: {ev['key_evidence']}")

        lines.append("")
        lines.append("Tool Commands Used")
        lines.append("• hostapd event parsing")
        lines.append("• wifistats counter analysis")
        lines.append("• Timeline correlation analysis")
        lines.append("")

        return "\n".join(lines)

    def _get_confidence_percentage(self, confidence: str) -> str:
        """Convert confidence level to percentage"""
        confidence_map = {
            "HIGH": "85",
            "MEDIUM": "65",
            "LOW": "35",
            "UNKNOWN": "50"
        }
        return confidence_map.get(confidence, "50")
