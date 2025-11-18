"""
Evaluation report generator.

Generates comprehensive reports of LLM evaluation metrics and performance.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class EvaluationReportGenerator:
    """Generates evaluation reports for LLM analysis quality."""

    @staticmethod
    def generate_markdown_report(
        mergeability_metrics: Optional[Dict[str, Any]] = None,
        assertion_metrics: Optional[Dict[str, Any]] = None,
        smell_metrics: Optional[Dict[str, Any]] = None,
        output_path: Optional[Path] = None,
    ) -> str:
        """
        Generate a comprehensive Markdown evaluation report.

        Args:
            mergeability_metrics: Metrics from mergeability evaluation
            assertion_metrics: Metrics from assertion quality evaluation
            smell_metrics: Metrics from test smell detection evaluation
            output_path: Optional path to save the report

        Returns:
            Markdown formatted report as string
        """
        report = []
        report.append("# LLM Test Analysis Evaluation Report\n")
        report.append(
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        )
        report.append("---\n\n")

        if mergeability_metrics:
            report.append("## Test Mergeability Analysis\n\n")
            report.append("### Overall Metrics\n\n")
            report.append("| Metric | Value |\n")
            report.append("|--------|-------|\n")
            report.append(
                f"| Precision | {mergeability_metrics.get('precision', 0):.4f} |\n"
            )
            report.append(f"| Recall | {mergeability_metrics.get('recall', 0):.4f} |\n")
            report.append(
                f"| F1-Score | {mergeability_metrics.get('f1_score', 0):.4f} |\n"
            )
            report.append(
                f"| Accuracy | {mergeability_metrics.get('accuracy', 0):.4f} |\n"
            )
            report.append("\n### Confusion Matrix\n\n")
            report.append("| Metric | Count |\n")
            report.append("|--------|-------|\n")
            report.append(
                f"| True Positives | {mergeability_metrics.get('true_positives', 0)} |\n"
            )
            report.append(
                f"| False Positives | {mergeability_metrics.get('false_positives', 0)} |\n"
            )
            report.append(
                f"| False Negatives | {mergeability_metrics.get('false_negatives', 0)} |\n"
            )
            report.append(
                f"| True Negatives | {mergeability_metrics.get('true_negatives', 0)} |\n"
            )
            report.append("\n---\n\n")

        if assertion_metrics:
            report.append("## Assertion Quality Analysis\n\n")
            report.append("### Overall Metrics\n\n")
            report.append("| Metric | Value |\n")
            report.append("|--------|-------|\n")
            report.append(
                f"| Precision | {assertion_metrics.get('precision', 0):.4f} |\n"
            )
            report.append(f"| Recall | {assertion_metrics.get('recall', 0):.4f} |\n")
            report.append(
                f"| F1-Score | {assertion_metrics.get('f1_score', 0):.4f} |\n"
            )
            report.append(
                f"| Quality Accuracy | {assertion_metrics.get('quality_accuracy', 0):.4f} |\n"
            )
            report.append("\n### Issue Detection\n\n")
            report.append("| Metric | Count |\n")
            report.append("|--------|-------|\n")
            report.append(
                f"| True Positives | {assertion_metrics.get('true_positives', 0)} |\n"
            )
            report.append(
                f"| False Positives | {assertion_metrics.get('false_positives', 0)} |\n"
            )
            report.append(
                f"| False Negatives | {assertion_metrics.get('false_negatives', 0)} |\n"
            )

            if "quality_distribution" in assertion_metrics:
                report.append("\n### Quality Distribution\n\n")
                report.append("| Quality Label | Count | Percentage |\n")
                report.append("|---------------|-------|------------|\n")
                for label, stats in assertion_metrics["quality_distribution"].items():
                    report.append(
                        f"| {label} | {stats['count']} | {stats['percentage']:.1f}% |\n"
                    )

            report.append("\n---\n\n")

        if smell_metrics:
            report.append("## Test Smell Detection\n\n")
            report.append("### Overall Metrics\n\n")
            report.append("| Metric | Value |\n")
            report.append("|--------|-------|\n")
            report.append(f"| Precision | {smell_metrics.get('precision', 0):.4f} |\n")
            report.append(f"| Recall | {smell_metrics.get('recall', 0):.4f} |\n")
            report.append(f"| F1-Score | {smell_metrics.get('f1_score', 0):.4f} |\n")
            report.append("\n### Detection Counts\n\n")
            report.append("| Metric | Count |\n")
            report.append("|--------|-------|\n")
            report.append(
                f"| True Positives | {smell_metrics.get('true_positives', 0)} |\n"
            )
            report.append(
                f"| False Positives | {smell_metrics.get('false_positives', 0)} |\n"
            )
            report.append(
                f"| False Negatives | {smell_metrics.get('false_negatives', 0)} |\n"
            )

            if "by_type" in smell_metrics:
                report.append("\n### Metrics by Smell Type\n\n")
                report.append(
                    "| Smell Type | Precision | Recall | F1-Score | Support |\n"
                )
                report.append(
                    "|-----------|-----------|--------|----------|--------|\n"
                )
                for smell_type, metrics in sorted(smell_metrics["by_type"].items()):
                    report.append(
                        f"| {smell_type} | {metrics['precision']:.4f} | "
                        f"{metrics['recall']:.4f} | {metrics['f1_score']:.4f} | "
                        f"{metrics['support']} |\n"
                    )

            report.append("\n---\n\n")

        report.append("## Summary\n\n")
        report.append("### Target Metrics\n\n")
        report.append(
            "| Analysis Type | Precision Target | Recall Target | F1 Target |\n"
        )
        report.append(
            "|--------------|------------------|---------------|----------|\n"
        )
        report.append("| Mergeability | ≥ 0.75 | ≥ 0.70 | ≥ 0.72 |\n")
        report.append("| Assertion Quality | ≥ 0.70 | ≥ 0.65 | ≥ 0.67 |\n")
        report.append("| Test Smells | ≥ 0.70 | ≥ 0.65 | ≥ 0.67 |\n")
        report.append("\n")

        report_content = "".join(report)

        if output_path:
            output_path.write_text(report_content)

        return report_content

    @staticmethod
    def save_baseline_metrics(metrics: Dict[str, Any], output_path: Path) -> None:
        """
        Save baseline metrics to JSON file.

        Args:
            metrics: Dictionary containing all evaluation metrics
            output_path: Path to save the baseline metrics
        """
        baseline = {
            "generated_at": datetime.now().isoformat(),
            "metrics": metrics,
        }

        with open(output_path, "w") as f:
            json.dump(baseline, f, indent=2)

    @staticmethod
    def compare_with_baseline(
        current_metrics: Dict[str, Any], baseline_path: Path
    ) -> Dict[str, Any]:
        """
        Compare current metrics with baseline.

        Args:
            current_metrics: Current evaluation metrics
            baseline_path: Path to baseline metrics file

        Returns:
            Dictionary with comparison results
        """
        if not baseline_path.exists():
            return {"baseline_exists": False, "message": "No baseline found"}

        with open(baseline_path, "r") as f:
            baseline = json.load(f)

        baseline_metrics = baseline.get("metrics", {})

        comparison = {
            "baseline_exists": True,
            "baseline_date": baseline.get("generated_at"),
            "improvements": [],
            "regressions": [],
        }

        for category in ["mergeability", "assertion_quality", "test_smells"]:
            if category in current_metrics and category in baseline_metrics:
                current = current_metrics[category]
                past = baseline_metrics[category]

                for metric in ["precision", "recall", "f1_score"]:
                    if metric in current and metric in past:
                        diff = current[metric] - past[metric]
                        if abs(diff) > 0.01:
                            entry = {
                                "category": category,
                                "metric": metric,
                                "current": current[metric],
                                "baseline": past[metric],
                                "diff": round(diff, 4),
                            }
                            if diff > 0:
                                comparison["improvements"].append(entry)
                            else:
                                comparison["regressions"].append(entry)

        return comparison
