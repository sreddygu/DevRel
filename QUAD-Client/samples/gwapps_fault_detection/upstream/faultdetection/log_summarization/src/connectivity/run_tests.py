# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# All rights reserved.
# Confidential and Proprietary - Qualcomm Technologies, Inc.

#!/usr/bin/env python3
"""
Test Runner for Agentic Workflow
Runs the Agentic Workflow on every sample in test_framework/data,
saves a triage_report.txt for each sample, and produces summary reports.

Usage:
    python run_tests.py
    python run_tests.py --data-dir test_framework/data
"""

import argparse
import os
import sys
import time
from datetime import datetime

# Ensure the src directory is on the path
_src_dir = os.path.dirname(os.path.abspath(__file__))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

# ---------------------------------------------------------------------------
# Token tracking: monkey-patch generate_llm_response so that every LLM call
# is recorded in TokenLogger regardless of which agent makes the call.
# ---------------------------------------------------------------------------
import model_calls as _model_calls
from test_framework.token_logger import TokenLogger, estimate_tokens

_original_generate_llm_response = _model_calls.generate_llm_response


def _tracked_generate_llm_response(MODEL, custom_prompt, call_type, agent_name=None):
    """Wrapper that records token usage before returning the response."""
    response = _original_generate_llm_response(MODEL, custom_prompt, call_type, agent_name)

    token_logger = TokenLogger()
    if token_logger.current_sample:
        input_tokens = estimate_tokens(custom_prompt)
        output_tokens = estimate_tokens(response) if response else 0
        success = not (isinstance(response, str) and response.startswith("Error:"))
        token_logger.log_llm_call(
            agent_name=agent_name or "unknown",
            call_type=call_type,
            model=MODEL,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            prompt_preview=custom_prompt,
            response_preview=response or "",
            success=success,
        )

    return response


# Patch model_calls module and the already-imported reference in base_agent
_model_calls.generate_llm_response = _tracked_generate_llm_response

try:
    import agentic_service.agents.base_agent as _base_agent_module
    _base_agent_module.generate_llm_response = _tracked_generate_llm_response
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Now import the agentic service entry point and evaluation framework
# ---------------------------------------------------------------------------
from agentic_service.main import run_analysis_from_files
from test_framework.test_framework import AgenticWorkflowEvaluator

# ---------------------------------------------------------------------------
# Core runner
# ---------------------------------------------------------------------------

