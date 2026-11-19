# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# All rights reserved.
# Confidential and Proprietary - Qualcomm Technologies, Inc.

#!/usr/bin/env python3
"""
Endpoint Test Runner
Submits the .tar file from each sample folder in 'data/' to the internal
LLM endpoint, polls for the result, and saves a triage_report.txt per sample.

Usage:
    python run_tests.py
    python run_tests.py --data-dir data
"""

import argparse
import os
import sys
import time
from datetime import datetime

# Ensure the directory containing this script is on the path.
_src_dir = os.path.dirname(os.path.abspath(__file__))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

import model_calls as _model_calls

# ---------------------------------------------------------------------------
# Core runner
# ---------------------------------------------------------------------------

def run_tests(data_dir: str = "data") -> None:
    """
    For every sample folder inside *data_dir*:
      - Locates the *.tar file
      - Submits it to the internal LLM endpoint via call_internal_endpoint_with_tar()
      - Writes the returned summary as triage_report.txt

    After all samples:
      - Writes test_run_times.txt
    """
    run_times: dict = {}

    print("=" * 80)
    print("ENDPOINT TEST RUNNER")
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

    for test_case in test_cases:
        test_path = os.path.join(data_dir, test_case)

        print(f"\n{'='*80}")
        print(f"Processing: {test_case}")
        print(f"{'='*80}")

        # Locate the .tar file
        tar_file = None
        for filename in os.listdir(test_path):
            if filename.endswith(".tar"):
                tar_file = os.path.join(test_path, filename)
                break

        if not tar_file:
            print("  Skipping: no *.tar file found.")
            run_times[test_case] = {
                "status": "skipped",
                "reason": "No tar file found",
                "elapsed_seconds": 0,
            }
            continue

        print(f"  Tar file  : {tar_file}")

        start_dt = datetime.now()
        start_time = time.time()
        try:
            report = _model_calls.call_internal_endpoint_with_tar(tar_file)
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

    # -----------------------------------------------------------------------
    # Generate summary reports
    # -----------------------------------------------------------------------
    print(f"\n{'='*80}")
    print("Generating summary reports ...")
    print(f"{'='*80}")

    _write_run_times_report(run_times)
    _print_final_summary(run_times)


# ---------------------------------------------------------------------------
# Report helpers
# ---------------------------------------------------------------------------

def _write_run_times_report(run_times: dict) -> None:
    """Write test_run_times.txt to the current directory."""
    completed = {k: v for k, v in run_times.items()
                 if v.get("status") in ("success", "error")}
    durations = [v["elapsed_seconds"] for v in completed.values()]
    total_elapsed = sum(durations)
    avg_elapsed = total_elapsed / len(durations) if durations else 0.0
    min_elapsed = min(durations) if durations else 0.0
    max_elapsed = max(durations) if durations else 0.0

    run_times_path = "test_run_times.txt"
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

    print(f"  Run times (TXT) : {run_times_path}")


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
        description="Submit tar files to the internal LLM endpoint and save triage reports."
    )
    parser.add_argument(
        "--data-dir",
        default="data",
        help="Path to the directory containing test-case folders (default: data)",
    )
    args = parser.parse_args()

    run_tests(data_dir=args.data_dir)
