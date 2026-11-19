# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# All rights reserved.
# Confidential and Proprietary - Qualcomm Technologies, Inc.

"""
Test Framework for Agentic Workflow Evaluation
Compares generated reports against ground truth using multiple metrics
"""

import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import numpy as np

# Add parent directory to path so we can import model_calls and agentic_service
_parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)

from model_calls import generate_llm_response
from simple_similarity import SimpleSimilarity

try:
    from test_framework.token_logger import TokenLogger, estimate_tokens
    _token_logger_available = True
except ImportError:
    _token_logger_available = False


@dataclass
class SectionScore:
    """Score for a single report section"""
    section_name: str
    semantic_similarity: float  # 0-1
    llm_accuracy_score: float  # 0-10
    llm_completeness_score: float  # 0-10
    specific_metrics: dict[str, float]  # Section-specific metrics
    feedback: str  # LLM feedback on what's missing/wrong


@dataclass
class ReportEvaluation:
    """Complete evaluation of a generated report"""
    test_case: str
    section_scores: list[SectionScore]
    overall_score: float
    strengths: list[str]
    weaknesses: list[str]
    recommendations: list[str]


class AgenticWorkflowEvaluator:
    """Evaluates generated triage reports against ground truth"""

    def __init__(self, model_name: str = "qgenie"):
        """
        Initialize evaluator

        Args:
            model_name: LLM model to use for evaluation
        """
        self.model_name = model_name
        # Use SimpleSimilarity for semantic similarity
        self.simple_similarity = SimpleSimilarity()

        # Define expected sections
        self.expected_sections = [
            "What Happened",
            "Root Cause Analysis",
            "Why This Root Cause Fits",
            "Mitigation / Next Steps",
            "Open Questions / Gaps",
            "References"
        ]

    def evaluate_report(self, generated_report: str, ground_truth: str, test_case: str) -> ReportEvaluation:
        """
        Evaluate a generated report against ground truth

        Args:
            generated_report: Generated triage report text
            ground_truth: Ground truth report text
            test_case: Name of test case

        Returns:
            ReportEvaluation with detailed scores
        """
        print(f"\n{'='*80}")
        print(f"Evaluating Test Case: {test_case}")
        print(f"{'='*80}\n")

        # Extract sections from both reports
        gen_sections = self._extract_sections(generated_report)
        gt_sections = self._extract_sections(ground_truth)

        # Evaluate each section
        section_scores = []
        for section_name in self.expected_sections:
            score = self._evaluate_section(
                section_name,
                gen_sections.get(section_name, ""),
                gt_sections.get(section_name, ""),
                test_case
            )
            section_scores.append(score)

        # Calculate overall score
        overall_score = self._calculate_overall_score(section_scores)

        # Generate summary feedback
        strengths, weaknesses, recommendations = self._generate_summary_feedback(
            section_scores, gen_sections, gt_sections
        )

        return ReportEvaluation(
            test_case=test_case,
            section_scores=section_scores,
            overall_score=overall_score,
            strengths=strengths,
            weaknesses=weaknesses,
            recommendations=recommendations
        )

    def _extract_sections(self, report: str) -> dict[str, str]:
        """Extract sections from report text"""
        sections = {}

        # Map actual report sections to expected test framework sections
        # This handles both the new agentic report format and legacy formats
        patterns = {
            # Map Executive Summary to What Happened
            "What Happened": [
                r"1\.\s*Executive Summary(.*?)(?=\d+\.|$)",
                r"(?:1\.|##)\s*What Happened(.*?)(?=(?:\d+\.|##)|$)"
            ],
            # Map Root Cause Hypothesis to Root Cause Analysis
            "Root Cause Analysis": [
                r"4\.\s*Root Cause Hypothesis(.*?)(?=\d+\.|$)",
                r"(?:2\.|##)\s*Root Cause Analysis(.*?)(?=(?:\d+\.|##)|$)"
            ],
            # Map Critical Findings + Timeline to Why This Root Cause Fits
            "Why This Root Cause Fits": [
                r"3\.\s*Critical Findings(.*?)(?=4\.|$)",
                r"(?:3\.|##)\s*Why This Root Cause Fits(.*?)(?=(?:\d+\.|##)|$)"
            ],
            # Map Recommended Actions to Mitigation / Next Steps
            "Mitigation / Next Steps": [
                r"5\.\s*Recommended Actions(.*?)(?=\d+\.|$)",
                r"(?:4\.|##)\s*(?:Mitigation|Recommended Actions)(.*?)(?=(?:\d+\.|##)|$)"
            ],
            # For now, map Timeline Analysis to Open Questions (since we don't have a direct match)
            "Open Questions / Gaps": [
                r"2\.\s*Timeline Analysis(.*?)(?=3\.|$)",
                r"(?:5\.|##)\s*Open Questions(.*?)(?=(?:\d+\.|##)|$)"
            ],
            # Map Evidence Summary to References
            "References": [
                r"6\.\s*Evidence Summary(.*?)(?=\d+\.|$)",
                r"(?:6\.|##)\s*References(.*?)(?=(?:\d+\.|##)|$)"
            ]
        }

        for section_name, pattern_list in patterns.items():
            for pattern in pattern_list:
                match = re.search(pattern, report, re.DOTALL | re.IGNORECASE)
                if match:
                    sections[section_name] = match.group(1).strip()
                    break  # Use first matching pattern

        return sections

    def _evaluate_section(self, section_name: str, generated: str,
                          ground_truth: str, test_case: str) -> SectionScore:
        """Evaluate a single section"""
        print(f"Evaluating section: {section_name}")

        # Calculate semantic similarity using TF-IDF
        semantic_sim = 0.0
        if generated and ground_truth:
            try:
                semantic_sim = self.simple_similarity.similarity(generated, ground_truth)
                print(f"  TF-IDF similarity: {semantic_sim:.3f}")
            except Exception as e:
                print(f"  Warning: Similarity calculation failed: {e}")

        # Use LLM to evaluate accuracy and completeness
        llm_scores = self._llm_evaluate_section(
            section_name, generated, ground_truth, test_case
        )

        # Calculate section-specific metrics
        specific_metrics = self._calculate_specific_metrics(
            section_name, generated, ground_truth
        )

        return SectionScore(
            section_name=section_name,
            semantic_similarity=semantic_sim,
            llm_accuracy_score=llm_scores['accuracy'],
            llm_completeness_score=llm_scores['completeness'],
            specific_metrics=specific_metrics,
            feedback=llm_scores['feedback']
        )

    def _llm_evaluate_section(self, section_name: str, generated: str,
                               ground_truth: str, test_case: str) -> dict[str, Any]:
        """Use LLM to evaluate section quality"""

        if not generated:
            return {
                'accuracy': 0.0,
                'completeness': 0.0,
                'feedback': f"Section '{section_name}' is completely missing from generated report"
            }

        if not ground_truth:
            return {
                'accuracy': 5.0,
                'completeness': 5.0,
                'feedback': f"No ground truth available for section '{section_name}'"
            }

        prompt = f"""You are evaluating a WiFi connectivity triage report section.

Test Case: {test_case}
Section: {section_name}

GROUND TRUTH (Expected):
{ground_truth}

GENERATED (Actual):
{generated}

Evaluate the generated section on two dimensions:

1. ACCURACY (0-10): How factually correct is the generated content compared to ground truth?
   - 10: All facts match, no errors
   - 7-9: Mostly correct with minor discrepancies
   - 4-6: Some correct facts but significant errors
   - 0-3: Mostly incorrect or contradicts ground truth

2. COMPLETENESS (0-10): How much of the ground truth content is covered?
   - 10: All key points covered
   - 7-9: Most key points covered, minor omissions
   - 4-6: Some key points covered, significant gaps
   - 0-3: Very incomplete, major gaps

Provide your evaluation in this exact format:
ACCURACY: <score>
COMPLETENESS: <score>
FEEDBACK: <detailed explanation of what's missing, wrong, or good>
"""

        input_tokens = estimate_tokens(prompt) if _token_logger_available else 0
        response = generate_llm_response(self.model_name, prompt, call_type="summary")
        output_tokens = (estimate_tokens(response) if response else 0) if _token_logger_available else 0

        # Log this evaluator LLM call to the token logger
        if _token_logger_available:
            try:
                tl = TokenLogger()
                if tl.current_sample:
                    tl.log_llm_call(
                        agent_name="Evaluator",
                        call_type="summary",
                        model=self.model_name,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        prompt_preview=prompt,
                        response_preview=response or "",
                        success=bool(response and not response.startswith("Error:")),
                    )
            except Exception:
                pass

        # Parse LLM response
        accuracy = 5.0
        completeness = 5.0
        feedback = "Could not parse LLM evaluation"

        if response:
            acc_match = re.search(r'ACCURACY:\s*(\d+(?:\.\d+)?)', response)
            comp_match = re.search(r'COMPLETENESS:\s*(\d+(?:\.\d+)?)', response)
            feedback_match = re.search(r'FEEDBACK:\s*(.+)', response, re.DOTALL)

            if acc_match:
                accuracy = float(acc_match.group(1))
            if comp_match:
                completeness = float(comp_match.group(1))
            if feedback_match:
                feedback = feedback_match.group(1).strip()

        return {
            'accuracy': accuracy,
            'completeness': completeness,
            'feedback': feedback
        }

    def _calculate_specific_metrics(self, section_name: str, generated: str,
                                    ground_truth: str) -> dict[str, float]:
        """Calculate section-specific metrics"""
        metrics = {}

        if section_name == "What Happened":
            # Check for key elements
            metrics['has_timestamp'] = 1.0 if re.search(r'\d{4}[-/]\d{2}[-/]\d{2}', generated) else 0.0
            metrics['has_mac_address'] = 1.0 if re.search(r'[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}', generated, re.I) else 0.0
            metrics['has_log_evidence'] = 1.0 if 'log' in generated.lower() or 'evidence' in generated.lower() else 0.0

        elif section_name == "Root Cause Analysis":
            # Check for likelihood rankings
            metrics['has_likelihood_ranking'] = 1.0 if any(x in generated.upper() for x in ['HIGH', 'MEDIUM', 'LOW']) else 0.0
            metrics['has_multiple_hypotheses'] = 1.0 if generated.count('Hypothesis') >= 2 or generated.count('Cause') >= 2 else 0.0
            metrics['has_kb_reference'] = 1.0 if 'KB' in generated or 'Knowledge' in generated or 'Section' in generated else 0.0

        elif section_name == "Why This Root Cause Fits":
            # Check for reasoning chain
            metrics['has_hostapd_evidence'] = 1.0 if 'hostapd' in generated.lower() else 0.0
            metrics['has_stats_verification'] = 1.0 if 'stats' in generated.lower() or 'wifistats' in generated.lower() else 0.0
            metrics['has_confidence_level'] = 1.0 if any(x in generated.upper() for x in ['HIGH', 'MEDIUM', 'LOW', 'CONFIDENCE']) else 0.0

        elif section_name == "Mitigation / Next Steps":
            # Check for actionable items
            metrics['has_commands'] = 1.0 if 'cfg80211tool' in generated or 'wifistats' in generated or '#' in generated else 0.0
            metrics['has_verification_steps'] = 1.0 if 'verify' in generated.lower() or 'check' in generated.lower() else 0.0
            metrics['not_empty'] = 1.0 if len(generated.strip()) > 50 else 0.0

        elif section_name == "Open Questions / Gaps":
            # Check for missing data identification
            metrics['identifies_gaps'] = 1.0 if 'missing' in generated.lower() or 'unknown' in generated.lower() else 0.0
            metrics['suggests_collection'] = 1.0 if 'collect' in generated.lower() or 'capture' in generated.lower() else 0.0
            metrics['not_empty'] = 1.0 if len(generated.strip()) > 50 else 0.0

        elif section_name == "References":
            # Check for proper references
            metrics['has_kb_references'] = 1.0 if 'KB' in generated or 'Section' in generated else 0.0
            metrics['has_log_files'] = 1.0 if '.txt' in generated or 'syslog' in generated else 0.0

        return metrics

    def _calculate_overall_score(self, section_scores: list[SectionScore]) -> float:
        """Calculate weighted overall score"""
        # Define section weights
        weights = {
            "What Happened": 0.15,
            "Root Cause Analysis": 0.25,
            "Why This Root Cause Fits": 0.20,
            "Mitigation / Next Steps": 0.20,
            "Open Questions / Gaps": 0.10,
            "References": 0.10
        }

        total_score = 0.0
        total_weight = 0.0

        for score in section_scores:
            weight = weights.get(score.section_name, 0.1)
            # Combine accuracy and completeness (weighted average)
            section_score = (score.llm_accuracy_score * 0.6 +
                             score.llm_completeness_score * 0.4)
            total_score += section_score * weight
            total_weight += weight

        return total_score / total_weight if total_weight > 0 else 0.0

    def _generate_summary_feedback(self, section_scores: list[SectionScore],
                                   gen_sections: dict[str, str],
                                   gt_sections: dict[str, str]) -> tuple[list[str], list[str], list[str]]:
        """Generate summary strengths, weaknesses, and recommendations"""
        strengths = []
        weaknesses = []
        recommendations = []

        for score in section_scores:
            avg_score = (score.llm_accuracy_score + score.llm_completeness_score) / 2

            if avg_score >= 8.0:
                strengths.append(f"{score.section_name}: Strong performance (score: {avg_score:.1f}/10)")
            elif avg_score < 5.0:
                weaknesses.append(f"{score.section_name}: Needs improvement (score: {avg_score:.1f}/10)")
                recommendations.append(f"Improve {score.section_name}: {score.feedback[:100]}...")

        # Check for missing sections
        for section_name in self.expected_sections:
            if section_name not in gen_sections or len(gen_sections[section_name]) < 50:
                weaknesses.append(f"{section_name}: Section missing or too short")
                recommendations.append(f"Add complete {section_name} section with LLM generation")

        return strengths, weaknesses, recommendations

    def print_evaluation(self, evaluation: ReportEvaluation):
        """Print evaluation results in readable format"""
        print(f"\n{'='*80}")
        print(f"EVALUATION RESULTS: {evaluation.test_case}")
        print(f"{'='*80}\n")

        print(f"Overall Score: {evaluation.overall_score:.2f}/10\n")

        print("Section Scores:")
        print("-" * 80)
        for score in evaluation.section_scores:
            print(f"\n{score.section_name}:")
            print(f"  Semantic Similarity: {score.semantic_similarity:.3f}")
            print(f"  Accuracy: {score.llm_accuracy_score:.1f}/10")
            print(f"  Completeness: {score.llm_completeness_score:.1f}/10")
            if score.specific_metrics:
                print(f"  Specific Metrics: {score.specific_metrics}")
            print(f"  Feedback: {score.feedback}")

        print(f"\n{'='*80}")
        print("STRENGTHS:")
        for strength in evaluation.strengths:
            print(f"  ✓ {strength}")

        print(f"\n{'='*80}")
        print("WEAKNESSES:")
        for weakness in evaluation.weaknesses:
            print(f"  ✗ {weakness}")

        print(f"\n{'='*80}")
        print("RECOMMENDATIONS:")
        for i, rec in enumerate(evaluation.recommendations, 1):
            print(f"  {i}. {rec}")

        print(f"\n{'='*80}\n")