def run_tests(data_dir: str = "test_framework/data") -> None:
    """
    Run the Agentic Workflow on every sample folder inside *data_dir*.

    For each sample:
      - Locates *_fd_logs.txt, syslog.txt, rate_of_change_wifistats.txt
      - Calls run_analysis_from_files()
      - Writes triage_report.txt into the sample folder

    After all samples:
      - Writes agentic_service_token_usage_report.json / .txt
      - Writes test_run_times.json / .txt
    """
    token_logger = TokenLogger()
    run_times: dict = {}

    print("=" * 80)
    print("AGENTIC WORKFLOW TEST RUNNER")
    print("=" * 80)
    print(f"Data directory : {data_dir}")
    print(f"Start time     : {datetime.now().isoformat()}")
    print()

    if not os.path.exists(data_dir):
        print(f"Error: data directory '{data_dir}' not found.")
        sys.exit(1)

    test_cases = sorted(
        d for d in os.listdir(data_dir)
        if os.path.isdir(os.path.join(data_dir, d))
    )

    if not test_cases:
        print(f"No test-case folders found in '{data_dir}'.")
        sys.exit(1)

    print(f"Found {len(test_cases)} test case(s):")
    for tc in test_cases:
        print(f"  - {tc}")
    print()

    kb_path = "knowledge_base.txt"

    for test_case in test_cases:
        test_path = os.path.join(data_dir, test_case)

        print(f"\n{'='*80}")
        print(f"Processing: {test_case}")
        print(f"{'='*80}")

        # Locate input files
        fd_logs = None
        syslog = None
        wifistats = None

        for filename in os.listdir(test_path):
            if filename.endswith("_fd_logs.txt"):
                fd_logs = os.path.join(test_path, filename)
            elif filename == "syslog.txt":
                syslog = os.path.join(test_path, filename)
            elif filename == "rate_of_change_wifistats.txt":
                wifistats = os.path.join(test_path, filename)

        if not fd_logs:
            print("  Skipping: no *_fd_logs.txt found.")
            run_times[test_case] = {"status": "skipped", "reason": "No fd_logs file", "elapsed_seconds": 0}
            continue

        print(f"  FD Logs   : {fd_logs}")
        print(f"  Syslog    : {syslog or 'not found'}")
        print(f"  Wifistats : {wifistats or 'not found'}")
        print(f"  KB        : {kb_path if os.path.exists(kb_path) else 'not found'}")

        # Register sample with token logger
        token_logger.set_current_sample(test_case)

        start_dt = datetime.now()
        start_time = time.time()
        try:
            report = run_analysis_from_files(
                fd_logs_path=fd_logs,
                hostapd_log_path=syslog,
                wifistats_path=wifistats,
                knowledge_base_path=kb_path if os.path.exists(kb_path) else None,
            )
            elapsed = time.time() - start_time
            end_dt = datetime.now()

            # Save triage report
            report_path = os.path.join(test_path, "triage_report.txt")
            with open(report_path, "w") as fh:
                fh.write(report)

            print(f"  Report saved : {report_path}")
            print(f"  Elapsed      : {elapsed:.2f}s")

            run_times[test_case] = {
                "status": "success",
                "elapsed_seconds": round(elapsed, 3),
                "start_time": start_dt.strftime("%Y-%m-%d %H:%M:%S"),
                "end_time": end_dt.strftime("%Y-%m-%d %H:%M:%S"),
                "report_length_chars": len(report),
            }

        except Exception as exc:
            elapsed = time.time() - start_time
            end_dt = datetime.now()
            print(f"  ERROR: {exc}")
            import traceback
            traceback.print_exc()
            run_times[test_case] = {
                "status": "error",
                "elapsed_seconds": round(elapsed, 3),
                "start_time": start_dt.strftime("%Y-%m-%d %H:%M:%S"),
                "end_time": end_dt.strftime("%Y-%m-%d %H:%M:%S"),
                "error": str(exc),
            }

        finally:
            token_logger.finish_sample(test_case)

    # -----------------------------------------------------------------------
    # Generate summary reports
    # -----------------------------------------------------------------------
    print(f"\n{'='*80}")
    print("Generating summary reports ...")
    print(f"{'='*80}")

    _write_token_usage_report(token_logger)
    _write_run_times_report(run_times)
    _print_final_summary(run_times)

    # -----------------------------------------------------------------------
    # Evaluation phase: compare each saved triage_report.txt against
    # ground_truth.txt using vector similarity + LLM scoring.
    # -----------------------------------------------------------------------
    _run_evaluation_phase(data_dir, run_times)


# ---------------------------------------------------------------------------
# Report helpers
# ---------------------------------------------------------------------------

def _run_evaluation_phase(data_dir: str, run_times: dict) -> None:
    """
    For every test case that has both a triage_report.txt and a
    ground_truth.txt, evaluate the generated report using
    AgenticWorkflowEvaluator (vector similarity + LLM scoring) and write
    a consolidated test_framework/test_evaluation_report.txt.
    """
    print(f"\n{'='*80}")
    print("EVALUATION PHASE  (triage_report.txt vs ground_truth.txt)")
    print(f"{'='*80}\n")

    evaluator = AgenticWorkflowEvaluator()
    evaluations: list = []

    test_cases = sorted(
        d for d in os.listdir(data_dir)
        if os.path.isdir(os.path.join(data_dir, d))
    )

    for test_case in test_cases:
        test_path = os.path.join(data_dir, test_case)
        report_path = os.path.join(test_path, "triage_report.txt")
        gt_path = os.path.join(test_path, "ground_truth.txt")

        if not os.path.exists(report_path):
            print(f"  Skipping {test_case}: no triage_report.txt found")
            continue
        if not os.path.exists(gt_path):
            print(f"  Skipping {test_case}: no ground_truth.txt found")
            continue

        print(f"  Evaluating: {test_case}")
        with open(report_path) as fh:
            generated_report = fh.read()
        with open(gt_path) as fh:
            ground_truth = fh.read()

        try:
            evaluation = evaluator.evaluate_report(generated_report, ground_truth, test_case)
            evaluations.append(evaluation)
        except Exception as exc:
            print(f"  ERROR evaluating {test_case}: {exc}")
            import traceback
            traceback.print_exc()

    if evaluations:
        _write_evaluation_report(evaluations)
    else:
        print("  No evaluations produced — skipping report.")


