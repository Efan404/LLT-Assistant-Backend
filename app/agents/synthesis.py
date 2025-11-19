"""
Synthesis agent for merging and deduplicating issues from multiple sources.

This module provides the SynthesisAgent which combines issues detected
by different analysis methods (rules and LLM) into a unified result set.
"""

import logging
from typing import List, Tuple

from app.agents.base import BaseAgent
from app.agents.context import AgentContext, AgentResult
from app.api.v1.schemas import Issue

logger = logging.getLogger(__name__)

# Severity ordering for sorting
SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}


class SynthesisAgent(BaseAgent):
    """
    Agent responsible for synthesizing issues from multiple sources.

    This agent merges issues from rule-based and LLM-based analysis,
    deduplicates them, and sorts them by severity, file, and line number
    for optimal presentation.
    """

    async def execute(self, context: AgentContext) -> AgentResult:
        """
        Merge and deduplicate issues from all analysis sources.

        This method combines issues from rule_issues and llm_issues,
        removes duplicates, and sorts the results for presentation.

        Args:
            context: Agent context containing rule_issues and llm_issues

        Returns:
            AgentResult with merged issues and statistics
        """
        self.logger.info("Synthesizing issues from all analysis sources")

        all_issues: List[Issue] = []
        errors: List[str] = []
        warnings: List[str] = []

        # Collect issues from rule-based analysis
        rule_issue_count = 0
        if context.mode in {"rules-only", "hybrid"}:
            if hasattr(context, "rule_issues") and context.rule_issues:
                all_issues.extend(context.rule_issues)
                rule_issue_count = len(context.rule_issues)
                self.logger.debug(f"Added {rule_issue_count} issues from rule engine")
            else:
                warning_msg = "Rule analysis was expected but no rule_issues found"
                self.logger.warning(warning_msg)
                warnings.append(warning_msg)

        # Collect issues from LLM analysis and deduplicate
        llm_issue_count = 0
        llm_duplicates = 0
        if context.mode in {"llm-only", "hybrid"}:
            if hasattr(context, "llm_issues") and context.llm_issues:
                for llm_issue in context.llm_issues:
                    if not self._is_duplicate(llm_issue, all_issues):
                        all_issues.append(llm_issue)
                        llm_issue_count += 1
                    else:
                        llm_duplicates += 1

                self.logger.debug(
                    f"Added {llm_issue_count} unique issues from LLM "
                    f"({llm_duplicates} duplicates filtered)"
                )
            else:
                warning_msg = "LLM analysis was expected but no llm_issues found"
                self.logger.warning(warning_msg)
                warnings.append(warning_msg)

        # Sort issues by severity, file, and line number
        all_issues = self._sort_issues(all_issues)

        # Store merged issues in context
        context.merged_issues = all_issues

        # Calculate statistics
        issue_counts_by_severity = {"error": 0, "warning": 0, "info": 0}
        issue_counts_by_source = {"rule_engine": 0, "llm": 0}
        issue_counts_by_type = {}

        for issue in all_issues:
            issue_counts_by_severity[issue.severity] = (
                issue_counts_by_severity.get(issue.severity, 0) + 1
            )
            issue_counts_by_source[issue.detected_by] = (
                issue_counts_by_source.get(issue.detected_by, 0) + 1
            )
            issue_counts_by_type[issue.type] = (
                issue_counts_by_type.get(issue.type, 0) + 1
            )

        data = {
            "total_issues": len(all_issues),
            "rule_issues": rule_issue_count,
            "llm_issues": llm_issue_count,
            "duplicates_removed": llm_duplicates,
            "by_severity": issue_counts_by_severity,
            "by_source": issue_counts_by_source,
            "by_type": issue_counts_by_type,
        }

        success = len(errors) == 0

        self.logger.info(
            f"Synthesis completed: {len(all_issues)} total issues "
            f"({rule_issue_count} from rules, {llm_issue_count} from LLM, "
            f"{llm_duplicates} duplicates removed)"
        )

        return AgentResult(
            success=success,
            data=data,
            errors=errors,
            warnings=warnings,
            metadata={"agent": self.name, "stage": "synthesis"},
            execution_time_ms=0,
        )

    def _is_duplicate(self, issue: Issue, existing_issues: List[Issue]) -> bool:
        """
        Check if an issue is a duplicate of any existing issue.

        An issue is considered a duplicate if it has the same file,
        line number, and issue type as an existing issue.

        Args:
            issue: Issue to check
            existing_issues: List of existing issues

        Returns:
            True if issue is a duplicate, False otherwise
        """
        issue_signature = self._get_issue_signature(issue)

        for existing in existing_issues:
            if self._get_issue_signature(existing) == issue_signature:
                return True

        return False

    def _get_issue_signature(self, issue: Issue) -> Tuple[str, int, str]:
        """
        Get a unique signature for an issue for deduplication.

        Args:
            issue: Issue to get signature for

        Returns:
            Tuple of (file, line, type) uniquely identifying the issue
        """
        return (issue.file, issue.line, issue.type)

    def _sort_issues(self, issues: List[Issue]) -> List[Issue]:
        """
        Sort issues by severity, file, and line number.

        Issues are sorted in the following priority:
        1. Severity (error > warning > info)
        2. File path (alphabetically)
        3. Line number (ascending)

        Args:
            issues: List of issues to sort

        Returns:
            Sorted list of issues
        """
        return sorted(
            issues,
            key=lambda issue: (
                SEVERITY_ORDER.get(issue.severity, 99),
                issue.file,
                issue.line,
            ),
        )

    async def validate_input(self, context: AgentContext) -> List[str]:
        """
        Validate that issue sources are available based on mode.

        Args:
            context: Agent context to validate

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        # Validate based on mode
        if context.mode in {"rules-only", "hybrid"}:
            if not hasattr(context, "rule_issues"):
                errors.append(
                    f"Mode '{context.mode}' requires rule_issues but it's not set"
                )

        if context.mode in {"llm-only", "hybrid"}:
            if not hasattr(context, "llm_issues"):
                errors.append(
                    f"Mode '{context.mode}' requires llm_issues but it's not set"
                )

        return errors

    async def validate_output(
        self, result: AgentResult, context: AgentContext
    ) -> List[str]:
        """
        Validate output from synthesis.

        Args:
            result: Result from execute()
            context: Agent context for reference

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        # Verify context was updated
        if result.success and not hasattr(context, "merged_issues"):
            errors.append("Synthesis succeeded but context.merged_issues not set")

        # Verify data contains expected fields
        if result.data:
            expected_fields = {"total_issues", "duplicates_removed"}
            missing_fields = expected_fields - set(result.data.keys())
            if missing_fields:
                errors.append(
                    f"Result data missing fields: {', '.join(missing_fields)}"
                )

        # Verify issue counts match
        if result.success and result.data:
            expected_total = result.data.get("total_issues", 0)
            actual_total = len(context.merged_issues)
            if expected_total != actual_total:
                errors.append(
                    f"Issue count mismatch: data reports {expected_total} "
                    f"but context has {actual_total}"
                )

        return errors
