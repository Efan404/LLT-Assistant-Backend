"""Main analysis orchestrator for test code quality.

This module provides the main TestAnalyzer class that orchestrates
the entire analysis pipeline using a clean separation of concerns.
"""

import asyncio
import logging
import time
import uuid
from typing import Dict, List, Optional

from app.analyzers.ast_parser import ParsedTestFile, parse_test_file
from app.api.v1.schemas import (
    AnalyzeResponse,
    FileInput,
    ImpactAnalysisResponse,
    ImpactItem,
)
from app.core.issue_aggregator import IssueAggregator
from app.core.metrics_calculator import MetricsCalculator
from app.core.protocols import LLMAnalyzerProtocol, RuleEngineProtocol
from app.core.strategies import get_strategy

logger = logging.getLogger(__name__)


class TestAnalyzer:
    """Main orchestrator for test analysis.

    This class follows the Single Responsibility Principle by delegating
    specific concerns to specialized components:
    - File parsing: handled by parse_test_file
    - Analysis strategy: handled by AnalysisStrategy implementations
    - Issue aggregation: handled by IssueAggregator
    - Metrics calculation: handled by MetricsCalculator

    The analyzer's single responsibility is high-level orchestration.
    """

    def __init__(
        self,
        rule_engine: RuleEngineProtocol,
        llm_analyzer: LLMAnalyzerProtocol,
        issue_aggregator: Optional[IssueAggregator] = None,
        metrics_calculator: Optional[MetricsCalculator] = None,
    ):
        """
        Initialize the test analyzer.

        Args:
            rule_engine: Rule-based analysis engine
            llm_analyzer: LLM-based analyzer
            issue_aggregator: Issue aggregation service (uses default if None)
            metrics_calculator: Metrics calculation service (uses default if None)
        """
        self.rule_engine = rule_engine
        self.llm_analyzer = llm_analyzer
        self.issue_aggregator = issue_aggregator or IssueAggregator()
        self.metrics_calculator = metrics_calculator or MetricsCalculator()

    async def analyze_files(
        self,
        files: List[FileInput],
        mode: str = "hybrid",
        config: Optional[Dict] = None,
    ) -> AnalyzeResponse:
        """
        Analyze test files and return detected issues.

        This method orchestrates the analysis pipeline:
        1. Parse files into AST
        2. Execute analysis strategy based on mode
        3. Aggregate and deduplicate issues
        4. Calculate metrics

        Args:
            files: List of test files to analyze
            mode: "rules-only" | "llm-only" | "hybrid"
            config: Optional configuration overrides

        Returns:
            AnalyzeResponse with issues and metrics

        Raises:
            ValueError: If mode is invalid or files are empty
        """
        if not files:
            raise ValueError("No files provided for analysis")

        start_time = time.time()
        analysis_id = str(uuid.uuid4())

        logger.info(
            f"Starting analysis {analysis_id} with mode: {mode}, files: {len(files)}"
        )

        try:
            # Step 1: Parse all files in parallel
            parsed_files = await self._parse_files_parallel(files)

            # Step 2: Get and execute analysis strategy
            strategy = get_strategy(mode)
            all_issues = await strategy.analyze(
                parsed_files, self.rule_engine, self.llm_analyzer
            )

            # Step 3: Calculate metrics
            metrics = self.metrics_calculator.calculate_metrics(
                parsed_files, all_issues, start_time
            )

            logger.info(
                f"Analysis {analysis_id} completed: {len(all_issues)} issues found "
                f"in {metrics.analysis_time_ms}ms"
            )

            return AnalyzeResponse(
                analysis_id=analysis_id, issues=all_issues, metrics=metrics
            )

        except Exception as e:
            logger.error(f"Analysis {analysis_id} failed: {e}")
            raise

    async def _parse_files_parallel(
        self, files: List[FileInput]
    ) -> List[ParsedTestFile]:
        """
        Parse multiple files in parallel for improved performance.

        Args:
            files: List of file inputs to parse

        Returns:
            List of successfully parsed test files
        """
        tasks = []
        for file_input in files:
            task = asyncio.create_task(self._parse_file_safe(file_input))
            tasks.append(task)

        parsed_files = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out failed parses and exceptions
        valid_files = []
        for i, result in enumerate(parsed_files):
            if isinstance(result, Exception):
                logger.error(f"Failed to parse file {files[i].path}: {result}")
            elif result.has_syntax_errors:
                logger.warning(
                    f"File {files[i].path} has syntax errors: {result.syntax_error_message}"
                )
                valid_files.append(result)
            else:
                valid_files.append(result)

        return valid_files

    async def _parse_file_safe(self, file_input: FileInput) -> ParsedTestFile:
        """
        Safely parse a single file with error handling.

        Args:
            file_input: File input to parse

        Returns:
            Parsed test file (with error flags set if parsing failed)
        """
        try:
            return parse_test_file(file_input.path, file_input.content)
        except Exception as e:
            logger.error(f"Error parsing file {file_input.path}: {e}")
            # Return a file with syntax errors marked
            return ParsedTestFile(
                file_path=file_input.path,
                imports=[],
                fixtures=[],
                test_functions=[],
                test_classes=[],
                has_syntax_errors=True,
                syntax_error_message=str(e),
            )

    async def close(self) -> None:
        """Close the analyzer and cleanup resources."""
        await self.llm_analyzer.close()


