# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# All rights reserved.
# Confidential and Proprietary - Qualcomm Technologies, Inc.

"""
Timeline Builder Agent
Creates chronological event timeline with precise timestamps and deltas
"""

import re
from datetime import datetime
from typing import Any

from .base_agent import BaseAgent


class TimelineBuilderAgent(BaseAgent):
    """
    Builds a chronological timeline of events from hostapd logs and other sources.
    Calculates time deltas between events and identifies patterns.
    """

    def __init__(self, context, model: str = "qgenie"):
        super().__init__("TimelineBuilder", context, model)

    def analyze(self) -> bool:
        """
        Build timeline from hostapd events
        
        Returns:
            bool: True if timeline built successfully
        """
        # Check if already cached
        if self.has_cached_data("timeline"):
            self._log_info("Using cached timeline")
            return True

        # Get hostapd events from shared context
        hostapd_events = self.get_cached_data("hostapd_events")

        if not hostapd_events:
            self._log_warning("No hostapd events available for timeline building")
            return True  # Not a failure, just no data

        # Build timeline
        timeline = self._build_timeline(hostapd_events)

        if not timeline:
            self._log_warning("Failed to build timeline")
            return False

        # Cache the timeline
        self.cache_data("timeline", timeline)

        # Add timeline as finding
        self.add_finding(
            finding_type="timeline",
            content=timeline,
            confidence="HIGH",
            metadata={"event_count": len(timeline)}
        )

        # Analyze timing patterns
        self._analyze_timing_patterns(timeline)

        self._log_info(f"Built timeline with {len(timeline)} events")
        return True

    def _build_timeline(self, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Build chronological timeline with time deltas
        
        Args:
            events: List of parsed hostapd events
        
        Returns:
            List of timeline entries with deltas
        """
        timeline = []

        # Sort events by timestamp
        sorted_events = self._sort_events_by_timestamp(events)

        prev_timestamp = None

        for event in sorted_events:
            timestamp_str = event.get('timestamp')

            if not timestamp_str:
                continue

            # Parse timestamp to get numeric value
            timestamp_value = self._parse_timestamp_to_seconds(timestamp_str)

            # Calculate delta from previous event
            delta_ms = None
            if prev_timestamp is not None and timestamp_value is not None:
                delta_ms = (timestamp_value - prev_timestamp) * 1000  # Convert to ms

            timeline_entry = {
                "timestamp": timestamp_str,
                "timestamp_value": timestamp_value,
                "delta_ms": delta_ms,
                "event_type": event.get('type'),
                "mac_address": event.get('mac_address'),
                "details": event.get('details', {}),
                "raw_line": event.get('raw_line'),
                "line_number": event.get('line_number'),
                "source": "hostapd"
            }

            timeline.append(timeline_entry)

            if timestamp_value is not None:
                prev_timestamp = timestamp_value

        return timeline

    def _sort_events_by_timestamp(self, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Sort events chronologically by timestamp"""
        def get_timestamp_value(event):
            timestamp_str = event.get('timestamp')
            if not timestamp_str:
                return 0
            return self._parse_timestamp_to_seconds(timestamp_str) or 0

        return sorted(events, key=get_timestamp_value)

    def _parse_timestamp_to_seconds(self, timestamp_str: str) -> float | None:
        """
        Parse timestamp string to seconds (epoch time)
        
        Args:
            timestamp_str: Timestamp string (e.g., "1763035290.422481" or "Thu Nov 13 12:01:30 2025")
        
        Returns:
            Timestamp in seconds or None
        """
        # Try parsing as epoch time with microseconds
        if re.match(r'^\d{10}\.\d{6}$', timestamp_str):
            try:
                return float(timestamp_str)
            except ValueError:
                pass

        # Try parsing as date string
        date_formats = [
            "%a %b %d %H:%M:%S %Y",  # Thu Nov 13 12:01:30 2025
            "%Y-%m-%d %H:%M:%S",
            "%m/%d/%Y %H:%M:%S"
        ]

        for fmt in date_formats:
            try:
                dt = datetime.strptime(timestamp_str, fmt)
                return dt.timestamp()
            except ValueError:
                continue

        return None

    def _analyze_timing_patterns(self, timeline: list[dict[str, Any]]) -> None:
        """
        Analyze timing patterns in the timeline using LLM
        """
        if len(timeline) < 2:
            return

        # Create timing summary
        timing_summary = self._create_timing_summary(timeline)

        prompt = f"""Analyze the following event timeline and identify timing patterns:

{timing_summary}

Focus on:
1. Rapid reconnection cycles (events occurring within 1-2 seconds)
2. Consistent timing patterns (e.g., disconnects always ~1 second after connection)
3. Unusual delays between expected event sequences
4. Timing that suggests firmware/driver issues vs. environmental issues

Provide a concise analysis of timing anomalies."""

        analysis = self.call_llm(prompt, call_type="hostapd")

        if analysis:
            self.add_finding(
                finding_type="timing_analysis",
                content={"analysis": analysis},
                confidence="MEDIUM"
            )

    def _create_timing_summary(self, timeline: list[dict[str, Any]]) -> str:
        """Create a concise timing summary for LLM"""
        summary_lines = ["Timestamp | Delta (ms) | Event | MAC | Details"]
        summary_lines.append("-" * 80)

        for entry in timeline[:30]:  # Limit to first 30 events
            timestamp = entry.get('timestamp', 'unknown')
            delta = entry.get('delta_ms')
            delta_str = f"+{delta:.1f}ms" if delta is not None else "-"
            event_type = entry.get('event_type', 'unknown').upper()
            mac = entry.get('mac_address', 'unknown')
            details = entry.get('details', {})

            detail_str = ""
            if details:
                detail_str = ", ".join([f"{k}={v}" for k, v in details.items()])

            line = f"{timestamp} | {delta_str:>12} | {event_type:>12} | {mac} | {detail_str}"
            summary_lines.append(line)

        if len(timeline) > 30:
            summary_lines.append(f"... and {len(timeline) - 30} more events")

        return "\n".join(summary_lines)
