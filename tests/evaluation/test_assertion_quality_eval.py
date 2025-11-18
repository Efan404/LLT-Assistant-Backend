"""
Evaluation tests for LLM assertion quality analysis.

Tests the accuracy of LLM-based assertion quality detection against ground truth data.
"""

import json
from typing import Any, Dict, List

import pytest

from tests.evaluation.conftest import parse_test_code_to_objects
from tests.evaluation.metrics.custom_metrics import EvaluationMetrics
from tests.evaluation.metrics.json_validators import JSONSchemaValidator


@pytest.mark.llm_evaluation
@pytest.mark.requires_api_key
class TestAssertionQualityEvaluation:
    """Evaluation test suite for assertion quality analysis."""

    @pytest.mark.asyncio
    async def test_assertion_quality_issue_detection(
        self,
        ground_truth_assertion_quality: Dict[str, Any],
        llm_analyzer_for_eval: Any,
        skip_if_no_api_key: None,
        evaluation_sample_size: int,
    ) -> None:
        """
        Test LLM assertion quality issue detection accuracy against ground truth.

        Measures precision, recall, and F1-score for detecting assertion issues.
        """
        test_cases = ground_truth_assertion_quality["test_cases"][
            :evaluation_sample_size
        ]

        predicted_issues_list = []
        ground_truth_issues_list = []
        predicted_qualities = []
        ground_truth_qualities = []
        validation_errors = []

        print(f"\n{'='*80}")
        print(f"ASSERTION QUALITY ANALYSIS EVALUATION")
        print(f"{'='*80}")
        print(f"Total test cases: {len(test_cases)}")
        print(f"{'='*80}\n")

        for idx, test_case in enumerate(test_cases, 1):
            test_id = test_case["id"]
            test_function_code = test_case["test_function"]
            expected = test_case["expected_output"]

            print(f"[{idx}/{len(test_cases)}] Evaluating {test_id}...", end=" ")

            try:
                # Parse test code string into proper objects
                test_func_info, context = parse_test_code_to_objects(
                    test_function_code, f"{test_id}.py"
                )

                result = await llm_analyzer_for_eval.analyze_assertion_quality(
                    test_func_info, context
                )

                is_valid, error = JSONSchemaValidator.validate_assertion_quality_output(
                    result
                )
                if not is_valid:
                    validation_errors.append({"test_id": test_id, "error": error})
                    print(f"❌ Invalid JSON: {error}")
                    continue

                predicted_issues = result.get("issues", [])
                expected_issues = expected.get("issues", [])
                predicted_quality = result.get("overall_quality", "unknown")
                expected_quality = expected.get("overall_quality", "unknown")

                predicted_issues_list.append(predicted_issues)
                ground_truth_issues_list.append(expected_issues)
                predicted_qualities.append(predicted_quality)
                ground_truth_qualities.append(expected_quality)

                issue_match = len(predicted_issues) == len(expected_issues)
                quality_match = predicted_quality == expected_quality
                match_symbol = "✓" if (issue_match and quality_match) else "✗"

                print(
                    f"{match_symbol} "
                    f"(issues: {len(predicted_issues)} vs {len(expected_issues)}, "
                    f"quality: {predicted_quality} vs {expected_quality})"
                )

            except Exception as e:
                print(f"❌ Error: {str(e)}")
                validation_errors.append({"test_id": test_id, "error": str(e)})

        assert (
            len(predicted_issues_list) >= evaluation_sample_size * 0.8
        ), f"Too many failures: only {len(predicted_issues_list)}/{evaluation_sample_size} completed"

        issue_metrics = EvaluationMetrics.calculate_issue_detection_metrics(
            predicted_issues_list, ground_truth_issues_list, match_by="type"
        )

        quality_distribution = EvaluationMetrics.calculate_quality_distribution(
            predicted_qualities
        )

        quality_agreement = sum(
            1
            for pred, truth in zip(predicted_qualities, ground_truth_qualities)
            if pred == truth
        )
        quality_accuracy = (
            quality_agreement / len(predicted_qualities) if predicted_qualities else 0.0
        )

        print(f"\n{'='*80}")
        print(f"ASSERTION QUALITY EVALUATION RESULTS")
        print(f"{'='*80}")
        print(f"Samples evaluated: {len(predicted_issues_list)}")
        print(f"\nIssue Detection Metrics:")
        print(f"  Precision: {issue_metrics['precision']:.4f}")
        print(f"  Recall: {issue_metrics['recall']:.4f}")
        print(f"  F1-Score: {issue_metrics['f1_score']:.4f}")
        print(f"  True Positives: {issue_metrics['true_positives']}")
        print(f"  False Positives: {issue_metrics['false_positives']}")
        print(f"  False Negatives: {issue_metrics['false_negatives']}")
        print(f"\nQuality Label Accuracy: {quality_accuracy:.4f}")
        print(f"\nQuality Distribution:")
        for label, stats in quality_distribution["distribution"].items():
            print(f"  {label}: {stats['count']} ({stats['percentage']:.1f}%)")
        if validation_errors:
            print(f"\nValidation Errors: {len(validation_errors)}")
            for error in validation_errors[:5]:
                print(f"  - {error['test_id']}: {error['error']}")
        print(f"{'='*80}\n")

        assert (
            issue_metrics["precision"] >= 0.70
        ), f"Precision {issue_metrics['precision']:.4f} below target 0.70"
        assert (
            issue_metrics["recall"] >= 0.65
        ), f"Recall {issue_metrics['recall']:.4f} below target 0.65"
        assert (
            issue_metrics["f1_score"] >= 0.67
        ), f"F1-score {issue_metrics['f1_score']:.4f} below target 0.67"

    @pytest.mark.asyncio
    async def test_assertion_quality_json_schema_compliance(
        self,
        ground_truth_assertion_quality: Dict[str, Any],
        llm_analyzer_for_eval: Any,
        skip_if_no_api_key: None,
    ) -> None:
        """
        Test that all assertion quality outputs conform to expected JSON schema.
        """
        test_cases = ground_truth_assertion_quality["test_cases"][:5]

        validation_results = []

        for test_case in test_cases:
            test_function_code = test_case["test_function"]

            # Parse test code string into proper objects
            test_func_info, context = parse_test_code_to_objects(
                test_function_code, f"{test_case['id']}.py"
            )

            result = await llm_analyzer_for_eval.analyze_assertion_quality(
                test_func_info, context
            )

            is_valid, error = JSONSchemaValidator.validate_assertion_quality_output(
                result
            )
            validation_results.append({"valid": is_valid, "error": error})

        valid_count = sum(1 for r in validation_results if r["valid"])
        validity_rate = valid_count / len(validation_results) * 100

        print(
            f"\nJSON Schema Validation: {valid_count}/{len(validation_results)} valid ({validity_rate:.1f}%)"
        )

        assert (
            validity_rate >= 90.0
        ), f"JSON schema validity rate {validity_rate:.1f}% below target 90%"

    @pytest.mark.asyncio
    async def test_assertion_quality_confidence_filtering(
        self,
        ground_truth_assertion_quality: Dict[str, Any],
        llm_analyzer_for_eval: Any,
        skip_if_no_api_key: None,
    ) -> None:
        """
        Test that assertion quality analysis properly filters by confidence.

        Issues with confidence <= 0.7 should be filtered out.
        """
        test_cases = ground_truth_assertion_quality["test_cases"][:5]

        all_confidences = []

        for test_case in test_cases:
            test_function_code = test_case["test_function"]

            # Parse test code string into proper objects
            test_func_info, context = parse_test_code_to_objects(
                test_function_code, f"{test_case['id']}.py"
            )

            result = await llm_analyzer_for_eval.analyze_assertion_quality(
                test_func_info, context
            )

            overall_confidence = result.get("confidence", 0.0)
            all_confidences.append(overall_confidence)

        avg_confidence = (
            sum(all_confidences) / len(all_confidences) if all_confidences else 0.0
        )
        min_confidence = min(all_confidences) if all_confidences else 0.0

        print(f"\nConfidence Statistics:")
        print(f"  Average: {avg_confidence:.4f}")
        print(f"  Minimum: {min_confidence:.4f}")
        print(f"  Maximum: {max(all_confidences) if all_confidences else 0.0:.4f}")

        assert (
            min_confidence >= 0.5
        ), f"Minimum confidence {min_confidence:.4f} below threshold 0.5"
        assert (
            avg_confidence >= 0.7
        ), f"Average confidence {avg_confidence:.4f} below threshold 0.7"