class ImpactAnalyzer:
    """Impact analysis analyzer for determining affected test files.

    This analyzer takes project context (changed files and related tests)
    and determines which tests may be impacted by the changes.
    """

    def __init__(
        self,
        rule_engine: RuleEngineProtocol,
        llm_analyzer: LLMAnalyzerProtocol,
    ):
        """
        Initialize the impact analyzer.

        Args:
            rule_engine: Rule-based analysis engine
            llm_analyzer: LLM-based analyzer (for future enhancement)
        """
        self.rule_engine = rule_engine
        self.llm_analyzer = llm_analyzer

    def analyze_impact(
        self, files_changed: List[Dict[str, str]], related_tests: List[str]
    ) -> ImpactAnalysisResponse:
        """
        Analyze the impact of file changes on test files.

        This method uses a combination of heuristics and rules to determine
        which tests are impacted by the changes.

        Args:
            files_changed: List of dictionaries with 'path' and 'change_type'
            related_tests: List of test file paths that may be related

        Returns:
            ImpactAnalysisResponse with impact assessment

        Raises:
            ValueError: If files_changed is empty
        """
        if not files_changed:
            raise ValueError("files_changed cannot be empty")

        # Basic validation
        changed_paths = [f.get("path", "") for f in files_changed]
        if not any(changed_paths):
            raise ValueError("files_changed paths cannot be empty")

        logger.info(
            f"Analyzing impact for {len(files_changed)} changed files and "
            f"{len(related_tests)} related tests"
        )

        try:
            # For now, use simple heuristics. In the future, this could use:
            # 1. Rule engine for pattern matching
            # 2. LLM for semantic analysis
            # 3. Import graph analysis
            impacted_tests = self._calculate_impact_simple(changed_paths, related_tests)

            # Determine overall severity and suggested action
            severity, suggested_action = self._determine_severity_and_action(
                impacted_tests
            )

            logger.info(
                f"Impact analysis completed: {len(impacted_tests)} tests impacted, "
                f"severity={severity}, action={suggested_action}"
            )

            return ImpactAnalysisResponse(
                impacted_tests=impacted_tests,
                severity=severity,
                suggested_action=suggested_action,
            )

        except Exception as e:
            logger.error(f"Impact analysis failed: {e}")
            raise

    def _calculate_impact_simple(
        self, changed_paths: List[str], related_tests: List[str]
    ) -> List[ImpactItem]:
        """
        Simple heuristic-based impact calculation.

        This is a placeholder implementation that will be enhanced later
        with rule engine and LLM capabilities.

        Args:
            changed_paths: List of changed file paths
            related_tests: List of potentially related test files

        Returns:
            List of ImpactItem with impact assessments
        """
        impacted_tests = []
        # Use a set for O(1) lookup to avoid O(n^2) complexity
        processed_test_paths = set()

        # Simple heuristics:
        # 1. If a test file is in the changed files, it's definitely impacted
        # 2. If a test file name matches a changed file (e.g., test_*.py vs *.py), it's likely impacted
        # 3. If no clear relationship, assign low impact

        # Combine changed paths with related tests for analysis
        all_test_candidates = list(related_tests)

        for changed_path in changed_paths:
            # Extract filename without extension
            changed_name = changed_path.split("/")[-1].split(".")[0]

            # If this is a test file, mark it as impacted
            if "test" in changed_path.lower() or changed_path.endswith(("_test.py",)):
                # Also check for test_*.py pattern using startswith
                test_file_pattern = (
                    changed_path.lower().endswith(("_test.py",))
                    or changed_path.lower().startswith("test_")
                    or "_test" in changed_path.lower()
                )
                if test_file_pattern or "test" in changed_path.lower():
                    impacted_tests.append(
                        ImpactItem(
                            test_path=changed_path,
                            impact_score=1.0,
                            severity="high",
                            reasons=["Test file was directly modified"],
                        )
                    )
                    processed_test_paths.add(changed_path)
                    continue

            # Look for potentially related test files
            for test_path in all_test_candidates:
                if test_path not in processed_test_paths:
                    test_name = test_path.split("/")[-1].split(".")[0]

                    # Check for naming patterns (e.g., module.py -> test_module.py)
                    if (
                        test_name == f"test_{changed_name}"
                        or test_name == f"{changed_name}_test"
                        or changed_name in test_name
                    ):
                        impacted_tests.append(
                            ImpactItem(
                                test_path=test_path,
                                impact_score=0.8,
                                severity="high",
                                reasons=[
                                    f"Test file name matches changed file: {changed_path}"
                                ],
                            )
                        )
                        processed_test_paths.add(test_path)
                        # Add break to prevent checking this test file again on next iteration
                        break
                    elif (
                        changed_name.replace("_", "").lower()
                        in test_name.replace("_", "").lower()
                    ):
                        impacted_tests.append(
                            ImpactItem(
                                test_path=test_path,
                                impact_score=0.5,
                                severity="medium",
                                reasons=[
                                    f"Test file may be related to changed file: {changed_path}"
                                ],
                            )
                        )
                        processed_test_paths.add(test_path)
                        # Add break to prevent duplicate entries
                        break

        # Add any remaining related tests with low impact
        for test_path in related_tests:
            if test_path not in processed_test_paths:
                impacted_tests.append(
                    ImpactItem(
                        test_path=test_path,
                        impact_score=0.1,
                        severity="low",
                        reasons=["Test file in related tests but no clear connection"],
                    )
                )
                processed_test_paths.add(test_path)

        return impacted_tests

    def _determine_severity_and_action(
        self, impacted_tests: List[ImpactItem]
    ) -> tuple[str, str]:
        """
        Determine overall severity and suggested action based on impacts.

        Args:
            impacted_tests: List of impact items

        Returns:
            Tuple of (severity, suggested_action)
        """
        if not impacted_tests:
            return "none", "no-action"

        # Check for high severity impacts
        high_impact_tests = [it for it in impacted_tests if it.severity == "high"]
        medium_impact_tests = [it for it in impacted_tests if it.severity == "medium"]

        if len(high_impact_tests) > 2:
            # Multiple high impact tests -> high severity, run all tests
            return "high", "run-all-tests"
        elif high_impact_tests or len(medium_impact_tests) > 3:
            # Some high impact or many medium impact -> medium severity
            return "medium", "run-affected-tests"
        else:
            # Only low impact tests -> low severity
            return "low", "run-affected-tests"
