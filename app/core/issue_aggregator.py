"""Issue aggregation and deduplication logic.

This class handles merging and deduplicating issues from different
analysis sources (rule engine and LLM).
"""

from typing import List

from app.api.v1.schemas import Issue
from app.core.constants import AnalysisMode


class IssueAggregator:
    """Aggregates and deduplicates issues from multiple sources."""

    def merge_issues(
        self, rule_issues: List[Issue], llm_issues: List[Issue], mode: AnalysisMode
    ) -> List[Issue]:
        """
        Merge and deduplicate issues from rule engine and LLM.

        Args:
            rule_issues: Issues detected by rule engine
            llm_issues: Issues detected by LLM
            mode: Analysis mode used

        Returns:
            Merged and deduplicated list of issues, sorted by file and line
        """
        all_issues = []

        if mode == AnalysisMode.RULES_ONLY:
            all_issues = rule_issues
        elif mode == AnalysisMode.LLM_ONLY:
            all_issues = llm_issues
        elif mode == AnalysisMode.HYBRID:
            # Start with rule issues (higher confidence)
            all_issues.extend(rule_issues)

            # Add LLM issues that don't conflict with rule issues
            for llm_issue in llm_issues:
                if not self._is_duplicate_issue(llm_issue, rule_issues):
                    all_issues.append(llm_issue)

        # Sort by file and line number for consistent output
        all_issues.sort(key=lambda x: (x.file, x.line))

        return all_issues

    def _is_duplicate_issue(self, issue: Issue, existing_issues: List[Issue]) -> bool:
        """
        Check if an issue is a duplicate of existing issues.

        An issue is considered a duplicate if it's on the same line
        in the same file and detects a similar type of problem.

        Args:
            issue: Issue to check
            existing_issues: List of existing issues

        Returns:
            True if issue is a duplicate
        """
        for existing in existing_issues:
            # Simple deduplication: same file, line, and similar type
            if (
                issue.file == existing.file
                and issue.line == existing.line
                and self._similar_issue_type(issue.type, existing.type)
            ):
                return True

        return False

    def _similar_issue_type(self, type1: str, type2: str) -> bool:
        """
        Check if two issue types are similar enough to be duplicates.

        Args:
            type1: First issue type
            type2: Second issue type

        Returns:
            True if issue types are similar
        """
        # Extract the base type (last part after hyphen)
        type1_base = type1.split("-")[-1]
        type2_base = type2.split("-")[-1]

        return type1_base == type2_base
