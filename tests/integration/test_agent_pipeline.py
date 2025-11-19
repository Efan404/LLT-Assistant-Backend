"""
Integration tests for the complete agent pipeline.

Tests the end-to-end execution of the agent framework with all
analysis agents working together.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.context import AgentContext
from app.agents.input_processing import InputProcessingAgent
from app.agents.llm_analysis import LLMAnalysisAgent
from app.agents.orchestrator import AgentOrchestrator
from app.agents.parsing import ParsingAgent
from app.agents.rule_analysis import RuleAnalysisAgent
from app.agents.strategy_planning import StrategyPlanningAgent
from app.agents.synthesis import SynthesisAgent
from app.api.v1.schemas import FileInput


@pytest.mark.asyncio
class TestAgentPipeline:
    """Integration tests for complete agent pipeline."""

    async def test_rules_only_pipeline(
        self, redundant_assertion_code: str
    ) -> None:
        """Test complete pipeline in rules-only mode."""
        orchestrator = AgentOrchestrator(name="test_pipeline")

        # Build pipeline
        orchestrator.add_sequential_agent(InputProcessingAgent(name="input"))
        orchestrator.add_sequential_agent(StrategyPlanningAgent(name="strategy"))
        orchestrator.add_sequential_agent(ParsingAgent(name="parser"))
        orchestrator.add_sequential_agent(RuleAnalysisAgent(name="rules"))
        orchestrator.add_sequential_agent(SynthesisAgent(name="synthesis"))

        # Create context
        context = AgentContext(
            request_id="test-123",
            files=[
                FileInput(path="test.py", content=redundant_assertion_code)
            ],
            mode="rules-only",
        )

        # Execute pipeline
        result_context = await orchestrator.execute(context)

        # Verify results
        assert not result_context.has_errors()
        assert len(result_context.parsed_files) == 1
        assert len(result_context.rule_issues) > 0
        assert len(result_context.merged_issues) > 0
        assert result_context.execution_plan["run_rules"] is True
        assert result_context.execution_plan["run_llm"] is False

    @patch("app.agents.llm_analysis.get_llm_client")
    async def test_llm_only_pipeline(
        self, mock_get_client, sample_test_code: str
    ) -> None:
        """Test complete pipeline in llm-only mode."""
        # Mock LLM client
        mock_client = MagicMock()
        mock_client.chat_completion = AsyncMock(
            return_value='{"issues": [], "overall_quality": "good", "confidence": 0.9}'
        )
        mock_client.close = AsyncMock()
        mock_get_client.return_value = mock_client

        orchestrator = AgentOrchestrator(name="test_pipeline")

        # Build pipeline
        orchestrator.add_sequential_agent(InputProcessingAgent(name="input"))
        orchestrator.add_sequential_agent(StrategyPlanningAgent(name="strategy"))
        orchestrator.add_sequential_agent(ParsingAgent(name="parser"))
        orchestrator.add_sequential_agent(LLMAnalysisAgent(name="llm"))
        orchestrator.add_sequential_agent(SynthesisAgent(name="synthesis"))

        # Create context
        context = AgentContext(
            request_id="test-123",
            files=[
                FileInput(path="test.py", content=sample_test_code)
            ],
            mode="llm-only",
        )

        # Execute pipeline
        result_context = await orchestrator.execute(context)

        # Verify results
        assert not result_context.has_errors()
        assert len(result_context.parsed_files) == 1
        assert result_context.execution_plan["run_rules"] is False
        assert result_context.execution_plan["run_llm"] is True

    @patch("app.agents.llm_analysis.get_llm_client")
    async def test_hybrid_pipeline(
        self, mock_get_client, redundant_assertion_code: str
    ) -> None:
        """Test complete pipeline in hybrid mode."""
        # Mock LLM client
        mock_client = MagicMock()
        mock_client.chat_completion = AsyncMock(
            return_value='{"issues": [], "overall_quality": "good", "confidence": 0.9}'
        )
        mock_client.close = AsyncMock()
        mock_get_client.return_value = mock_client

        orchestrator = AgentOrchestrator(name="test_pipeline")

        # Build pipeline
        orchestrator.add_sequential_agent(InputProcessingAgent(name="input"))
        orchestrator.add_sequential_agent(StrategyPlanningAgent(name="strategy"))
        orchestrator.add_sequential_agent(ParsingAgent(name="parser"))

        # Parallel analysis
        orchestrator.add_parallel_agent_group([
            RuleAnalysisAgent(name="rules"),
            LLMAnalysisAgent(name="llm"),
        ])

        # Synthesis (as a parallel group of one to run after the analysis group)
        orchestrator.add_parallel_agent_group([
            SynthesisAgent(name="synthesis")
        ])

        # Create context
        context = AgentContext(
            request_id="test-123",
            files=[
                FileInput(path="test.py", content=redundant_assertion_code)
            ],
            mode="hybrid",
        )

        # Execute pipeline
        result_context = await orchestrator.execute(context)

        # Verify results
        assert not result_context.has_errors()
        assert len(result_context.parsed_files) == 1
        assert len(result_context.rule_issues) > 0
        assert len(result_context.merged_issues) > 0
        assert result_context.execution_plan["run_rules"] is True
        assert result_context.execution_plan["run_llm"] is True

    async def test_multiple_files_pipeline(
        self, sample_test_code: str, redundant_assertion_code: str
    ) -> None:
        """Test pipeline with multiple files."""
        orchestrator = AgentOrchestrator(name="test_pipeline")

        # Build pipeline
        orchestrator.add_sequential_agent(InputProcessingAgent(name="input"))
        orchestrator.add_sequential_agent(StrategyPlanningAgent(name="strategy"))
        orchestrator.add_sequential_agent(ParsingAgent(name="parser"))
        orchestrator.add_sequential_agent(RuleAnalysisAgent(name="rules"))
        orchestrator.add_sequential_agent(SynthesisAgent(name="synthesis"))

        # Create context with multiple files
        context = AgentContext(
            request_id="test-123",
            files=[
                FileInput(path="test1.py", content=sample_test_code),
                FileInput(path="test2.py", content=redundant_assertion_code),
            ],
            mode="rules-only",
        )

        # Execute pipeline
        result_context = await orchestrator.execute(context)

        # Verify results
        assert not result_context.has_errors()
        assert len(result_context.parsed_files) == 2
        assert len(result_context.merged_issues) > 0

    async def test_pipeline_with_syntax_errors(
        self, syntax_error_code: str
    ) -> None:
        """Test pipeline handles syntax errors gracefully."""
        orchestrator = AgentOrchestrator(name="test_pipeline")

        # Build pipeline
        orchestrator.add_sequential_agent(InputProcessingAgent(name="input"))
        orchestrator.add_sequential_agent(StrategyPlanningAgent(name="strategy"))
        orchestrator.add_sequential_agent(ParsingAgent(name="parser"))
        orchestrator.add_sequential_agent(RuleAnalysisAgent(name="rules"))
        orchestrator.add_sequential_agent(SynthesisAgent(name="synthesis"))

        # Create context
        context = AgentContext(
            request_id="test-123",
            files=[
                FileInput(path="bad.py", content=syntax_error_code)
            ],
            mode="rules-only",
        )

        # Execute pipeline
        result_context = await orchestrator.execute(context)

        # Verify pipeline completes despite syntax errors
        assert len(result_context.parsed_files) == 1
        assert result_context.parsed_files[0].has_syntax_errors

    async def test_pipeline_input_validation_failure(self) -> None:
        """Test pipeline stops on input validation failure."""
        orchestrator = AgentOrchestrator(name="test_pipeline")

        # Build pipeline
        orchestrator.add_sequential_agent(InputProcessingAgent(name="input"))
        orchestrator.add_sequential_agent(StrategyPlanningAgent(name="strategy"))

        # Create context with invalid mode
        context = AgentContext(
            request_id="test-123",
            files=[
                FileInput(path="test.py", content="test")
            ],
            mode="invalid-mode",
        )

        # Execute pipeline
        result_context = await orchestrator.execute(context)

        # Verify pipeline stopped
        assert result_context.has_errors()
        assert "input" in result_context.agent_results
        assert not result_context.agent_results["input"].success

    async def test_pipeline_metrics(
        self, sample_test_code: str
    ) -> None:
        """Test pipeline collects metrics from all agents."""
        orchestrator = AgentOrchestrator(name="test_pipeline")

        # Build pipeline
        orchestrator.add_sequential_agent(InputProcessingAgent(name="input"))
        orchestrator.add_sequential_agent(StrategyPlanningAgent(name="strategy"))
        orchestrator.add_sequential_agent(ParsingAgent(name="parser"))
        orchestrator.add_sequential_agent(RuleAnalysisAgent(name="rules"))
        orchestrator.add_sequential_agent(SynthesisAgent(name="synthesis"))

        # Create context
        context = AgentContext(
            request_id="test-123",
            files=[
                FileInput(path="test.py", content=sample_test_code)
            ],
            mode="rules-only",
        )

        # Execute pipeline
        result_context = await orchestrator.execute(context)

        # Verify metrics
        metrics = result_context.get_agent_metrics()
        assert "input" in metrics
        assert "strategy" in metrics
        assert "parser" in metrics
        assert "rules" in metrics
        assert "synthesis" in metrics

        # Verify each metric has expected fields
        for agent_name, agent_metrics in metrics.items():
            assert "success" in agent_metrics
            assert "execution_time_ms" in agent_metrics
            assert agent_metrics["execution_time_ms"] >= 0

    async def test_pipeline_summary(
        self, sample_test_code: str
    ) -> None:
        """Test pipeline generates execution summary."""
        orchestrator = AgentOrchestrator(name="test_pipeline")

        # Build pipeline
        orchestrator.add_sequential_agent(InputProcessingAgent(name="input"))
        orchestrator.add_sequential_agent(StrategyPlanningAgent(name="strategy"))
        orchestrator.add_sequential_agent(ParsingAgent(name="parser"))
        orchestrator.add_sequential_agent(RuleAnalysisAgent(name="rules"))
        orchestrator.add_sequential_agent(SynthesisAgent(name="synthesis"))

        # Create context
        context = AgentContext(
            request_id="test-123",
            files=[
                FileInput(path="test.py", content=sample_test_code)
            ],
            mode="rules-only",
        )

        # Execute pipeline
        result_context = await orchestrator.execute(context)

        # Get summary
        summary = orchestrator.get_pipeline_summary(result_context)

        # Verify summary structure
        assert "orchestrator_name" in summary
        assert "request_id" in summary
        assert "total_execution_time_ms" in summary
        assert "total_agents" in summary
        assert "successful_agents" in summary
        assert "failed_agents" in summary
        assert "agent_metrics" in summary
