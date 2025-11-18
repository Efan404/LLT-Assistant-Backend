"""
Evaluation tests for LLM mergeability analysis.

Tests the accuracy of LLM-based test mergeability predictions against ground truth data.
"""

import json
from typing import Any, Dict, List

import pytest

from tests.evaluation.conftest import parse_test_code_to_objects
from tests.evaluation.metrics.custom_metrics import EvaluationMetrics
from tests.evaluation.metrics.json_validators import JSONSchemaValidator


@pytest.mark.llm_evaluation
@pytest.mark.requires_api_key
class TestMergeabilityEvaluation:
    """Evaluation test suite for mergeability analysis."""

    @pytest.mark.asyncio
    async def test_mergeability_accuracy(
        self,
        ground_truth_mergeability: Dict[str, Any],
        llm_analyzer_for_eval: Any,
        skip_if_no_api_key: None,
        evaluation_sample_size: int,
    ) -> None:
        """
        Test LLM mergeability prediction accuracy against ground truth.

        This test measures precision, recall, and F1-score for mergeability detection.
        """
        test_cases = ground_truth_mergeability["test_cases"][:evaluation_sample_size]

        predictions = []
        ground_truths = []
        confidences = []
        validation_errors = []

        print(f"\n{'='*80}")
        print(f"MERGEABILITY ANALYSIS EVALUATION")
        print(f"{'='*80}")
        print(f"Total test cases: {len(test_cases)}")
        print(f"{'='*80}\n")

        for idx, test_case in enumerate(test_cases, 1):
            test_id = test_case["id"]
            func1_code = test_case["test_function_1"]
            func2_code = test_case["test_function_2"]
            expected = test_case["expected_output"]

            print(f"[{idx}/{len(test_cases)}] Evaluating {test_id}...", end=" ")

            try:
                # Parse test code strings into proper objects
                test1_info, context1 = parse_test_code_to_objects(
                    func1_code, f"{test_id}_func1.py"
                )
                test2_info, _ = parse_test_code_to_objects(
                    func2_code, f"{test_id}_func2.py"
                )

                result = await llm_analyzer_for_eval.analyze_mergeability(
                    test1_info, test2_info, context1
                )

                is_valid, error = JSONSchemaValidator.validate_mergeability_output(
                    result
                )
                if not is_valid:
                    validation_errors.append({"test_id": test_id, "error": error})
                    print(f"❌ Invalid JSON: {error}")
                    continue

                predicted_mergeable = result.get("mergeable", False)
                expected_mergeable = expected.get("mergeable", False)
                confidence = result.get("confidence", 0.0)

                predictions.append(predicted_mergeable)
                ground_truths.append(expected_mergeable)
                confidences.append(confidence)

                match_symbol = "✓" if predicted_mergeable == expected_mergeable else "✗"
                print(f"{match_symbol} (confidence: {confidence:.2f})")

            except Exception as e:
                print(f"❌ Error: {str(e)}")
                validation_errors.append({"test_id": test_id, "error": str(e)})

        assert (
            len(predictions) >= evaluation_sample_size * 0.8
        ), f"Too many failures: only {len(predictions)}/{evaluation_sample_size} completed"

        metrics = EvaluationMetrics.calculate_mergeability_metrics(
            predictions, ground_truths
        )

        calibration = EvaluationMetrics.calculate_confidence_calibration(
            predictions, confidences, ground_truths
        )

        print(f"\n{'='*80}")
        print(f"MERGEABILITY EVALUATION RESULTS")
        print(f"{'='*80}")
        print(f"Samples evaluated: {len(predictions)}")
        print(f"Precision: {metrics['precision']:.4f}")
        print(f"Recall: {metrics['recall']:.4f}")
        print(f"F1-Score: {metrics['f1_score']:.4f}")
        print(f"Accuracy: {metrics['accuracy']:.4f}")
        print(f"\nConfusion Matrix:")
        print(f"  True Positives: {metrics['true_positives']}")
        print(f"  False Positives: {metrics['false_positives']}")
        print(f"  False Negatives: {metrics['false_negatives']}")
        print(f"  True Negatives: {metrics['true_negatives']}")
        print(f"\nConfidence Calibration:")
        print(
            f"  Expected Calibration Error: {calibration['expected_calibration_error']:.4f}"
        )
        print(f"  Bin Accuracies: {calibration['bin_accuracies']}")
        print(f"  Bin Confidences: {calibration['bin_confidences']}")
        print(f"  Bin Counts: {calibration['bin_counts']}")
        if validation_errors:
            print(f"\nValidation Errors: {len(validation_errors)}")
            for error in validation_errors[:5]:
                print(f"  - {error['test_id']}: {error['error']}")
        print(f"{'='*80}\n")

        assert (
            metrics["precision"] >= 0.75
        ), f"Precision {metrics['precision']:.4f} below target 0.75"
        assert (
            metrics["recall"] >= 0.70
        ), f"Recall {metrics['recall']:.4f} below target 0.70"
        assert (
            metrics["f1_score"] >= 0.72
        ), f"F1-score {metrics['f1_score']:.4f} below target 0.72"

    @pytest.mark.asyncio
    async def test_mergeability_json_schema_compliance(
        self,
        ground_truth_mergeability: Dict[str, Any],
        llm_analyzer_for_eval: Any,
        skip_if_no_api_key: None,
    ) -> None:
        """
        Test that all mergeability outputs conform to expected JSON schema.
        """
        test_cases = ground_truth_mergeability["test_cases"][:5]

        validation_results = []

        for test_case in test_cases:
            func1_code = test_case["test_function_1"]
            func2_code = test_case["test_function_2"]

            # Parse test code strings into proper objects
            test1_info, context1 = parse_test_code_to_objects(
                func1_code, f"{test_case['id']}_func1.py"
            )
            test2_info, _ = parse_test_code_to_objects(
                func2_code, f"{test_case['id']}_func2.py"
            )

            result = await llm_analyzer_for_eval.analyze_mergeability(
                test1_info, test2_info, context1
            )

            is_valid, error = JSONSchemaValidator.validate_mergeability_output(result)
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
    async def test_mergeability_confidence_threshold(
        self,
        ground_truth_mergeability: Dict[str, Any],
        llm_analyzer_for_eval: Any,
        skip_if_no_api_key: None,
    ) -> None:
        """
        Test that mergeability analysis returns appropriate confidence scores.

        All confidence scores should be > 0.7 as per the system's filtering threshold.
        """
        test_cases = ground_truth_mergeability["test_cases"][:5]

        confidences = []

        for test_case in test_cases:
            func1_code = test_case["test_function_1"]
            func2_code = test_case["test_function_2"]

            # Parse test code strings into proper objects
            test1_info, context1 = parse_test_code_to_objects(
                func1_code, f"{test_case['id']}_func1.py"
            )
            test2_info, _ = parse_test_code_to_objects(
                func2_code, f"{test_case['id']}_func2.py"
            )

            result = await llm_analyzer_for_eval.analyze_mergeability(
                test1_info, test2_info, context1
            )
            confidence = result.get("confidence", 0.0)
            confidences.append(confidence)

        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        min_confidence = min(confidences) if confidences else 0.0

        print(f"\nConfidence Statistics:")
        print(f"  Average: {avg_confidence:.4f}")
        print(f"  Minimum: {min_confidence:.4f}")
        print(f"  Maximum: {max(confidences) if confidences else 0.0:.4f}")

        assert (
            min_confidence >= 0.5
        ), f"Minimum confidence {min_confidence:.4f} below threshold 0.5"
        assert (
            avg_confidence >= 0.7
        ), f"Average confidence {avg_confidence:.4f} below threshold 0.7"