def run_test_suite(data_dir: str = "test_framework/data") -> list[ReportEvaluation]:
    """
    Run evaluation on all test cases

    Args:
        data_dir: Directory containing test case folders

    Returns:
        List of evaluations for each test case
    """
    # Initialize token logger
    try:
        from test_framework.token_logger import TokenLogger
        token_logger = TokenLogger()
        print("[TOKEN_LOG] Token logging initialized for test framework")
    except ImportError:
        print("[WARNING] Could not import TokenLogger, token logging disabled")
        token_logger = None

    evaluator = AgenticWorkflowEvaluator()
    evaluations = []
    run_times: dict = {}

    # Get all test case directories
    test_cases = [d for d in os.listdir(data_dir)
                  if os.path.isdir(os.path.join(data_dir, d))]

    for test_case in sorted(test_cases):
        test_path = os.path.join(data_dir, test_case)

        # Check if ground truth exists
        gt_path = os.path.join(test_path, "ground_truth.txt")
        if not os.path.exists(gt_path):
            print(f"Skipping {test_case}: No ground truth found")
            run_times[test_case] = {"status": "skipped", "reason": "No ground truth", "elapsed_seconds": 0}
            continue

        # Set current sample for token logging
        if token_logger:
            token_logger.set_current_sample(test_case)

        # Read ground truth
        with open(gt_path) as f:
            ground_truth = f.read()

        # Generate report for this test case (timed)
        start_dt = datetime.now()
        start_time = time.time()
        generated_report = generate_report_for_test_case(test_path)
        elapsed = time.time() - start_time
        end_dt = datetime.now()
        print(f"  Report generation elapsed: {elapsed:.2f}s")

        # Mark sample as finished
        if token_logger:
            token_logger.finish_sample(test_case)

        # Evaluate
        evaluation = evaluator.evaluate_report(generated_report, ground_truth, test_case)
        evaluations.append(evaluation)
        run_times[test_case] = {
            "status": "success",
            "elapsed_seconds": round(elapsed, 3),
            "start_time": start_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "end_time": end_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "overall_score": round(evaluation.overall_score, 2),
        }

        # Print results
        evaluator.print_evaluation(evaluation)

    # Generate token usage report
    if token_logger:
        json_report, txt_report = token_logger.generate_report(
            os.path.join("test_framework", "agentic_service_token_usage_report.json")
        )
        print("\n[TOKEN_LOG] Token usage reports generated:")
        print(f"  JSON: {json_report}")
        print(f"  TXT: {txt_report}")

    # Write run-times report
    _write_run_times_report(run_times)

    # Print summary
    print_test_suite_summary(evaluations)

    return evaluations


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
                elif status == "success" and "overall_score" in data:
                    fh.write(f"  Score: {data['overall_score']}/10\n")

    print(f"  Run times (TXT)  : {run_times_path}")