def _write_evaluation_report(evaluations: list) -> None:
    """Write test_framework/test_evaluation_report.txt."""
    report_path = os.path.join("test_framework", "test_evaluation_report.txt")

    with open(report_path, "w") as fh:
        fh.write("=" * 80 + "\n")
        fh.write("TRIAGE REPORT EVALUATION RESULTS\n")
        fh.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        fh.write("=" * 80 + "\n\n")

        # Summary table
        fh.write("SUMMARY\n")
        fh.write("-" * 80 + "\n")
        fh.write(f"{'Test Case':<52} {'Overall Score':>13}\n")
        fh.write("-" * 80 + "\n")
        for ev in evaluations:
            fh.write(f"{ev.test_case:<52} {ev.overall_score:>10.2f}/10\n")
        if evaluations:
            avg = sum(e.overall_score for e in evaluations) / len(evaluations)
            fh.write("-" * 80 + "\n")
            fh.write(f"{'AVERAGE':<52} {avg:>10.2f}/10\n")
        fh.write("\n")

        # Per-sample detail
        for ev in evaluations:
            fh.write("=" * 80 + "\n")
            fh.write(f"TEST CASE: {ev.test_case}\n")
            fh.write(f"Overall Score: {ev.overall_score:.2f}/10\n")
            fh.write("=" * 80 + "\n\n")

            fh.write("Section Scores:\n")
            fh.write("-" * 80 + "\n")
            for sc in ev.section_scores:
                fh.write(f"\n  Section: {sc.section_name}\n")
                # Convert 0-1 similarity to 0-10 scale for consistency
                sim_10 = sc.semantic_similarity * 10
                fh.write(f"    Vector Similarity Score : {sim_10:.2f}/10\n")
                fh.write(f"    LLM Accuracy Score      : {sc.llm_accuracy_score:.1f}/10\n")
                fh.write(f"    LLM Completeness Score  : {sc.llm_completeness_score:.1f}/10\n")
                if sc.specific_metrics:
                    fh.write(f"    Specific Metrics        : {sc.specific_metrics}\n")
                fh.write("    LLM Feedback:\n")
                # Indent feedback lines
                for line in sc.feedback.splitlines():
                    fh.write(f"      {line}\n")

            fh.write("\n")
            if ev.strengths:
                fh.write("  Strengths:\n")
                for s in ev.strengths:
                    fh.write(f"    + {s}\n")
            if ev.weaknesses:
                fh.write("  Weaknesses:\n")
                for w in ev.weaknesses:
                    fh.write(f"    - {w}\n")
            if ev.recommendations:
                fh.write("  Recommendations:\n")
                for i, r in enumerate(ev.recommendations, 1):
                    fh.write(f"    {i}. {r}\n")
            fh.write("\n")

    print(f"\n  Evaluation report : {report_path}")


def _write_token_usage_report(token_logger: TokenLogger) -> None:
    """Write test_framework/agentic_service_token_usage_report.txt (TXT only)."""
    report_data = token_logger.get_all_samples_summary()
    txt_path = os.path.join("test_framework", "agentic_service_token_usage_report.txt")

    with open(txt_path, "w") as fh:
        fh.write("AGENTIC SERVICE TOKEN USAGE REPORT\n")
        fh.write("=" * 50 + "\n\n")

        overall = report_data["overall_summary"]
        fh.write("Overall Summary:\n")
        fh.write(f"  Total Samples      : {overall['total_samples']}\n")
        fh.write(f"  Total LLM Calls    : {overall['total_calls']}\n")
        fh.write(f"  Total Input Tokens : {overall['total_input_tokens']:,}\n")
        fh.write(f"  Total Output Tokens: {overall['total_output_tokens']:,}\n")
        fh.write(f"  Total Tokens       : {overall['total_tokens']:,}\n")
        fh.write(f"  Session Duration   : {overall['session_start_time']} to {overall['session_end_time']}\n\n")

        for sample_name, sample_data in report_data["samples"].items():
            fh.write(f"Sample: {sample_name}\n")
            fh.write("-" * 30 + "\n")
            fh.write(f"  Total Calls    : {sample_data['total_calls']}\n")
            fh.write(f"  Input Tokens   : {sample_data['total_input_tokens']:,}\n")
            fh.write(f"  Output Tokens  : {sample_data['total_output_tokens']:,}\n")
            fh.write(f"  Total Tokens   : {sample_data['total_tokens']:,}\n")
            fh.write(f"  Duration       : {sample_data['start_time']} to {sample_data.get('end_time', 'In Progress')}\n")
            fh.write("\n  Individual Calls:\n")
            for call in sample_data["calls"]:
                fh.write(
                    f"    {call['call_id']:2d}. {call['agent_name']:15s} | {call['call_type']:10s} | "
                    f"In: {call['input_tokens']:4d} | Out: {call['output_tokens']:4d} | "
                    f"{'✓' if call['success'] else '✗'}\n"
                )
                if not call["success"] and call.get("error_message"):
                    fh.write(f"        Error: {call['error_message']}\n")
            fh.write("\n")

    print(f"  Token usage (TXT)  : {txt_path}")


