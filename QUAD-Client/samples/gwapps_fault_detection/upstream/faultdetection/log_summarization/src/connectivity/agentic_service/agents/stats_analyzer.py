# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# All rights reserved.
# Confidential and Proprietary - Qualcomm Technologies, Inc.

"""
Stats Analyzer Agent
Parses wifistats and classifies RAW vs rate-of-change stats
Uses LLM-based chunking for comprehensive analysis
"""

import os
import sys
import tempfile
from typing import Any

# Add parent directory to path to import model_calls and extract_firmware_stats
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from model_calls import RAW_STATS

# Import firmware stats extraction functions
try:
    from extract_firmware_stats import clean_and_save_stats, process_runs
    FIRMWARE_STATS_AVAILABLE = True
except ImportError:
    FIRMWARE_STATS_AVAILABLE = False
    print("[StatsAnalyzer] Warning: extract_firmware_stats not available")

# Import CCA OBSS percentage calculator
try:
    from cca_obss_percentage import calculate_cca_obss_percentage, get_cca_obss_severity
    CCA_OBSS_AVAILABLE = True
except ImportError:
    CCA_OBSS_AVAILABLE = False
    print("[StatsAnalyzer] Warning: cca_obss_percentage not available")

# Import RTS success rate calculator
try:
    from rts_success_rate import calculate_rts_success_rate, get_rts_success_severity
    RTS_AVAILABLE = True
except ImportError:
    RTS_AVAILABLE = False
    print("[StatsAnalyzer] Warning: rts_success_rate not available")

from .base_agent import BaseAgent


