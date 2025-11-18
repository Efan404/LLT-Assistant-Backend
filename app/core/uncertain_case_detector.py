"""Detector for uncertain test cases that require LLM analysis.

This class encapsulates the heuristics for identifying test functions
that need deeper LLM-based analysis in hybrid mode.
"""

from typing import List

from app.analyzers.ast_parser import ParsedTestFile, TestFunctionInfo
from app.core.constants import MIN_ASSERTIONS_FOR_COMPLEX, MIN_DECORATORS_FOR_UNUSUAL


class UncertainCaseDetector:
    """Identifies test functions that need LLM analysis in hybrid mode."""

    def identify_uncertain_cases(
        self, parsed_file: ParsedTestFile
    ) -> List[TestFunctionInfo]:
        """
        Identify test functions that need LLM analysis in hybrid mode.

        Criteria:
        - Functions with similar names (potential merge candidates)
        - Functions with complex assertions
        - Functions with unusual patterns

        Args:
            parsed_file: Parsed test file to analyze

        Returns:
            List of test functions that need LLM analysis
        """
        uncertain_functions = []

        # Get all test functions
        all_functions = list(parsed_file.test_functions)
        for test_class in parsed_file.test_classes:
            all_functions.extend(test_class.methods)

        # Find functions with similar names (potential merge candidates)
        for i, func1 in enumerate(all_functions):
            for func2 in all_functions[i + 1 :]:
                if self._are_similar_functions(func1, func2):
                    if func1 not in uncertain_functions:
                        uncertain_functions.append(func1)
                    if func2 not in uncertain_functions:
                        uncertain_functions.append(func2)

        # Find functions with complex assertions
        for func in all_functions:
            if self._has_complex_assertions(func) and func not in uncertain_functions:
                uncertain_functions.append(func)

        # Find functions with unusual patterns
        for func in all_functions:
            if self._has_unusual_patterns(func) and func not in uncertain_functions:
                uncertain_functions.append(func)

        return uncertain_functions

    def _are_similar_functions(
        self, func1: TestFunctionInfo, func2: TestFunctionInfo
    ) -> bool:
        """
        Check if two functions have similar names.

        Args:
            func1: First test function
            func2: Second test function

        Returns:
            True if functions have similar names
        """
        name1_parts = func1.name.split("_")
        name2_parts = func2.name.split("_")

        # If they share most words, they might be similar
        common_parts = set(name1_parts) & set(name2_parts)
        min_parts = min(len(name1_parts), len(name2_parts))

        return len(common_parts) >= min_parts - 1 and min_parts > 1

    def _has_complex_assertions(self, test_func: TestFunctionInfo) -> bool:
        """
        Check if function has complex assertions.

        Args:
            test_func: Test function to check

        Returns:
            True if function has complex assertions
        """
        # Heuristic: more than threshold assertions or assertions with complex expressions
        if len(test_func.assertions) > MIN_ASSERTIONS_FOR_COMPLEX:
            return True

        for assertion in test_func.assertions:
            if assertion.assertion_type == "other":
                return True

        return False

    def _has_unusual_patterns(self, test_func: TestFunctionInfo) -> bool:
        """
        Check if function has unusual patterns that might indicate code smells.

        Args:
            test_func: Test function to check

        Returns:
            True if function has unusual patterns
        """
        source_lower = test_func.source_code.lower()

        # Check for timing-related code
        if "time.sleep" in source_lower or "asyncio.sleep" in source_lower:
            return True

        # Check for global state modification
        if "global " in source_lower:
            return True

        # Check for many mock decorators
        decorator_count = len(test_func.decorators)
        if decorator_count > MIN_DECORATORS_FOR_UNUSUAL:
            return True

        return False
