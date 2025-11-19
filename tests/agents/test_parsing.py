"""
Unit tests for ParsingAgent.

Tests parsing agent functionality including file parsing, error handling,
and validation.
"""

import pytest

from app.agents.context import AgentContext
from app.agents.parsing import ParsingAgent
from app.api.v1.schemas import FileInput


@pytest.mark.asyncio
class TestParsingAgent:
    """Test cases for ParsingAgent class."""

    async def test_successful_parsing(self, sample_test_code: str) -> None:
        """Test agent successfully parses valid test file."""
        agent = ParsingAgent(name="parser")
        context = AgentContext(
            request_id="req-123",
            files=[FileInput(path="test.py", content=sample_test_code)],
            mode="hybrid",
        )

        result = await agent.run(context)

        assert result.success is True
        assert result.data["parsed_count"] == 1
        assert result.data["syntax_errors"] == 0
        assert result.data["total_test_functions"] == 1
        assert len(context.parsed_files) == 1
        assert context.parsed_files[0].file_path == "test.py"
        assert not context.parsed_files[0].has_syntax_errors

    async def test_parsing_multiple_files(
        self, sample_test_code: str, sample_test_class: str
    ) -> None:
        """Test agent parses multiple files in parallel."""
        agent = ParsingAgent(name="parser")
        context = AgentContext(
            request_id="req-123",
            files=[
                FileInput(path="test1.py", content=sample_test_code),
                FileInput(path="test2.py", content=sample_test_class),
            ],
            mode="hybrid",
        )

        result = await agent.run(context)

        assert result.success is True
        assert result.data["parsed_count"] == 2
        assert len(context.parsed_files) == 2

    async def test_parsing_syntax_error(self, syntax_error_code: str) -> None:
        """Test agent handles syntax errors gracefully."""
        agent = ParsingAgent(name="parser")
        context = AgentContext(
            request_id="req-123",
            files=[FileInput(path="bad.py", content=syntax_error_code)],
            mode="hybrid",
        )

        result = await agent.run(context)

        assert result.success is True  # Parsing succeeds even with syntax errors
        assert result.data["parsed_count"] == 1
        assert result.data["syntax_errors"] == 1
        assert len(result.warnings) == 1
        assert "Syntax error" in result.warnings[0]
        assert context.parsed_files[0].has_syntax_errors is True

    async def test_parsing_mixed_files(
        self, sample_test_code: str, syntax_error_code: str
    ) -> None:
        """Test agent handles mix of valid and invalid files."""
        agent = ParsingAgent(name="parser")
        context = AgentContext(
            request_id="req-123",
            files=[
                FileInput(path="good.py", content=sample_test_code),
                FileInput(path="bad.py", content=syntax_error_code),
            ],
            mode="hybrid",
        )

        result = await agent.run(context)

        assert result.success is True
        assert result.data["parsed_count"] == 2
        assert result.data["syntax_errors"] == 1

    async def test_validation_no_files(self) -> None:
        """Test input validation catches missing files."""
        agent = ParsingAgent(name="parser")
        context = AgentContext(
            request_id="req-123",
            files=[],
            mode="hybrid",
        )

        result = await agent.run(context)

        assert result.success is False
        assert any("No files" in error for error in result.errors)
        assert result.metadata["stage"] == "input_validation"

    async def test_validation_empty_content(self) -> None:
        """Test input validation catches empty file content."""
        agent = ParsingAgent(name="parser")
        context = AgentContext(
            request_id="req-123",
            files=[FileInput(path="empty.py", content="")],
            mode="hybrid",
        )

        result = await agent.run(context)

        assert result.success is False
        assert any("empty content" in error for error in result.errors)

    async def test_parsing_test_class(self, sample_test_class: str) -> None:
        """Test agent correctly parses test classes."""
        agent = ParsingAgent(name="parser")
        context = AgentContext(
            request_id="req-123",
            files=[FileInput(path="test_class.py", content=sample_test_class)],
            mode="hybrid",
        )

        result = await agent.run(context)

        assert result.success is True
        assert result.data["total_test_classes"] == 1
        assert result.data["total_test_functions"] == 2  # Two methods in class

    async def test_parsing_with_fixture(self, sample_test_with_fixture: str) -> None:
        """Test agent correctly parses tests with fixtures."""
        agent = ParsingAgent(name="parser")
        context = AgentContext(
            request_id="req-123",
            files=[FileInput(path="test_fixture.py", content=sample_test_with_fixture)],
            mode="hybrid",
        )

        result = await agent.run(context)

        assert result.success is True
        assert result.data["parsed_count"] == 1
        parsed_file = context.parsed_files[0]
        assert len(parsed_file.fixtures) == 1
        assert parsed_file.fixtures[0].name == "sample_data"

    async def test_output_validation(self, sample_test_code: str) -> None:
        """Test output validation ensures parsed files are present."""
        agent = ParsingAgent(name="parser")
        context = AgentContext(
            request_id="req-123",
            files=[FileInput(path="test.py", content=sample_test_code)],
            mode="hybrid",
        )

        result = await agent.run(context)

        # Manually clear parsed_files to trigger validation error
        context.parsed_files = []
        validation_errors = await agent.validate_output(result, context)

        assert len(validation_errors) > 0
        assert any("no parsed files" in error.lower() for error in validation_errors)

    async def test_metrics_tracking(self, sample_test_code: str) -> None:
        """Test agent tracks execution metrics."""
        agent = ParsingAgent(name="parser")
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
