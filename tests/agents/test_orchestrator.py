"""
Unit tests for AgentOrchestrator.

Tests the orchestrator's ability to manage sequential and parallel
agent execution, error handling, and metrics collection.
"""

import pytest

from app.agents.base import BaseAgent
from app.agents.context import AgentContext, AgentResult
from app.agents.orchestrator import AgentOrchestrator, ParallelAgentGroup


class CounterAgent(BaseAgent):
    """Agent that increments a counter in context metadata."""

    async def execute(self, context: AgentContext) -> AgentResult:
        """Increment counter."""
        current = context.execution_plan.get("counter", 0)
        context.execution_plan["counter"] = current + 1

        return AgentResult(
            success=True,
            data={"counter": context.execution_plan["counter"]},
            errors=[],
            warnings=[],
            metadata={"agent": self.name},
            execution_time_ms=0,
        )


class ParallelSafeAgent(BaseAgent):
    """Agent safe for parallel execution - doesn't modify shared state."""

    async def execute(self, context: AgentContext) -> AgentResult:
        """Execute without modifying shared state."""
        # Read-only operation on context - safe for parallel execution
        file_count = len(context.files)

        return AgentResult(
            success=True,
            data={"file_count": file_count, "agent": self.name},
            errors=[],
            warnings=[],
            metadata={"agent": self.name},
            execution_time_ms=0,
        )


class SlowAgent(BaseAgent):
    """Agent that simulates slow execution."""

    async def execute(self, context: AgentContext) -> AgentResult:
        """Execute with delay."""
        import asyncio

        await asyncio.sleep(0.1)  # 100ms delay

        return AgentResult(
            success=True,
            data={"message": "Completed after delay"},
            errors=[],
            warnings=[],
            metadata={"agent": self.name},
            execution_time_ms=0,
        )


class CriticalFailureAgent(BaseAgent):
    """Agent that fails with a critical error."""

    async def execute(self, context: AgentContext) -> AgentResult:
        """Fail critically."""
        return AgentResult(
            success=False,
            data=None,
            errors=["Critical failure occurred"],
            warnings=[],
            metadata={
                "agent": self.name,
                "stage": "input_validation",
                "critical": True,
            },
            execution_time_ms=0,
        )


class NonCriticalFailureAgent(BaseAgent):
    """Agent that fails without stopping the pipeline."""

    async def execute(self, context: AgentContext) -> AgentResult:
        """Fail non-critically."""
        return AgentResult(
            success=False,
            data=None,
            errors=["Non-critical failure"],
            warnings=[],
            metadata={"agent": self.name},
            execution_time_ms=0,
        )


