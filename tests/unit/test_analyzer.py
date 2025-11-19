"""
Unit tests for the core TestAnalyzer class.

Tests cover the main analysis orchestration, file parsing,
rule/LLM integration, and metric calculation.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.analyzers.ast_parser import AssertionInfo, ParsedTestFile, TestFunctionInfo
from app.analyzers.rule_engine import RuleEngine
from app.api.v1.schemas import FileInput, Issue
from app.core.analyzer import TestAnalyzer
from app.core.llm_analyzer import LLMAnalyzer


@pytest.fixture
def mock_rule_engine():
    """Provide mock RuleEngine."""
    engine = Mock(spec=RuleEngine)
    engine.analyze = Mock(return_value=[])
    return engine


@pytest.fixture
def mock_llm_analyzer():
    """Provide mock LLMAnalyzer."""
    analyzer = Mock(spec=LLMAnalyzer)
    analyzer.analyze_assertion_quality = AsyncMock(return_value=[])
    analyzer.analyze_test_smells = AsyncMock(return_value=[])
    analyzer.close = AsyncMock()
    return analyzer


@pytest.fixture
def test_analyzer(mock_rule_engine, mock_llm_analyzer):
    """Provide TestAnalyzer instance with mocked dependencies."""
    return TestAnalyzer(rule_engine=mock_rule_engine, llm_analyzer=mock_llm_analyzer)


@pytest.fixture
def sample_file_input():
    """Provide sample FileInput for testing."""
    return FileInput(
        path="test_example.py",
        content="""
def test_addition():
    result = 1 + 1
    assert result == 2