def _write_run_times_report(run_times: dict) -> None:
    """Write test_framework/test_run_times.txt"""
    completed = {k: v for k, v in run_times.items()
                 if v.get("status") in ("success", "error")}
    durations = [v["elapsed_seconds"] for v in completed.values()]
    total_elapsed = sum(durations)
    avg_elapsed = total_elapsed / len(durations) if durations else 0.0
    min_elapsed = min(durations) if durations else 0.0
    max_elapsed = max(durations) if durations else 0.0

    run_times_path = os.path.join("test_framework", "test_run_times.txt")
    with open(run_times_path, "w") as fh:
        fh.write("=" * 80 + "\n")
        fh.write("TEST RUN TIMES REPORT\n")
        fh.write("=" * 80 + "\n\n")
        fh.write(f"Total Tests: {len(run_times)}\n")
        fh.write(f"Total Time: {total_elapsed:.2f} seconds ({total_elapsed / 60:.2f} minutes)\n")
        fh.write(f"Average Time per Test: {avg_elapsed:.2f} seconds\n")
        fh.write(f"Min Time: {min_elapsed:.2f} seconds\n")
        fh.write(f"Max Time: {max_elapsed:.2f} seconds\n")
        fh.write("\n")
        fh.write("=" * 80 + "\n")
        fh.write(f"{'Test Case':<52} {'Duration (seconds)':>18}\n")
        fh.write("-" * 80 + "\n")
        for test_case, data in run_times.items():
            elapsed = data.get("elapsed_seconds", 0)
            if data.get("status") == "skipped":
                fh.write(f"{test_case:<52} {'skipped':>18}\n")
            else:
                fh.write(f"{test_case:<52} {elapsed:>18.2f}\n")
        fh.write("=" * 80 + "\n")
        fh.write("\nDetailed Timing Information:\n")
        fh.write("-" * 80 + "\n")
        for test_case, data in run_times.items():
            fh.write(f"\n{test_case}:\n")
            status = data.get("status", "unknown")
            if status == "skipped":
                fh.write(f"  Status: skipped ({data.get('reason', '')})\n")
            else:
                fh.write(f"  Start Time: {data.get('start_time', 'N/A')}\n")
                fh.write(f"  End Time: {data.get('end_time', 'N/A')}\n")
                fh.write(f"  Duration: {data.get('elapsed_seconds', 0):.2f} seconds\n")
                if status == "error":
                    fh.write(f"  Error: {data.get('error', '')}\n")

    print(f"  Run times  (TXT)  : {run_times_path}")


def _print_final_summary(run_times: dict) -> None:
    successful = [k for k, v in run_times.items() if v.get("status") == "success"]
    failed = [k for k, v in run_times.items() if v.get("status") == "error"]
    skipped = [k for k, v in run_times.items() if v.get("status") == "skipped"]

    print(f"\n{'='*80}")
    print("FINAL SUMMARY")
    print(f"{'='*80}")
    print(f"Total: {len(run_times)}  |  Success: {len(successful)}  |  Failed: {len(failed)}  |  Skipped: {len(skipped)}\n")

    if successful:
        print("Successful:")
        for tc in successful:
            elapsed = run_times[tc].get("elapsed_seconds", 0)
            print(f"  ✓  {tc}  ({elapsed:.2f}s)")

    if failed:
        print("\nFailed:")
        for tc in failed:
            err = run_times[tc].get("error", "unknown error")
            print(f"  ✗  {tc}: {err}")

    if skipped:
        print("\nSkipped:")
        for tc in skipped:
            reason = run_times[tc].get("reason", "unknown reason")
            print(f"  -  {tc}: {reason}")

    print(f"\n{'='*80}\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run the Agentic Workflow on all test samples and produce summary reports."
    )
    parser.add_argument(
        "--data-dir",
        default="test_framework/data",
        help="Path to the directory containing test-case folders (default: test_framework/data)",
    )
    args = parser.parse_args()

    run_tests(data_dir=args.data_dir)
