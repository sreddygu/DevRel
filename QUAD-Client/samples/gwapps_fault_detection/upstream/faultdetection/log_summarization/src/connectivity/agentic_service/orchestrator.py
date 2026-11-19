# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# All rights reserved.
# Confidential and Proprietary - Qualcomm Technologies, Inc.

"""
Orchestrator - Master Agent
Dynamically determines tasks and spawns specialized agents
"""

import re
from typing import Any

from .agents import (
    ConfidenceScorerAgent,
    DisconnectAnalyzerAgent,
    EvidenceCollectorAgent,
    FDLogsParserAgent,
    HostapdParserAgent,
    KBMatcherAgent,
    KnownIssueCheckerAgent,
    MitigationAgent,
    ReportGeneratorAgent,
    RootCauseAgent,
    StatsAnalyzerAgent,
    TimelineBuilderAgent,
)
from .shared_context import SharedContext


class Orchestrator:
    """
    Master agent that:
    1. Analyzes inputs to determine what analysis tasks are needed
    2. Spawns specialized agents dynamically based on anomaly type and available data
    3. Coordinates agent execution following the 9-step workflow
    4. Supports multiple rounds of refinement
    """

    def __init__(self, model: str = "qgenie"):
        self.model = model
        self.context = SharedContext()
        self.max_refinement_rounds = 2
        self.current_round = 0

    def analyze(self,
                fd_logs: str,
                hostapd_log: str | None = None,
                wifistats: str | None = None,
                knowledge_base: str | None = None) -> str:
        """
        Main entry point for analysis
        
        Args:
            fd_logs: Fault detection logs (notification file)
            hostapd_log: Optional hostapd log
            wifistats: Optional wifistats (rate of change)
            knowledge_base: Optional knowledge base content
        
        Returns:
            Final triage report
        """
        print("[ORCHESTRATOR] Starting analysis...")

        # Step 1: Ingest logs and extract metadata
        self._ingest_logs(fd_logs, hostapd_log, wifistats, knowledge_base)

        # Step 2: Determine anomaly type and available data
        anomaly_type, mac_address = self._detect_anomaly_type(fd_logs)
        self.context.set_metadata("anomaly_type", anomaly_type)
        self.context.set_metadata("mac_address", mac_address)

        print(f"[ORCHESTRATOR] Detected anomaly: {anomaly_type}, MAC: {mac_address}")

        # Step 3: Determine which agents to spawn
        agent_plan = self._determine_agent_plan(anomaly_type, hostapd_log, wifistats)

        print(f"[ORCHESTRATOR] Agent plan: {agent_plan}")

        # Step 4: Execute agents following workflow
        success = self._execute_workflow(agent_plan)

        if not success:
            print("[ORCHESTRATOR] Workflow execution failed")
            return "Analysis failed - see logs for details"

        # Step 5: Check if refinement is needed
        if self.current_round < self.max_refinement_rounds:
            if self._needs_refinement():
                print(f"[ORCHESTRATOR] Starting refinement round {self.current_round + 1}")
                self.current_round += 1
                return self._refine_analysis(agent_plan)

        # Step 6: Get final report
        final_report = self.context.get_cached_data("final_report")

        if not final_report:
            print("[ORCHESTRATOR] No final report generated")
            return "Analysis incomplete - no report generated"

        print("[ORCHESTRATOR] Analysis complete")
        return final_report

    def _ingest_logs(self,
                     fd_logs: str,
                     hostapd_log: str | None,
                     wifistats: str | None,
                     knowledge_base: str | None) -> None:
        """Store input data in shared context"""
        self.context.set_input_data("fd_logs", fd_logs)

        if hostapd_log:
            self.context.set_input_data("hostapd_log", hostapd_log)

        if wifistats:
            self.context.set_input_data("wifistats", wifistats)

        if knowledge_base:
            self.context.set_input_data("knowledge_base", knowledge_base)

    # Map exact "Anomaly Type:" field values to internal names.
    # The fd_logs header always contains exactly one of these four strings.
    _ANOMALY_TYPE_MAP = {
        "FAIL TO CONNECT": "FAIL_TO_CONNECT",
        "DISCONNECT":      "DISCONNECT",
        "BEACON STUCK":    "BEACON_STUCK",
        "DATA STALL":      "DATA_STALL",
    }

    def _detect_anomaly_type(self, fd_logs: str) -> tuple:
        """
        Detect anomaly type and MAC address from fd_logs.

        Anomaly type is read exclusively from the "Anomaly Type:" header line
        so that words like "disconnected" in event-detail lines cannot trigger
        a false DISCONNECT match.

        Returns:
            (anomaly_type, mac_address)
        """
        anomaly_type = "UNKNOWN"
        mac_address = "Unknown"

        # Match the exact "Anomaly Type:" line against the four known values.
        # Alternation is ordered longest-first to avoid partial matches.
        anomaly_match = re.search(
            r'Anomaly Type:\s*(FAIL TO CONNECT|DISCONNECT|BEACON STUCK|DATA STALL)',
            fd_logs,
            re.IGNORECASE
        )
        if anomaly_match:
            anomaly_type = self._ANOMALY_TYPE_MAP[anomaly_match.group(1).upper()]

        # Extract MAC address
        mac_pattern = r'([0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2})'
        mac_match = re.search(mac_pattern, fd_logs)
        if mac_match:
            mac_address = mac_match.group(1)

        return anomaly_type, mac_address

    def _determine_agent_plan(self,
                             anomaly_type: str,
                             hostapd_log: str | None,
                             wifistats: str | None) -> list[str]:
        """
        Dynamically determine which agents to spawn based on:
        - Anomaly type
        - Available data (hostapd present vs absent)
        - Workflow priorities (hostapd-first approach)
        
        Returns:
            List of agent names to execute in order
        """
        agent_plan = []

        # Hostapd-first approach for DISCONNECT and FAIL_TO_CONNECT
        if anomaly_type in ["DISCONNECT", "FAIL_TO_CONNECT"]:
            if hostapd_log:
                # Full analysis with hostapd
                agent_plan = [
                    "HostapdParser",      # Parse hostapd events
                    "TimelineBuilder",    # Build timeline
                    "DisconnectAnalyzer", # Analyze disconnect initiator (DISCONNECT only)
                    "KnownIssueChecker",  # Check for known issues
                    "KBMatcher",          # Match against KB (hostapd-first)
                    "StatsAnalyzer",      # Analyze stats
                    "RootCause",          # Formulate hypotheses
                    "EvidenceCollector",  # Collect evidence
                    "ConfidenceScorer",   # Score confidence
                    "Mitigation",         # Generate mitigations
                    "ReportGenerator"     # Generate report
                ]
            else:
                # Stats-first approach (no hostapd)
                agent_plan = [
                    "KnownIssueChecker",  # Check for known issues (even without hostapd)
                    "StatsAnalyzer",      # Analyze stats first
                    "KBMatcher",          # Match against KB (stats-based)
                    "RootCause",          # Formulate hypotheses
                    "EvidenceCollector",  # Collect evidence
                    "ConfidenceScorer",   # Score confidence (will be MEDIUM/LOW)
                    "Mitigation",         # Generate mitigations
                    "ReportGenerator"     # Generate report
                ]

        # Stats-focused approach for DATA_STALL and BEACON_STUCK
        elif anomaly_type in ["DATA_STALL", "BEACON_STUCK"]:
            agent_plan = [
                "FDLogsParser",       # Extract anomaly-specific metrics from FD logs
                "StatsAnalyzer",      # Primary focus on stats
                "KBMatcher",          # Match against KB
                "RootCause",          # Formulate hypotheses
                "EvidenceCollector",  # Collect evidence
                "ConfidenceScorer",   # Score confidence
                "Mitigation",         # Generate mitigations
                "ReportGenerator"     # Generate report
            ]

            # Add hostapd analysis if available
            if hostapd_log:
                agent_plan.insert(0, "HostapdParser")
                agent_plan.insert(1, "TimelineBuilder")

        # Default plan for unknown anomaly types
        else:
            if hostapd_log:
                agent_plan = [
                    "HostapdParser",
                    "TimelineBuilder",
                    "KBMatcher",
                    "StatsAnalyzer",
                    "RootCause",
                    "EvidenceCollector",
                    "ConfidenceScorer",
                    "Mitigation",
                    "ReportGenerator"
                ]
            else:
                agent_plan = [
                    "StatsAnalyzer",
                    "KBMatcher",
                    "RootCause",
                    "EvidenceCollector",
                    "ConfidenceScorer",
                    "Mitigation",
                    "ReportGenerator"
                ]

        return agent_plan

    def _execute_workflow(self, agent_plan: list[str]) -> bool:
        """
        Execute agents in order following the 9-step workflow
        
        Returns:
            True if all agents succeeded
        """
        agent_classes = {
            "HostapdParser": HostapdParserAgent,
            "TimelineBuilder": TimelineBuilderAgent,
            "DisconnectAnalyzer": DisconnectAnalyzerAgent,
            "FDLogsParser": FDLogsParserAgent,
            "KnownIssueChecker": KnownIssueCheckerAgent,
            "KBMatcher": KBMatcherAgent,
            "StatsAnalyzer": StatsAnalyzerAgent,
            "RootCause": RootCauseAgent,
            "EvidenceCollector": EvidenceCollectorAgent,
            "ConfidenceScorer": ConfidenceScorerAgent,
            "Mitigation": MitigationAgent,
            "ReportGenerator": ReportGeneratorAgent
        }

        for agent_name in agent_plan:
            print(f"[ORCHESTRATOR] Spawning agent: {agent_name}")

            agent_class = agent_classes.get(agent_name)
            if not agent_class:
                print(f"[ORCHESTRATOR] Unknown agent: {agent_name}")
                continue

            # Spawn and run agent
            agent = agent_class(self.context, self.model)
            success = agent.run()

            if not success:
                print(f"[ORCHESTRATOR] Agent {agent_name} failed")
                # Continue with other agents even if one fails
                # (following the "try a few more times, eventually move on" approach)

        return True

    def _needs_refinement(self) -> bool:
        """
        Determine if refinement is needed based on:
        - Low confidence scores
        - Contradictions in findings
        - Missing critical data
        
        Returns:
            True if refinement is needed
        """
        # Check confidence scores
        confidence_scores = self.context.get_cached_data("confidence_scores") or []

        if confidence_scores:
            primary_confidence = confidence_scores[0].get("confidence", "UNKNOWN")
            if primary_confidence == "LOW":
                print("[ORCHESTRATOR] Low confidence detected - refinement needed")
                return True

        # Check for contradictions (simplified check)
        findings = self.context.get_all_findings()
        if len(findings) < 5:  # Too few findings
            print("[ORCHESTRATOR] Insufficient findings - refinement needed")
            return True

        return False

    def _refine_analysis(self, agent_plan: list[str]) -> str:
        """
        Refine analysis by re-running specific agents
        
        Returns:
            Final report after refinement
        """
        # Re-run KB matcher and root cause agents for refinement
        refinement_agents = ["KBMatcher", "RootCause", "ConfidenceScorer", "ReportGenerator"]

        for agent_name in refinement_agents:
            if agent_name in agent_plan:
                print(f"[ORCHESTRATOR] Refining with agent: {agent_name}")

                agent_classes = {
                    "KBMatcher": KBMatcherAgent,
                    "RootCause": RootCauseAgent,
                    "ConfidenceScorer": ConfidenceScorerAgent,
                    "ReportGenerator": ReportGeneratorAgent
                }

                agent_class = agent_classes.get(agent_name)
                if agent_class:
                    agent = agent_class(self.context, self.model)
                    agent.run()

        # Get refined report
        final_report = self.context.get_cached_data("final_report")
        return final_report or "Refinement failed"

    def get_context_summary(self) -> dict[str, Any]:
        """Get summary of shared context for debugging"""
        return self.context.get_summary()
