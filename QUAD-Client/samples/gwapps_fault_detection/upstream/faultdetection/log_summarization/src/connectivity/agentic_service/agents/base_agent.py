# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# All rights reserved.
# Confidential and Proprietary - Qualcomm Technologies, Inc.

"""
Base Agent Class
All specialized agents inherit from this base class
"""

import os
import sys
from abc import ABC, abstractmethod
from typing import Any

# Add parent directory to path to import model_calls
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from model_calls import generate_llm_response

from ..shared_context import Finding, SharedContext


class BaseAgent(ABC):
    """
    Abstract base class for all agents in the system.
    Provides common functionality and enforces interface.
    """

    def __init__(self, name: str, context: SharedContext, model: str = "qgenie"):
        """
        Initialize the agent
        
        Args:
            name: Agent name (e.g., "HostapdParser", "TimelineBuilder")
            context: Shared context for communication
            model: LLM model to use (bedrock, qgenie, internal)
        """
        self.name = name
        self.context = context
        self.model = model
        self.max_retries = 3
        self.retry_count = 0

    @abstractmethod
    def analyze(self) -> bool:
        """
        Main analysis method - must be implemented by subclasses
        
        Returns:
            bool: True if analysis succeeded, False otherwise
        """
        pass

    def call_llm(self, prompt: str, call_type: str = "wifi") -> str | None:
        """
        Call LLM using the preserved generate_llm_response method
        
        Args:
            prompt: The prompt to send to the LLM
            call_type: Type of call (wifi, hostapd, or default)
        
        Returns:
            LLM response or None if failed
        """
        try:
            self._log_debug(f"call_llm: model={self.model}, call_type={call_type}, prompt_length={len(prompt)}")
            response = generate_llm_response(self.model, prompt, call_type, agent_name=self.name)
            self._log_debug(f"call_llm: response type={type(response)}, response_length={len(response) if response else 0}")

            # Check if response is an error message
            if response and response.startswith("Error:"):
                self._log_error(f"LLM returned error: {response}")
                return None

            return response
        except Exception as e:
            self._log_error(f"LLM call failed with exception: {str(e)}")
            import traceback
            self._log_debug(f"Exception traceback:\n{traceback.format_exc()}")
            return None

    def add_finding(self,
                   finding_type: str,
                   content: Any,
                   confidence: str | None = None,
                   references: list = None,
                   metadata: dict = None) -> None:
        """
        Add a finding to the shared context
        
        Args:
            finding_type: Type of finding (e.g., "timeline_event", "kb_match")
            content: The actual finding content
            confidence: Confidence level (HIGH, MEDIUM, LOW)
            references: List of file references
            metadata: Additional metadata
        """
        finding = Finding(
            agent_name=self.name,
            finding_type=finding_type,
            content=content,
            confidence=confidence,
            references=references or [],
            metadata=metadata or {}
        )
        self.context.add_finding(finding)

    def get_findings(self, finding_type: str | None = None) -> list:
        """
        Get findings from shared context, optionally filtered by type
        
        Args:
            finding_type: Optional filter by finding type
        
        Returns:
            List of findings
        """
        return self.context.get_findings(finding_type=finding_type)

    def get_input_data(self, key: str) -> Any | None:
        """Get input data from shared context"""
        return self.context.get_input_data(key)

    def get_metadata(self, key: str) -> Any | None:
        """Get metadata from shared context"""
        return self.context.get_metadata(key)

    def cache_data(self, key: str, data: Any) -> None:
        """Cache data in shared context"""
        self.context.cache_data(key, data)

    def get_cached_data(self, key: str) -> Any | None:
        """Get cached data from shared context"""
        return self.context.get_cached_data(key)

    def has_cached_data(self, key: str) -> bool:
        """Check if data is cached"""
        return self.context.has_cached_data(key)

    def set_status(self, status: str) -> None:
        """Update agent status in shared context"""
        self.context.set_agent_status(self.name, status)

    def run(self) -> bool:
        """
        Execute the agent with retry logic
        
        Returns:
            bool: True if successful, False otherwise
        """
        self.set_status("running")
        self.retry_count = 0

        while self.retry_count < self.max_retries:
            try:
                success = self.analyze()

                if success:
                    self.set_status("completed")
                    self._log_info(f"Agent {self.name} completed successfully")
                    return True
                else:
                    self.retry_count += 1
                    if self.retry_count < self.max_retries:
                        self._log_warning(f"Agent {self.name} failed, retrying ({self.retry_count}/{self.max_retries})")
                    else:
                        self.set_status("failed")
                        self._log_error(f"Agent {self.name} failed after {self.max_retries} attempts")
                        return False

            except Exception as e:
                self.retry_count += 1
                self._log_error(f"Agent {self.name} error: {str(e)}")

                if self.retry_count >= self.max_retries:
                    self.set_status("failed")
                    return False

        return False

    def _log_info(self, message: str) -> None:
        """Log info message"""
        print(f"[INFO] [{self.name}] {message}")

    def _log_warning(self, message: str) -> None:
        """Log warning message"""
        print(f"[WARNING] [{self.name}] {message}")

    def _log_error(self, message: str) -> None:
        """Log error message"""
        print(f"[ERROR] [{self.name}] {message}")

    def _log_debug(self, message: str) -> None:
        """Log debug message"""
        print(f"[DEBUG] [{self.name}] {message}")
