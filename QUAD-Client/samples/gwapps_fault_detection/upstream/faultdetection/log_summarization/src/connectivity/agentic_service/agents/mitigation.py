# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# All rights reserved.
# Confidential and Proprietary - Qualcomm Technologies, Inc.

"""
Mitigation Agent
Suggests actions based on KB recommendations and root cause
"""

from typing import Any

from .base_agent import BaseAgent


class MitigationAgent(BaseAgent):
    """Suggests mitigation actions and next steps"""

    def __init__(self, context, model: str = "qgenie"):
        super().__init__("Mitigation", context, model)

    def analyze(self) -> bool:
        """Generate mitigation recommendations"""
        if self.has_cached_data("mitigations"):
            self._log_info("Using cached mitigations")
            return True

        # Get root causes and KB matches
        root_causes = self.get_cached_data("root_causes") or []
        kb_matches = self.get_cached_data("kb_matches") or []

        if not root_causes:
            self._log_warning("No root causes for mitigation")
            return True

        # Generate mitigations using LLM
        mitigations = self._generate_mitigations(root_causes, kb_matches)

        self.cache_data("mitigations", mitigations)

        for mitigation in mitigations:
            self.add_finding(
                finding_type="mitigation",
                content=mitigation,
                confidence="MEDIUM"
            )

        self._log_info(f"Generated {len(mitigations)} mitigation recommendations")
        return True

    def _generate_mitigations(self, root_causes: list[dict], kb_matches: list[dict]) -> list[dict[str, Any]]:
        """Use LLM to generate mitigation recommendations"""

        # Create context
        context_parts = []
        for rc in root_causes[:2]:  # Top 2 root causes
            context_parts.append(f"Root Cause: {rc.get('description', '')}")
            context_parts.append(f"Confidence: {rc.get('confidence', 'UNKNOWN')}")

        if kb_matches:
            context_parts.append("\nRelevant KB Sections:")
            for kb in kb_matches[:2]:
                context_parts.append(f"- {kb.get('section', '')}")

        context_str = "\n".join(context_parts)

        prompt = f"""Based on the following WiFi connectivity issue analysis:

{context_str}

Provide detailed mitigation recommendations following this structure:

1. IMMEDIATE ACTIONS (low-risk, can be done now):
   - Enable enhanced debug logging: cfg80211tool athX dbgLVL 0x80c00000
   - Check client-side logs if available
   - Monitor for pattern repetition

2. VERIFICATION STEPS (to confirm diagnosis):
   - Capture specific statistics: wifistats wifiX [relevant counters]
   - Enable hostapd debug: hostapd_cli -i athX log_level DEBUG
   - Check for firmware/driver issues

3. CONFIGURATION ADJUSTMENTS (if diagnosis confirmed):
   - Specific parameter changes based on root cause
   - Timeout adjustments
   - Power/channel optimizations

4. ESCALATION PATH (if issue persists):
   - Packet capture requirements
   - Firmware bug investigation
   - Hardware replacement considerations

For each recommendation, provide:
- Specific commands where applicable
- Expected outcomes
- Risk level (LOW/MEDIUM/HIGH)

Focus on WiFi-specific troubleshooting commands and procedures."""

        response = self.call_llm(prompt, call_type="wifi")

        mitigations = []
        if response:
            mitigations = self._parse_mitigation_response(response)

        if not mitigations:
            mitigations = self._generate_fallback_mitigations(root_causes)

        return mitigations

    def _generate_fallback_mitigations(self, root_causes: list[dict]) -> list[dict[str, Any]]:
        """Generate fallback mitigations if LLM fails"""
        mitigations = []

        # Always add standard debugging
        mitigations.append({
            "type": "immediate",
            "action": "Enable enhanced debug logging: cfg80211tool athX dbgLVL 0x80c00000",
            "priority": "HIGH"
        })

        mitigations.append({
            "type": "verification",
            "action": "Check client-side logs and wpa_supplicant status",
            "priority": "MEDIUM"
        })

        # Add specific based on root cause keywords
        if root_causes:
            rc_desc = root_causes[0].get("description", "").lower()

            if "auth" in rc_desc or "assoc" in rc_desc:
                mitigations.append({
                    "type": "immediate",
                    "action": "Verify security settings (PSK/SAE) and check for mismatched configurations",
                    "priority": "HIGH"
                })
                mitigations.append({
                    "type": "verification",
                    "action": "Enable hostapd debug logging: hostapd_cli -i athX log_level DEBUG",
                    "priority": "MEDIUM"
                })

            if "disassoc" in rc_desc or "deauth" in rc_desc:
                mitigations.append({
                    "type": "verification",
                    "action": "Monitor signal strength (RSSI) and interference levels",
                    "priority": "MEDIUM"
                })

        return mitigations

    def _parse_mitigation_response(self, response: str) -> list[dict[str, Any]]:
        """Parse LLM response to extract mitigations"""
        mitigations = []

        # Split into sections
        sections = {
            "immediate": [],
            "verification": [],
            "escalation": []
        }

        current_section = None

        for line in response.split('\n'):
            line = line.strip()
            if not line:
                continue

            # Detect section headers with more flexibility
            line_upper = line.upper()
            if 'IMMEDIATE' in line_upper:
                current_section = "immediate"
            elif 'VERIFICATION' in line_upper:
                current_section = "verification"
            elif 'ESCALATION' in line_upper:
                current_section = "escalation"
            elif 'CONFIGURATION' in line_upper:
                current_section = "verification" # Map config to verification/medium priority
            elif (line.startswith('-') or line.startswith('*') or line[0].isdigit()) and current_section:
                # Handle various bullet points
                action = line.lstrip('-*0123456789. ').strip()
                if action:
                    sections[current_section].append(action)

        # Create mitigation objects
        for section_type, actions in sections.items():
            for action in actions:
                mitigations.append({
                    "type": section_type,
                    "action": action,
                    "priority": "HIGH" if section_type == "immediate" else "MEDIUM"
                })

        return mitigations
