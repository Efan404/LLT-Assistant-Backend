"""Main analysis orchestrator for test code quality."""

import asyncio
import logging
import time
import uuid
from typing import Dict, List, Optional, Set

from app.analyzers.ast_parser import ParsedTestFile, parse_test_file
from app.analyzers.rule_engine import RuleEngine
from app.api.v1.schemas import (
    AnalysisMetrics,
    AnalyzeRequest,
    AnalyzeResponse,
    FileInput,
    Issue,
)
from app.core.llm_analyzer import LLMAnalyzer
from app.core.llm_client import create_llm_client

logger = logging.getLogger(__name__)


class TestAnalyzer:
    """Main orchestrator for test analysis."""

    def __init__(self, rule_engine: RuleEngine, llm_analyzer: LLMAnalyzer):
        self.rule_engine = rule_engine
        self.llm_analyzer = llm_analyzer

    async def analyze_files(
        self,
        files: List[FileInput],
        mode: str = "hybrid",
        config: Optional[Dict] = None,
    ) -> AnalyzeResponse:
        """
        Analyze test files and return detected issues.

        Pipeline:
        1. Parse files into AST
        2. Run rule engine (always fast)
        3. If mode includes LLM:
           - Identify uncertain cases
           - Run LLM analysis on those cases
           - Merge results
        4. Generate suggestions for each issue
        5. Calculate metrics

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

        if mode not in ["rules-only", "llm-only", "hybrid"]:
            raise ValueError(f"Invalid analysis mode: {mode}")

        start_time = time.time()
        analysis_id = str(uuid.uuid4())

        logger.info(
            f"Starting analysis {analysis_id} with mode: {mode}, files: {len(files)}"
        )

        try:
            # Step 1: Parse all files in parallel
            parsed_files = await self._parse_files_parallel(files)

            # Step 2: Run rule engine analysis (always runs for rules-only and hybrid)
            rule_issues = []
            if mode in ["rules-only", "hybrid"]:
                rule_issues = await self._run_rule_analysis(parsed_files)

            # Step 3: Run LLM analysis if needed
            llm_issues = []
            if mode in ["llm-only", "hybrid"]:
                llm_issues = await self._run_llm_analysis(parsed_files, mode)

            # Step 4: Merge and deduplicate issues
            all_issues = self._merge_issues(rule_issues, llm_issues, mode)

            # Step 5: Calculate metrics
            metrics = self._calculate_metrics(parsed_files, all_issues, start_time)

            logger.info(
                f"Analysis {analysis_id} completed: {len(all_issues)} issues found in {metrics.analysis_time_ms}ms"
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
        """Parse multiple files in parallel."""
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
        """Safely parse a single file."""
        try:
            return parse_test_file(file_input.path, file_input.content)
        except Exception as e:
            logger.error(f"Error parsing file {file_input.path}: {e}")
            # Return a file with syntax errors
            return ParsedTestFile(
                file_path=file_input.path,
                imports=[],
                fixtures=[],
                test_functions=[],
                test_classes=[],
                has_syntax_errors=True,
                syntax_error_message=str(e),
            )

    async def _run_rule_analysis(
        self, parsed_files: List[ParsedTestFile]
    ) -> List[Issue]:
        """Run rule engine analysis on parsed files."""
        rule_issues = []

        for parsed_file in parsed_files:
            try:
                file_issues = self.rule_engine.analyze(parsed_file)
                rule_issues.extend(file_issues)
            except Exception as e:
                logger.error(
                    f"Rule engine failed for file {parsed_file.file_path}: {e}"
                )

        return rule_issues

    async def _run_llm_analysis(
        self, parsed_files: List[ParsedTestFile], mode: str
    ) -> List[Issue]:
        """Run LLM analysis on parsed files."""
        llm_issues = []

        # For llm-only mode, analyze all test functions
        if mode == "llm-only":
            for parsed_file in parsed_files:
                file_issues = await self._analyze_file_with_llm(parsed_file)
                llm_issues.extend(file_issues)

        # For hybrid mode, only analyze uncertain cases
        elif mode == "hybrid":
            for parsed_file in parsed_files:
                uncertain_functions = self._identify_uncertain_cases(parsed_file)
                for test_func in uncertain_functions:
                    func_issues = await self._analyze_function_with_llm(
                        test_func, parsed_file
                    )
                    llm_issues.extend(func_issues)

        return llm_issues

    def _identify_uncertain_cases(self, parsed_file: ParsedTestFile) -> List:
        """
        Identify test functions that need LLM analysis in hybrid mode.

        Criteria:
        - Functions with similar names (potential merge candidates)
        - Functions with complex assertions
        - Functions with unusual patterns
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

    def _are_similar_functions(self, func1, func2) -> bool:
        """Check if two functions have similar names."""
        name1_parts = func1.name.split("_")
        name2_parts = func2.name.split("_")

        # If they share most words, they might be similar
        common_parts = set(name1_parts) & set(name2_parts)
        min_parts = min(len(name1_parts), len(name2_parts))

        return len(common_parts) >= min_parts - 1 and min_parts > 1

    def _has_complex_assertions(self, test_func) -> bool:
        """Check if function has complex assertions."""
        # Simple heuristic: more than 3 assertions or assertions with complex expressions
        if len(test_func.assertions) > 3:
            return True

        for assertion in test_func.assertions:
            if assertion.assertion_type == "other":
                return True

        return False

    def _has_unusual_patterns(self, test_func) -> bool:
        """Check if function has unusual patterns that might indicate code smells."""
        # Simple heuristics
        source_lower = test_func.source_code.lower()

        # Check for timing-related code
        if "time.sleep" in source_lower or "asyncio.sleep" in source_lower:
            return True

        # Check for global state modification
        if "global " in source_lower:
            return True

        # Check for many mock decorators
        decorator_count = len(test_func.decorators)
        if decorator_count > 3:
            return True

        return False

    async def _analyze_file_with_llm(self, parsed_file: ParsedTestFile) -> List[Issue]:
        """Analyze entire file with LLM."""
        llm_issues = []

        # Analyze module-level functions
        for test_func in parsed_file.test_functions:
            func_issues = await self._analyze_function_with_llm(test_func, parsed_file)
            llm_issues.extend(func_issues)

        # Analyze test class methods
        for test_class in parsed_file.test_classes:
            for test_method in test_class.methods:
                method_issues = await self._analyze_function_with_llm(
                    test_method, parsed_file
                )
                llm_issues.extend(method_issues)

        return llm_issues

    async def _analyze_function_with_llm(self, test_func, parsed_file) -> List[Issue]:
        """Analyze a single test function with LLM."""
        llm_issues = []

        try:
            # Analyze assertion quality
            quality_issues = await self.llm_analyzer.analyze_assertion_quality(
                test_func, parsed_file
            )
            llm_issues.extend(quality_issues)

            # Analyze test smells
            smell_issues = await self.llm_analyzer.analyze_test_smells(
                test_func, parsed_file
            )
            llm_issues.extend(smell_issues)

        except Exception as e:
            logger.error(f"LLM analysis failed for function {test_func.name}: {e}")

        return llm_issues

    def _merge_issues(
        self, rule_issues: List[Issue], llm_issues: List[Issue], mode: str
    ) -> List[Issue]:
        """Merge and deduplicate issues from rule engine and LLM."""
        all_issues = []

        if mode == "rules-only":
            all_issues = rule_issues
        elif mode == "llm-only":
            all_issues = llm_issues
        elif mode == "hybrid":
            # Start with rule issues (higher confidence)
            all_issues.extend(rule_issues)

            # Add LLM issues that don't conflict with rule issues
            for llm_issue in llm_issues:
                if not self._is_duplicate_issue(llm_issue, rule_issues):
                    all_issues.append(llm_issue)

        # Sort by file and line number
        all_issues.sort(key=lambda x: (x.file, x.line))

        return all_issues

    def _is_duplicate_issue(self, issue: Issue, existing_issues: List[Issue]) -> bool:
        """Check if an issue is a duplicate of existing issues."""
        for existing in existing_issues:
            # Simple deduplication: same file, line, and similar message
            if (
                issue.file == existing.file
                and issue.line == existing.line
                and issue.type.split("-")[-1] == existing.type.split("-")[-1]
            ):
                return True

        return False

    def _calculate_metrics(
        self, parsed_files: List[ParsedTestFile], issues: List[Issue], start_time: float
    ) -> AnalysisMetrics:
        """Calculate analysis metrics."""
        total_tests = 0

        for parsed_file in parsed_files:
            total_tests += len(parsed_file.test_functions)
            for test_class in parsed_file.test_classes:
                total_tests += len(test_class.methods)

        analysis_time_ms = int((time.time() - start_time) * 1000)

        return AnalysisMetrics(
            total_tests=total_tests,
            issues_count=len(issues),
            analysis_time_ms=analysis_time_ms,
        )

    async def close(self) -> None:
        """Close the analyzer and its dependencies."""
        await self.llm_analyzer.close()
