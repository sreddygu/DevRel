# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# All rights reserved.
# Confidential and Proprietary - Qualcomm Technologies, Inc.

"""
Hostapd Parser Agent
Extracts control-plane events from hostapd logs
Uses hybrid approach: regex + parse_hostapd_logs() + LLM chunking
"""

import os
import re
import sys
from typing import Any

from .base_agent import BaseAgent

# Add parent directory to path to import extract_host_apd_stats
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
try:
    from extract_host_apd_stats import parse_hostapd_logs
    PARSE_HOSTAPD_AVAILABLE = True
except ImportError:
    PARSE_HOSTAPD_AVAILABLE = False
    print("[HOSTAPD_PARSER] Warning: Could not import parse_hostapd_logs from extract_host_apd_stats.py")


class HostapdParserAgent(BaseAgent):
    """
    Parses hostapd logs to extract control-plane events:
    - Authentication (SAE, Open, etc.)
    - Association
    - Deauthentication/Disassociation
    - EAPOL (4-way handshake)
    - MLO link transitions
    - SA Query
    """

    def __init__(self, context, model: str = "qgenie"):
        super().__init__("HostapdParser", context, model)

        # Event patterns to match in hostapd logs
        self.event_patterns = {
            'auth': r'authentication|AUTH',
            'assoc': r'association|ASSOC',
            'deauth': r'deauthentication|deauth|DEAUTH',
            'disassoc': r'disassociation|disassoc|DISASSOC',
            'eapol': r'EAPOL|4-way handshake|WPA:',
            'sae': r'SAE|WPA3',
            'mlo': r'MLO|MLD|link_id',
            'sa_query': r'SA Query',
            'del_station': r'DEL_STATION|Delete station|sta_remove'
        }

    def analyze(self) -> bool:
        """
        Parse hostapd logs and extract events
        
        Returns:
            bool: True if parsing succeeded
        """
        # Check if already cached
        if self.has_cached_data("hostapd_events"):
            self._log_info("Using cached hostapd events")
            return True

        # Get hostapd log from shared context
        hostapd_log = self.get_input_data("hostapd_log")

        if not hostapd_log:
            self._log_warning("No hostapd log provided")
            self.add_finding(
                finding_type="hostapd_status",
                content={"status": "missing", "message": "No hostapd log available"},
                confidence="LOW"
            )
            return True  # Not a failure, just no data

        # Parse the log
        events = self._parse_hostapd_log(hostapd_log)

        if not events:
            self._log_warning("No events found in hostapd log")
            self.add_finding(
                finding_type="hostapd_status",
                content={"status": "empty", "message": "No events found in hostapd log"},
                confidence="LOW"
            )
            return True

        # Cache the parsed events
        self.cache_data("hostapd_events", events)

        # Add findings for each event
        for event in events:
            self.add_finding(
                finding_type="hostapd_event",
                content=event,
                references=[f"syslog.txt:line {event.get('line_number', 'unknown')}"],
                metadata={"event_type": event.get("type"), "timestamp": event.get("timestamp")}
            )

        # Use LLM to analyze event patterns
        self._analyze_event_patterns(events)

        self._log_info(f"Parsed {len(events)} hostapd events")
        return True

    def _parse_hostapd_log(self, log_content: str) -> list[dict[str, Any]]:
        """
        Parse hostapd log content using hybrid approach:
        1. Existing regex-based extraction
        2. parse_hostapd_logs() from extract_host_apd_stats.py
        3. LLM-based chunking for comprehensive coverage
        
        Args:
            log_content: Raw hostapd log content
        
        Returns:
            List of event dictionaries (merged and deduplicated)
        """
        all_events = []

        # Method 1: Existing regex-based extraction
        self._log_info("Method 1: Regex-based extraction")
        regex_events = self._parse_with_regex(log_content)
        self._log_info(f"Regex extraction found {len(regex_events)} events")
        all_events.extend(regex_events)

        # Method 2: parse_hostapd_logs() from extract_host_apd_stats.py
        if PARSE_HOSTAPD_AVAILABLE:
            self._log_info("Method 2: parse_hostapd_logs() extraction")
            try:
                # Get anomaly type for parse_hostapd_logs
                anomaly_type = self.get_metadata("anomaly_type") or "DISCONNECT"
                reason = "client_disconnect" if anomaly_type == "DISCONNECT" else "fail_to_connect"

                # Write log to temp file for parse_hostapd_logs
                import tempfile
                with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as tmp:
                    tmp.write(log_content)
                    tmp_path = tmp.name

                # Call parse_hostapd_logs
                parsed_events = parse_hostapd_logs(tmp_path, reason)
                self._log_info(f"parse_hostapd_logs found {len(parsed_events)} events")

                # Convert to our event format
                for pe in parsed_events:
                    event = {
                        "line_number": 0,  # Unknown from parse_hostapd_logs
                        "timestamp": None,
                        "raw_line": pe.get('Line', ''),
                        "type": pe.get('Event', '').lower().replace(' ', '_'),
                        "mac_address": pe.get('MAC Address'),
                        "details": {"description": pe.get('Details', '')}
                    }
                    all_events.append(event)

                # Clean up temp file
                os.unlink(tmp_path)
            except Exception as e:
                self._log_warning(f"parse_hostapd_logs failed: {e}")

        # Method 3: LLM-based chunking
        self._log_info("Method 3: LLM-based chunking extraction")
        llm_events = self._parse_with_llm_chunking(log_content)
        self._log_info(f"LLM chunking found {len(llm_events)} events")
        all_events.extend(llm_events)

        # Deduplicate events
        deduplicated = self._deduplicate_events(all_events)
        self._log_info(f"After deduplication: {len(deduplicated)} unique events")

        return deduplicated

    def _parse_with_regex(self, log_content: str) -> list[dict[str, Any]]:
        """Original regex-based parsing"""
        events = []
        lines = log_content.split('\n')

        for line_num, line in enumerate(lines, 1):
            if not line.strip():
                continue

            # Extract timestamp
            timestamp = self._extract_timestamp(line)

            # Extract MAC address
            mac_address = self._extract_mac_address(line)

            # Determine event type
            event_type = self._determine_event_type(line)

            if event_type:
                event = {
                    "line_number": line_num,
                    "timestamp": timestamp,
                    "raw_line": line,
                    "type": event_type,
                    "mac_address": mac_address,
                    "details": self._extract_event_details(line, event_type),
                    "source": "regex"
                }
                events.append(event)

        return events

    def _parse_with_llm_chunking(self, log_content: str) -> list[dict[str, Any]]:
        """
        Parse log using LLM with chunking strategy
        Breaks log into ~4000 token chunks with 200 token overlap
        """
        events = []
        lines = log_content.split('\n')

        # Estimate tokens (rough: 1 token ≈ 4 characters)
        chunk_size = 2000 * 4  # ~8000 characters (matches LLM prompt truncation limit)
        overlap_size = 200 * 4  # ~800 characters

        chunks = []
        current_chunk = []
        current_size = 0

        for line in lines:
            line_size = len(line)
            if current_size + line_size > chunk_size and current_chunk:
                # Save current chunk
                chunks.append('\n'.join(current_chunk))
                # Start new chunk with overlap
                overlap_lines = current_chunk[-20:]  # Last ~20 lines for overlap
                current_chunk = overlap_lines + [line]
                current_size = sum(len(l) for l in current_chunk)
            else:
                current_chunk.append(line)
                current_size += line_size

        # Add final chunk
        if current_chunk:
            chunks.append('\n'.join(current_chunk))

        self._log_info(f"Split log into {len(chunks)} chunks for LLM processing")

        # Process each chunk with LLM
        for i, chunk in enumerate(chunks):
            self._log_debug(f"Processing chunk {i+1}/{len(chunks)}")
            chunk_events = self._extract_events_from_chunk(chunk, i)
            events.extend(chunk_events)

        return events

    def _extract_events_from_chunk(self, chunk: str, chunk_num: int) -> list[dict[str, Any]]:
        """Extract WiFi events from a log chunk using LLM"""
        prompt = f"""Extract WiFi-related events from this syslog chunk. For each event, provide:
- Timestamp (if present)
- Event type (auth, assoc, deauth, disassoc, EAPOL, SAE, error, etc.)
- MAC address (if present)
- Key details

Focus on WiFi connectivity events. Ignore non-WiFi logs (SSH, dropbear, vendor events, etc.).

Format each event as:
EVENT: <event_type> | TIMESTAMP: <timestamp> | MAC: <mac_address> | DETAILS: <details>

Log chunk:
{chunk[:8000]}
"""

        response = self.call_llm(prompt, call_type="hostapd")

        if not response:
            return []

        # Parse LLM response
        events = []
        for line in response.split('\n'):
            if line.startswith('EVENT:'):
                try:
                    # Parse format: EVENT: <type> | TIMESTAMP: <ts> | MAC: <mac> | DETAILS: <details>
                    parts = line.split('|')
                    event_type = parts[0].replace('EVENT:', '').strip().lower()
                    timestamp = parts[1].replace('TIMESTAMP:', '').strip() if len(parts) > 1 else None
                    mac = parts[2].replace('MAC:', '').strip() if len(parts) > 2 else None
                    details_str = parts[3].replace('DETAILS:', '').strip() if len(parts) > 3 else ""

                    event = {
                        "line_number": 0,
                        "timestamp": timestamp if timestamp and timestamp != 'unknown' else None,
                        "raw_line": line,
                        "type": event_type,
                        "mac_address": mac if mac and mac != 'unknown' else None,
                        "details": {"description": details_str},
                        "source": f"llm_chunk_{chunk_num}"
                    }
                    events.append(event)
                except Exception as e:
                    self._log_debug(f"Failed to parse LLM event line: {line[:100]} - {e}")

        return events

    def _deduplicate_events(self, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Deduplicate events based on timestamp + MAC + event type
        Prefer events with more details
        """
        seen = {}

        for event in events:
            # Create key for deduplication
            timestamp = event.get('timestamp') or 'no_ts'
            mac = event.get('mac_address') or 'no_mac'
            event_type = event.get('type') or 'no_type'
            key = f"{timestamp}_{mac}_{event_type}"

            # Keep event with more details
            if key not in seen:
                seen[key] = event
            else:
                # Compare detail richness
                existing_details = seen[key].get('details', {})
                new_details = event.get('details', {})

                if len(str(new_details)) > len(str(existing_details)):
                    seen[key] = event

        return list(seen.values())

    def _extract_timestamp(self, line: str) -> str | None:
        """Extract timestamp from log line"""
        # Pattern: Thu Nov 13 12:01:30 2025 or 1763035290.422481
        timestamp_patterns = [
            r'(\w{3}\s+\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}\s+\d{4})',
            r'(\d{10}\.\d{6})'
        ]

        for pattern in timestamp_patterns:
            match = re.search(pattern, line)
            if match:
                return match.group(1)

        return None

    def _extract_mac_address(self, line: str) -> str | None:
        """Extract MAC address from log line"""
        # Pattern: xx:xx:xx:xx:xx:xx
        mac_pattern = r'([0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2})'
        match = re.search(mac_pattern, line)
        return match.group(1) if match else None

    def _determine_event_type(self, line: str) -> str | None:
        """Determine the type of event from the log line"""
        line_lower = line.lower()

        # Skip non-WiFi related logs (SSH, dropbear, etc.)
        if any(keyword in line_lower for keyword in ['dropbear', 'ssh', 'authpriv', 'child connection']):
            return None

        # Check for specific WiFi/hostapd patterns first (more specific matches)
        if 'disassociated' in line_lower or 'disassoc' in line_lower:
            return 'disassoc'
        elif 'deauthenticate' in line_lower or 'deauth' in line_lower:
            return 'deauth'
        elif 'authenticated' in line_lower and ('hostapd' in line_lower or 'ieee 802.11' in line_lower):
            return 'auth'
        elif 'associated' in line_lower and ('hostapd' in line_lower or 'ieee 802.11' in line_lower):
            return 'assoc'

        # Then check general patterns
        for event_type, pattern in self.event_patterns.items():
            if re.search(pattern, line, re.IGNORECASE):
                return event_type

        return None

    def _extract_event_details(self, line: str, event_type: str) -> dict[str, Any]:
        """Extract specific details based on event type"""
        details = {}

        if event_type == 'deauth' or event_type == 'disassoc':
            # Extract reason code
            reason_match = re.search(r'reason[:\s=]+(\d+)', line, re.IGNORECASE)
            if reason_match:
                details['reason_code'] = int(reason_match.group(1))

            # CRITICAL: Detect RX frame direction and frame subtype for disconnect initiator detection
            # Pattern: nl80211: RX frame ... stype=12 (WLAN_FC_STYPE_DEAUTH)
            if 'nl80211: RX frame' in line and 'stype=' in line:
                stype_match = re.search(r'stype=(\d+)', line)
                if stype_match:
                    details['frame_direction'] = 'RX'
                    details['stype'] = int(stype_match.group(1))
                    # Extract frame type description
                    if 'WLAN_FC_STYPE_DEAUTH' in line:
                        details['frame_type'] = 'DEAUTH'
                    elif 'WLAN_FC_STYPE_DISASSOC' in line:
                        details['frame_type'] = 'DISASSOC'

            # CRITICAL: Detect "trying to deauthenticate, but it is not authenticated"
            # This is the smoking gun for STA-initiated disconnect
            if 'trying to deauthenticate' in line.lower() and 'not authenticated' in line.lower():
                details['initiator'] = 'STA'
                details['status'] = 'sta_initiated_deauth'
                details['evidence'] = 'Station sent deauth frame after already being disconnected'
                # DEBUG: Log smoking gun detection
                print("[HOSTAPD_PARSER DEBUG] SMOKING GUN DETECTED!")
                print(f"[HOSTAPD_PARSER DEBUG] Details: {details}")
                print(f"[HOSTAPD_PARSER DEBUG] Raw line: {line[:100]}")

            # Extract general description
            if event_type == 'disassoc':
                details['action'] = 'disassociated'
            elif event_type == 'deauth':
                details['action'] = 'deauthenticated'

            # Extract specific status messages
            if 'trying to deauthenticate' in line.lower() and 'initiator' not in details:
                details['status'] = 'deauth_attempt'
            elif 'not authenticated' in line.lower() and 'initiator' not in details:
                details['status'] = 'not_authenticated'

        elif event_type == 'eapol':
            # Extract EAPOL message number (M1, M2, M3, M4)
            eapol_match = re.search(r'(M[1-4]|msg [1-4]/[24]|EAPOL-Key [1-4]/[24])', line, re.IGNORECASE)
            if eapol_match:
                details['eapol_message'] = eapol_match.group(1)

            # Extract EAPOL status
            if 'handshake completed' in line.lower():
                details['status'] = 'handshake_completed'
            elif 'TX status' in line:
                details['status'] = 'tx_status'
            elif 'RX EAPOL' in line:
                details['status'] = 'rx_eapol'

        elif event_type == 'sae':
            # Extract SAE state
            if 'commit' in line.lower():
                details['sae_state'] = 'commit'
            elif 'confirm' in line.lower():
                details['sae_state'] = 'confirm'

            # Extract SAE status
            if 'State' in line and '->' in line:
                state_match = re.search(r'State\s+(\w+)\s+->\s+(\w+)', line)
                if state_match:
                    details['state_transition'] = f"{state_match.group(1)}->{state_match.group(2)}"

        elif event_type == 'mlo':
            # Extract link ID
            link_match = re.search(r'link[_\s]id[:\s=]+(\d+)', line, re.IGNORECASE)
            if link_match:
                details['link_id'] = int(link_match.group(1))

        elif event_type == 'auth':
            # Extract auth algorithm and transaction
            auth_alg_match = re.search(r'auth_alg=(\d+)', line)
            if auth_alg_match:
                details['auth_alg'] = int(auth_alg_match.group(1))

            auth_trans_match = re.search(r'auth_transaction=(\d+)', line)
            if auth_trans_match:
                details['auth_transaction'] = int(auth_trans_match.group(1))

            # Extract status
            if 'authenticated' in line.lower():
                details['status'] = 'authenticated'
            elif 'authentication reply' in line.lower():
                details['status'] = 'auth_reply'

        elif event_type == 'assoc':
            # Extract association status
            if 'associated' in line.lower():
                details['status'] = 'associated'
                # Extract AID
                aid_match = re.search(r'aid (\d+)', line)
                if aid_match:
                    details['aid'] = int(aid_match.group(1))
            elif 'association request' in line.lower():
                details['status'] = 'assoc_request'
            elif 'reassociation request' in line.lower():
                details['status'] = 'reassoc_request'

        elif event_type == 'del_station':
            # Extract deletion reason
            if 'DEL_STATION' in line:
                details['action'] = 'del_station'
            elif 'Delete station' in line:
                details['action'] = 'delete_station'
            elif 'sta_remove' in line:
                details['action'] = 'sta_remove'

        # If no specific details were extracted, create a general description
        if not details:
            # Extract key phrases for a general description
            key_phrases = []

            # Look for common hostapd keywords
            keywords = ['authenticated', 'associated', 'disassociated', 'deauth', 'EAPOL', 'SAE', 'handshake', 'completed']
            for keyword in keywords:
                if keyword.lower() in line.lower():
                    key_phrases.append(keyword)

            if key_phrases:
                details['description'] = ', '.join(key_phrases)
            else:
                # Extract the main message after the timestamp and process info
                # Pattern to remove timestamp and syslog prefix
                clean_match = re.search(r'(?:hostapd:|root:)\s*(.+)', line)
                if clean_match:
                    message = clean_match.group(1).strip()
                    # Truncate very long messages
                    if len(message) > 100:
                        message = message[:97] + "..."
                    details['message'] = message

        return details

    def _analyze_event_patterns(self, events: list[dict[str, Any]]) -> None:
        """
        Use LLM to analyze event patterns and identify sequences
        """
        if not events:
            return

        # Create a summary of events for LLM analysis
        event_summary = self._create_event_summary(events)

        prompt = f"""Analyze the following hostapd event sequence and identify patterns:

{event_summary}

Identify:
1. Connection establishment sequences (auth -> assoc -> EAPOL)
2. Disconnection patterns (deauth/disassoc with reason codes)
3. Timing anomalies (rapid reconnects, delays)
4. MLO-specific patterns
5. Any unusual sequences

Provide a concise analysis focusing on patterns relevant to WiFi connectivity issues."""

        analysis = self.call_llm(prompt, call_type="hostapd")

        if analysis:
            self.add_finding(
                finding_type="hostapd_pattern_analysis",
                content={"analysis": analysis, "event_count": len(events)},
                confidence="MEDIUM"
            )

    def _create_event_summary(self, events: list[dict[str, Any]]) -> str:
        """Create a concise summary of events for LLM"""
        summary_lines = []

        for event in events[:50]:  # Limit to first 50 events to avoid token limits
            timestamp = event.get('timestamp', 'unknown')
            event_type = event.get('type', 'unknown')
            mac = event.get('mac_address', 'unknown')
            details = event.get('details', {})

            line = f"{timestamp} | {event_type.upper()} | MAC: {mac}"

            if details:
                detail_str = ", ".join([f"{k}={v}" for k, v in details.items()])
                line += f" | {detail_str}"

            summary_lines.append(line)

        if len(events) > 50:
            summary_lines.append(f"... and {len(events) - 50} more events")

        return "\n".join(summary_lines)
