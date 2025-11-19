"""
Unit tests for SynthesisAgent.

Tests issue merging, deduplication, and sorting functionality.
"""

import pytest

from app.agents.context import AgentContext
from app.agents.synthesis import SynthesisAgent
from app.api.v1.schemas import FileInput, Issue, IssueSuggestion


@pytest.mark.asyncio
class TestSynthesisAgent:
    """Test cases for SynthesisAgent class."""

    def create_sample_issue(
        self, file: str, line: int, issue_type: str, severity: str, detected_by: str
    ) -> Issue:
        """Helper to create sample issues for testing."""
        return Issue(
            file=file,
            line=line,
            column=0,
            severity=severity,
            type=issue_type,
            message=f"Test issue at line {line}",
            detected_by=detected_by,
            suggestion=IssueSuggestion(action="remove", explanation="Test suggestion"),
        )

    async def test_merge_rules_only_mode(self) -> None:
        """Test synthesis in rules-only mode."""
        agent = SynthesisAgent(name="synthesizer")
        context = AgentContext(
            request_id="req-123",
            files=[],
            mode="rules-only",
        )

        # Add rule issues
        context.rule_issues = [
            self.create_sample_issue(
                "test.py", 10, "redundant-assertion", "warning", "rule_engine"
            ),
            self.create_sample_issue(
                "test.py", 20, "missing-assertion", "error", "rule_engine"
            ),
        ]

        result = await agent.run(context)

        assert result.success is True
        assert len(context.merged_issues) == 2
        assert result.data["total_issues"] == 2
        assert result.data["rule_issues"] == 2
        assert result.data["llm_issues"] == 0

    async def test_merge_llm_only_mode(self) -> None:
        """Test synthesis in llm-only mode."""
        agent = SynthesisAgent(name="synthesizer")
        context = AgentContext(
            request_id="req-123",
            files=[],
            mode="llm-only",
        )

        # Add LLM issues
        context.llm_issues = [
            self.create_sample_issue("test.py", 10, "weak-assertion", "warning", "llm"),
            self.create_sample_issue("test.py", 15, "test-smell", "info", "llm"),
        ]

        result = await agent.run(context)

        assert result.success is True
        assert len(context.merged_issues) == 2
        assert result.data["total_issues"] == 2
        assert result.data["rule_issues"] == 0
        assert result.data["llm_issues"] == 2

    async def test_merge_hybrid_mode(self) -> None:
        """Test synthesis merges both sources in hybrid mode."""
        agent = SynthesisAgent(name="synthesizer")
        context = AgentContext(
            request_id="req-123",
            files=[],
            mode="hybrid",
        )

        # Add both rule and LLM issues
        context.rule_issues = [
            self.create_sample_issue(
                "test.py", 10, "redundant-assertion", "warning", "rule_engine"
            ),
        ]
        context.llm_issues = [
            self.create_sample_issue("test.py", 20, "weak-assertion", "warning", "llm"),
        ]

        result = await agent.run(context)

        assert result.success is True
        assert len(context.merged_issues) == 2
        assert result.data["total_issues"] == 2
        assert result.data["rule_issues"] == 1
        assert result.data["llm_issues"] == 1

    async def test_deduplication(self) -> None:
        """Test duplicate issues are removed."""
        agent = SynthesisAgent(name="synthesizer")
        context = AgentContext(
            request_id="req-123",
            files=[],
            mode="hybrid",
        )

        # Add duplicate issues (same file, line, type)
        context.rule_issues = [
            self.create_sample_issue(
                "test.py", 10, "redundant-assertion", "warning", "rule_engine"
            ),
        ]
        context.llm_issues = [
            self.create_sample_issue(
                "test.py", 10, "redundant-assertion", "warning", "llm"
            ),
        ]

        result = await agent.run(context)

        assert result.success is True
        assert len(context.merged_issues) == 1  # Duplicate removed
        assert result.data["duplicates_removed"] == 1

    async def test_sorting_by_severity(self) -> None:
        """Test issues are sorted by severity."""
        agent = SynthesisAgent(name="synthesizer")
        context = AgentContext(
            request_id="req-123",
            files=[],
            mode="rules-only",
        )

        context.rule_issues = [
            self.create_sample_issue("test.py", 10, "issue1", "info", "rule_engine"),
            self.create_sample_issue("test.py", 20, "issue2", "error", "rule_engine"),
            self.create_sample_issue("test.py", 30, "issue3", "warning", "rule_engine"),
        ]

        result = await agent.run(context)

        assert result.success is True
        # Errors should come first
        assert context.merged_issues[0].severity == "error"
        assert context.merged_issues[1].severity == "warning"
        assert context.merged_issues[2].severity == "info"

    async def test_sorting_by_file_and_line(self) -> None:
        """Test issues are sorted by file and line within same severity."""
        agent = SynthesisAgent(name="synthesizer")
        context = AgentContext(
            request_id="req-123",
            files=[],
            mode="rules-only",
        )

        context.rule_issues = [
            self.create_sample_issue("b.py", 20, "issue1", "error", "rule_engine"),
            self.create_sample_issue("a.py", 10, "issue2", "error", "rule_engine"),
            self.create_sample_issue("a.py", 5, "issue3", "error", "rule_engine"),
        ]

        result = await agent.run(context)

        assert result.success is True
        # Should be sorted by file then line
        assert context.merged_issues[0].file == "a.py"
        assert context.merged_issues[0].line == 5
        assert context.merged_issues[1].file == "a.py"
        assert context.merged_issues[1].line == 10
        assert context.merged_issues[2].file == "b.py"
        assert context.merged_issues[2].line == 20

    async def test_statistics_calculation(self) -> None:
        """Test correct statistics are calculated."""
        agent = SynthesisAgent(name="synthesizer")
        context = AgentContext(
            request_id="req-123",
            files=[],
            mode="hybrid",
        )

        context.rule_issues = [
            self.create_sample_issue(
                "test.py", 10, "redundant-assertion", "error", "rule_engine"
            ),
            self.create_sample_issue(
                "test.py", 20, "missing-assertion", "warning", "rule_engine"
            ),
        ]
        context.llm_issues = [
            self.create_sample_issue("test.py", 30, "weak-assertion", "info", "llm"),
        ]

        result = await agent.run(context)

        assert result.data["by_severity"]["error"] == 1
        assert result.data["by_severity"]["warning"] == 1
        assert result.data["by_severity"]["info"] == 1
        assert result.data["by_source"]["rule_engine"] == 2
        assert result.data["by_source"]["llm"] == 1

    async def test_empty_issues(self) -> None:
        """Test handling of no issues."""
        agent = SynthesisAgent(name="synthesizer")
        context = AgentContext(
            request_id="req-123",
            files=[],
            mode="hybrid",
        )

        context.rule_issues = []
        context.llm_issues = []

        result = await agent.run(context)

        assert result.success is True
        assert len(context.merged_issues) == 0
        assert result.data["total_issues"] == 0

    async def test_validation_missing_rule_issues(self) -> None:
        """Test agent warns about missing rule_issues in rules-only mode."""
        agent = SynthesisAgent(name="synthesizer")
        context = AgentContext(
            request_id="req-123",
            files=[],
            mode="rules-only",
        )

        result = await agent.run(context)

        # Should succeed with warning about empty issues
        assert result.success is True
        assert len(result.warnings) > 0
        assert any("rule_issues" in w.lower() for w in result.warnings)

    async def test_validation_missing_llm_issues(self) -> None:
        """Test agent warns about missing llm_issues in llm-only mode."""
        agent = SynthesisAgent(name="synthesizer")
        context = AgentContext(
            request_id="req-123",
            files=[],
            mode="llm-only",
        )

        result = await agent.run(context)

        # Should succeed with warning about empty issues
        assert result.success is True
        assert len(result.warnings) > 0
        assert any("llm_issues" in w.lower() for w in result.warnings)

    async def test_metrics_tracking(self) -> None:
        """Test agent tracks execution metrics."""
        agent = SynthesisAgent(name="synthesizer")
        context = AgentContext(
            request_id="req-123",
            files=[],
            mode="rules-only",
        )
        context.rule_issues = []

        await agent.run(context)
        metrics = agent.get_metrics()

        assert metrics["total_executions"] == 1
        assert metrics["total_errors"] == 0
        assert metrics["success_rate"] == 1.0
