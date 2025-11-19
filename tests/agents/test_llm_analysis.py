"""
Unit tests for LLMAnalysisAgent.

Tests LLM-based analysis, mode handling, and uncertain case detection.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.context import AgentContext
from app.agents.llm_analysis import LLMAnalysisAgent
from app.analyzers.ast_parser import parse_test_file
from app.api.v1.schemas import FileInput


@pytest.mark.asyncio
class TestLLMAnalysisAgent:
    """Test cases for LLMAnalysisAgent class."""

    @patch("app.agents.llm_analysis.get_llm_client")
    async def test_analysis_in_llm_only_mode(
        self, mock_get_client, sample_test_code: str
    ) -> None:
        """Test agent runs in llm-only mode."""
        # Mock LLM client
        mock_client = MagicMock()
        mock_client.chat_completion = AsyncMock(
            return_value=json.dumps(
                {
                    "issues": [],
                    "overall_quality": "good",
                    "confidence": 0.9,
                }
            )
        )
        mock_client.close = AsyncMock()
        mock_get_client.return_value = mock_client

        agent = LLMAnalysisAgent(name="llm_analyzer")
        parsed_file = parse_test_file("test.py", sample_test_code)

        context = AgentContext(
            request_id="req-123",
            files=[FileInput(path="test.py", content=sample_test_code)],
            mode="llm-only",
        )
        context.parsed_files = [parsed_file]
        context.execution_plan = {"run_llm": True}

        result = await agent.run(context)

        assert result.success is True
        assert "skipped" not in result.data or not result.data["skipped"]
        assert result.data["tests_analyzed"] >= 1

    @patch("app.agents.llm_analysis.get_llm_client")
    async def test_analysis_in_hybrid_mode(
        self, mock_get_client, sample_test_code: str
    ) -> None:
        """Test agent runs in hybrid mode with selective analysis."""
        # Mock LLM client
        mock_client = MagicMock()
        mock_client.chat_completion = AsyncMock(
            return_value=json.dumps(
                {
                    "issues": [],
                    "overall_quality": "good",
                    "confidence": 0.9,
                }
            )
        )
        mock_client.close = AsyncMock()
        mock_get_client.return_value = mock_client

        agent = LLMAnalysisAgent(name="llm_analyzer")
        parsed_file = parse_test_file("test.py", sample_test_code)

        context = AgentContext(
            request_id="req-123",
            files=[FileInput(path="test.py", content=sample_test_code)],
            mode="hybrid",
        )
        context.parsed_files = [parsed_file]
        context.execution_plan = {"run_llm": True}

        result = await agent.run(context)

        assert result.success is True

    async def test_skipped_in_rules_only_mode(self, sample_test_code: str) -> None:
        """Test agent skips execution in rules-only mode."""
        agent = LLMAnalysisAgent(name="llm_analyzer")
        parsed_file = parse_test_file("test.py", sample_test_code)

        context = AgentContext(
            request_id="req-123",
            files=[FileInput(path="test.py", content=sample_test_code)],
            mode="rules-only",
        )
        context.parsed_files = [parsed_file]
        context.execution_plan = {"run_llm": False}

        result = await agent.run(context)

        assert result.success is True
        assert result.data.get("skipped") is True

    @patch("app.agents.llm_analysis.get_llm_client")
    async def test_detects_assertion_issues(
        self, mock_get_client, sample_test_code: str
    ) -> None:
        """Test agent detects assertion quality issues."""
        # Mock LLM client with assertion issues
        mock_client = MagicMock()
        mock_client.chat_completion = AsyncMock(
            return_value=json.dumps(
                {
                    "issues": [
                        {
                            "type": "weak-assertion",
                            "line": 2,
                            "severity": "warning",
                            "message": "Assertion could be more specific",
                            "suggestion": "Use more specific assertion",
                            "example_code": "assert result == 2",
                            "confidence": 0.85,
                        }
                    ],
                    "overall_quality": "fair",
                    "confidence": 0.8,
                }
            )
        )
        mock_client.close = AsyncMock()
        mock_get_client.return_value = mock_client

        agent = LLMAnalysisAgent(name="llm_analyzer")
        parsed_file = parse_test_file("test.py", sample_test_code)

        context = AgentContext(
            request_id="req-123",
            files=[],
            mode="llm-only",
        )
        context.parsed_files = [parsed_file]
        context.execution_plan = {"run_llm": True}

        result = await agent.run(context)

        assert result.success is True
        assert result.data["issue_count"] > 0

    @patch("app.agents.llm_analysis.get_llm_client")
    async def test_detects_test_smells(
        self, mock_get_client, sample_test_code: str
    ) -> None:
        """Test agent detects test smells."""
        # Mock LLM client with test smell
        mock_client = MagicMock()

        # Return different responses for assertion quality and test smells
        mock_client.chat_completion = AsyncMock(
            side_effect=[
                # First call - assertion quality (empty)
                json.dumps(
                    {
                        "issues": [],
                        "overall_quality": "good",
                        "confidence": 0.9,
                    }
                ),
                # Second call - test smells
                json.dumps(
                    {
                        "smells": [
                            {
                                "type": "timing-dependent",
                                "line": 2,
                                "severity": "warning",
                                "description": "Uses time.sleep",
                                "impact": "Can cause flaky tests",
                                "suggestion": "Use mock time",
                                "example_code": "mock.patch('time.sleep')",
                                "confidence": 0.9,
                            }
                        ],
                        "confidence": 0.85,
                    }
                ),
            ]
        )
        mock_client.close = AsyncMock()
        mock_get_client.return_value = mock_client

        agent = LLMAnalysisAgent(name="llm_analyzer")
        parsed_file = parse_test_file("test.py", sample_test_code)

        context = AgentContext(
            request_id="req-123",
            files=[],
            mode="llm-only",
        )
        context.parsed_files = [parsed_file]
        context.execution_plan = {"run_llm": True}

        result = await agent.run(context)

        assert result.success is True

    @patch("app.agents.llm_analysis.get_llm_client")
    async def test_handles_syntax_errors(
        self, mock_get_client, syntax_error_code: str
    ) -> None:
        """Test agent skips files with syntax errors."""
        mock_client = MagicMock()
        mock_client.close = AsyncMock()
        mock_get_client.return_value = mock_client

        agent = LLMAnalysisAgent(name="llm_analyzer")
        parsed_file = parse_test_file("bad.py", syntax_error_code)

        context = AgentContext(
            request_id="req-123",
            files=[],
            mode="llm-only",
        )
        context.parsed_files = [parsed_file]
        context.execution_plan = {"run_llm": True}

        result = await agent.run(context)

        assert result.success is True
        assert len(result.warnings) > 0

    @patch("app.agents.llm_analysis.get_llm_client")
    async def test_statistics_calculation(
        self, mock_get_client, sample_test_code: str
    ) -> None:
        """Test agent calculates correct statistics."""
        mock_client = MagicMock()
        mock_client.chat_completion = AsyncMock(
            return_value=json.dumps(
                {
                    "issues": [],
                    "overall_quality": "good",
                    "confidence": 0.9,
                }
            )
        )
        mock_client.close = AsyncMock()
        mock_get_client.return_value = mock_client

        agent = LLMAnalysisAgent(name="llm_analyzer")
        parsed_file = parse_test_file("test.py", sample_test_code)

        context = AgentContext(
            request_id="req-123",
            files=[],
            mode="llm-only",
        )
        context.parsed_files = [parsed_file]
        context.execution_plan = {"run_llm": True}

        result = await agent.run(context)

        assert "tests_analyzed" in result.data
        assert "tests_skipped" in result.data
        assert isinstance(result.data["tests_analyzed"], int)
        assert isinstance(result.data["tests_skipped"], int)

    async def test_validation_no_parsed_files(self) -> None:
        """Test input validation catches missing parsed files."""
        agent = LLMAnalysisAgent(name="llm_analyzer")
        context = AgentContext(
            request_id="req-123",
            files=[],
            mode="llm-only",
        )
        context.execution_plan = {"run_llm": True}

        result = await agent.run(context)

        assert result.success is False
        assert result.metadata["stage"] == "input_validation"

    @patch("app.agents.llm_analysis.get_llm_client")
    async def test_metrics_tracking(
        self, mock_get_client, sample_test_code: str
    ) -> None:
        """Test agent tracks execution metrics."""
        mock_client = MagicMock()
        mock_client.chat_completion = AsyncMock(
            return_value=json.dumps(
                {
                    "issues": [],
                    "overall_quality": "good",
                    "confidence": 0.9,
                }
            )
        )
        mock_client.close = AsyncMock()
        mock_get_client.return_value = mock_client

        agent = LLMAnalysisAgent(name="llm_analyzer")
        parsed_file = parse_test_file("test.py", sample_test_code)

        context = AgentContext(
            request_id="req-123",
            files=[],
            mode="llm-only",
        )
        context.parsed_files = [parsed_file]
        context.execution_plan = {"run_llm": True}

        await agent.run(context)
        metrics = agent.get_metrics()

        assert metrics["total_executions"] == 1
        assert metrics["total_errors"] == 0
        assert metrics["success_rate"] == 1.0
