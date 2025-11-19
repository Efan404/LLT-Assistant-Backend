"""
Unit tests for StrategyPlanningAgent.

Tests strategy selection, estimation, and execution planning.
"""

import pytest

from app.agents.context import AgentContext
from app.agents.strategy_planning import StrategyPlanningAgent
from app.api.v1.schemas import FileInput


@pytest.mark.asyncio
class TestStrategyPlanningAgent:
    """Test cases for StrategyPlanningAgent class."""

    async def test_rules_only_mode(self, sample_test_code: str) -> None:
        """Test strategy planning for rules-only mode."""
        agent = StrategyPlanningAgent(name="planner")
        context = AgentContext(
            request_id="req-123",
            files=[FileInput(path="test.py", content=sample_test_code)],
            mode="rules-only",
        )

        result = await agent.run(context)

        assert result.success is True
        assert context.execution_plan["run_rules"] is True
        assert context.execution_plan["run_llm"] is False
        assert context.execution_plan["selected_mode"] == "rules-only"

    async def test_llm_only_mode(self, sample_test_code: str) -> None:
        """Test strategy planning for llm-only mode."""
        agent = StrategyPlanningAgent(name="planner")
        context = AgentContext(
            request_id="req-123",
            files=[FileInput(path="test.py", content=sample_test_code)],
            mode="llm-only",
        )

        result = await agent.run(context)

        assert result.success is True
        assert context.execution_plan["run_rules"] is False
        assert context.execution_plan["run_llm"] is True
        assert context.execution_plan["selected_mode"] == "llm-only"

    async def test_hybrid_mode(self, sample_test_code: str) -> None:
        """Test strategy planning for hybrid mode."""
        agent = StrategyPlanningAgent(name="planner")
        context = AgentContext(
            request_id="req-123",
            files=[FileInput(path="test.py", content=sample_test_code)],
            mode="hybrid",
        )

        result = await agent.run(context)

        assert result.success is True
        assert context.execution_plan["run_rules"] is True
        assert context.execution_plan["run_llm"] is True
        assert context.execution_plan["selected_mode"] == "hybrid"

    async def test_file_statistics(self, sample_test_code: str) -> None:
        """Test agent calculates file statistics correctly."""
        agent = StrategyPlanningAgent(name="planner")
        context = AgentContext(
            request_id="req-123",
            files=[
                FileInput(path="test1.py", content=sample_test_code),
                FileInput(path="test2.py", content=sample_test_code),
            ],
            mode="hybrid",
        )

        result = await agent.run(context)

        assert result.success is True
        file_stats = context.execution_plan["file_stats"]
        assert file_stats["file_count"] == 2
        assert file_stats["total_size"] > 0
        assert file_stats["average_size"] > 0
        assert file_stats["estimated_test_count"] >= 0

    async def test_time_estimation(self, sample_test_code: str) -> None:
        """Test agent estimates execution time."""
        agent = StrategyPlanningAgent(name="planner")
        context = AgentContext(
            request_id="req-123",
            files=[FileInput(path="test.py", content=sample_test_code)],
            mode="hybrid",
        )

        result = await agent.run(context)

        assert result.success is True
        assert "estimated_time_ms" in context.execution_plan
        assert context.execution_plan["estimated_time_ms"] > 0

    async def test_cost_estimation(self, sample_test_code: str) -> None:
        """Test agent estimates computational cost."""
        agent = StrategyPlanningAgent(name="planner")
        context = AgentContext(
            request_id="req-123",
            files=[FileInput(path="test.py", content=sample_test_code)],
            mode="hybrid",
        )

        result = await agent.run(context)

        assert result.success is True
        assert "estimated_cost" in context.execution_plan
        assert context.execution_plan["estimated_cost"] >= 0

    async def test_files_to_analyze_list(self, sample_test_code: str) -> None:
        """Test agent creates list of files to analyze."""
        agent = StrategyPlanningAgent(name="planner")
        context = AgentContext(
            request_id="req-123",
            files=[
                FileInput(path="test1.py", content=sample_test_code),
                FileInput(path="test2.py", content=sample_test_code),
            ],
            mode="hybrid",
        )

        result = await agent.run(context)

        assert result.success is True
        assert "files_to_analyze" in context.execution_plan
        assert len(context.execution_plan["files_to_analyze"]) == 2
        assert "test1.py" in context.execution_plan["files_to_analyze"]
        assert "test2.py" in context.execution_plan["files_to_analyze"]

    async def test_validation_no_files(self) -> None:
        """Test input validation catches missing files."""
        agent = StrategyPlanningAgent(name="planner")
        context = AgentContext(
            request_id="req-123",
            files=[],
            mode="hybrid",
        )

        result = await agent.run(context)

        assert result.success is False
        assert result.metadata["stage"] == "input_validation"

    async def test_output_validation(self, sample_test_code: str) -> None:
        """Test output validation checks execution plan."""
        agent = StrategyPlanningAgent(name="planner")
        context = AgentContext(
            request_id="req-123",
            files=[FileInput(path="test.py", content=sample_test_code)],
            mode="hybrid",
        )

        result = await agent.run(context)

        # Should have all required fields
        assert "run_rules" in context.execution_plan
        assert "run_llm" in context.execution_plan
        assert "estimated_time_ms" in context.execution_plan
        assert "files_to_analyze" in context.execution_plan

    async def test_metrics_tracking(self, sample_test_code: str) -> None:
        """Test agent tracks execution metrics."""
        agent = StrategyPlanningAgent(name="planner")
        context = AgentContext(
            request_id="req-123",
            files=[FileInput(path="test.py", content=sample_test_code)],
            mode="hybrid",
        )

        await agent.run(context)
        metrics = agent.get_metrics()

        assert metrics["total_executions"] == 1
        assert metrics["total_errors"] == 0
        assert metrics["success_rate"] == 1.0
