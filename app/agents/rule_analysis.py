"""
Rule-based analysis agent for detecting test quality issues.

This module provides the RuleAnalysisAgent which uses the rule engine
to detect common test quality issues through static analysis.
"""

import logging
from typing import List

from app.agents.base import BaseAgent
from app.agents.context import AgentContext, AgentResult
from app.analyzers.rule_engine import RuleEngine
from app.api.v1.schemas import Issue

logger = logging.getLogger(__name__)


class RuleAnalysisAgent(BaseAgent):
    """
    Agent responsible for rule-based test quality analysis.

    This agent applies the rule engine to detect common test quality
    issues such as redundant assertions, missing assertions, and
    trivial assertions. It only runs when the analysis mode includes
    rule-based detection.
    """

    def __init__(self, name: str = "rule_analysis", config: dict = None):
        """
        Initialize the rule analysis agent.

        Args:
            name: Unique name for this agent
            config: Optional configuration overrides
        """
        super().__init__(name, config)
        self.rule_engine = RuleEngine()

    async def execute(self, context: AgentContext) -> AgentResult:
        """
        Execute rule-based analysis on parsed files.

        This method applies all rules from the rule engine to each
        parsed test file and aggregates the detected issues.

        Args:
            context: Agent context containing parsed files and execution plan

        Returns:
            AgentResult with detected issues and statistics
        """
        # Check if rule analysis should run
        if not self._should_run(context):
            self.logger.info(
                f"Skipping rule analysis (mode={context.mode}, "
                f"run_rules={context.execution_plan.get('run_rules', False)})"
            )
            return AgentResult(
                success=True,
                data={"skipped": True, "reason": "not enabled for this mode"},
                errors=[],
                warnings=[],
                metadata={"agent": self.name, "stage": "rule_analysis"},
                execution_time_ms=0,
            )

        self.logger.info(f"Running rule analysis on {len(context.parsed_files)} files")

        all_issues: List[Issue] = []
        errors: List[str] = []
        warnings: List[str] = []
        files_analyzed = 0

        # Analyze each parsed file
        for parsed_file in context.parsed_files:
            try:
                # Skip files with syntax errors
                if parsed_file.has_syntax_errors:
                    warning_msg = (
                        f"Skipping rule analysis for {parsed_file.file_path} "
                        f"due to syntax errors"
                    )
                    self.logger.warning(warning_msg)
                    warnings.append(warning_msg)
                    continue

                # Run rule engine
                issues = self.rule_engine.analyze(parsed_file)
                all_issues.extend(issues)
                files_analyzed += 1

                self.logger.debug(
                    f"Found {len(issues)} issues in {parsed_file.file_path}"
                )

            except Exception as e:
                error_msg = f"Failed to analyze {parsed_file.file_path}: {str(e)}"
                self.logger.error(error_msg)
                errors.append(error_msg)

        # Store results in context
        context.rule_issues = all_issues

        # Calculate statistics
        issue_counts_by_severity = {"error": 0, "warning": 0, "info": 0}
        issue_counts_by_type = {}

        for issue in all_issues:
            issue_counts_by_severity[issue.severity] = (
                issue_counts_by_severity.get(issue.severity, 0) + 1
            )
            issue_counts_by_type[issue.type] = issue_counts_by_type.get(issue.type, 0) + 1

        data = {
            "issue_count": len(all_issues),
            "files_analyzed": files_analyzed,
            "files_skipped": len(context.parsed_files) - files_analyzed,
            "by_severity": issue_counts_by_severity,
            "by_type": issue_counts_by_type,
        }

        success = len(errors) == 0

        self.logger.info(
            f"Rule analysis completed: {len(all_issues)} issues found "
            f"across {files_analyzed} files "
            f"({issue_counts_by_severity['error']} errors, "
            f"{issue_counts_by_severity['warning']} warnings, "
            f"{issue_counts_by_severity['info']} info)"
        )

        return AgentResult(
            success=success,
            data=data,
            errors=errors,
            warnings=warnings,
            metadata={"agent": self.name, "stage": "rule_analysis"},
            execution_time_ms=0,
        )

    def _should_run(self, context: AgentContext) -> bool:
        """
        Determine if rule analysis should run based on mode and execution plan.

        Args:
            context: Agent context

        Returns:
            True if rule analysis should run, False otherwise
        """
        # Check execution plan first (set by strategy planning agent)
        if context.execution_plan:
            return context.execution_plan.get("run_rules", False)

        # Fall back to checking mode directly
        return context.mode in {"rules-only", "hybrid"}

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
            errors.append("No parsed files available for rule analysis")

        return errors

    async def validate_output(
        self, result: AgentResult, context: AgentContext
    ) -> List[str]:
        """
        Validate output from rule analysis.

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
        if result.success and not hasattr(context, "rule_issues"):
            errors.append("Rule analysis succeeded but context.rule_issues not set")

        # Verify data contains expected fields
        if result.data and not result.data.get("skipped"):
            expected_fields = {"issue_count", "files_analyzed"}
            missing_fields = expected_fields - set(result.data.keys())
            if missing_fields:
                errors.append(
                    f"Result data missing fields: {', '.join(missing_fields)}"
                )

        return errors
