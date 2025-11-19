"""
LLM-based analysis agent for detecting complex test quality issues.

This module provides the LLMAnalysisAgent which uses large language models
to perform deep analysis of test code, detecting issues that require
semantic understanding.
"""

import logging
from typing import List

from app.agents.base import BaseAgent
from app.agents.context import AgentContext, AgentResult
from app.agents.llm import get_llm_client
from app.api.v1.schemas import Issue
from app.core.llm_analyzer import LLMAnalyzer
from app.core.uncertain_case_detector import UncertainCaseDetector

logger = logging.getLogger(__name__)


class LLMAnalysisAgent(BaseAgent):
    """
    Agent responsible for LLM-based test quality analysis.

    This agent uses large language models to detect subtle test quality
    issues that require semantic understanding, such as weak assertions,
    test smells, and merge opportunities.
    """

    def __init__(self, name: str = "llm_analysis", config: dict = None):
        """
        Initialize the LLM analysis agent.

        Args:
            name: Unique name for this agent
            config: Optional configuration overrides
        """
        super().__init__(name, config)
        self.uncertain_detector = UncertainCaseDetector()

    async def execute(self, context: AgentContext) -> AgentResult:
        """
        Execute LLM-based analysis on parsed files.

        This method analyzes test functions using LLMs, intelligently
        selecting which functions need deep analysis based on the mode.

        Args:
            context: Agent context containing parsed files and execution plan

        Returns:
            AgentResult with detected issues and statistics
        """
        # Check if LLM analysis should run
        if not self._should_run(context):
            self.logger.info(
                f"Skipping LLM analysis (mode={context.mode}, "
                f"run_llm={context.execution_plan.get('run_llm', False)})"
            )
            return AgentResult(
                success=True,
                data={"skipped": True, "reason": "not enabled for this mode"},
                errors=[],
                warnings=[],
                metadata={"agent": self.name, "stage": "llm_analysis"},
                execution_time_ms=0,
            )

        self.logger.info(
            f"Running LLM analysis on {len(context.parsed_files)} files "
            f"in mode '{context.mode}'"
        )

        # Initialize LLM client and analyzer
        llm_client = get_llm_client()
        llm_analyzer = LLMAnalyzer(llm_client)

        all_issues: List[Issue] = []
        errors: List[str] = []
        warnings: List[str] = []
        tests_analyzed = 0
        tests_skipped = 0

        # Analyze each parsed file
        for parsed_file in context.parsed_files:
            try:
                # Skip files with syntax errors
                if parsed_file.has_syntax_errors:
                    warning_msg = (
                        f"Skipping LLM analysis for {parsed_file.file_path} "
                        f"due to syntax errors"
                    )
                    self.logger.warning(warning_msg)
                    warnings.append(warning_msg)
                    continue

                # Determine which test functions to analyze
                functions_to_analyze = self._select_functions_for_analysis(
                    parsed_file, context
                )

                tests_skipped += self._count_total_tests(parsed_file) - len(
                    functions_to_analyze
                )

                # Analyze selected functions
                for test_func in functions_to_analyze:
                    # Analyze assertion quality
                    assertion_issues = await llm_analyzer.analyze_assertion_quality(
                        test_func, parsed_file
                    )
                    all_issues.extend(assertion_issues)

                    # Analyze test smells
                    smell_issues = await llm_analyzer.analyze_test_smells(
                        test_func, parsed_file
                    )
                    all_issues.extend(smell_issues)

                    tests_analyzed += 1

                    self.logger.debug(
                        f"LLM analyzed {test_func.name}: "
                        f"{len(assertion_issues)} assertion issues, "
                        f"{len(smell_issues)} smell issues"
                    )

            except Exception as e:
                error_msg = f"Failed to analyze {parsed_file.file_path}: {str(e)}"
                self.logger.error(error_msg)
                errors.append(error_msg)

        # Store results in context
        context.llm_issues = all_issues

        # Calculate statistics
        issue_counts_by_severity = {"error": 0, "warning": 0, "info": 0}
        issue_counts_by_type = {}

        for issue in all_issues:
            issue_counts_by_severity[issue.severity] = (
                issue_counts_by_severity.get(issue.severity, 0) + 1
            )
            issue_counts_by_type[issue.type] = (
                issue_counts_by_type.get(issue.type, 0) + 1
            )

        data = {
            "issue_count": len(all_issues),
            "tests_analyzed": tests_analyzed,
            "tests_skipped": tests_skipped,
            "by_severity": issue_counts_by_severity,
            "by_type": issue_counts_by_type,
        }

        success = len(errors) == 0

        self.logger.info(
            f"LLM analysis completed: {len(all_issues)} issues found "
            f"from {tests_analyzed} tests analyzed "
            f"({issue_counts_by_severity['error']} errors, "
            f"{issue_counts_by_severity['warning']} warnings, "
            f"{issue_counts_by_severity['info']} info)"
        )

        return AgentResult(
            success=success,
            data=data,
            errors=errors,
            warnings=warnings,
            metadata={"agent": self.name, "stage": "llm_analysis"},
            execution_time_ms=0,
        )

    def _should_run(self, context: AgentContext) -> bool:
        """
        Determine if LLM analysis should run based on mode and execution plan.

        Args:
            context: Agent context

        Returns:
            True if LLM analysis should run, False otherwise
        """
        # Check execution plan first (set by strategy planning agent)
        if context.execution_plan:
            return context.execution_plan.get("run_llm", False)

        # Fall back to checking mode directly
        return context.mode in {"llm-only", "hybrid"}

    def _select_functions_for_analysis(
        self, parsed_file, context: AgentContext
    ) -> list:
        """
        Select which test functions need LLM analysis.

        In hybrid mode, only uncertain cases are analyzed.
        In llm-only mode, all functions are analyzed.

        Args:
            parsed_file: Parsed test file
            context: Agent context

        Returns:
            List of test functions to analyze
        """
        # Get all test functions
        all_functions = list(parsed_file.test_functions)
        for test_class in parsed_file.test_classes:
            all_functions.extend(test_class.methods)

        # In llm-only mode, analyze all functions
        if context.mode == "llm-only":
            return all_functions

        # In hybrid mode, only analyze uncertain cases
        if context.mode == "hybrid":
            uncertain_functions = self.uncertain_detector.identify_uncertain_cases(
                parsed_file
            )
            self.logger.debug(
                f"Identified {len(uncertain_functions)}/{len(all_functions)} "
                f"uncertain cases in {parsed_file.file_path}"
            )
            return uncertain_functions

        # Default: analyze all
        return all_functions

    def _count_total_tests(self, parsed_file) -> int:
        """
        Count total number of test functions in a file.

        Args:
            parsed_file: Parsed test file

        Returns:
            Total number of test functions
        """
        count = len(parsed_file.test_functions)
        for test_class in parsed_file.test_classes:
            count += len(test_class.methods)
        return count

    async def validate_input(self, context: AgentContext) -> List[str]:
        """
        Validate that parsed files are available.

        Args:
            context: Agent context to validate

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        # Only validate if we should run
        if not self._should_run(context):
            return errors

        if not hasattr(context, "parsed_files"):
            errors.append("Context missing 'parsed_files' attribute")
        elif not context.parsed_files:
            errors.append("No parsed files available for LLM analysis")

        return errors

    async def validate_output(
        self, result: AgentResult, context: AgentContext
    ) -> List[str]:
        """
        Validate output from LLM analysis.

        Args:
            result: Result from execute()
            context: Agent context for reference

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        # Skip validation if agent was skipped
        if result.data and result.data.get("skipped"):
            return errors

        # Verify context was updated
        if result.success and not hasattr(context, "llm_issues"):
            errors.append("LLM analysis succeeded but context.llm_issues not set")

        # Verify data contains expected fields
        if result.data and not result.data.get("skipped"):
            expected_fields = {"issue_count", "tests_analyzed"}
            missing_fields = expected_fields - set(result.data.keys())
            if missing_fields:
                errors.append(
                    f"Result data missing fields: {', '.join(missing_fields)}"
                )

        return errors
