# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# All rights reserved.
# Confidential and Proprietary - Qualcomm Technologies, Inc.

"""
Main entry point for Agentic LLM Service
Example usage and testing
"""

import os
import sys

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from agentic_service import Orchestrator


def run_analysis_from_files(
    fd_logs_path: str,
    hostapd_log_path: str = None,
    wifistats_path: str = None,
    knowledge_base_path: str = None,
    model: str = "qgenie"
) -> str:
    """
    Run analysis from file paths
    
    Args:
        fd_logs_path: Path to fault detection logs
        hostapd_log_path: Optional path to hostapd log
        wifistats_path: Optional path to wifistats
        knowledge_base_path: Optional path to knowledge base
        model: LLM model to use (bedrock, qgenie, internal)
    
    Returns:
        Final triage report
    """
    # Read files
    with open(fd_logs_path) as f:
        fd_logs = f.read()

    hostapd_log = None
    if hostapd_log_path and os.path.exists(hostapd_log_path):
        with open(hostapd_log_path) as f:
            hostapd_log = f.read()

    wifistats = None
    if wifistats_path and os.path.exists(wifistats_path):
        with open(wifistats_path) as f:
            wifistats = f.read()

    knowledge_base = None
    if knowledge_base_path and os.path.exists(knowledge_base_path):
        with open(knowledge_base_path) as f:
            knowledge_base = f.read()

    # Create orchestrator and run analysis
    orchestrator = Orchestrator(model=model)
    report = orchestrator.analyze(
        fd_logs=fd_logs,
        hostapd_log=hostapd_log,
        wifistats=wifistats,
        knowledge_base=knowledge_base
    )

    return report


def main():
    """Main function for testing"""
    # Example usage with sample files
    current_dir = os.path.dirname(os.path.dirname(__file__))

    fd_logs_path = os.path.join(current_dir, "0_fd_logs.txt")
    hostapd_log_path = os.path.join(current_dir, "syslog.txt")
    wifistats_path = os.path.join(current_dir, "rate_of_change_wifistats.txt")
    knowledge_base_path = os.path.join(current_dir, "knowledge_base.txt")

    print("=" * 80)
    print("Agentic LLM Service for WiFi Connectivity Triage")
    print("=" * 80)
    print()

    # Check if files exist
    if not os.path.exists(fd_logs_path):
        print(f"Error: {fd_logs_path} not found")
        return

    print("Input files:")
    print(f"  - FD Logs: {fd_logs_path}")
    print(f"  - Hostapd Log: {hostapd_log_path if os.path.exists(hostapd_log_path) else 'Not provided'}")
    print(f"  - Wifistats: {wifistats_path if os.path.exists(wifistats_path) else 'Not provided'}")
    print(f"  - Knowledge Base: {knowledge_base_path if os.path.exists(knowledge_base_path) else 'Not provided'}")
    print()

    # Run analysis
    try:
        report = run_analysis_from_files(
            fd_logs_path=fd_logs_path,
            hostapd_log_path=hostapd_log_path if os.path.exists(hostapd_log_path) else None,
            wifistats_path=wifistats_path if os.path.exists(wifistats_path) else None,
            knowledge_base_path=knowledge_base_path if os.path.exists(knowledge_base_path) else None,
            model="qgenie"
        )

        print()
        print("=" * 80)
        print("ANALYSIS COMPLETE")
        print("=" * 80)
        print()
        print(report)

        # Save report to file
        output_path = os.path.join(current_dir, "triage_report.txt")
        with open(output_path, 'w') as f:
            f.write(report)
        print()
        print(f"Report saved to: {output_path}")

    except Exception as e:
        print(f"Error during analysis: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
