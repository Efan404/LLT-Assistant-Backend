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
from app.api.v1.schemas import AnalyzeResponse, FileInput
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