class StatsAnalyzerAgent(BaseAgent):
    """
    Analyzes wifistats to identify anomalies and verify hypotheses.
    Classifies stats as RAW or rate-of-change based on model_calls.RAW_STATS.
    """

    def __init__(self, context, model: str = "qgenie"):
        super().__init__("StatsAnalyzer", context, model)
        self.raw_stats = RAW_STATS  # Use the preserved RAW_STATS set

    def analyze(self) -> bool:
        """
        Analyze wifistats using hybrid approach:
        1. Check for FD logs metrics (DATA_STALL, BEACON_STUCK)
        2. Extract relevant stats using process_runs() from extract_firmware_stats.py
        3. Clean stats using clean_and_save_stats() to remove HTT_TX headers
        4. Split stats by WIFISTAT sections
        5. Use LLM to analyze each section
        6. Aggregate LLM observations
        
        Returns:
            bool: True if analysis succeeded
        """
        # Check if already cached
        if self.has_cached_data("stats_analysis"):
            self._log_info("Using cached stats analysis")
            return True

        # Get anomaly type for targeted extraction
        anomaly_type = self.get_metadata("anomaly_type") or "UNKNOWN"

        # Check for FD logs metrics (DATA_STALL, BEACON_STUCK)
        fd_logs_metrics = self.get_cached_data("fd_logs_metrics")
        fd_anomalies = []

        if fd_logs_metrics:
            self._log_info(f"Found FD logs metrics for {anomaly_type}")

            # Process DATA_STALL metrics
            if anomaly_type == "DATA_STALL":
                data_retry_pct = fd_logs_metrics.get("data_retry_pct")
                rssi_in_dbm_avg = fd_logs_metrics.get("rssi_in_dbm_avg")

                if data_retry_pct is not None:
                    severity = "HIGH" if data_retry_pct > 0.5 else "MEDIUM"
                    fd_anomalies.append({
                        "type": "high_data_retry_percentage",
                        "section": "FD_LOGS",
                        "stat": "data_retry_pct",
                        "value": data_retry_pct,
                        "severity": severity,
                        "description": f"Data retry percentage: {data_retry_pct:.2%}"
                    })

                if rssi_in_dbm_avg is not None:
                    severity = "HIGH" if rssi_in_dbm_avg < -70 else "MEDIUM"
                    fd_anomalies.append({
                        "type": "poor_rssi",
                        "section": "FD_LOGS",
                        "stat": "rssi_in_dbm",
                        "value": rssi_in_dbm_avg,
                        "severity": severity,
                        "description": f"Average RSSI: {rssi_in_dbm_avg:.1f} dBm"
                    })

            # Process BEACON_STUCK metrics
            elif anomaly_type == "BEACON_STUCK":
                beacon_fail_rate = fd_logs_metrics.get("beacon_fail_rate")

                if beacon_fail_rate is not None:
                    severity = "HIGH" if beacon_fail_rate > 0.5 else "MEDIUM"
                    fd_anomalies.append({
                        "type": "high_beacon_fail_rate",
                        "section": "FD_LOGS",
                        "stat": "beacon_fail_rate",
                        "value": beacon_fail_rate,
                        "severity": severity,
                        "description": f"Beacon fail rate: {beacon_fail_rate:.2%}"
                    })

        # Get wifistats from shared context
        wifistats = self.get_input_data("wifistats")

        if not wifistats:
            self._log_warning("No wifistats provided")
            # If we have FD logs metrics, still proceed with those
            if fd_anomalies:
                analysis = {
                    "parsed_stats": {},
                    "classified_stats": {"raw": {}, "rate_of_change": {}},
                    "anomalies": fd_anomalies,
                    "llm_observations": [],
                    "relevant_stats_extracted": False,
                    "fd_logs_metrics": fd_logs_metrics
                }
                self.cache_data("stats_analysis", analysis)

                for anomaly in fd_anomalies:
                    self.add_finding(
                        finding_type="fd_logs_anomaly",
                        content=anomaly,
                        confidence="HIGH"
                    )

                return True
            return True  # Not a failure, just no data

        # Map anomaly type to reason for extract_firmware_stats
        reason_mapping = {
            "DISCONNECT": "client_disconnect",
            "FAIL_TO_CONNECT": "fail_to_connect",
            "DATA_STALL": "data_stall",
            "BEACON_STUCK": "beacon_stuck"
        }
        reason = reason_mapping.get(anomaly_type, "client_disconnect")

        # Method 1: Use process_runs() to extract relevant stats
        relevant_stats = ""
        if FIRMWARE_STATS_AVAILABLE:
            try:
                # Create temp directory with wifistats file
                with tempfile.TemporaryDirectory() as temp_dir:
                    stats_path = os.path.join(temp_dir, "rate_of_change_wifistats.txt")
                    with open(stats_path, 'w') as f:
                        f.write(wifistats)

                    # Extract relevant stats for this anomaly type
                    relevant_stats = process_runs(temp_dir, reason)

                    if relevant_stats:
                        # Clean stats to remove HTT_TX headers
                        relevant_stats = clean_and_save_stats(relevant_stats, temp_dir)
                        self._log_info(f"Extracted relevant stats using process_runs() for reason: {reason}")
            except Exception as e:
                self._log_warning(f"Failed to use process_runs(): {e}")
                relevant_stats = ""

        # If process_runs() didn't work, use original wifistats
        stats_to_analyze = relevant_stats if relevant_stats else wifistats

        # ------------------------------------------------------------------ #
        # BEACON_STUCK: calculate cca_obss busy-time percentage from the raw #
        # wifistats content (rate_of_change_wifistats.txt).                  #
        # extract_wifistats_19() strips collection_interval / usec_cnt so    #
        # we must use the original wifistats string, not stats_to_analyze.   #
        # Severity: >= 80 % → HIGH, >= 40 % → MEDIUM, < 40 % → LOW          #
        # ------------------------------------------------------------------ #
        if anomaly_type == "BEACON_STUCK" and CCA_OBSS_AVAILABLE and wifistats:
            cca_obss_by_chan = calculate_cca_obss_percentage(wifistats)
            for chan_num, cca_obss_pct in cca_obss_by_chan.items():
                severity = get_cca_obss_severity(cca_obss_pct)
                fd_anomalies.append({
                    "type": "high_cca_obss",
                    "section": "WIFISTAT_19",
                    "stat": "cca_obss_pct",
                    "chan_num": chan_num,
                    "value": round(cca_obss_pct, 2),
                    "severity": severity,
                    "description": (
                        f"CCA OBSS busy time on channel {chan_num}: "
                        f"{cca_obss_pct:.1f}% "
                        f"— indicates OBSS interference on the channel"
                    ),
                })
                self._log_info(
                    f"Parsed BEACON STUCK cca_obss_pct={cca_obss_pct:.1f}% "
                    f"chan={chan_num} (severity={severity})"
                )

        # ------------------------------------------------------------------ #
        # DATA_STALL: check CCA OBSS busy-time (channel congestion can also  #
        # cause data stalls by preventing channel access).                   #
        # Severity: >= 80 % → HIGH, >= 40 % → MEDIUM, < 40 % → LOW          #
        # ------------------------------------------------------------------ #
        if anomaly_type == "DATA_STALL" and CCA_OBSS_AVAILABLE and wifistats:
            cca_obss_by_chan = calculate_cca_obss_percentage(wifistats)
            for chan_num, cca_obss_pct in cca_obss_by_chan.items():
                severity = get_cca_obss_severity(cca_obss_pct)
                fd_anomalies.append({
                    "type": "high_cca_obss",
                    "section": "WIFISTAT_19",
                    "stat": "cca_obss_pct",
                    "chan_num": chan_num,
                    "value": round(cca_obss_pct, 2),
                    "severity": severity,
                    "description": (
                        f"CCA OBSS busy time on channel {chan_num}: "
                        f"{cca_obss_pct:.1f}% "
                        f"— indicates OBSS interference causing channel access failures"
                    ),
                })
                self._log_info(
                    f"Parsed DATA_STALL cca_obss_pct={cca_obss_pct:.1f}% "
                    f"chan={chan_num} (severity={severity})"
                )

        # ------------------------------------------------------------------ #
        # DATA_STALL: check RTS success rate from WIFISTAT 9                 #
        # (HTT_TX_PDEV_RATE_STATS_TLV).                                      #
        # Low RTS success rate indicates severe channel access impairment.   #
        # Severity: < 20 % → HIGH, < 50 % → MEDIUM, >= 50 % → LOW           #
        # ------------------------------------------------------------------ #
        if anomaly_type == "DATA_STALL" and RTS_AVAILABLE and wifistats:
            rts_by_mac = calculate_rts_success_rate(wifistats)
            for mac_id, success_rate_pct in rts_by_mac.items():
                severity = get_rts_success_severity(success_rate_pct)
                # Compute failure rate for the description
                failure_rate_pct = 100.0 - success_rate_pct
                fd_anomalies.append({
                    "type": "low_rts_success_rate",
                    "section": "WIFISTAT_9",
                    "stat": "rts_success_rate_pct",
                    "mac_id": mac_id,
                    "value": round(success_rate_pct, 2),
                    "severity": severity,
                    "description": (
                        f"RTS success rate on mac_id {mac_id}: "
                        f"{success_rate_pct:.1f}% "
                        f"({failure_rate_pct:.1f}% failure rate) "
                        f"— indicates channel access severely impaired"
                    ),
                })
                self._log_info(
                    f"Parsed DATA_STALL rts_success_rate={success_rate_pct:.1f}% "
                    f"mac_id={mac_id} (severity={severity})"
                )

        # Parse wifistats (basic parsing for backward compatibility)
        parsed_stats = self._parse_wifistats(stats_to_analyze)

        if not parsed_stats:
            self._log_warning("Failed to parse wifistats")
            return False

        # Classify stats as RAW or rate-of-change
        classified_stats = self._classify_stats(parsed_stats)

        # Identify anomalies using threshold-based detection
        anomalies = self._identify_anomalies(classified_stats)

        # Merge FD anomalies with wifistats anomalies
        if fd_anomalies:
            anomalies.extend(fd_anomalies)
            self._log_info(f"Added {len(fd_anomalies)} FD logs anomalies to analysis")

        # Method 2: LLM-based analysis with chunking by WIFISTAT sections
        llm_observations = self._analyze_stats_with_llm_chunking(stats_to_analyze, anomaly_type)

        # Cache the analysis
        analysis = {
            "parsed_stats": parsed_stats,
            "classified_stats": classified_stats,
            "anomalies": anomalies,
            "llm_observations": llm_observations,
            "relevant_stats_extracted": bool(relevant_stats),
            "fd_logs_metrics": fd_logs_metrics  # Include FD logs metrics in analysis
        }
        self.cache_data("stats_analysis", analysis)

        # Add findings
        self.add_finding(
            finding_type="stats_summary",
            content={
                "total_stats": len(parsed_stats),
                "anomalies": len(anomalies),
                "llm_observations": len(llm_observations),
                "fd_logs_anomalies": len(fd_anomalies) if fd_anomalies else 0
            },
            confidence="HIGH"
        )

        # Add FD logs anomalies as HIGH confidence findings
        for anomaly in fd_anomalies:
            self.add_finding(
                finding_type="fd_logs_anomaly",
                content=anomaly,
                confidence="HIGH"
            )

        # Add wifistats anomalies as MEDIUM confidence findings
        for anomaly in anomalies:
            if anomaly not in fd_anomalies:  # Avoid duplicates
                self.add_finding(
                    finding_type="stats_anomaly",
                    content=anomaly,
                    confidence="MEDIUM",
                    references=["rate_of_change_wifistats.txt"]
                )

        # Add LLM observations as findings
        for obs in llm_observations:
            self.add_finding(
                finding_type="stats_llm_observation",
                content=obs,
                confidence="MEDIUM",
                references=["rate_of_change_wifistats.txt"]
            )

        self._log_info(
            f"Analyzed {len(parsed_stats)} stats, found {len(anomalies)} anomalies, "
            f"{len(llm_observations)} LLM observations"
        )
        return True

    def _parse_wifistats(self, wifistats_content: str) -> dict[str, Any]:
        """
        Parse wifistats content
        
        Args:
            wifistats_content: Raw wifistats content
        
        Returns:
            Dictionary of parsed stats
        """
        stats = {}
        current_section = None

        lines = wifistats_content.split('\n')

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Detect section headers (e.g., "WIFISTAT 1", "HTT_TX_PDEV_STATS")
            if line.startswith('WIFISTAT') or line.startswith('HTT_'):
                current_section = line
                stats[current_section] = {}
                continue

            # Parse stat lines (e.g., "hw_queued = 1234")
            if '=' in line and current_section:
                parts = line.split('=', 1)
                if len(parts) == 2:
                    stat_name = parts[0].strip()
                    stat_value = parts[1].strip()

                    # Try to parse as number
                    try:
                        if '.' in stat_value:
                            stat_value = float(stat_value)
                        else:
                            stat_value = int(stat_value)
                    except ValueError:
                        pass  # Keep as string

                    stats[current_section][stat_name] = stat_value

        return stats

    def _classify_stats(self, parsed_stats: dict[str, Any]) -> dict[str, dict[str, Any]]:
        """
        Classify stats as RAW or rate-of-change
        
        Args:
            parsed_stats: Parsed stats dictionary
        
        Returns:
            Dictionary with classification
        """
        classified = {
            "raw": {},
            "rate_of_change": {}
        }

        for section, stats in parsed_stats.items():
            for stat_name, stat_value in stats.items():
                # Check if stat is in RAW_STATS set
                if stat_name in self.raw_stats:
                    if section not in classified["raw"]:
                        classified["raw"][section] = {}
                    classified["raw"][section][stat_name] = stat_value
                else:
                    if section not in classified["rate_of_change"]:
                        classified["rate_of_change"][section] = {}
                    classified["rate_of_change"][section][stat_name] = stat_value

        return classified

    def _identify_anomalies(self, classified_stats: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Identify anomalies in stats
        
        Args:
            classified_stats: Classified stats
        
        Returns:
            List of anomalies
        """
        anomalies = []

        # Check rate-of-change stats for high values
        for section, stats in classified_stats.get("rate_of_change", {}).items():
            for stat_name, stat_value in stats.items():
                if isinstance(stat_value, (int, float)):
                    # High TX failure rate
                    if 'fail' in stat_name.lower() and stat_value > 100:
                        anomalies.append({
                            "type": "high_failure_rate",
                            "section": section,
                            "stat": stat_name,
                            "value": stat_value,
                            "severity": "HIGH"
                        })

                    # High retry count
                    elif 'retry' in stat_name.lower() and stat_value > 50:
                        anomalies.append({
                            "type": "high_retry_count",
                            "section": section,
                            "stat": stat_name,
                            "value": stat_value,
                            "severity": "MEDIUM"
                        })

                    # High drop count
                    elif 'drop' in stat_name.lower() and stat_value > 50:
                        anomalies.append({
                            "type": "high_drop_count",
                            "section": section,
                            "stat": stat_name,
                            "value": stat_value,
                            "severity": "MEDIUM"
                        })

        # Check RAW stats for concerning values
        for section, stats in classified_stats.get("raw", {}).items():
            for stat_name, stat_value in stats.items():
                if isinstance(stat_value, (int, float)):
                    # Poor RSSI
                    if 'rssi' in stat_name.lower() and stat_value < -70:
                        anomalies.append({
                            "type": "poor_rssi",
                            "section": section,
                            "stat": stat_name,
                            "value": stat_value,
                            "severity": "MEDIUM"
                        })

        return anomalies

    def _analyze_stats_with_llm_chunking(self,
                                         stats_content: str,
                                         anomaly_type: str) -> list[dict[str, Any]]:
        """
        Analyze WiFi stats using LLM with chunking by WIFISTAT sections
        
        Args:
            stats_content: Raw or cleaned stats content
            anomaly_type: Type of anomaly being investigated
        
        Returns:
            List of observations from LLM analysis
        """
        observations = []

        # Split stats by WIFISTAT sections
        sections = self._split_stats_by_sections(stats_content)

        if not sections:
            self._log_warning("No WIFISTAT sections found for LLM analysis")
            return observations

        self._log_info(f"Analyzing {len(sections)} WIFISTAT sections with LLM")

        # Analyze each section with LLM
        for section_name, section_content in sections:
            # Skip empty sections
            if not section_content.strip():
                continue

            # Create analysis prompt for this section
            prompt = self._create_section_analysis_prompt(
                section_name,
                section_content,
                anomaly_type
            )

            # Call LLM
            analysis = self.call_llm(prompt, call_type="wifi")

            if analysis and analysis.strip():
                observations.append({
                    "section": section_name,
                    "analysis": analysis,
                    "anomaly_type": anomaly_type
                })

        return observations

    def _split_stats_by_sections(self, stats_content: str) -> list[tuple]:
        """
        Split stats content by WIFISTAT sections
        
        Args:
            stats_content: Raw stats content
        
        Returns:
            List of (section_name, section_content) tuples
        """
        sections = []
        current_section = None
        current_lines = []

        lines = stats_content.split('\n')

        for line in lines:
            # Check for WIFISTAT section header
            if line.strip().startswith('WIFISTAT') or line.strip().startswith('==='):
                # Save previous section if exists
                if current_section and current_lines:
                    sections.append((current_section, '\n'.join(current_lines)))

                # Start new section
                current_section = line.strip()
                current_lines = []
            else:
                # Add line to current section
                if current_section:
                    current_lines.append(line)

        # Add last section
        if current_section and current_lines:
            sections.append((current_section, '\n'.join(current_lines)))

        return sections

    def _create_section_analysis_prompt(self,
                                       section_name: str,
                                       section_content: str,
                                       anomaly_type: str) -> str:
        """
        Create LLM prompt for analyzing a specific WIFISTAT section
        
        Args:
            section_name: Name of the section (e.g., "WIFISTAT 1")
            section_content: Content of the section
            anomaly_type: Type of anomaly being investigated
        
        Returns:
            Prompt string for LLM
        """
        # Get KB matches for context
        kb_matches = self.get_cached_data("kb_matches") or []
        kb_context = ""
        if kb_matches:
            kb_context = f"\nKnowledge Base Context: {len(kb_matches)} relevant KB sections found"

        prompt = f"""Analyze the following WiFi statistics section in the context of a {anomaly_type} issue.

Section: {section_name}
{kb_context}

Statistics:
{section_content}

INSTRUCTIONS:
1. Identify any concerning values or patterns in these statistics
2. Explain how these stats relate to the {anomaly_type} issue
3. Note any missing or zero values that might indicate problems
4. Provide specific observations with stat names and values
5. Keep analysis concise and technical (3-5 key observations)

Format your response as a list of observations, each starting with "- "

Example:
- tx_xretry shows high retry rate (500+), indicating poor link quality
- ppdu_ok is low compared to attempts, suggesting transmission failures
- flush_errs are elevated, pointing to buffer management issues

Your analysis:"""

        return prompt

    def _create_stats_summary(self,
                             classified_stats: dict[str, dict[str, Any]],
                             anomalies: list[dict[str, Any]]) -> str:
        """Create a concise stats summary for LLM"""
        summary_lines = []

        # Summarize anomalies
        if anomalies:
            summary_lines.append("ANOMALIES DETECTED:")
            for anomaly in anomalies[:10]:  # Limit to 10
                summary_lines.append(
                    f"  - {anomaly['type']}: {anomaly['stat']} = {anomaly['value']} "
                    f"(severity: {anomaly['severity']})"
                )
            summary_lines.append("")

        # Summarize key rate-of-change stats
        summary_lines.append("KEY RATE-OF-CHANGE STATS:")
        roc_stats = classified_stats.get("rate_of_change", {})
        for section, stats in list(roc_stats.items())[:5]:  # Limit to 5 sections
            summary_lines.append(f"  {section}:")
            for stat_name, stat_value in list(stats.items())[:5]:  # Limit to 5 stats per section
                summary_lines.append(f"    {stat_name} = {stat_value}")

        return "\n".join(summary_lines)
