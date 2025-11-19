"""
Strategy planning agent for determining optimal analysis approach.

This module provides the StrategyPlanningAgent which analyzes file
characteristics and determines the best execution strategy for analysis.
"""

import logging
from typing import Any, Dict, List, Tuple

from app.agents.base import BaseAgent
from app.agents.context import AgentContext, AgentResult

logger = logging.getLogger(__name__)

# Strategy thresholds
SMALL_FILE_SIZE = 5000  # Characters
SIMPLE_TEST_THRESHOLD = 10  # Number of test functions
COMPLEX_TEST_THRESHOLD = 30  # Number of test functions

# Cost estimates (in arbitrary units, can be tuned)
RULE_COST_PER_FILE = 10
LLM_COST_PER_TEST = 50
COST_SCALE_FACTOR = 1000.0  # Scale factor to convert cost to reasonable units

# Time estimates (in milliseconds)
RULE_TIME_PER_FILE_MS = 50
LLM_TIME_PER_TEST_MS = 500
BASELINE_OVERHEAD_MS = 500  # Overhead for parsing and synthesis


class StrategyPlanningAgent(BaseAgent):
    """
    Agent responsible for determining optimal analysis strategy.

    This agent examines file characteristics and selects the best
    combination of analysis methods to use. It respects user-specified
    modes but can optimize the execution plan within those constraints.
    """

    async def execute(self, context: AgentContext) -> AgentResult:
        """
        Analyze files and create execution plan.

        This method examines file characteristics and creates an
        execution plan that determines which analysis methods to run.

        Args:
            context: Agent context containing files and mode

        Returns:
            AgentResult with execution plan and estimates
        """
        self.logger.info(
            f"Planning analysis strategy for {len(context.files)} files "
            f"in mode '{context.mode}'"
        )

        # Analyze file characteristics
        file_stats = self._analyze_files(context)

        # Determine which analysis methods to run
        run_rules, run_llm = self._determine_methods(context, file_stats)

        # Estimate execution time and cost
        estimated_time_ms = self._estimate_time(file_stats, run_rules, run_llm)
        estimated_cost = self._estimate_cost(file_stats, run_rules, run_llm)

        # Create execution plan
        execution_plan = {
            "selected_mode": context.mode,
            "run_rules": run_rules,
            "run_llm": run_llm,
            "estimated_time_ms": estimated_time_ms,
            "estimated_cost": estimated_cost,
            "file_stats": file_stats,
            "files_to_analyze": [f.path for f in context.files],
        }

        # Store plan in context
        context.execution_plan = execution_plan

        self.logger.info(
            f"Strategy plan created: mode={context.mode}, "
            f"run_rules={run_rules}, run_llm={run_llm}, "
            f"estimated_time={estimated_time_ms}ms, "
            f"estimated_cost={estimated_cost}"
        )

        return AgentResult(
            success=True,
            data=execution_plan,
            errors=[],
            warnings=[],
            metadata={"agent": self.name, "stage": "strategy_planning"},
            execution_time_ms=0,
        )

    def _analyze_files(self, context: AgentContext) -> Dict[str, Any]:
        """
        Analyze file characteristics to inform strategy decisions.

        Args:
            context: Agent context containing files

        Returns:
            Dictionary containing file statistics
        """
        total_size = sum(len(f.content) for f in context.files)
        avg_size = total_size / len(context.files) if context.files else 0

        # Estimate test count based on file content
        # This is a rough estimate before parsing
        estimated_test_count = sum(
            f.content.count("def test_") + f.content.count("async def test_")
            for f in context.files
        )

        return {
            "file_count": len(context.files),
            "total_size": total_size,
            "average_size": avg_size,
            "estimated_test_count": estimated_test_count,
            "is_small_dataset": total_size < SMALL_FILE_SIZE * len(context.files),
            "is_simple": estimated_test_count < SIMPLE_TEST_THRESHOLD,
            "is_complex": estimated_test_count > COMPLEX_TEST_THRESHOLD,
        }

    def _determine_methods(
        self, context: AgentContext, file_stats: Dict[str, Any]
    ) -> Tuple[bool, bool]:
        """
        Determine which analysis methods to run.

        This respects the user's mode selection and determines
        which specific methods to execute.

        Args:
            context: Agent context
            file_stats: File statistics from _analyze_files()

        Returns:
            Tuple of (run_rules, run_llm) booleans
        """
        mode = context.mode

        # Respect user's explicit mode selection
        if mode == "rules-only":
            return (True, False)
        elif mode == "llm-only":
            return (False, True)
        elif mode == "hybrid":
            # Both methods run in hybrid mode
            return (True, True)
        else:
            # Default to hybrid for unknown modes
            self.logger.warning(f"Unknown mode '{mode}', defaulting to hybrid")
            return (True, True)

    def _estimate_time(
        self, file_stats: Dict[str, Any], run_rules: bool, run_llm: bool
    ) -> int:
        """
        Estimate total execution time in milliseconds.

        Args:
            file_stats: File statistics
            run_rules: Whether rule analysis will run
            run_llm: Whether LLM analysis will run

        Returns:
            Estimated time in milliseconds
        """
        time_ms = 0

        if run_rules:
            time_ms += file_stats["file_count"] * RULE_TIME_PER_FILE_MS

        if run_llm:
            time_ms += file_stats["estimated_test_count"] * LLM_TIME_PER_TEST_MS

        # Add baseline overhead for parsing and synthesis
        time_ms += BASELINE_OVERHEAD_MS

        return int(time_ms)

    def _estimate_cost(
        self, file_stats: Dict[str, Any], run_rules: bool, run_llm: bool
    ) -> float:
        """
        Estimate computational cost (arbitrary units).

        Args:
            file_stats: File statistics
            run_rules: Whether rule analysis will run
            run_llm: Whether LLM analysis will run

        Returns:
            Estimated cost
        """
        cost = 0.0

        if run_rules:
            cost += file_stats["file_count"] * RULE_COST_PER_FILE

        if run_llm:
            cost += file_stats["estimated_test_count"] * LLM_COST_PER_TEST

        return cost / COST_SCALE_FACTOR

    async def validate_input(self, context: AgentContext) -> List[str]:
        """
        Validate that required context data is available.

        Args:
            context: Agent context to validate

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        if not hasattr(context, "files"):
            errors.append("Context missing 'files' attribute")
        elif not context.files:
            errors.append("No files provided for strategy planning")

        if not hasattr(context, "mode"):
            errors.append("Context missing 'mode' attribute")

        return errors

    async def validate_output(
        self, result: AgentResult, context: AgentContext
    ) -> List[str]:
        """
        Validate output from strategy planning.

        Args:
            result: Result from execute()
            context: Agent context for reference

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        # Verify context was updated
        if result.success and not hasattr(context, "execution_plan"):
            errors.append(
                "Strategy planning succeeded but context.execution_plan not set"
            )

        # Verify execution plan contains required fields
        if result.success and context.execution_plan:
            required_fields = {
                "run_rules",
                "run_llm",
                "estimated_time_ms",
                "files_to_analyze",
            }
            missing_fields = required_fields - set(context.execution_plan.keys())
            if missing_fields:
                errors.append(
                    f"Execution plan missing fields: {', '.join(missing_fields)}"
                )

        return errors