@pytest.mark.asyncio
class TestAgentOrchestrator:
    """Test cases for AgentOrchestrator."""

    async def test_sequential_execution(self) -> None:
        """Test sequential agent execution."""
        orchestrator = AgentOrchestrator(name="seq_test")
        orchestrator.add_sequential_agent(CounterAgent(name="agent1"))
        orchestrator.add_sequential_agent(CounterAgent(name="agent2"))
        orchestrator.add_sequential_agent(CounterAgent(name="agent3"))

        context = AgentContext(
            request_id="req-123",
            files=[],
            mode="hybrid",
        )

        result_context = await orchestrator.execute(context)

        # Counter should be incremented 3 times
        assert result_context.execution_plan["counter"] == 3

        # All agents should have results
        assert len(result_context.agent_results) == 3
        assert "agent1" in result_context.agent_results
        assert "agent2" in result_context.agent_results
        assert "agent3" in result_context.agent_results

    async def test_parallel_execution(self) -> None:
        """Test parallel agent execution."""
        orchestrator = AgentOrchestrator(name="parallel_test")
        orchestrator.add_parallel_agent_group(
            [
                SlowAgent(name="slow1"),
                SlowAgent(name="slow2"),
                SlowAgent(name="slow3"),
            ]
        )

        context = AgentContext(
            request_id="req-123",
            files=[],
            mode="hybrid",
        )

        import time

        start = time.time()
        result_context = await orchestrator.execute(context)
        duration = time.time() - start

        # All 3 agents executed
        assert len(result_context.agent_results) == 3

        # Parallel execution should be faster than sequential
        # Sequential would be 300ms, parallel should be ~100ms
        assert duration < 0.2  # 200ms threshold (with some margin)

    async def test_mixed_execution(self) -> None:
        """Test mixed sequential and parallel execution."""
        orchestrator = AgentOrchestrator(name="mixed_test")

        # Sequential agents
        orchestrator.add_sequential_agent(CounterAgent(name="seq1"))
        orchestrator.add_sequential_agent(CounterAgent(name="seq2"))

        # Parallel group - use ParallelSafeAgent to avoid race conditions
        orchestrator.add_parallel_agent_group(
            [
                ParallelSafeAgent(name="par1"),
                ParallelSafeAgent(name="par2"),
            ]
        )

        # More sequential
        orchestrator.add_sequential_agent(CounterAgent(name="seq3"))

        context = AgentContext(
            request_id="req-123",
            files=[],
            mode="hybrid",
        )

        result_context = await orchestrator.execute(context)

        # All 5 agents executed
        assert len(result_context.agent_results) == 5

        # Counter incremented 3 times (only sequential agents)
        assert result_context.execution_plan["counter"] == 3

    async def test_critical_error_stops_pipeline(self) -> None:
        """Test that critical errors stop the pipeline."""
        orchestrator = AgentOrchestrator(name="critical_test")
        orchestrator.add_sequential_agent(CounterAgent(name="agent1"))
        orchestrator.add_sequential_agent(CriticalFailureAgent(name="critical"))
        orchestrator.add_sequential_agent(CounterAgent(name="agent2"))

        context = AgentContext(
            request_id="req-123",
            files=[],
            mode="hybrid",
        )

        result_context = await orchestrator.execute(context)

        # First agent executed
        assert "agent1" in result_context.agent_results

        # Critical agent executed and failed
        assert "critical" in result_context.agent_results
        assert not result_context.agent_results["critical"].success

        # Third agent should NOT have executed (pipeline stopped)
        assert "agent2" not in result_context.agent_results

    async def test_non_critical_error_continues_pipeline(self) -> None:
        """Test that non-critical errors don't stop the pipeline."""
        orchestrator = AgentOrchestrator(name="non_critical_test")
        orchestrator.add_sequential_agent(CounterAgent(name="agent1"))
        orchestrator.add_sequential_agent(NonCriticalFailureAgent(name="non_critical"))
        orchestrator.add_sequential_agent(CounterAgent(name="agent2"))

        context = AgentContext(
            request_id="req-123",
            files=[],
            mode="hybrid",
        )

        result_context = await orchestrator.execute(context)

        # All agents should have executed
        assert "agent1" in result_context.agent_results
        assert "non_critical" in result_context.agent_results
        assert "agent2" in result_context.agent_results

        # Counter should be 2 (non-critical agent doesn't increment)
        assert result_context.execution_plan["counter"] == 2

    async def test_get_pipeline_summary(self) -> None:
        """Test pipeline summary generation."""
        orchestrator = AgentOrchestrator(name="summary_test")
        orchestrator.add_sequential_agent(CounterAgent(name="agent1"))
        orchestrator.add_sequential_agent(CounterAgent(name="agent2"))

        context = AgentContext(
            request_id="req-123",
            files=[],
            mode="hybrid",
        )

        await orchestrator.execute(context)
        summary = orchestrator.get_pipeline_summary(context)

        assert summary["orchestrator_name"] == "summary_test"
        assert summary["request_id"] == "req-123"
        assert summary["total_agents"] == 2
        assert summary["successful_agents"] == 2
        assert summary["failed_agents"] == 0
        assert summary["total_errors"] == 0
        assert "agent_metrics" in summary

    async def test_reset_all_metrics(self) -> None:
        """Test resetting metrics for all agents."""
        orchestrator = AgentOrchestrator(name="reset_test")
        agent1 = CounterAgent(name="agent1")
        agent2 = CounterAgent(name="agent2")

        orchestrator.add_sequential_agent(agent1)
        orchestrator.add_sequential_agent(agent2)

        context = AgentContext(
            request_id="req-123",
            files=[],
            mode="hybrid",
        )

        # Execute pipeline
        await orchestrator.execute(context)

        # Verify metrics exist
        assert agent1.get_metrics()["total_executions"] > 0
        assert agent2.get_metrics()["total_executions"] > 0

        # Reset all
        orchestrator.reset_all_metrics()

        # Verify metrics cleared
        assert agent1.get_metrics()["total_executions"] == 0
        assert agent2.get_metrics()["total_executions"] == 0

    def test_orchestrator_repr(self) -> None:
        """Test orchestrator string representation."""
        orchestrator = AgentOrchestrator(name="test_orch")
        orchestrator.add_sequential_agent(CounterAgent(name="seq1"))
        orchestrator.add_parallel_agent_group(
            [CounterAgent(name="par1"), CounterAgent(name="par2")]
        )

        repr_str = repr(orchestrator)

        assert "AgentOrchestrator" in repr_str
        assert "test_orch" in repr_str
        assert "sequential_agents=1" in repr_str
        assert "parallel_agents=2" in repr_str


@pytest.mark.asyncio
class TestParallelAgentGroup:
    """Test cases for ParallelAgentGroup utility."""

    async def test_run_all_agents(self) -> None:
        """Test running all agents in a parallel group."""
        group = ParallelAgentGroup(
            name="test_group",
            agents=[
                CounterAgent(name="agent1"),
                CounterAgent(name="agent2"),
                CounterAgent(name="agent3"),
            ],
        )

        context = AgentContext(
            request_id="req-123",
            files=[],
            mode="hybrid",
        )

        results = await group.run_all(context)

        assert len(results) == 3
        assert all(r.success for r in results)

    async def test_handles_agent_exceptions(self) -> None:
        """Test that group handles agent exceptions."""

        class ExceptionAgent(BaseAgent):
            async def execute(self, context: AgentContext) -> AgentResult:
                raise ValueError("Test exception")

        group = ParallelAgentGroup(
            name="exception_group",
            agents=[
                CounterAgent(name="good"),
                ExceptionAgent(name="bad"),
            ],
        )

        context = AgentContext(
            request_id="req-123",
            files=[],
            mode="hybrid",
        )

        results = await group.run_all(context)

        assert len(results) == 2
        assert results[0].success is True  # Good agent succeeded
        assert results[1].success is False  # Bad agent failed
