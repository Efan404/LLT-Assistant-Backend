"""
Custom evaluation metrics for LLM test analysis.

Provides metrics for measuring precision, recall, F1-score, and confidence
calibration of LLM-generated test analysis results.
"""

from typing import Any, Dict, List, Optional

from sklearn.metrics import precision_recall_fscore_support


class EvaluationMetrics:
    """Custom metrics for evaluating LLM analysis quality."""

    @staticmethod
    def calculate_mergeability_metrics(
        predictions: List[bool], ground_truth: List[bool]
    ) -> Dict[str, float]:
        """
        Calculate precision, recall, and F1-score for mergeability predictions.

        Args:
            predictions: List of predicted mergeability values (True/False)
            ground_truth: List of ground truth mergeability values (True/False)

        Returns:
            Dictionary containing precision, recall, f1, and accuracy
        """
        if len(predictions) != len(ground_truth):
            raise ValueError("Predictions and ground truth must have same length")

        true_positives = sum(
            1 for pred, truth in zip(predictions, ground_truth) if pred and truth
        )
        false_positives = sum(
            1 for pred, truth in zip(predictions, ground_truth) if pred and not truth
        )
        false_negatives = sum(
            1 for pred, truth in zip(predictions, ground_truth) if not pred and truth
        )
        true_negatives = sum(
            1
            for pred, truth in zip(predictions, ground_truth)
            if not pred and not truth
        )

        precision = (
            true_positives / (true_positives + false_positives)
            if (true_positives + false_positives) > 0
            else 0.0
        )
        recall = (
            true_positives / (true_positives + false_negatives)
            if (true_positives + false_negatives) > 0
            else 0.0
        )
        f1 = (
            2 * (precision * recall) / (precision + recall)
            if (precision + recall) > 0
            else 0.0
        )
        accuracy = (
            (true_positives + true_negatives) / len(predictions)
            if len(predictions) > 0
            else 0.0
        )

        return {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1_score": round(f1, 4),
            "accuracy": round(accuracy, 4),
            "true_positives": true_positives,
            "false_positives": false_positives,
            "false_negatives": false_negatives,
            "true_negatives": true_negatives,
        }

    @staticmethod
    def calculate_issue_detection_metrics(
        predicted_issues: List[List[Dict[str, Any]]],
        ground_truth_issues: List[List[Dict[str, Any]]],
        match_by: str = "type",
    ) -> Dict[str, float]:
        """
        Calculate metrics for issue detection quality.

        Args:
            predicted_issues: List of predicted issues for each test case
            ground_truth_issues: List of ground truth issues for each test case
            match_by: Field to match issues by (default: "type")

        Returns:
            Dictionary containing precision, recall, and F1-score
        """
        if len(predicted_issues) != len(ground_truth_issues):
            raise ValueError("Predictions and ground truth must have same length")

        total_tp = 0
        total_fp = 0
        total_fn = 0

        for pred_list, truth_list in zip(predicted_issues, ground_truth_issues):
            pred_types = {issue[match_by] for issue in pred_list if match_by in issue}
            truth_types = {issue[match_by] for issue in truth_list if match_by in issue}

            total_tp += len(pred_types & truth_types)
            total_fp += len(pred_types - truth_types)
            total_fn += len(truth_types - pred_types)

        precision = (
            total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
        )
        recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
        f1 = (
            2 * (precision * recall) / (precision + recall)
            if (precision + recall) > 0
            else 0.0
        )

        return {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1_score": round(f1, 4),
            "true_positives": total_tp,
            "false_positives": total_fp,
            "false_negatives": total_fn,
        }

    @staticmethod
    def calculate_confidence_calibration(
        predictions: List[bool], confidences: List[float], ground_truth: List[bool]
    ) -> Dict[str, float]:
        """
        Calculate confidence calibration metrics.

        Measures how well the LLM's confidence scores align with actual accuracy.

        Args:
            predictions: List of predicted values
            confidences: List of confidence scores (0.0 to 1.0)
            ground_truth: List of ground truth values

        Returns:
            Dictionary with calibration metrics
        """
        if not (len(predictions) == len(confidences) == len(ground_truth)):
            raise ValueError("All inputs must have same length")

        bins = [0.0, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
        bin_accuracies = []
        bin_confidences = []
        bin_counts = []

        for i in range(len(bins) - 1):
            lower, upper = bins[i], bins[i + 1]
            indices = [
                idx
                for idx, conf in enumerate(confidences)
                if lower <= conf < upper or (i == len(bins) - 2 and conf == upper)
            ]

            if indices:
                bin_predictions = [predictions[idx] for idx in indices]
                bin_truths = [ground_truth[idx] for idx in indices]
                bin_confs = [confidences[idx] for idx in indices]

                accuracy = sum(
                    1
                    for pred, truth in zip(bin_predictions, bin_truths)
                    if pred == truth
                ) / len(indices)
                avg_confidence = sum(bin_confs) / len(bin_confs)

                bin_accuracies.append(accuracy)
                bin_confidences.append(avg_confidence)
                bin_counts.append(len(indices))
            else:
                bin_accuracies.append(0.0)
                bin_confidences.append(0.0)
                bin_counts.append(0)

        expected_calibration_error = (
            sum(
                count * abs(acc - conf)
                for acc, conf, count in zip(bin_accuracies, bin_confidences, bin_counts)
            )
            / sum(bin_counts)
            if sum(bin_counts) > 0
            else 0.0
        )

        return {
            "expected_calibration_error": round(expected_calibration_error, 4),
            "bin_accuracies": [round(acc, 4) for acc in bin_accuracies],
            "bin_confidences": [round(conf, 4) for conf in bin_confidences],
            "bin_counts": bin_counts,
        }

    @staticmethod
    def calculate_quality_distribution(
        quality_labels: List[str],
    ) -> Dict[str, Any]:
        """
        Calculate distribution of quality labels.

        Args:
            quality_labels: List of quality labels (e.g., "poor", "fair", "good", "excellent")

        Returns:
            Dictionary with distribution statistics
        """
        from collections import Counter

        counter = Counter(quality_labels)
        total = len(quality_labels)

        distribution = {
            label: {
                "count": count,
                "percentage": round((count / total) * 100, 2) if total > 0 else 0.0,
            }
            for label, count in counter.items()
        }

        return {
            "total_samples": total,
            "distribution": distribution,
            "unique_labels": len(counter),
        }

    @staticmethod
    def calculate_smell_detection_metrics_by_type(
        predicted_smells: List[List[Dict[str, Any]]],
        ground_truth_smells: List[List[Dict[str, Any]]],
    ) -> Dict[str, Dict[str, float]]:
        """
        Calculate precision/recall for each smell type separately.

        Args:
            predicted_smells: List of predicted smell lists for each test
            ground_truth_smells: List of ground truth smell lists for each test

        Returns:
            Dictionary mapping smell type to metrics
        """
        all_smell_types: set = set()
        for smell_list in ground_truth_smells:
            for smell in smell_list:
                if "type" in smell:
                    all_smell_types.add(smell["type"])

        metrics_by_type = {}

        for smell_type in all_smell_types:
            predicted_presence = []
            ground_truth_presence = []

            for pred_list, truth_list in zip(predicted_smells, ground_truth_smells):
                pred_has = any(smell.get("type") == smell_type for smell in pred_list)
                truth_has = any(smell.get("type") == smell_type for smell in truth_list)

                predicted_presence.append(pred_has)
                ground_truth_presence.append(truth_has)

            tp = sum(
                1
                for pred, truth in zip(predicted_presence, ground_truth_presence)
                if pred and truth
            )
            fp = sum(
                1
                for pred, truth in zip(predicted_presence, ground_truth_presence)
                if pred and not truth
            )
            fn = sum(
                1
                for pred, truth in zip(predicted_presence, ground_truth_presence)
                if not pred and truth
            )

            precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = (
                2 * (precision * recall) / (precision + recall)
                if (precision + recall) > 0
                else 0.0
            )

            metrics_by_type[smell_type] = {
                "precision": round(precision, 4),
                "recall": round(recall, 4),
                "f1_score": round(f1, 4),
                "support": tp + fn,
            }

        return metrics_by_type
