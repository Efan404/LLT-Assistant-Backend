"""
Evaluation tests for LLM test smell detection.

Tests the accuracy of LLM-based test smell detection against ground truth data.
"""

import json
from typing import Any, Dict, List

import pytest

from tests.evaluation.conftest import parse_test_code_to_objects
from tests.evaluation.metrics.custom_metrics import EvaluationMetrics
from tests.evaluation.metrics.json_validators import JSONSchemaValidator


@pytest.mark.llm_evaluation
@pytest.mark.requires_api_key
class TestSmellDetectionEvaluation:
    """Evaluation test suite for test smell detection."""

    @pytest.mark.asyncio
    async def test_smell_detection_accuracy(
        self,
        ground_truth_test_smells: Dict[str, Any],
        llm_analyzer_for_eval: Any,
        skip_if_no_api_key: None,
        evaluation_sample_size: int,
    ) -> None:
        """
        Test LLM test smell detection accuracy against ground truth.

        Measures precision, recall, and F1-score for detecting test smells.
        """
        test_cases = ground_truth_test_smells["test_cases"][:evaluation_sample_size]

        predicted_smells_list = []
        ground_truth_smells_list = []
        validation_errors = []

        print(f"\n{'='*80}")
        print(f"TEST SMELL DETECTION EVALUATION")
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

                result = await llm_analyzer_for_eval.analyze_test_smells(
                    test_func_info, context
                )

                is_valid, error = JSONSchemaValidator.validate_test_smell_output(result)
                if not is_valid:
                    validation_errors.append({"test_id": test_id, "error": error})
                    print(f"❌ Invalid JSON: {error}")
                    continue

                predicted_smells = result.get("smells", [])
                expected_smells = expected.get("smells", [])

                predicted_smells_list.append(predicted_smells)
                ground_truth_smells_list.append(expected_smells)

                smell_match = len(predicted_smells) == len(expected_smells)
                match_symbol = "✓" if smell_match else "✗"

                print(
                    f"{match_symbol} "
                    f"(detected: {len(predicted_smells)}, expected: {len(expected_smells)})"
                )

            except Exception as e:
                print(f"❌ Error: {str(e)}")
                validation_errors.append({"test_id": test_id, "error": str(e)})

        assert (
            len(predicted_smells_list) >= evaluation_sample_size * 0.8
        ), f"Too many failures: only {len(predicted_smells_list)}/{evaluation_sample_size} completed"

        overall_metrics = EvaluationMetrics.calculate_issue_detection_metrics(
            predicted_smells_list, ground_truth_smells_list, match_by="type"
        )

        smell_type_metrics = (
            EvaluationMetrics.calculate_smell_detection_metrics_by_type(
                predicted_smells_list, ground_truth_smells_list
            )
        )

        print(f"\n{'='*80}")
        print(f"TEST SMELL DETECTION EVALUATION RESULTS")
        print(f"{'='*80}")
        print(f"Samples evaluated: {len(predicted_smells_list)}")
        print(f"\nOverall Detection Metrics:")
        print(f"  Precision: {overall_metrics['precision']:.4f}")
        print(f"  Recall: {overall_metrics['recall']:.4f}")
        print(f"  F1-Score: {overall_metrics['f1_score']:.4f}")
        print(f"  True Positives: {overall_metrics['true_positives']}")
        print(f"  False Positives: {overall_metrics['false_positives']}")
        print(f"  False Negatives: {overall_metrics['false_negatives']}")

        if smell_type_metrics:
            print(f"\nMetrics by Smell Type:")
            for smell_type, metrics in sorted(smell_type_metrics.items()):
                if metrics["support"] > 0:
                    print(f"  {smell_type}:")
                    print(f"    Precision: {metrics['precision']:.4f}")
                    print(f"    Recall: {metrics['recall']:.4f}")
                    print(f"    F1-Score: {metrics['f1_score']:.4f}")
                    print(f"    Support: {metrics['support']}")

        if validation_errors:
            print(f"\nValidation Errors: {len(validation_errors)}")
            for error in validation_errors[:5]:
                print(f"  - {error['test_id']}: {error['error']}")
        print(f"{'='*80}\n")

        assert (
            overall_metrics["precision"] >= 0.70
        ), f"Precision {overall_metrics['precision']:.4f} below target 0.70"
        assert (
            overall_metrics["recall"] >= 0.65
        ), f"Recall {overall_metrics['recall']:.4f} below target 0.65"
        assert (
            overall_metrics["f1_score"] >= 0.67
        ), f"F1-score {overall_metrics['f1_score']:.4f} below target 0.67"

    @pytest.mark.asyncio
    async def test_smell_detection_json_schema_compliance(
        self,
        ground_truth_test_smells: Dict[str, Any],
        llm_analyzer_for_eval: Any,
        skip_if_no_api_key: None,
    ) -> None:
        """
        Test that all test smell outputs conform to expected JSON schema.
        """
        test_cases = ground_truth_test_smells["test_cases"][:5]

        validation_results = []

        for test_case in test_cases:
            test_function_code = test_case["test_function"]

            # Parse test code string into proper objects
            test_func_info, context = parse_test_code_to_objects(
                test_function_code, f"{test_case['id']}.py"
            )

            result = await llm_analyzer_for_eval.analyze_test_smells(
                test_func_info, context
            )

            is_valid, error = JSONSchemaValidator.validate_test_smell_output(result)
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
    async def test_smell_detection_confidence_scores(
        self,
        ground_truth_test_smells: Dict[str, Any],
        llm_analyzer_for_eval: Any,
        skip_if_no_api_key: None,
    ) -> None:
        """
        Test that test smell detection returns appropriate confidence scores.
        """
        test_cases = ground_truth_test_smells["test_cases"][:5]

        all_confidences = []

        for test_case in test_cases:
            test_function_code = test_case["test_function"]

            # Parse test code string into proper objects
            test_func_info, context = parse_test_code_to_objects(
                test_function_code, f"{test_case['id']}.py"
            )

            result = await llm_analyzer_for_eval.analyze_test_smells(
                test_func_info, context
            )

            confidence = result.get("confidence", 0.0)
            all_confidences.append(confidence)

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

    @pytest.mark.asyncio
    async def test_smell_detection_no_false_positives_on_clean_code(
        self,
        ground_truth_test_smells: Dict[str, Any],
        llm_analyzer_for_eval: Any,
        skip_if_no_api_key: None,
    ) -> None:
        """
        Test that clean test code doesn't trigger false positive smell detections.
        """
        test_cases = [
            tc
            for tc in ground_truth_test_smells["test_cases"]
            if len(tc["expected_output"]["smells"]) == 0
        ][:5]

        if not test_cases:
            pytest.skip("No clean test cases available in ground truth")

        false_positives = 0
        total_tested = 0

        for test_case in test_cases:
            test_function_code = test_case["test_function"]

            # Parse test code string into proper objects
            test_func_info, context = parse_test_code_to_objects(
                test_function_code, f"{test_case['id']}.py"
            )

            result = await llm_analyzer_for_eval.analyze_test_smells(
                test_func_info, context
            )

            detected_smells = result.get("smells", [])
            if detected_smells:
                false_positives += len(detected_smells)

            total_tested += 1

        false_positive_rate = (
            false_positives / total_tested if total_tested > 0 else 0.0
        )

        print(f"\nFalse Positive Rate on Clean Code:")
        print(f"  Total clean tests: {total_tested}")
        print(f"  False positives: {false_positives}")
        print(f"  FP Rate: {false_positive_rate:.4f}")

        assert (
            false_positive_rate <= 0.2
        ), f"False positive rate {false_positive_rate:.4f} exceeds threshold 0.2"
