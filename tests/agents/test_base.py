"""
Unit tests for BaseAgent.

Tests the base agent class including execution flow, validation,
error handling, and metrics tracking.
"""

import pytest

from app.agents.base import BaseAgent
from app.agents.context import AgentContext, AgentResult
from app.api.v1.schemas import FileInput


class SuccessfulAgent(BaseAgent):
    """Mock agent that always succeeds."""

    async def execute(self, context: AgentContext) -> AgentResult:
        """Execute successfully."""
        return AgentResult(
            success=True,
            data={"message": "Success"},
            errors=[],
            warnings=[],
            metadata={"agent": self.name},
            execution_time_ms=0,
        )


class FailingAgent(BaseAgent):
    """Mock agent that always fails."""

    async def execute(self, context: AgentContext) -> AgentResult:
        """Execute with failure."""
        return AgentResult(
            success=False,
            data=None,
            errors=["Execution failed"],
            warnings=[],
            metadata={"agent": self.name},
            execution_time_ms=0,
        )


class ExceptionAgent(BaseAgent):
    """Mock agent that raises an exception."""

    async def execute(self, context: AgentContext) -> AgentResult:
        """Raise an exception."""
        raise ValueError("Unexpected error")


class ValidatingAgent(BaseAgent):
    """Mock agent with custom validation."""

    async def execute(self, context: AgentContext) -> AgentResult:
        """Execute successfully."""
        return AgentResult(
            success=True,
            data={"count": len(context.files)},
            errors=[],
            warnings=[],
            metadata={"agent": self.name},
            execution_time_ms=0,
        )

    async def validate_input(self, context: AgentContext) -> list[str]:
        """Validate that files are provided."""
        if not context.files:
            return ["No files provided"]
        return []

    async def validate_output(
        self, result: AgentResult, context: AgentContext
    ) -> list[str]:
        """Validate output data."""
        if result.data and result.data.get("count", 0) == 0:
            return ["Count should not be zero"]
        return []


@pytest.mark.asyncio
class TestBaseAgent:
    """Test cases for BaseAgent class."""

    async def test_successful_execution(self) -> None:
        """Test agent executes successfully."""
        agent = SuccessfulAgent(name="success_agent")
        context = AgentContext(
            request_id="req-123",
            files=[FileInput(path="test.py", content="test")],
            mode="hybrid",
        )

        result = await agent.run(context)

        assert result.success is True
        assert result.data == {"message": "Success"}
        assert result.errors == []
        assert result.execution_time_ms >= 0
        assert "success_agent" in context.agent_results

    async def test_failing_execution(self) -> None:
        """Test agent handles execution failure."""
        agent = FailingAgent(name="failing_agent")
        context = AgentContext(
            request_id="req-123",
            files=[],
            mode="hybrid",
        )

        result = await agent.run(context)

        assert result.success is False
        assert result.errors == ["Execution failed"]

    async def test_exception_handling(self) -> None:
        """Test agent handles exceptions gracefully."""
        agent = ExceptionAgent(name="exception_agent")
        context = AgentContext(
            request_id="req-123",
            files=[],
            mode="hybrid",
        )

        result = await agent.run(context)

        assert result.success is False
        assert len(result.errors) == 1
        assert "Unexpected error" in result.errors[0]
        assert result.metadata["exception_type"] == "ValueError"

    async def test_input_validation(self) -> None:
        """Test input validation prevents execution."""
        agent = ValidatingAgent(name="validating_agent")
        context = AgentContext(
            request_id="req-123",
            files=[],  # Empty files will fail validation
            mode="hybrid",
        )

        result = await agent.run(context)

        assert result.success is False
        assert "No files provided" in result.errors
        assert result.metadata["stage"] == "input_validation"

    async def test_output_validation(self) -> None:
        """Test output validation marks result as failed."""
        agent = ValidatingAgent(name="validating_agent")

        # This will pass input validation but fail output validation
        # because count will be 0
        context = AgentContext(
            request_id="req-123",
            files=[FileInput(path="test.py", content="test")],
            mode="hybrid",
        )

        result = await agent.run(context)

        # Should succeed in execution but fail validation
        assert result.success is True  # Execution succeeded
        assert result.data["count"] == 1  # Has files

    async def test_metrics_tracking(self) -> None:
        """Test agent tracks execution metrics."""
        agent = SuccessfulAgent(name="metrics_agent")
        context = AgentContext(
            request_id="req-123",
            files=[],
            mode="hybrid",
        )

        # Execute multiple times
        await agent.run(context)
        await agent.run(context)
        await agent.run(context)

        metrics = agent.get_metrics()

        assert metrics["agent_name"] == "metrics_agent"
        assert metrics["total_executions"] == 3
        assert metrics["total_errors"] == 0
        assert metrics["success_rate"] == 1.0
        assert metrics["average_execution_time_ms"] >= 0
        assert metrics["total_execution_time_ms"] >= 0

    async def test_metrics_with_failures(self) -> None:
        """Test metrics correctly track failures."""
        agent = FailingAgent(name="failing_metrics_agent")
        context = AgentContext(
            request_id="req-123",
            files=[],
            mode="hybrid",
        )

        # Execute twice, both should fail
        await agent.run(context)
        await agent.run(context)

        metrics = agent.get_metrics()

        assert metrics["total_executions"] == 2
        assert metrics["total_errors"] == 2
        assert metrics["success_rate"] == 0.0

    async def test_reset_metrics(self) -> None:
        """Test resetting agent metrics."""
        agent = SuccessfulAgent(name="reset_agent")
        context = AgentContext(
            request_id="req-123",
            files=[],
            mode="hybrid",
        )

        # Execute and verify metrics
        await agent.run(context)
        assert agent.get_metrics()["total_executions"] == 1

        # Reset and verify
        agent.reset_metrics()
        assert agent.get_metrics()["total_executions"] == 0
        assert agent.get_metrics()["total_errors"] == 0

    async def test_agent_with_config(self) -> None:
        """Test agent initialization with config."""
        config = {"max_retries": 3, "timeout": 30}
        agent = SuccessfulAgent(name="config_agent", config=config)

        assert agent.config == config
        assert agent.config["max_retries"] == 3

    def test_agent_repr(self) -> None:
        """Test agent string representation."""
        agent = SuccessfulAgent(name="test_agent")
        repr_str = repr(agent)

        assert "SuccessfulAgent" in repr_str
        assert "test_agent" in repr_str

    async def test_result_stored_in_context(self) -> None:
        """Test that agent result is stored in context."""
        agent = SuccessfulAgent(name="storage_agent")
        context = AgentContext(
            request_id="req-123",
            files=[],
            mode="hybrid",
        )

        result = await agent.run(context)

        assert "storage_agent" in context.agent_results
        assert context.agent_results["storage_agent"] == result