def generate_report_for_test_case(test_path: str) -> str:
    """
    Generate triage report for a test case

    Args:
        test_path: Path to test case directory

    Returns:
        Generated report text
    """
    from agentic_service.main import run_analysis_from_files

    # Find input files
    fd_logs = None
    syslog = None
    wifistats = None
    kb = "knowledge_base.txt"  # Use main KB file

    for filename in os.listdir(test_path):
        if filename.endswith('_fd_logs.txt'):
            fd_logs = os.path.join(test_path, filename)
        elif filename == 'syslog.txt':
            syslog = os.path.join(test_path, filename)
        elif filename == 'rate_of_change_wifistats.txt':
            wifistats = os.path.join(test_path, filename)

    # Check for required files
    if not fd_logs:
        return "Error: Missing required fd_logs file"

    # Run analysis - this returns the report content directly
    report = run_analysis_from_files(fd_logs, syslog, wifistats, kb)

    # Save the generated report to the test case folder for manual review
    report_path = os.path.join(test_path, "triage_report.txt")
    try:
        with open(report_path, 'w') as f:
            f.write(report)
        print(f"  Report saved to: {report_path}")
    except Exception as e:
        print(f"  Warning: Could not save report to {report_path}: {e}")

    return report


def print_test_suite_summary(evaluations: list[ReportEvaluation]):
    """Print summary of all test cases"""
    print(f"\n{'='*80}")
    print("TEST SUITE SUMMARY")
    print(f"{'='*80}\n")

    if not evaluations:
        print("No evaluations to summarize.")
        return

    avg_score = np.mean([e.overall_score for e in evaluations])
    print(f"Average Overall Score: {avg_score:.2f}/10\n")

    print("Individual Test Case Scores:")
    for eval in evaluations:
        print(f"  {eval.test_case}: {eval.overall_score:.2f}/10")

    print(f"\n{'='*80}\n")


if __name__ == "__main__":
    # Run test suite
    evaluations = run_test_suite()
