"""Batch quality analysis service for Feature 4.

This module provides QualityAnalysisService which handles batch analysis
of multiple test files for quality issues with fix suggestions.
"""

import logging
import time
import uuid
from typing import List, Optional

from app.analyzers.rule_engine import RuleEngine
from app.api.v1.schemas import (
    FileInput,
    FixSuggestion,
    QualityAnalysisResponse,
    QualityIssue,
    QualitySummary,
)
from app.core.analyzer import TestAnalyzer
from app.core.llm_analyzer import LLMAnalyzer
from app.core.llm_client import create_llm_client

logger = logging.getLogger(__name__)


class QualityAnalysisService:
    """Service for batch quality analysis of test files.

    This service provides a simplified interface for analyzing multiple
    test files and returning quality issues with fix suggestions.
    """

    def __init__(self, test_analyzer: Optional[TestAnalyzer] = None):
        """
        Initialize the quality analysis service.

        Args:
            test_analyzer: Optional TestAnalyzer instance (will create if None)
        """
        if test_analyzer is None:
            rule_engine = RuleEngine()
            llm_client = create_llm_client()
            llm_analyzer = LLMAnalyzer(llm_client)
            self.test_analyzer = TestAnalyzer(rule_engine, llm_analyzer)
        else:
            self.test_analyzer = test_analyzer

    async def analyze_batch(
        self, files: List[FileInput], mode: str = "hybrid"
    ) -> QualityAnalysisResponse:
        """
        Analyze multiple test files for quality issues.

        This method orchestrates the analysis of multiple files and converts
        the results to the Feature 4 Quality Analysis format.

        Args:
            files: List of test files to analyze
            mode: Analysis mode - "fast" (rules-only), "deep" (llm-only), or "hybrid"

        Returns:
            QualityAnalysisResponse with issues and summary

        Raises:
            ValueError: If files are empty or mode is invalid
        """
        if not files:
            raise ValueError("No files provided for analysis")

        start_time = time.time()
        analysis_id = str(uuid.uuid4())

        logger.info(
            f"Starting quality analysis {analysis_id} with {len(files)} files, mode: {mode}"
        )

        try:
            # Convert mode to TestAnalyzer format
            analyzer_mode = self._convert_mode(mode)

            # Perform analysis using existing TestAnalyzer
            analysis_result = await self.test_analyzer.analyze_files(
                files=files, mode=analyzer_mode
            )

            # Convert results to Quality Analysis format
            quality_issues = self._convert_issues(analysis_result.issues)

            # Calculate summary statistics
            summary = self._calculate_summary(files, quality_issues)

            logger.info(
                f"Quality analysis {analysis_id} completed: {len(quality_issues)} issues found "
                f"in {int((time.time() - start_time) * 1000)}ms"
            )

            return QualityAnalysisResponse(
                analysis_id=analysis_id, summary=summary, issues=quality_issues
            )

        except Exception as e:
            logger.error(f"Quality analysis {analysis_id} failed: {e}")
            raise

    def _convert_mode(self, mode: str) -> str:
        """
        Convert Feature 4 mode to TestAnalyzer mode.

        Args:
            mode: Feature 4 mode (fast/deep/hybrid)

        Returns:
            TestAnalyzer mode (rules-only/llm-only/hybrid)
        """
        mode_mapping = {
            "fast": "rules-only",
            "deep": "llm-only",
            "hybrid": "hybrid",
        }

        if mode not in mode_mapping:
            raise ValueError(
                f"Invalid mode: {mode}. Must be one of {list(mode_mapping.keys())}"
            )

        return mode_mapping[mode]

    def _convert_issues(self, issues: List) -> List[QualityIssue]:
        """
        Convert TestAnalyzer issues to QualityIssue format.

        Args:
            issues: Issues from TestAnalyzer

        Returns:
            List of QualityIssue objects
        """
        quality_issues = []

        for issue in issues:
            # Convert suggestion if present
            suggestion = None
            if hasattr(issue, "suggestion") and issue.suggestion is not None:
                suggestion = self._convert_suggestion(issue.suggestion)

            # Map detected_by field
            detected_by = "rule" if issue.detected_by == "rule_engine" else "llm"

            quality_issue = QualityIssue(
                file_path=issue.file,
                line=issue.line,
                column=issue.column,
                severity=issue.severity,
                code=issue.type,
                message=issue.message,
                detected_by=detected_by,
                suggestion=suggestion,
            )
            quality_issues.append(quality_issue)

        return quality_issues

    def _convert_suggestion(self, suggestion) -> FixSuggestion:
        """
        Convert IssueSuggestion to FixSuggestion format.

        Args:
            suggestion: IssueSuggestion from TestAnalyzer

        Returns:
            FixSuggestion object
        """
        # Map action types
        action_mapping = {
            "replace": "replace",
            "remove": "delete",
            "add": "insert",
        }

        fix_type = action_mapping.get(suggestion.action, "replace")

        # For insert/add operations, use new_code
        # For replace, show both old and new
        # For delete, old_code contains what to delete
        new_text = suggestion.new_code

        return FixSuggestion(
            type=fix_type,
            new_text=new_text,
            description=suggestion.explanation,
        )

    def _calculate_summary(
        self, files: List[FileInput], issues: List[QualityIssue]
    ) -> QualitySummary:
        """
        Calculate summary statistics for the analysis.

        Args:
            files: List of analyzed files
            issues: List of detected issues

        Returns:
            QualitySummary with statistics
        """
        total_files = len(files)
        total_issues = len(issues)
        critical_issues = len([issue for issue in issues if issue.severity == "error"])

        return QualitySummary(
            total_files=total_files,
            total_issues=total_issues,
            critical_issues=critical_issues,
        )

    async def close(self) -> None:
        """Close resources used by the service."""
        await self.test_analyzer.close()
