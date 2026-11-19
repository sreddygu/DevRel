# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# All rights reserved.
# Confidential and Proprietary - Qualcomm Technologies, Inc.

"""
Shared Context (Blackboard Pattern) for Agent Communication
Allows agents to read and write findings, share data, and coordinate analysis
"""

import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class Finding:
    """Represents a finding from an agent"""
    agent_name: str
    finding_type: str  # e.g., "timeline_event", "kb_match", "root_cause", "evidence"
    content: Any
    confidence: str | None = None  # HIGH, MEDIUM, LOW
    timestamp: datetime = field(default_factory=datetime.now)
    references: list[str] = field(default_factory=list)  # File references, line numbers
    metadata: dict[str, Any] = field(default_factory=dict)


class SharedContext:
    """
    Blackboard pattern implementation for agent communication.
    Thread-safe storage for findings, cached data, and agent coordination.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._findings: list[Finding] = []
        self._cache: dict[str, Any] = {}
        self._agent_status: dict[str, str] = {}  # agent_name -> status
        self._input_data: dict[str, Any] = {}
        self._metadata: dict[str, Any] = {}

    def add_finding(self, finding: Finding) -> None:
        """Add a finding to the shared context"""
        with self._lock:
            self._findings.append(finding)

    def get_findings(self,
                     agent_name: str | None = None,
                     finding_type: str | None = None) -> list[Finding]:
        """
        Retrieve findings, optionally filtered by agent name or finding type
        """
        with self._lock:
            findings = self._findings

            if agent_name:
                findings = [f for f in findings if f.agent_name == agent_name]

            if finding_type:
                findings = [f for f in findings if f.finding_type == finding_type]

            return findings.copy()

    def get_all_findings(self) -> list[Finding]:
        """Get all findings"""
        with self._lock:
            return self._findings.copy()

    def cache_data(self, key: str, data: Any) -> None:
        """Cache data to avoid redundant processing"""
        with self._lock:
            self._cache[key] = data

    def get_cached_data(self, key: str) -> Any | None:
        """Retrieve cached data"""
        with self._lock:
            return self._cache.get(key)

    def has_cached_data(self, key: str) -> bool:
        """Check if data is cached"""
        with self._lock:
            return key in self._cache

    def set_agent_status(self, agent_name: str, status: str) -> None:
        """Update agent status (e.g., 'running', 'completed', 'failed')"""
        with self._lock:
            self._agent_status[agent_name] = status

    def get_agent_status(self, agent_name: str) -> str | None:
        """Get agent status"""
        with self._lock:
            return self._agent_status.get(agent_name)

    def set_input_data(self, key: str, data: Any) -> None:
        """Store input data (logs, stats, etc.)"""
        with self._lock:
            self._input_data[key] = data

    def get_input_data(self, key: str) -> Any | None:
        """Retrieve input data"""
        with self._lock:
            return self._input_data.get(key)

    def get_all_input_data(self) -> dict[str, Any]:
        """Get all input data"""
        with self._lock:
            return self._input_data.copy()

    def set_metadata(self, key: str, value: Any) -> None:
        """Store metadata (anomaly type, MAC address, etc.)"""
        with self._lock:
            self._metadata[key] = value

    def get_metadata(self, key: str) -> Any | None:
        """Retrieve metadata"""
        with self._lock:
            return self._metadata.get(key)

    def get_all_metadata(self) -> dict[str, Any]:
        """Get all metadata"""
        with self._lock:
            return self._metadata.copy()

    def clear(self) -> None:
        """Clear all data (useful for testing or new analysis)"""
        with self._lock:
            self._findings.clear()
            self._cache.clear()
            self._agent_status.clear()
            self._input_data.clear()
            self._metadata.clear()

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of the current context state"""
        with self._lock:
            return {
                "total_findings": len(self._findings),
                "findings_by_type": self._count_by_type(),
                "findings_by_agent": self._count_by_agent(),
                "agent_statuses": self._agent_status.copy(),
                "cached_keys": list(self._cache.keys()),
                "input_data_keys": list(self._input_data.keys()),
                "metadata": self._metadata.copy()
            }

    def _count_by_type(self) -> dict[str, int]:
        """Count findings by type"""
        counts = {}
        for finding in self._findings:
            counts[finding.finding_type] = counts.get(finding.finding_type, 0) + 1
        return counts

    def _count_by_agent(self) -> dict[str, int]:
        """Count findings by agent"""
        counts = {}
        for finding in self._findings:
            counts[finding.agent_name] = counts.get(finding.agent_name, 0) + 1
        return counts
