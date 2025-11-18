"""Analysis metrics calculation.

This class handles the calculation of analysis metrics such as
test counts, issue counts, and timing information.
"""

from typing import List

from app.analyzers.ast_parser import ParsedTestFile
from app.api.v1.schemas import AnalysisMetrics, Issue


class MetricsCalculator:
    """Calculates analysis metrics."""

    def calculate_metrics(
        self,
        parsed_files: List[ParsedTestFile],
        issues: List[Issue],
        start_time: float,
    ) -> AnalysisMetrics:
        """
        Calculate analysis metrics.

        Args:
            parsed_files: List of parsed test files
            issues: List of detected issues
            start_time: Analysis start time (from time.time())

        Returns:
            Analysis metrics
        """
        import time

        total_tests = self._count_total_tests(parsed_files)
        analysis_time_ms = int((time.time() - start_time) * 1000)

        return AnalysisMetrics(
            total_tests=total_tests,
            issues_count=len(issues),
            analysis_time_ms=analysis_time_ms,
        )

    def _count_total_tests(self, parsed_files: List[ParsedTestFile]) -> int:
        """
        Count total number of test functions across all files.

        Args:
            parsed_files: List of parsed test files

        Returns:
            Total number of test functions
        """
        total_tests = 0

        for parsed_file in parsed_files:
            # Count module-level test functions
            total_tests += len(parsed_file.test_functions)

            # Count test methods in test classes
            for test_class in parsed_file.test_classes:
                total_tests += len(test_class.methods)

        return total_tests
