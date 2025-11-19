"""
Unit tests for RuleAnalysisAgent.

Tests rule-based analysis, mode handling, and issue detection.
"""

import pytest

from app.agents.context import AgentContext
from app.agents.rule_analysis import RuleAnalysisAgent
from app.analyzers.ast_parser import parse_test_file
from app.api.v1.schemas import FileInput


@pytest.mark.asyncio
class TestRuleAnalysisAgent:
    """Test cases for RuleAnalysisAgent class."""

    async def test_analysis_in_rules_only_mode(
        self, redundant_assertion_code: str
    ) -> None:
        """Test agent runs in rules-only mode."""
        agent = RuleAnalysisAgent(name="rule_analyzer")

        # Parse the file first
        parsed_file = parse_test_file("test.py", redundant_assertion_code)

        context = AgentContext(
            request_id="req-123",
            files=[FileInput(path="test.py", content=redundant_assertion_code)],
            mode="rules-only",
        )
        context.parsed_files = [parsed_file]
        context.execution_plan = {"run_rules": True}

        result = await agent.run(context)

        assert result.success is True
        assert "skipped" not in result.data or not result.data["skipped"]
        assert result.data["files_analyzed"] >= 1
        assert len(context.rule_issues) > 0

    async def test_analysis_in_hybrid_mode(self, redundant_assertion_code: str) -> None:
        """Test agent runs in hybrid mode."""
        agent = RuleAnalysisAgent(name="rule_analyzer")
        parsed_file = parse_test_file("test.py", redundant_assertion_code)

        context = AgentContext(
            request_id="req-123",
            files=[FileInput(path="test.py", content=redundant_assertion_code)],
            mode="hybrid",
        )
        context.parsed_files = [parsed_file]
        context.execution_plan = {"run_rules": True}

        result = await agent.run(context)

        assert result.success is True
        assert result.data["files_analyzed"] >= 1

    async def test_skipped_in_llm_only_mode(self, sample_test_code: str) -> None:
        """Test agent skips execution in llm-only mode."""
        agent = RuleAnalysisAgent(name="rule_analyzer")
        parsed_file = parse_test_file("test.py", sample_test_code)

        context = AgentContext(
            request_id="req-123",
            files=[FileInput(path="test.py", content=sample_test_code)],
            mode="llm-only",
        )
        context.parsed_files = [parsed_file]
        context.execution_plan = {"run_rules": False}

        result = await agent.run(context)

        assert result.success is True
        assert result.data.get("skipped") is True

    async def test_detects_redundant_assertions(
        self, redundant_assertion_code: str
    ) -> None:
        """Test agent detects redundant assertions."""
        agent = RuleAnalysisAgent(name="rule_analyzer")
        parsed_file = parse_test_file("test.py", redundant_assertion_code)

        context = AgentContext(
            request_id="req-123",
            files=[],
            mode="rules-only",
        )
        context.parsed_files = [parsed_file]
        context.execution_plan = {"run_rules": True}

        result = await agent.run(context)

        assert result.success is True
        assert result.data["issue_count"] > 0
        assert any(issue.type == "redundant-assertion" for issue in context.rule_issues)

    async def test_detects_missing_assertions(
        self, missing_assertion_code: str
    ) -> None:
        """Test agent detects missing assertions."""
        agent = RuleAnalysisAgent(name="rule_analyzer")
        parsed_file = parse_test_file("test.py", missing_assertion_code)

        context = AgentContext(
            request_id="req-123",
            files=[],
            mode="rules-only",
        )
        context.parsed_files = [parsed_file]
        context.execution_plan = {"run_rules": True}

        result = await agent.run(context)

        assert result.success is True
        assert result.data["issue_count"] > 0
        assert any(issue.type == "missing-assertion" for issue in context.rule_issues)

    async def test_detects_trivial_assertions(
        self, trivial_assertion_code: str
    ) -> None:
        """Test agent detects trivial assertions."""
        agent = RuleAnalysisAgent(name="rule_analyzer")
        parsed_file = parse_test_file("test.py", trivial_assertion_code)

        context = AgentContext(
            request_id="req-123",
            files=[],
            mode="rules-only",
        )
        context.parsed_files = [parsed_file]
        context.execution_plan = {"run_rules": True}

        result = await agent.run(context)

        assert result.success is True
        assert result.data["issue_count"] > 0
        assert any(issue.type == "trivial-assertion" for issue in context.rule_issues)

    async def test_detects_unused_fixtures(self, unused_fixture_code: str) -> None:
        """Test agent detects unused fixtures."""
        agent = RuleAnalysisAgent(name="rule_analyzer")
        parsed_file = parse_test_file("test.py", unused_fixture_code)

        context = AgentContext(
            request_id="req-123",
            files=[],
            mode="rules-only",
        )
        context.parsed_files = [parsed_file]
        context.execution_plan = {"run_rules": True}

        result = await agent.run(context)

        assert result.success is True
        assert result.data["issue_count"] > 0
        assert any(issue.type == "unused-fixture" for issue in context.rule_issues)

    async def test_handles_syntax_errors(self, syntax_error_code: str) -> None:
        """Test agent skips files with syntax errors."""
        agent = RuleAnalysisAgent(name="rule_analyzer")
        parsed_file = parse_test_file("bad.py", syntax_error_code)

        context = AgentContext(
            request_id="req-123",
            files=[],
            mode="rules-only",
        )
        context.parsed_files = [parsed_file]
        context.execution_plan = {"run_rules": True}

        result = await agent.run(context)

        assert result.success is True
        assert result.data["files_skipped"] == 1
        assert len(result.warnings) > 0

    async def test_statistics_calculation(self, redundant_assertion_code: str) -> None:
        """Test agent calculates correct statistics."""
        agent = RuleAnalysisAgent(name="rule_analyzer")
        parsed_file = parse_test_file("test.py", redundant_assertion_code)

        context = AgentContext(
            request_id="req-123",
            files=[],
            mode="rules-only",
        )
        context.parsed_files = [parsed_file]
        context.execution_plan = {"run_rules": True}

        result = await agent.run(context)

        assert "by_severity" in result.data
        assert "by_type" in result.data
        assert isinstance(result.data["by_severity"], dict)
        assert isinstance(result.data["by_type"], dict)

    async def test_validation_no_parsed_files(self) -> None:
        """Test input validation catches missing parsed files."""
        agent = RuleAnalysisAgent(name="rule_analyzer")
        context = AgentContext(
            request_id="req-123",
            files=[],
            mode="rules-only",
        )
        context.execution_plan = {"run_rules": True}

        result = await agent.run(context)

        assert result.success is False
        assert result.metadata["stage"] == "input_validation"

    async def test_metrics_tracking(self, sample_test_code: str) -> None:
        """Test agent tracks execution metrics."""
        agent = RuleAnalysisAgent(name="rule_analyzer")
        parsed_file = parse_test_file("test.py", sample_test_code)

        context = AgentContext(
            request_id="req-123",
            files=[],
            mode="rules-only",
        )
        context.parsed_files = [parsed_file]
        context.execution_plan = {"run_rules": True}

        await agent.run(context)
        metrics = agent.get_metrics()

        assert metrics["total_executions"] == 1
        assert metrics["total_errors"] == 0
        assert metrics["success_rate"] == 1.0