""",
        git_diff=None,
    )


@pytest.fixture
def sample_parsed_file():
    """Provide sample ParsedTestFile for testing."""
    return ParsedTestFile(
        file_path="test_example.py",
        imports=[],
        fixtures=[],
        test_functions=[
            TestFunctionInfo(
                name="test_addition",
                line_number=2,
                decorators=[],
                parameters=[],
                assertions=[
                    AssertionInfo(
                        line_number=4,
                        column=4,
                        assertion_type="equality",
                        operands=["result", "2"],
                        is_trivial=False,
                        source_code="assert result == 2",
                    )
                ],
                has_docstring=False,
                body_lines=(2, 4),
                source_code="def test_addition():\n    result = 1 + 1\n    assert result == 2\n",
            )
        ],
        test_classes=[],
        has_syntax_errors=False,
        syntax_error_message=None,
    )


class TestTestAnalyzer:
    """Test suite for TestAnalyzer class."""

    @pytest.mark.asyncio
    async def test_analyzer_initialization(self, mock_rule_engine, mock_llm_analyzer):
        """Test that analyzer initializes with correct dependencies."""
        analyzer = TestAnalyzer(
            rule_engine=mock_rule_engine, llm_analyzer=mock_llm_analyzer
        )

        assert analyzer.rule_engine is mock_rule_engine
        assert analyzer.llm_analyzer is mock_llm_analyzer

    @pytest.mark.asyncio
    async def test_analyze_files_empty_list_raises_error(self, test_analyzer):
        """Test that analyzing empty file list raises ValueError."""
        with pytest.raises(ValueError, match="No files provided"):
            await test_analyzer.analyze_files(files=[])

    @pytest.mark.asyncio
    async def test_analyze_files_invalid_mode_raises_error(
        self, test_analyzer, sample_file_input
    ):
        """Test that invalid mode raises ValueError."""
        with pytest.raises(ValueError, match="Invalid analysis mode"):
            await test_analyzer.analyze_files(
                files=[sample_file_input], mode="invalid-mode"
            )

    @pytest.mark.asyncio
    async def test_analyze_files_rules_only_mode(
        self, test_analyzer, sample_file_input, sample_parsed_file, mock_rule_engine
    ):
        """Test analysis in rules-only mode."""
        # Setup mock to return sample issues
        mock_issue = Issue(
            file="test_example.py",
            line=4,
            column=4,
            severity="warning",
            type="redundant-assertion",
            message="Redundant assertion detected",
            detected_by="rule_engine",
            suggestion=None,
        )
        mock_rule_engine.analyze.return_value = [mock_issue]

        # Mock file parsing
        with patch.object(
            test_analyzer, "_parse_files_parallel", return_value=[sample_parsed_file]
        ):
            response = await test_analyzer.analyze_files(
                files=[sample_file_input], mode="rules-only"
            )

        # Verify response
        assert response.analysis_id is not None
        assert len(response.issues) == 1
        assert response.issues[0].type == "redundant-assertion"
        assert response.issues[0].detected_by == "rule_engine"
        assert response.metrics.total_tests == 1
        assert response.metrics.issues_count == 1
        assert response.metrics.analysis_time_ms >= 0

    @pytest.mark.asyncio
    async def test_analyze_files_llm_only_mode(
        self, test_analyzer, sample_file_input, sample_parsed_file, mock_llm_analyzer
    ):
        """Test analysis in llm-only mode."""
        # Setup mock to return LLM issues
        mock_issue = Issue(
            file="test_example.py",
            line=2,
            column=0,
            severity="info",
            type="test-smell",
            message="Test could be more descriptive",
            detected_by="llm",
            suggestion=None,
        )
        mock_llm_analyzer.analyze_assertion_quality.return_value = [mock_issue]

        # Mock file parsing
        with patch.object(
            test_analyzer, "_parse_files_parallel", return_value=[sample_parsed_file]
        ):
            response = await test_analyzer.analyze_files(
                files=[sample_file_input], mode="llm-only"
            )

        # Verify that LLM analyzer was called
        assert mock_llm_analyzer.analyze_assertion_quality.called
        assert len(response.issues) == 1
        assert response.issues[0].detected_by == "llm"

    @pytest.mark.asyncio
    async def test_analyze_files_hybrid_mode(
        self,
        test_analyzer,
        sample_file_input,
        sample_parsed_file,
        mock_rule_engine,
        mock_llm_analyzer,
    ):
        """Test analysis in hybrid mode combines both rule and LLM results."""
        # Setup mock issues from both sources
        rule_issue = Issue(
            file="test_example.py",
            line=4,
            column=4,
            severity="warning",
            type="redundant-assertion",
            message="Redundant assertion",
            detected_by="rule_engine",
            suggestion=None,
        )
        llm_issue = Issue(
            file="test_example.py",
            line=2,
            column=0,
            severity="info",
            type="test-smell",
            message="Test smell detected",
            detected_by="llm",
            suggestion=None,
        )

        mock_rule_engine.analyze.return_value = [rule_issue]
        mock_llm_analyzer.analyze_test_smells.return_value = [llm_issue]

        # Mock file parsing and uncertain case identification
        with patch.object(
            test_analyzer, "_parse_files_parallel", return_value=[sample_parsed_file]
        ):
            # Patch UncertainCaseDetector since it's now in a separate class
            with patch(
                "app.core.strategies.UncertainCaseDetector"
            ) as mock_detector_class:
                mock_detector = Mock()
                mock_detector.identify_uncertain_cases.return_value = [
                    sample_parsed_file.test_functions[0]
                ]
                mock_detector_class.return_value = mock_detector

                response = await test_analyzer.analyze_files(
                    files=[sample_file_input], mode="hybrid"
                )

        # Verify both analyzers were called
        assert mock_rule_engine.analyze.called
        assert mock_llm_analyzer.analyze_test_smells.called

        # Should have issues from both sources
        assert len(response.issues) >= 1

    @pytest.mark.asyncio
    async def test_parse_files_parallel_success(self, test_analyzer, sample_file_input):
        """Test successful parallel file parsing."""
        with patch("app.core.analyzer.parse_test_file") as mock_parse:
            mock_parsed = ParsedTestFile(
                file_path="test_example.py",
                imports=[],
                fixtures=[],
                test_functions=[],
                test_classes=[],
                has_syntax_errors=False,
                syntax_error_message=None,
            )
            mock_parse.return_value = mock_parsed

            results = await test_analyzer._parse_files_parallel([sample_file_input])

            assert len(results) == 1
            assert results[0].file_path == "test_example.py"
            assert not results[0].has_syntax_errors

    @pytest.mark.asyncio
    async def test_parse_files_handles_syntax_errors(self, test_analyzer):
        """Test that parser handles files with syntax errors gracefully."""
        bad_file = FileInput(
            path="test_bad.py", content="def test_broken(:\n    pass", git_diff=None
        )

        with patch("app.core.analyzer.parse_test_file") as mock_parse:
            mock_parse.side_effect = SyntaxError("invalid syntax")

            results = await test_analyzer._parse_files_parallel([bad_file])

            assert len(results) == 1
            assert results[0].has_syntax_errors
            assert "invalid syntax" in results[0].syntax_error_message

    @pytest.mark.asyncio
    async def test_close_calls_llm_analyzer_close(
        self, test_analyzer, mock_llm_analyzer
    ):
        """Test that close() properly closes the LLM analyzer."""
        await test_analyzer.close()

        mock_llm_analyzer.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_analyze_files_handles_parsing_exceptions(
        self, test_analyzer, sample_file_input
    ):
        """Test that analyzer handles parsing exceptions gracefully."""
        with patch.object(
            test_analyzer, "_parse_files_parallel", side_effect=Exception("Parse error")
        ):
            with pytest.raises(Exception, match="Parse error"):
                await test_analyzer.analyze_files(
                    files=[sample_file_input], mode="rules-only"
                )

    @pytest.mark.asyncio
    async def test_analyze_multiple_files(self, test_analyzer):
        """Test analyzing multiple files at once."""
        files = [
            FileInput(
                path=f"test_{i}.py",
                content=f"def test_{i}(): assert True",
                git_diff=None,
            )
            for i in range(3)
        ]

        mock_parsed_files = [
            ParsedTestFile(
                file_path=f"test_{i}.py",
                imports=[],
                fixtures=[],
                test_functions=[Mock()],
                test_classes=[],
                has_syntax_errors=False,
                syntax_error_message=None,
            )
            for i in range(3)
        ]

        with patch.object(
            test_analyzer, "_parse_files_parallel", return_value=mock_parsed_files
        ):
            response = await test_analyzer.analyze_files(files=files, mode="rules-only")

        assert response.metrics.total_tests == 3
