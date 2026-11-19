# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# All rights reserved.
# Confidential and Proprietary - Qualcomm Technologies, Inc.

"""
Knowledge Base Matcher Agent
Advanced AI/ML-powered KB matching using semantic similarity and vector search
"""

import os
import re
import sys
from typing import Any

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

# Import TF-IDF similarity implementation
from sklearn.metrics.pairwise import cosine_similarity

from .base_agent import BaseAgent

_kb_src_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _kb_src_dir not in sys.path:
    sys.path.insert(0, _kb_src_dir)
from simple_similarity import SimpleSimilarity


class KBMatcherAgent(BaseAgent):
    """
    Advanced AI/ML-powered KB matching using semantic similarity and vector search.
    Combines multiple techniques for accurate knowledge base matching.
    """

    def __init__(self, context, model: str = "qgenie"):
        super().__init__("KBMatcher", context, model)
        self.kb_content = None
        self.kb_sections = []  # Parsed KB sections for vector search
        self.kb_embeddings = None  # Precomputed embeddings

        # Initialize ML models
        self._init_ml_models()

    def _init_ml_models(self):
        """Initialize TF-IDF models for KB matching"""
        try:
            # Use SimpleSimilarity for semantic similarity
            self.simple_similarity = SimpleSimilarity()
            # Use TF-IDF vectorizer for pattern matching
            self.tfidf_vectorizer = TfidfVectorizer(
                stop_words='english',
                ngram_range=(1, 3),  # Include trigrams for technical terms
                max_features=2000,
                lowercase=True
            )
            self._log_info("TF-IDF similarity models loaded successfully")
        except Exception as e:
            self._log_warning(f"Could not load similarity models: {e}")
            self.simple_similarity = None
            self.tfidf_vectorizer = None

    def analyze(self) -> bool:
        """
        Advanced AI/ML-powered KB matching with multi-stage pipeline
        
        Returns:
            bool: True if matching succeeded
        """
        # Check if already cached
        if self.has_cached_data("kb_matches"):
            self._log_info("Using cached KB matches")
            return True

        # Load knowledge base
        kb_content = self.get_input_data("knowledge_base")
        if not kb_content:
            self._log_warning("No knowledge base provided")
            return True  # Not a failure, just no KB

        self.kb_content = kb_content

        # Parse KB into sections for vector search
        self._parse_kb_sections()

        # Get anomaly type and other metadata
        anomaly_type = self.get_metadata("anomaly_type")
        mac_address = self.get_metadata("mac_address")

        # Get hostapd events and timeline for context
        hostapd_events = self.get_cached_data("hostapd_events")
        timeline = self.get_cached_data("timeline") or []

        # Get disconnect analysis if available
        disconnect_analysis = self.get_cached_data("disconnect_analysis")

        # Multi-stage ML-powered matching pipeline
        matches = []

        # Stage 1: Semantic vector search
        semantic_matches = self._semantic_vector_search(anomaly_type, hostapd_events, timeline, disconnect_analysis)
        matches.extend(semantic_matches)

        # Stage 2: Traditional pattern matching (enhanced)
        if hostapd_events:
            pattern_matches = self._enhanced_pattern_matching(hostapd_events)
            matches.extend(pattern_matches)

        # Stage 3: Detailed rule-based anomaly matching (High Priority)
        if anomaly_type:
            # Use the detailed rule matcher which handles disconnect initiator logic
            rule_matches = self._match_anomaly_type(anomaly_type, hostapd_events, timeline, disconnect_analysis)
            matches.extend(rule_matches)

            # Also run contextual matching for additional context
            contextual_matches = self._contextual_anomaly_matching(anomaly_type, timeline)
            matches.extend(contextual_matches)

        # Stage 4: LLM-guided analysis with ML preprocessing
        llm_matches = self._ml_enhanced_llm_analysis(anomaly_type, hostapd_events, timeline)
        if llm_matches:
            matches.extend(llm_matches)

        # Advanced deduplication and ranking with ML scoring
        unique_matches = self._ml_deduplicate_and_rank(matches, anomaly_type, timeline)

        # Cache the matches
        self.cache_data("kb_matches", unique_matches)

        # Add findings
        for match in unique_matches:
            self.add_finding(
                finding_type="kb_match",
                content=match,
                confidence=match.get("confidence", "MEDIUM"),
                references=[f"knowledge_base.txt:{match.get('section', 'unknown')}"]
            )

        self._log_info(f"Found {len(unique_matches)} KB matches using advanced ML pipeline")
        return True

    def _parse_kb_sections(self):
        """Parse KB into structured sections for vector search"""
        if not self.kb_content:
            return

        self.kb_sections = []

        # Split KB into logical sections
        # Look for main section headers (## or numbered)
        section_pattern = r'(?:^##\s+(.+?)$|^(\d+\.\s+.+?)$)'
        sections = re.split(section_pattern, self.kb_content, flags=re.MULTILINE)

        current_section = {"title": "Introduction", "content": ""}

        for i, part in enumerate(sections):
            if part and part.strip():
                if re.match(r'^##\s+|^\d+\.\s+', part.strip()):
                    # This is a section header
                    if current_section["content"].strip():
                        self.kb_sections.append(current_section)
                    current_section = {"title": part.strip(), "content": ""}
                else:
                    # This is section content
                    current_section["content"] += part

        # Add the last section
        if current_section["content"].strip():
            self.kb_sections.append(current_section)

        self._log_debug(f"Parsed KB into {len(self.kb_sections)} sections")

    def _semantic_vector_search(self, anomaly_type: str | None,
                               hostapd_events: list[dict[str, Any]] | None,
                               timeline: list[dict[str, Any]],
                               disconnect_analysis: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Use semantic embeddings to find relevant KB sections"""
        if not self.kb_sections:
            return []

        # Create query from context
        query_parts = []

        # Incorporate disconnect analysis into query
        if disconnect_analysis:
            initiator = disconnect_analysis.get('initiator')
            if initiator and initiator != 'UNKNOWN':
                query_parts.append(f"Disconnection initiated by {initiator}")
                if initiator == 'STA':
                    query_parts.append("Station sent deauth frame")
                elif initiator == 'AP':
                    query_parts.append("AP sent deauth frame")

        if anomaly_type:
            query_parts.append(f"WiFi {anomaly_type.lower().replace('_', ' ')} issue")

        if hostapd_events:
            event_types = [e.get('type', '') for e in hostapd_events[:5]]
            query_parts.append(f"hostapd events: {' '.join(event_types)}")

        if timeline:
            # Extract key details from timeline
            details = []
            for event in timeline[:3]:
                event_details = event.get('details', {})
                if isinstance(event_details, dict):
                    for key, value in event_details.items():
                        if key in ['reason_code', 'status', 'action']:
                            details.append(f"{key}: {value}")
            if details:
                query_parts.append(f"technical details: {' '.join(details)}")

        query_text = " ".join(query_parts)

        if not query_text:
            return []

        matches = []

        # Use TF-IDF similarity
        if hasattr(self, 'simple_similarity') and self.simple_similarity:
            try:
                for section in self.kb_sections:
                    section_text = f"{section['title']} {section['content'][:1000]}"
                    similarity = self.simple_similarity.similarity(query_text, section_text)

                    if similarity > 0.2:  # Lower threshold for simple similarity
                        matches.append({
                            "type": "simple_semantic",
                            "section": section["title"],
                            "context": section["content"][:500],
                            "confidence": "MEDIUM" if similarity > 0.4 else "LOW",
                            "relevance_score": similarity,
                            "similarity": similarity
                        })

                # Sort by similarity and take top 3
                matches.sort(key=lambda x: x['similarity'], reverse=True)
                matches = matches[:3]

                self._log_debug(f"Simple semantic search found {len(matches)} matches")

            except Exception as e:
                self._log_warning(f"Simple semantic search failed: {e}")

        return matches

    def _enhanced_pattern_matching(self, hostapd_events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Enhanced pattern matching with ML-powered relevance scoring"""
        matches = []

        # Extract patterns from events
        patterns = []
        for event in hostapd_events:
            event_type = event.get('type')
            details = event.get('details', {})

            if event_type in ['deauth', 'disassoc']:
                reason_code = details.get('reason_code')
                if reason_code:
                    patterns.append(f"reason code {reason_code}")
                    patterns.append(f"disconnection {event_type}")

            elif event_type == 'eapol':
                patterns.append("4-way handshake")
                patterns.append("EAPOL key exchange")
                if 'eapol_message' in details:
                    patterns.append(f"EAPOL {details['eapol_message']}")

            elif event_type == 'sae':
                patterns.append("SAE authentication")
                patterns.append("WPA3 security")
                if 'sae_state' in details:
                    patterns.append(f"SAE {details['sae_state']}")

            elif event_type == 'mlo':
                patterns.append("Multi-Link Operation")
                patterns.append("MLO configuration")
                if 'link_id' in details:
                    patterns.append(f"link ID {details['link_id']}")

        # Search KB for each pattern with ML-enhanced scoring
        for pattern in patterns:
            kb_match = self._ml_enhanced_pattern_search(pattern)
            if kb_match:
                matches.append(kb_match)

        return matches

    def _ml_enhanced_pattern_search(self, pattern: str) -> dict[str, Any] | None:
        """ML-enhanced pattern search with contextual understanding"""
        if not self.kb_content:
            return None

        # Use TF-IDF for better pattern matching if available
        if self.tfidf_vectorizer and self.kb_sections:
            try:
                # Create corpus of KB sections
                section_texts = [f"{section['title']} {section['content']}"
                               for section in self.kb_sections]

                # Fit TF-IDF on KB sections + pattern
                all_texts = section_texts + [pattern]
                tfidf_matrix = self.tfidf_vectorizer.fit_transform(all_texts)

                # Calculate similarity between pattern and each section
                pattern_vector = tfidf_matrix[-1]  # Last item is the pattern
                section_vectors = tfidf_matrix[:-1]  # All except last

                similarities = cosine_similarity(pattern_vector, section_vectors)[0]

                # Find best match
                best_idx = np.argmax(similarities)
                best_score = similarities[best_idx]

                if best_score > 0.1:  # Threshold for TF-IDF relevance
                    return {
                        "type": "ml_pattern_match",
                        "pattern": pattern,
                        "section": self.kb_sections[best_idx]["title"],
                        "context": self.kb_sections[best_idx]["content"][:500],
                        "confidence": "HIGH" if best_score > 0.3 else "MEDIUM",
                        "relevance_score": float(best_score),
                        "tfidf_score": float(best_score)
                    }

            except Exception as e:
                self._log_debug(f"TF-IDF pattern search failed: {e}")

        # Fallback to regex search
        match = re.search(re.escape(pattern), self.kb_content, re.IGNORECASE)
        if match:
            context = self._extract_context(self.kb_content, match.start(), 500)
            section = self._identify_section(self.kb_content, match.start())

            return {
                "type": "regex_pattern_match",
                "pattern": pattern,
                "section": section,
                "context": context,
                "confidence": "MEDIUM",
                "relevance_score": 0.6
            }

        return None

    def _contextual_anomaly_matching(self, anomaly_type: str,
                                   timeline: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Context-aware anomaly matching using timeline analysis"""
        matches = []

        # Analyze timeline for contextual clues
        context_clues = self._extract_timeline_context(timeline)

        # Enhanced anomaly-specific matching with context
        if anomaly_type == "DISCONNECT":
            # Look for specific disconnect patterns
            if context_clues.get('has_inactivity_pattern'):
                match = self._search_kb_for_pattern("inactive.*timeout|keepalive.*timeout")
                if match:
                    match["context_evidence"] = "Timeline shows inactivity pattern"
                    match["relevance_score"] = 0.9
                    matches.append(match)

            if context_clues.get('has_rapid_disconnects'):
                match = self._search_kb_for_pattern("kickout.*STA|excessive.*retry")
                if match:
                    match["context_evidence"] = "Timeline shows rapid disconnection pattern"
                    match["relevance_score"] = 0.85
                    matches.append(match)

        elif anomaly_type == "FAIL_TO_CONNECT":
            if context_clues.get('auth_failures'):
                match = self._search_kb_for_pattern("2\\..*Authentication")
                if match:
                    match["context_evidence"] = f"Timeline shows {context_clues['auth_failures']} auth failures"
                    match["relevance_score"] = 0.9
                    matches.append(match)

            if context_clues.get('eapol_issues'):
                match = self._search_kb_for_pattern("4.*Way.*Handshaking")
                if match:
                    match["context_evidence"] = "Timeline shows EAPOL handshake issues"
                    match["relevance_score"] = 0.85
                    matches.append(match)

        return matches

    def _extract_timeline_context(self, timeline: list[dict[str, Any]]) -> dict[str, Any]:
        """Extract contextual patterns from timeline"""
        context = {}

        if not timeline:
            return context

        # Count event types
        event_counts = {}
        for event in timeline:
            event_type = event.get('event_type', '')
            event_counts[event_type] = event_counts.get(event_type, 0) + 1

        # Analyze patterns
        context['auth_failures'] = event_counts.get('auth', 0)
        context['eapol_issues'] = event_counts.get('eapol', 0)
        context['disconnect_count'] = event_counts.get('disassoc', 0) + event_counts.get('deauth', 0)

        # Check for rapid disconnects (multiple disconnects in short time)
        context['has_rapid_disconnects'] = context['disconnect_count'] > 2

        # Check for inactivity patterns (long gaps between events)
        if len(timeline) > 1:
            timestamps = [event.get('timestamp', '') for event in timeline if event.get('timestamp')]
            # Simple heuristic: if we have few events but they span time, might be inactivity
            context['has_inactivity_pattern'] = len(timestamps) < 5 and len(set(timestamps)) > 1

        return context

    def _ml_enhanced_llm_analysis(self, anomaly_type: str | None,
                                 hostapd_events: list[dict[str, Any]] | None,
                                 timeline: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """LLM analysis enhanced with ML preprocessing"""
        if not self.kb_content:
            return []

        # Use ML to pre-select most relevant KB sections
        relevant_sections = self._ml_select_relevant_sections(anomaly_type, timeline)

        # Create enhanced situation summary with ML insights
        situation_summary = self._create_enhanced_situation_summary(
            anomaly_type, hostapd_events, timeline
        )

        prompt = f"""Given the following WiFi connectivity issue analysis:

{situation_summary}

And these pre-selected relevant KB sections (chosen by ML analysis):

{relevant_sections}

Identify the most relevant KB sections that match this issue. Focus on:
1. Event sequences that match the timeline patterns
2. Specific technical indicators and error codes
3. Root cause patterns described in the KB
4. Contextual evidence from the timeline analysis

For each match, provide:
1. Section name/title (be specific and exact)
2. Why it's relevant (cite specific evidence from timeline/events)
3. Confidence level (HIGH/MEDIUM/LOW)
4. Key technical context from that section

Format your response as:
SECTION: [exact section name from KB]
RELEVANCE: [detailed explanation with specific evidence]
CONTEXT: [key technical information from this KB section]
CONFIDENCE: [HIGH/MEDIUM/LOW]
---"""

        response = self.call_llm(prompt, call_type="wifi")

        if response:
            return self._parse_llm_kb_response(response)

        return []

    def _ml_select_relevant_sections(self, anomaly_type: str | None,
                                   timeline: list[dict[str, Any]]) -> str:
        """Use ML to pre-select most relevant KB sections"""
        if not self.kb_sections:
            return self.kb_content[:8000]

        # Create query from anomaly type and timeline
        query_parts = []
        if anomaly_type:
            query_parts.append(anomaly_type.lower().replace('_', ' '))

        # Extract technical terms from timeline
        tech_terms = []
        for event in timeline[:5]:
            details = event.get('details', {})
            if isinstance(details, dict):
                for key, value in details.items():
                    tech_terms.append(f"{key} {value}")

        if tech_terms:
            query_parts.extend(tech_terms)

        query = " ".join(query_parts)

        # Use TF-IDF similarity to rank sections if query available
        if self.simple_similarity and query and self.kb_sections:
            try:
                section_scores = []
                for idx, section in enumerate(self.kb_sections):
                    section_text = f"{section['title']} {section['content'][:500]}"
                    similarity = self.simple_similarity.similarity(query, section_text)
                    section_scores.append((idx, similarity))

                # Sort by similarity and take top 5
                section_scores.sort(key=lambda x: x[1], reverse=True)
                top_sections = section_scores[:5]

                selected_sections = []
                for idx, score in top_sections:
                    if score > 0.2:  # Relevance threshold
                        section = self.kb_sections[idx]
                        selected_sections.append(f"=== {section['title']} ===\n{section['content'][:2000]}")

                if selected_sections:
                    return "\n\n".join(selected_sections)

            except Exception as e:
                self._log_debug(f"TF-IDF section selection failed: {e}")

        # Fallback to original method
        return self._get_relevant_kb_sections(anomaly_type)

    def _create_enhanced_situation_summary(self, anomaly_type: str | None,
                                         hostapd_events: list[dict[str, Any]] | None,
                                         timeline: list[dict[str, Any]]) -> str:
        """Create enhanced situation summary with ML-extracted insights"""
        summary_parts = []

        if anomaly_type:
            summary_parts.append(f"Anomaly Type: {anomaly_type}")

        mac_address = self.get_metadata("mac_address")
        if mac_address:
            summary_parts.append(f"MAC Address: {mac_address}")

        # Enhanced event analysis
        if hostapd_events:
            event_analysis = self._analyze_event_patterns(hostapd_events)
            summary_parts.append(f"Event Pattern Analysis: {event_analysis}")

        # Timeline insights
        if timeline:
            timeline_insights = self._extract_timeline_insights(timeline)
            summary_parts.append(f"Timeline Insights: {timeline_insights}")

        return "\n".join(summary_parts)

    def _analyze_event_patterns(self, hostapd_events: list[dict[str, Any]]) -> str:
        """Analyze patterns in hostapd events"""
        patterns = []

        event_types = [e.get('type') for e in hostapd_events]
        event_counts = {t: event_types.count(t) for t in set(event_types)}

        # Identify significant patterns
        if event_counts.get('eapol', 0) > 5:
            patterns.append("High EAPOL activity (handshake issues)")

        if event_counts.get('sae', 0) > 3:
            patterns.append("Multiple SAE authentication attempts")

        if event_counts.get('mlo', 0) > 10:
            patterns.append("Extensive MLO activity (link management issues)")

        # Check for reason codes
        reason_codes = []
        for event in hostapd_events:
            details = event.get('details', {})
            if 'reason_code' in details:
                reason_codes.append(str(details['reason_code']))

        if reason_codes:
            patterns.append(f"Reason codes: {', '.join(set(reason_codes))}")

        return "; ".join(patterns) if patterns else "Standard event sequence"

    def _extract_timeline_insights(self, timeline: list[dict[str, Any]]) -> str:
        """Extract insights from timeline analysis"""
        insights = []

        if len(timeline) > 20:
            insights.append("High event volume")

        # Check for timing patterns
        timestamps = [e.get('timestamp') for e in timeline if e.get('timestamp')]
        if len(set(timestamps)) < len(timestamps) / 2:
            insights.append("Events clustered in time")

        # Check for specific technical details
        tech_details = []
        for event in timeline[:5]:
            details = event.get('details', {})
            if isinstance(details, dict):
                for key, value in details.items():
                    if key in ['reason_code', 'status', 'link_id', 'auth_alg']:
                        tech_details.append(f"{key}={value}")

        if tech_details:
            insights.append(f"Technical indicators: {', '.join(tech_details[:3])}")

        return "; ".join(insights) if insights else "Standard timeline pattern"

    def _ml_deduplicate_and_rank(self, matches: list[dict[str, Any]],
                                anomaly_type: str | None,
                                timeline: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Advanced ML-powered deduplication and ranking"""
        if not matches:
            return []

        # Remove duplicates based on section similarity
        unique_matches = []
        seen_sections = set()

        for match in matches:
            section = match.get('section', '')
            # Normalize section names for better deduplication
            normalized_section = re.sub(r'^\d+\.\s*', '', section.lower().strip())

            if normalized_section and normalized_section not in seen_sections:
                seen_sections.add(normalized_section)
                unique_matches.append(match)

        # ML-enhanced ranking
        for match in unique_matches:
            # Base relevance score
            base_score = match.get('relevance_score', 0.5)

            # Boost score based on match type
            type_boost = {
                'semantic_vector': 0.3,
                'ml_pattern_match': 0.2,
                'reason_code': 0.25,
                'llm_analysis': 0.15
            }

            match_type = match.get('type', '')
            boost = type_boost.get(match_type, 0.0)

            # Context-based boosting
            if 'context_evidence' in match:
                boost += 0.1

            # Anomaly-specific boosting
            if anomaly_type == "DISCONNECT" and any(term in match.get('section', '').lower()
                                                   for term in ['disconnect', 'kickout', 'inactive']):
                boost += 0.15

            # Final score
            final_score = min(1.0, base_score + boost)
            match['final_relevance_score'] = final_score

        # Sort by final relevance score
        unique_matches.sort(key=lambda x: x.get('final_relevance_score', 0), reverse=True)

        # Return top matches
        return unique_matches[:5]

    def _match_hostapd_events(self, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Match hostapd events against KB patterns
        
        Args:
            events: List of hostapd events
        
        Returns:
            List of KB matches
        """
        matches = []

        for event in events:
            event_type = event.get('type')
            details = event.get('details', {})

            # Match disconnection events with reason codes
            if event_type in ['deauth', 'disassoc']:
                reason_code = details.get('reason_code')
                if reason_code:
                    kb_match = self._search_kb_for_reason_code(reason_code)
                    if kb_match:
                        matches.append(kb_match)

            # Match EAPOL events
            elif event_type == 'eapol':
                kb_match = self._search_kb_for_pattern("4-way handshake|EAPOL")
                if kb_match:
                    matches.append(kb_match)

            # Match SAE events
            elif event_type == 'sae':
                kb_match = self._search_kb_for_pattern("SAE|WPA3|Authentication")
                if kb_match:
                    matches.append(kb_match)

            # Match MLO events
            elif event_type == 'mlo':
                kb_match = self._search_kb_for_pattern("MLO|Multi-Link|MLD")
                if kb_match:
                    matches.append(kb_match)

        return matches

    def _match_anomaly_type(self, anomaly_type: str,
                          hostapd_events: list[dict[str, Any]] = None,
                          timeline: list[dict[str, Any]] = None,
                          disconnect_analysis: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """
        Match anomaly type against KB sections
        
        Args:
            anomaly_type: Type of anomaly (DISCONNECT, DATA_STALL, etc.)
            hostapd_events: List of hostapd events
            timeline: Timeline events
            disconnect_analysis: Analysis from DisconnectAnalyzerAgent
        
        Returns:
            List of KB matches
        """
        matches = []

        # Ensure we have data
        if hostapd_events is None:
            hostapd_events = self.get_cached_data("hostapd_events") or []
        if timeline is None:
            timeline = self.get_cached_data("timeline") or []

        if anomaly_type == "DISCONNECT":
            # Analyze evidence to determine disconnect initiator
            sta_evidence_score = 0
            ap_evidence_score = 0

            # DEBUG: Start evidence analysis
            print("\n[KB_MATCHER DEBUG] Starting evidence analysis for DISCONNECT anomaly")

            # CRITICAL: Use DisconnectAnalyzer result if available
            if disconnect_analysis:
                initiator = disconnect_analysis.get('initiator')
                confidence_val = disconnect_analysis.get('confidence', 0.0)

                # Convert string confidence to float if needed
                if isinstance(confidence_val, str):
                    if confidence_val.upper() == 'HIGH':
                        confidence_score = 1.0
                    elif confidence_val.upper() == 'MEDIUM':
                        confidence_score = 0.5
                    elif confidence_val.upper() == 'LOW':
                        confidence_score = 0.2
                    else:
                        confidence_score = 0.5
                elif isinstance(confidence_val, (int, float)):
                    confidence_score = float(confidence_val)
                else:
                    confidence_score = 0.5

                print(f"[KB_MATCHER DEBUG] DisconnectAnalyzer result: initiator={initiator}, confidence={confidence_val} (score={confidence_score})")

                if initiator == 'STA':
                    # Boost STA evidence significantly based on specialized agent analysis
                    boost = 30 * confidence_score  # Up to 30 points
                    sta_evidence_score += boost
                    print(f"[KB_MATCHER DEBUG] Added {boost} to STA score based on DisconnectAnalyzer")
                elif initiator == 'AP':
                    # Boost AP evidence
                    boost = 30 * confidence_score
                    ap_evidence_score += boost
                    print(f"[KB_MATCHER DEBUG] Added {boost} to AP score based on DisconnectAnalyzer")

            print(f"[KB_MATCHER DEBUG] Total hostapd events to analyze: {len(hostapd_events)}")

            # Check for smoking gun evidence in hostapd events
            for event in hostapd_events:
                details = event.get('details', {})

                # CRITICAL: Check for STA-initiated smoking gun
                if details.get('initiator') == 'STA':
                    sta_evidence_score += 20  # Very strong evidence
                    print("[KB_MATCHER DEBUG] SMOKING GUN FOUND! initiator='STA' in event details")
                    print(f"[KB_MATCHER DEBUG] Event details: {details}")
                    print(f"[KB_MATCHER DEBUG] STA evidence score now: {sta_evidence_score}")

                # Check for RX frame direction
                if details.get('frame_direction') == 'RX':
                    sta_evidence_score += 5
                    print("[KB_MATCHER DEBUG] RX frame detected (STA->AP direction)")

                # Check for specific status messages
                status = details.get('status', '')
                if 'sta_initiated' in status:
                    sta_evidence_score += 10
                    print(f"[KB_MATCHER DEBUG] STA-initiated status detected: {status}")
                elif 'not_authenticated' in status:
                    sta_evidence_score += 3
                    print(f"[KB_MATCHER DEBUG] Not authenticated status detected: {status}")

            # DEBUG: Final evidence scores
            print("\n[KB_MATCHER DEBUG] Evidence Analysis Complete:")
            print(f"[KB_MATCHER DEBUG] STA evidence score: {sta_evidence_score}")
            print(f"[KB_MATCHER DEBUG] AP evidence score: {ap_evidence_score}")

            # Search for specific subsection patterns with proper hierarchy
            disconnect_patterns = []

            # Prioritize based on evidence
            if sta_evidence_score > ap_evidence_score:
                # STA-initiated is more likely - prioritize those patterns
                disconnect_patterns = [
                    ("7\\.2\\..*Disconnection initiated by STA", "7.2. Disconnection initiated by STA"),
                    ("### 2\\. Disconnection initiated by STA", "7.2. Disconnection initiated by STA"),
                    ("2\\. Disconnection initiated by STA", "7.2. Disconnection initiated by STA"),
                    ("Disconnection initiated by STA", "7.2. Disconnection initiated by STA"),
                    ("7\\.1\\..*Disconnection initiated by AP", "7.1. Disconnection initiated by AP"),
                    ("### 1\\. Disconnection initiated by AP", "7.1. Disconnection initiated by AP"),
                ]
            else:
                # AP-initiated is more likely - prioritize those patterns
                disconnect_patterns = [
                    ("7\\.1\\..*Disconnection initiated by AP", "7.1. Disconnection initiated by AP"),
                    ("### 1\\. Disconnection initiated by AP", "7.1. Disconnection initiated by AP"),
                    ("1\\. Disconnection initiated by AP", "7.1. Disconnection initiated by AP"),
                    ("Disconnection initiated by AP", "7.1. Disconnection initiated by AP"),
                    ("7\\.2\\..*Disconnection initiated by STA", "7.2. Disconnection initiated by STA"),
                    ("### 2\\. Disconnection initiated by STA", "7.2. Disconnection initiated by STA"),
                ]

            # Add general patterns at the end
            disconnect_patterns.extend([
                ("kickout.*STA|STA.*kickout", "Kickout STA (AP-initiated)"),
                ("Inactive.*timeout|timeout.*inactive", "Inactive timeout (AP-initiated)"),
                ("## 7\\. Disconnection", "7. Disconnection (General)"),
            ])

            # Find all relevant disconnect patterns
            for pattern, description in disconnect_patterns:
                match = self._search_kb_for_pattern(pattern)
                if match:
                    match["description"] = description
                    # Add evidence-based confidence scoring
                    match = self._enhance_disconnect_match_with_evidence(match, hostapd_events, timeline)

                    # CRITICAL: Filter out conflicting matches based on strong evidence
                    # If we have strong STA evidence and this is an AP match, mark it as conflicting
                    if sta_evidence_score >= 20:  # Strong STA evidence (smoking gun)
                        if 'ap' in match.get('section', '').lower() and 'sta' not in match.get('section', '').lower():
                            match['evidence_conflict'] = True
                            match['confidence'] = 'LOW'
                            match['relevance_score'] = 0.1  # Very low score

                    # If we have strong AP evidence and this is a STA match, mark it as conflicting
                    elif ap_evidence_score >= 10:  # Strong AP evidence
                        if 'sta' in match.get('section', '').lower() and 'ap' not in match.get('section', '').lower():
                            match['evidence_conflict'] = True
                            match['confidence'] = 'LOW'
                            match['relevance_score'] = 0.1  # Very low score

                    matches.append(match)

        elif anomaly_type == "DATA_STALL":
            # Search for data stall-related KB entries
            patterns = [
                ("5\\..*Connection Stability", "5. Connection Stability"),
                ("Tx.*stuck|Rx.*stuck", "TX/RX stuck"),
                ("data.*drop|packet.*drop", "Data/packet drop")
            ]

            for pattern, description in patterns:
                match = self._search_kb_for_pattern(pattern)
                if match:
                    match["description"] = description
                    matches.append(match)
                    break

        elif anomaly_type == "BEACON_STUCK":
            # Search for beacon-related KB entries
            patterns = [
                ("1\\..*Scan", "1. Scan"),
                ("Beacon.*stuck|stuck.*beacon", "Beacon stuck"),
                ("No.*beacon|beacon.*miss", "Beacon miss")
            ]

            for pattern, description in patterns:
                match = self._search_kb_for_pattern(pattern)
                if match:
                    match["description"] = description
                    matches.append(match)
                    break

        elif anomaly_type == "FAIL_TO_CONNECT":
            # Search for connection failure KB entries
            patterns = [
                ("2\\..*Authentication", "2. Authentication"),
                ("3\\..*Association", "3. Association"),
                ("4\\..*4‑Way Handshaking", "4. 4-Way Handshaking"),
                ("Auth.*fail|fail.*auth", "Authentication failure"),
                ("Assoc.*fail|fail.*assoc", "Association failure")
            ]

            for pattern, description in patterns:
                match = self._search_kb_for_pattern(pattern)
                if match:
                    match["description"] = description
                    matches.append(match)
                    break

        return matches

    def _enhance_disconnect_match_with_evidence(self, match: dict[str, Any],
                                              hostapd_events: list[dict[str, Any]],
                                              timeline: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Enhance disconnect match with evidence-based analysis to determine
        if disconnection was AP-initiated or STA-initiated
        
        Args:
            match: Initial KB match
            hostapd_events: List of hostapd events for evidence
            timeline: Timeline events for context
            
        Returns:
            Enhanced match with evidence-based confidence scoring
        """
        section = match.get('section', '').lower()
        description = match.get('description', '').lower()

        # Initialize evidence counters
        ap_initiated_evidence = 0
        sta_initiated_evidence = 0
        evidence_details = []

        # Analyze hostapd events for evidence
        for event in hostapd_events:
            event_type = event.get('type', '')
            details = event.get('details', {})

            # CRITICAL: Check for the smoking gun evidence from parser
            if event_type in ['deauth', 'disassoc']:
                # Check if parser identified the initiator
                initiator = details.get('initiator')
                if initiator == 'STA':
                    sta_initiated_evidence += 10  # Very strong evidence
                    evidence_details.append("SMOKING GUN: Parser detected STA-initiated disconnect (RX deauth after disconnect)")
                    evidence_details.append(f"Evidence: {details.get('evidence', 'Station sent deauth frame')}")

                # Check for RX frame direction (additional evidence)
                frame_direction = details.get('frame_direction')
                if frame_direction == 'RX' and details.get('frame_type') in ['DEAUTH', 'DISASSOC']:
                    sta_initiated_evidence += 3
                    evidence_details.append(f"RX {details.get('frame_type')} frame from STA (stype={details.get('stype')})")

                reason_code = details.get('reason_code')

                # AP-initiated reason codes (common ones)
                ap_reason_codes = [
                    1,   # Unspecified reason
                    2,   # Previous authentication no longer valid
                    3,   # Deauthenticated because sending STA is leaving
                    4,   # Disassociated due to inactivity
                    5,   # Disassociated because AP is unable to handle all currently associated STAs
                    6,   # Class 2 frame received from nonauthenticated STA
                    7,   # Class 3 frame received from nonassociated STA
                    8,   # Disassociated because sending STA is leaving BSS
                    15,  # 4-Way Handshake timeout
                    16,  # Group Key Handshake timeout
                    17,  # IE in 4-Way Handshake different from (Re)Association Request/Probe Response/Beacon frame
                    23,  # IEEE 802.1X authentication failed
                ]

                # STA-initiated reason codes
                sta_reason_codes = [
                    3,   # Deauthenticated because sending STA is leaving (can be STA)
                    8,   # Disassociated because sending STA is leaving BSS (can be STA)
                    36,  # Requested from peer STA as it does not want to use the mechanism
                ]

                if reason_code in ap_reason_codes:
                    ap_initiated_evidence += 2
                    evidence_details.append(f"AP-initiated reason code {reason_code}")
                elif reason_code in sta_reason_codes:
                    sta_initiated_evidence += 2
                    evidence_details.append(f"STA-initiated reason code {reason_code}")

                # Special handling for ambiguous codes
                if reason_code in [3, 8]:  # Can be either AP or STA initiated
                    # Look for additional context in event details
                    if 'inactive' in str(details).lower() or 'timeout' in str(details).lower():
                        ap_initiated_evidence += 1
                        evidence_details.append(f"Reason code {reason_code} with inactivity/timeout context (AP-initiated)")
                    else:
                        sta_initiated_evidence += 1
                        evidence_details.append(f"Reason code {reason_code} without timeout context (STA-initiated)")

        # Analyze timeline for additional evidence
        for event in timeline:
            event_type = event.get('event_type', '')
            details = event.get('details', {})

            # Look for inactivity patterns (AP-initiated)
            if isinstance(details, dict):
                detail_str = str(details).lower()
                if any(term in detail_str for term in ['inactive', 'timeout', 'keepalive', 'kickout']):
                    ap_initiated_evidence += 1
                    evidence_details.append("Timeline shows inactivity/timeout patterns (AP-initiated)")

                # Look for client-initiated patterns
                if any(term in detail_str for term in ['client', 'sta disconnect', 'leaving']):
                    sta_initiated_evidence += 1
                    evidence_details.append("Timeline shows client-initiated disconnect patterns")

        # Determine final classification and confidence
        total_evidence = ap_initiated_evidence + sta_initiated_evidence

        if total_evidence == 0:
            # No clear evidence, keep original match
            match['evidence_analysis'] = "No clear evidence for AP vs STA initiation"
            match['evidence_confidence'] = "LOW"
        else:
            ap_probability = ap_initiated_evidence / total_evidence
            sta_probability = sta_initiated_evidence / total_evidence

            # Adjust match based on evidence
            if ap_probability > 0.6:
                # Strong evidence for AP-initiated
                if 'sta' in section and 'ap' not in section:
                    # This was a STA-initiated match but evidence suggests AP-initiated
                    match['confidence'] = "LOW"
                    match['evidence_conflict'] = True
                elif 'ap' in section:
                    # This was an AP-initiated match and evidence confirms it
                    match['confidence'] = "HIGH"
                    match['relevance_score'] = min(1.0, match.get('relevance_score', 0.7) + 0.2)

                match['evidence_analysis'] = f"Strong evidence for AP-initiated disconnect ({ap_probability:.1%} confidence)"
                match['evidence_confidence'] = "HIGH"

            elif sta_probability > 0.6:
                # Strong evidence for STA-initiated
                if 'ap' in section and 'sta' not in section:
                    # This was an AP-initiated match but evidence suggests STA-initiated
                    match['confidence'] = "LOW"
                    match['evidence_conflict'] = True
                elif 'sta' in section:
                    # This was a STA-initiated match and evidence confirms it
                    match['confidence'] = "HIGH"
                    match['relevance_score'] = min(1.0, match.get('relevance_score', 0.7) + 0.2)

                match['evidence_analysis'] = f"Strong evidence for STA-initiated disconnect ({sta_probability:.1%} confidence)"
                match['evidence_confidence'] = "HIGH"

            else:
                # Mixed evidence
                match['evidence_analysis'] = f"Mixed evidence: AP={ap_probability:.1%}, STA={sta_probability:.1%}"
                match['evidence_confidence'] = "MEDIUM"

        # Add evidence details to match
        match['evidence_details'] = evidence_details[:5]  # Limit to top 5 pieces of evidence
        match['ap_evidence_score'] = ap_initiated_evidence
        match['sta_evidence_score'] = sta_initiated_evidence

        return match

    def _search_kb_for_reason_code(self, reason_code: int) -> dict[str, Any] | None:
        """
        Search KB for specific reason code
        
        Args:
            reason_code: Deauth/disassoc reason code
        
        Returns:
            KB match or None
        """
        if not self.kb_content:
            return None

        # Search for reason code in KB
        pattern = f"reason.*{reason_code}|code.*{reason_code}"
        match = re.search(pattern, self.kb_content, re.IGNORECASE)

        if match:
            # Extract context around the match
            context = self._extract_context(self.kb_content, match.start(), 500)
            section = self._identify_section(self.kb_content, match.start())

            return {
                "type": "reason_code",
                "reason_code": reason_code,
                "section": section,
                "context": context,
                "confidence": "HIGH",
                "relevance_score": 0.9
            }

        return None

    def _search_kb_for_pattern(self, pattern: str) -> dict[str, Any] | None:
        """
        Search KB for a pattern
        
        Args:
            pattern: Regex pattern to search for
        
        Returns:
            KB match or None
        """
        if not self.kb_content:
            return None

        match = re.search(pattern, self.kb_content, re.IGNORECASE)

        if match:
            context = self._extract_context(self.kb_content, match.start(), 500)
            section = self._identify_section(self.kb_content, match.start())

            return {
                "type": "pattern_match",
                "pattern": pattern,
                "section": section,
                "context": context,
                "confidence": "MEDIUM",
                "relevance_score": 0.7
            }

        return None

    def _extract_context(self, text: str, position: int, context_size: int = 500) -> str:
        """Extract context around a match position"""
        start = max(0, position - context_size // 2)
        end = min(len(text), position + context_size // 2)
        return text[start:end]

    def _identify_section(self, text: str, position: int) -> str:
        """Identify which KB section a match belongs to"""
        # Find the nearest section header before the position
        text_before = text[:position]

        # Look for section headers (## or numbered sections)
        section_patterns = [
            r'##\s+(\d+\..*?)(?=\n)',
            r'^(\d+\.\s+[A-Z][^\n]+)$',
            r'^([A-Z][^\n]+)$'
        ]

        for pattern in section_patterns:
            matches = list(re.finditer(pattern, text_before, re.MULTILINE))
            if matches:
                return matches[-1].group(1).strip()

        return "Unknown Section"

    def _llm_kb_analysis(self,
                        anomaly_type: str | None,
                        hostapd_events: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
        """
        Use LLM to perform deeper KB analysis
        
        Args:
            anomaly_type: Type of anomaly
            hostapd_events: List of hostapd events
        
        Returns:
            List of KB matches from LLM analysis
        """
        if not self.kb_content:
            return []

        # Create a summary of the situation
        situation_summary = self._create_situation_summary(anomaly_type, hostapd_events)

        # Get timeline for more context
        timeline = self.get_cached_data("timeline") or []
        if timeline:
            situation_summary += "\n\nKey Timeline Events:\n"
            for event in timeline[:5]:
                situation_summary += f"- {event.get('timestamp', '')}: {event.get('event_type', '')} - {event.get('details', '')}\n"

        # Use more targeted KB sections based on anomaly type
        kb_sample = self._get_relevant_kb_sections(anomaly_type)

        prompt = f"""Given the following WiFi connectivity issue:

{situation_summary}

And this knowledge base excerpt:

{kb_sample}

Identify the most relevant KB sections that match this issue. Focus on:
1. Event sequences that match the timeline
2. Specific error patterns or symptoms
3. Root cause patterns described in the KB

For each match, provide:
1. Section name/title (be specific)
2. Why it's relevant (cite specific evidence)
3. Confidence level (HIGH/MEDIUM/LOW)
4. Key context from that section

Format your response as:
SECTION: [specific section name]
RELEVANCE: [detailed explanation with evidence]
CONTEXT: [key information from this KB section]
CONFIDENCE: [HIGH/MEDIUM/LOW]
---"""

        response = self.call_llm(prompt, call_type="wifi")

        if response:
            return self._parse_llm_kb_response(response)

        return []

    def _get_relevant_kb_sections(self, anomaly_type: str | None) -> str:
        """Get relevant KB sections based on anomaly type"""
        if not self.kb_content:
            return ""

        # Define section priorities based on anomaly type
        section_priorities = {
            "DISCONNECT": ["7. Disconnection", "6. Roaming", "5. Connection Stability"],
            "FAIL_TO_CONNECT": ["2. Authentication", "3. Association", "4. 4‑Way Handshaking"],
            "DATA_STALL": ["5. Connection Stability", "7. Disconnection"],
            "BEACON_STUCK": ["1. Scan", "5. Connection Stability"]
        }

        relevant_sections = section_priorities.get(anomaly_type, [])

        # Extract relevant sections from KB using improved patterns
        kb_parts = []
        for section in relevant_sections:
            # Try multiple patterns to find the section
            patterns = [
                f"##\\s*{re.escape(section)}.*?(?=##|$)",  # ## Section
                f"^{re.escape(section)}.*?(?=^\\d+\\.|$)",  # Numbered section
                f".*{re.escape(section.split('.')[1].strip() if '.' in section else section)}.*?(?=##|^\\d+\\.|$)"  # Partial match
            ]

            for pattern in patterns:
                match = re.search(pattern, self.kb_content, re.DOTALL | re.IGNORECASE | re.MULTILINE)
                if match:
                    section_text = match.group(0)[:3000]  # Increased limit
                    kb_parts.append(f"=== {section} ===\n{section_text}")
                    break

        # If no specific sections found, try to find sections by keywords
        if not kb_parts and anomaly_type:
            keyword_patterns = {
                "DISCONNECT": ["disconnection", "kickout", "deauth", "disassoc"],
                "FAIL_TO_CONNECT": ["authentication", "association", "handshake"],
                "DATA_STALL": ["connection stability", "tx stuck", "rx stuck"],
                "BEACON_STUCK": ["beacon", "scan"]
            }

            keywords = keyword_patterns.get(anomaly_type, [])
            for keyword in keywords:
                # Find sections containing the keyword
                lines = self.kb_content.split('\n')
                for i, line in enumerate(lines):
                    if keyword.lower() in line.lower() and ('##' in line or line.strip().startswith(tuple('123456789'))):
                        # Extract section starting from this line
                        section_lines = []
                        for j in range(i, min(i + 100, len(lines))):  # Next 100 lines or until next section
                            if j > i and ('##' in lines[j] or (lines[j].strip() and lines[j].strip()[0].isdigit() and '.' in lines[j])):
                                break
                            section_lines.append(lines[j])

                        if section_lines:
                            kb_parts.append('\n'.join(section_lines))
                            break

        # If still no sections found, use first 8000 chars
        if not kb_parts:
            return self.kb_content[:8000]

        return "\n\n".join(kb_parts)

    def _create_situation_summary(self,
                                  anomaly_type: str | None,
                                  hostapd_events: list[dict[str, Any]] | None) -> str:
        """Create a summary of the current situation for LLM"""
        summary_parts = []

        if anomaly_type:
            summary_parts.append(f"Anomaly Type: {anomaly_type}")

        mac_address = self.get_metadata("mac_address")
        if mac_address:
            summary_parts.append(f"MAC Address: {mac_address}")

        if hostapd_events:
            event_types = [e.get('type') for e in hostapd_events[:10]]
            summary_parts.append(f"Recent Events: {', '.join(event_types)}")

        return "\n".join(summary_parts)

    def _parse_llm_kb_response(self, response: str) -> list[dict[str, Any]]:
        """Parse LLM response to extract KB matches"""
        matches = []

        # Split by separator
        sections = response.split('---')

        for section in sections:
            if not section.strip():
                continue

            # Extract fields
            section_match = re.search(r'SECTION:\s*(.+?)(?=\n|$)', section, re.IGNORECASE)
            relevance_match = re.search(r'RELEVANCE:\s*(.+?)(?=\n|$)', section, re.IGNORECASE | re.DOTALL)
            confidence_match = re.search(r'CONFIDENCE:\s*(HIGH|MEDIUM|LOW)', section, re.IGNORECASE)

            if section_match:
                match = {
                    "type": "llm_analysis",
                    "section": section_match.group(1).strip(),
                    "relevance": relevance_match.group(1).strip() if relevance_match else "",
                    "confidence": confidence_match.group(1).upper() if confidence_match else "MEDIUM",
                    "relevance_score": 0.8
                }
                matches.append(match)

        return matches

    def _deduplicate_and_rank(self, matches: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Remove duplicates and rank matches by relevance"""
        # Remove duplicates based on section
        seen_sections = set()
        unique_matches = []

        for match in matches:
            section = match.get('section', '')
            if section and section not in seen_sections:
                seen_sections.add(section)
                unique_matches.append(match)

        # Sort by relevance score (descending)
        unique_matches.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)

        return unique_matches
