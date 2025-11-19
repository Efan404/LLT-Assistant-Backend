"""
Unit tests for InputProcessingAgent.

Tests input validation, file size limits, and request sanitization.
"""

import pytest

from app.agents.context import AgentContext
from app.agents.input_processing import (
    MAX_FILE_SIZE_BYTES,
    MAX_FILES,
    InputProcessingAgent,
)
from app.api.v1.schemas import FileInput


@pytest.mark.asyncio
class TestInputProcessingAgent:
    """Test cases for InputProcessingAgent class."""

    async def test_valid_input(self, sample_test_code: str) -> None:
        """Test agent accepts valid input."""
        agent = InputProcessingAgent(name="input_processor")
        context = AgentContext(
            request_id="req-123",
            files=[FileInput(path="test.py", content=sample_test_code)],
            mode="hybrid",
        )

        result = await agent.run(context)

        assert result.success is True
        assert result.data["file_count"] == 1
        assert result.data["mode"] == "hybrid"
        assert result.errors == []

    async def test_valid_modes(self, sample_test_code: str) -> None:
        """Test agent accepts all valid modes."""
        agent = InputProcessingAgent(name="input_processor")

        for mode in ["rules-only", "llm-only", "hybrid"]:
            context = AgentContext(
                request_id="req-123",
                files=[FileInput(path="test.py", content=sample_test_code)],
                mode=mode,
            )

            result = await agent.run(context)
            assert result.success is True
            assert result.data["mode"] == mode

    async def test_invalid_mode(self, sample_test_code: str) -> None:
        """Test agent rejects invalid mode."""
        agent = InputProcessingAgent(name="input_processor")
        context = AgentContext(
            request_id="req-123",
            files=[FileInput(path="test.py", content=sample_test_code)],
            mode="invalid-mode",
        )

        result = await agent.run(context)

        assert result.success is False
        assert any("Invalid mode" in error for error in result.errors)
        assert result.metadata.get("critical") is True

    async def test_no_files(self) -> None:
        """Test agent rejects empty file list."""
        agent = InputProcessingAgent(name="input_processor")
        context = AgentContext(
            request_id="req-123",
            files=[],
            mode="hybrid",
        )

        result = await agent.run(context)

        assert result.success is False
        assert any("No files" in error for error in result.errors)

    async def test_too_many_files(self, sample_test_code: str) -> None:
        """Test agent rejects too many files."""
        agent = InputProcessingAgent(name="input_processor")

        # Create more files than the limit
        files = [
            FileInput(path=f"test_{i}.py", content=sample_test_code)
            for i in range(MAX_FILES + 1)
        ]

        context = AgentContext(
            request_id="req-123",
            files=files,
            mode="hybrid",
        )

        result = await agent.run(context)

        assert result.success is False
        assert any("Too many files" in error for error in result.errors)

    async def test_file_size_limit(self) -> None:
        """Test agent rejects oversized files."""
        agent = InputProcessingAgent(name="input_processor")

        # Create a file larger than the limit
        large_content = "x" * (MAX_FILE_SIZE_BYTES + 1)

        context = AgentContext(
            request_id="req-123",
            files=[FileInput(path="large.py", content=large_content)],
            mode="hybrid",
        )

        result = await agent.run(context)

        assert result.success is False
        assert any("exceed size limit" in error for error in result.errors)

    async def test_empty_file_warning(self) -> None:
        """Test agent warns about empty files."""
        agent = InputProcessingAgent(name="input_processor")
        context = AgentContext(
            request_id="req-123",
            files=[FileInput(path="empty.py", content="   \n  \n")],
            mode="hybrid",
        )

        result = await agent.run(context)

        assert result.success is True  # Empty files are a warning, not error
        assert len(result.warnings) > 0
        assert any("no content" in warning.lower() for warning in result.warnings)

    async def test_multiple_files_statistics(self, sample_test_code: str) -> None:
        """Test agent calculates correct statistics for multiple files."""
        agent = InputProcessingAgent(name="input_processor")
        context = AgentContext(
            request_id="req-123",
            files=[
                FileInput(path="test1.py", content=sample_test_code),
                FileInput(path="test2.py", content=sample_test_code),
                FileInput(path="test3.py", content=sample_test_code),
            ],
            mode="hybrid",
        )

        result = await agent.run(context)

        assert result.success is True
        assert result.data["file_count"] == 3
        assert result.data["total_size_bytes"] > 0
        assert result.data["average_size_bytes"] > 0

    async def test_mixed_valid_and_empty_files(self, sample_test_code: str) -> None:
        """Test agent handles mix of valid and empty files."""
        agent = InputProcessingAgent(name="input_processor")
        context = AgentContext(
            request_id="req-123",
            files=[
                FileInput(path="test.py", content=sample_test_code),
                FileInput(path="empty.py", content="   "),
            ],
            mode="hybrid",
        )

        result = await agent.run(context)

        assert result.success is True
        assert result.data["file_count"] == 2
        assert len(result.warnings) > 0

    async def test_output_validation(self, sample_test_code: str) -> None:
        """Test output validation checks for required fields."""
        agent = InputProcessingAgent(name="input_processor")
        context = AgentContext(
            request_id="req-123",
            files=[FileInput(path="test.py", content=sample_test_code)],
            mode="hybrid",
        )

        result = await agent.run(context)

        # Should have required fields
        assert "file_count" in result.data
        assert "total_size_bytes" in result.data
        assert "mode" in result.data

    async def test_context_validation(self) -> None:
        """Test agent validates context structure."""
        agent = InputProcessingAgent(name="input_processor")

        # Create context with missing attributes
        context = AgentContext(
            request_id="req-123",
            files=[],
            mode="hybrid",
        )

        # Validation should pass for valid context
        errors = await agent.validate_input(context)
        assert len(errors) == 0

    async def test_metrics_tracking(self, sample_test_code: str) -> None:
        """Test agent tracks execution metrics."""
        agent = InputProcessingAgent(name="input_processor")
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
