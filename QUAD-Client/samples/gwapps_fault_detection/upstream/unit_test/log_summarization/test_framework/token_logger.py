# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# All rights reserved.
# Confidential and Proprietary - Qualcomm Technologies, Inc.

"""
Token Logger for Agentic Service
Tracks LLM token usage across all agents and samples
"""

import json
import threading
from datetime import datetime
from typing import Any


class TokenLogger:
    """
    Singleton class to track token usage across all LLM calls
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.current_sample = None
        self.sample_data = {}  # sample_name -> token data
        self.call_counter = 0
        self.start_time = datetime.now()
        self._initialized = True

    def set_current_sample(self, sample_name: str):
        """Set the current sample being processed"""
        self.current_sample = sample_name
        if sample_name not in self.sample_data:
            self.sample_data[sample_name] = {
                'calls': [],
                'total_input_tokens': 0,
                'total_output_tokens': 0,
                'start_time': datetime.now().isoformat(),
                'end_time': None
            }

    def log_llm_call(self,
                     agent_name: str,
                     call_type: str,
                     model: str,
                     input_tokens: int,
                     output_tokens: int,
                     prompt_preview: str = "",
                     response_preview: str = "",
                     success: bool = True,
                     error_message: str = None):
        """Log a single LLM call"""
        if not self.current_sample:
            print(f"[WARNING] TokenLogger: No current sample set for call from {agent_name}")
            return

        self.call_counter += 1

        call_data = {
            'call_id': self.call_counter,
            'agent_name': agent_name,
            'call_type': call_type,
            'model': model,
            'input_tokens': input_tokens,
            'output_tokens': output_tokens,
            'timestamp': datetime.now().isoformat(),
            'prompt_preview': prompt_preview[:200] + "..." if len(prompt_preview) > 200 else prompt_preview,
            'response_preview': response_preview[:200] + "..." if len(response_preview) > 200 else response_preview,
            'success': success,
            'error_message': error_message
        }

        # Add to current sample
        sample_data = self.sample_data[self.current_sample]
        sample_data['calls'].append(call_data)
        sample_data['total_input_tokens'] += input_tokens
        sample_data['total_output_tokens'] += output_tokens

        print(f"[TOKEN_LOG] {agent_name} | {call_type} | Input: {input_tokens} | Output: {output_tokens} | Total Sample: {sample_data['total_input_tokens']}+{sample_data['total_output_tokens']}")

    def finish_sample(self, sample_name: str):
        """Mark a sample as finished"""
        if sample_name in self.sample_data:
            self.sample_data[sample_name]['end_time'] = datetime.now().isoformat()

    def get_sample_summary(self, sample_name: str) -> dict[str, Any]:
        """Get token summary for a specific sample"""
        if sample_name not in self.sample_data:
            return {}

        data = self.sample_data[sample_name]
        return {
            'sample_name': sample_name,
            'total_calls': len(data['calls']),
            'total_input_tokens': data['total_input_tokens'],
            'total_output_tokens': data['total_output_tokens'],
            'total_tokens': data['total_input_tokens'] + data['total_output_tokens'],
            'start_time': data['start_time'],
            'end_time': data['end_time'],
            'calls': data['calls']
        }

    def get_all_samples_summary(self) -> dict[str, Any]:
        """Get token summary for all samples"""
        summaries = {}
        total_input = 0
        total_output = 0
        total_calls = 0

        for sample_name in self.sample_data:
            summary = self.get_sample_summary(sample_name)
            summaries[sample_name] = summary
            total_input += summary['total_input_tokens']
            total_output += summary['total_output_tokens']
            total_calls += summary['total_calls']

        return {
            'samples': summaries,
            'overall_summary': {
                'total_samples': len(self.sample_data),
                'total_calls': total_calls,
                'total_input_tokens': total_input,
                'total_output_tokens': total_output,
                'total_tokens': total_input + total_output,
                'session_start_time': self.start_time.isoformat(),
                'session_end_time': datetime.now().isoformat()
            }
        }

    def generate_report(self, output_file: str = "token_usage_report.json"):
        """Generate a comprehensive token usage report"""
        report_data = self.get_all_samples_summary()

        # Write JSON report
        with open(output_file, 'w') as f:
            json.dump(report_data, f, indent=2)

        # Generate human-readable report
        txt_file = output_file.replace('.json', '.txt')
        with open(txt_file, 'w') as f:
            f.write("AGENTIC SERVICE TOKEN USAGE REPORT\n")
            f.write("=" * 50 + "\n\n")

            overall = report_data['overall_summary']
            f.write("Overall Summary:\n")
            f.write(f"  Total Samples: {overall['total_samples']}\n")
            f.write(f"  Total LLM Calls: {overall['total_calls']}\n")
            f.write(f"  Total Input Tokens: {overall['total_input_tokens']:,}\n")
            f.write(f"  Total Output Tokens: {overall['total_output_tokens']:,}\n")
            f.write(f"  Total Tokens: {overall['total_tokens']:,}\n")
            f.write(f"  Session Duration: {overall['session_start_time']} to {overall['session_end_time']}\n\n")

            # Per-sample breakdown
            for sample_name, sample_data in report_data['samples'].items():
                f.write(f"Sample: {sample_name}\n")
                f.write("-" * 30 + "\n")
                f.write(f"  Total Calls: {sample_data['total_calls']}\n")
                f.write(f"  Input Tokens: {sample_data['total_input_tokens']:,}\n")
                f.write(f"  Output Tokens: {sample_data['total_output_tokens']:,}\n")
                f.write(f"  Total Tokens: {sample_data['total_tokens']:,}\n")
                f.write(f"  Duration: {sample_data['start_time']} to {sample_data.get('end_time', 'In Progress')}\n")

                f.write("\n  Individual Calls:\n")
                for call in sample_data['calls']:
                    f.write(f"    {call['call_id']:2d}. {call['agent_name']:15s} | {call['call_type']:10s} | "
                           f"In: {call['input_tokens']:4d} | Out: {call['output_tokens']:4d} | "
                           f"{'✓' if call['success'] else '✗'}\n")
                    if not call['success'] and call['error_message']:
                        f.write(f"        Error: {call['error_message']}\n")
                f.write("\n")

        print(f"[TOKEN_LOG] Report generated: {output_file} and {txt_file}")
        return output_file, txt_file


def estimate_tokens(text: str) -> int:
    """
    Rough estimation of token count for text
    Uses approximation of ~4 characters per token for English text
    """
    if not text:
        return 0
    return max(1, len(text) // 4)


def extract_token_counts_from_response(response_data: Any) -> tuple:
    """
    Extract token counts from different LLM response formats
    Returns (input_tokens, output_tokens)
    """
    input_tokens = 0
    output_tokens = 0

    try:
        # Handle different response formats
        if isinstance(response_data, dict):
            # Bedrock format
            if 'usage' in response_data:
                usage = response_data['usage']
                input_tokens = usage.get('inputTokens', 0)
                output_tokens = usage.get('outputTokens', 0)
            # QGenie format
            elif 'token_usage' in response_data:
                usage = response_data['token_usage']
                input_tokens = usage.get('prompt_tokens', 0)
                output_tokens = usage.get('completion_tokens', 0)

        # If we couldn't extract from response, we'll estimate later
        return input_tokens, output_tokens

    except Exception as e:
        print(f"[TOKEN_LOG] Error extracting token counts: {e}")
        return 0, 0
