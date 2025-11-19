"""
Unit tests for AgentContext and AgentResult.

Tests the context and result data structures used for agent communication.
"""

import time

from app.agents.context import AgentContext, AgentResult
from app.api.v1.schemas import FileInput


class TestAgentResult:
    """Test cases for AgentResult data class."""

    def test_agent_result_creation(self) -> None:
        """Test creating a basic AgentResult."""
        result = AgentResult(
            success=True,
            data={"key": "value"},
            errors=[],
            warnings=[],
            metadata={"agent": "test_agent"},
            execution_time_ms=100,
        )

        assert result.success is True
        assert result.data == {"key": "value"}
        assert result.errors == []
        assert result.warnings == []
        assert result.metadata == {"agent": "test_agent"}
        assert result.execution_time_ms == 100

    def test_agent_result_with_errors(self) -> None:
        """Test creating an AgentResult with errors."""
        result = AgentResult(
            success=False,
            data=None,
            errors=["Error 1", "Error 2"],
            warnings=["Warning 1"],
            metadata={"agent": "failing_agent"},
            execution_time_ms=50,
        )

        assert result.success is False
        assert result.data is None
        assert len(result.errors) == 2
        assert len(result.warnings) == 1


class TestAgentContext:
    """Test cases for AgentContext data class."""

    def test_context_creation(self) -> None:
        """Test creating a basic AgentContext."""
        files = [
            FileInput(path="test.py", content="def test(): pass"),
        ]

        context = AgentContext(
            request_id="req-123",
            files=files,
            mode="hybrid",
            config={"key": "value"},
        )

        assert context.request_id == "req-123"
        assert len(context.files) == 1
        assert context.mode == "hybrid"
        assert context.config == {"key": "value"}
        assert context.parsed_files == []
        assert context.rule_issues == []
        assert context.llm_issues == []
        assert context.merged_issues == []
        assert context.execution_plan == {}
        assert context.agent_results == {}

    def test_add_agent_result(self) -> None:
        """Test adding agent results to context."""
        context = AgentContext(
            request_id="req-123",
            files=[],
            mode="hybrid",
        )

        result = AgentResult(
            success=True,
            data={"output": "test"},
            errors=[],
            warnings=[],
            metadata={},
            execution_time_ms=100,
        )

        context.add_agent_result("test_agent", result)

        assert "test_agent" in context.agent_results
        assert context.agent_results["test_agent"] == result

    def test_get_total_execution_time(self) -> None:
        """Test calculating total execution time."""
        context = AgentContext(
            request_id="req-123",
            files=[],
            mode="hybrid",
        )

        # Wait a bit
        time.sleep(0.1)

        total_time = context.get_total_execution_time_ms()
        assert total_time >= 100  # At least 100ms

    def test_has_errors(self) -> None:
        """Test checking if context has errors."""
        context = AgentContext(
            request_id="req-123",
            files=[],
            mode="hybrid",
        )

        # Initially no errors
        assert not context.has_errors()

        # Add successful result
        context.add_agent_result(
            "agent1",
            AgentResult(
                success=True,
                data=None,
                errors=[],
                warnings=[],
                metadata={},
                execution_time_ms=100,
            ),
        )
        assert not context.has_errors()

        # Add failed result
        context.add_agent_result(
            "agent2",
            AgentResult(
                success=False,
                data=None,
                errors=["Error occurred"],
                warnings=[],
                metadata={},
                execution_time_ms=50,
            ),
        )
        assert context.has_errors()

    def test_get_all_errors(self) -> None:
        """Test collecting all errors from agent results."""
        context = AgentContext(
            request_id="req-123",
            files=[],
            mode="hybrid",
        )

        context.add_agent_result(
            "agent1",
            AgentResult(
                success=False,
                data=None,
                errors=["Error 1", "Error 2"],
                warnings=[],
                metadata={},
                execution_time_ms=100,
            ),
        )

        context.add_agent_result(
            "agent2",
            AgentResult(
                success=False,
                data=None,
                errors=["Error 3"],
                warnings=[],
                metadata={},
                execution_time_ms=50,
            ),
        )

        all_errors = context.get_all_errors()
        assert len(all_errors) == 3
        assert "[agent1] Error 1" in all_errors
        assert "[agent1] Error 2" in all_errors
        assert "[agent2] Error 3" in all_errors

    def test_get_all_warnings(self) -> None:
        """Test collecting all warnings from agent results."""
        context = AgentContext(
            request_id="req-123",
            files=[],
            mode="hybrid",
        )

        context.add_agent_result(
            "agent1",
            AgentResult(
                success=True,
                data=None,
                errors=[],
                warnings=["Warning 1"],
                metadata={},
                execution_time_ms=100,
            ),
        )

        all_warnings = context.get_all_warnings()
        assert len(all_warnings) == 1
        assert "[agent1] Warning 1" in all_warnings

    def test_get_agent_metrics(self) -> None:
        """Test extracting agent metrics from context."""
        context = AgentContext(
            request_id="req-123",
            files=[],
            mode="hybrid",
        )

        context.add_agent_result(
            "agent1",
            AgentResult(
                success=True,
                data=None,
                errors=[],
                warnings=["Warning"],
                metadata={},
                execution_time_ms=100,
            ),
        )

        context.add_agent_result(
            "agent2",
            AgentResult(
                success=False,
                data=None,
                errors=["Error"],
                warnings=[],
                metadata={},
                execution_time_ms=200,
            ),
        )

        metrics = context.get_agent_metrics()

        assert "agent1" in metrics
        assert metrics["agent1"]["success"] is True
        assert metrics["agent1"]["execution_time_ms"] == 100
        assert metrics["agent1"]["error_count"] == 0
        assert metrics["agent1"]["warning_count"] == 1

        assert "agent2" in metrics
        assert metrics["agent2"]["success"] is False
        assert metrics["agent2"]["execution_time_ms"] == 200
        assert metrics["agent2"]["error_count"] == 1
        assert metrics["agent2"]["warning_count"] == 0
