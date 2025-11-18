"""
Unit tests for the core TestAnalyzer class.

Tests cover the main analysis orchestration, file parsing,
rule/LLM integration, and metric calculation.
"""

import asyncio
from typing import List
from unittest.mock import AsyncMock, MagicMock, Mock, patch

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
                lineno=2,
                decorators=[],
                parameters=[],
                assertions=[
                    AssertionInfo(
                        lineno=4, assertion_type="equality", values=["result", "2"]
                    )
                ],
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
            with patch.object(
                test_analyzer,
                "_identify_uncertain_cases",
                return_value=[sample_parsed_file.test_functions[0]],
            ):
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

    def test_identify_uncertain_cases_similar_names(self, test_analyzer):
        """Test identification of similar function names."""
        func1 = TestFunctionInfo(
            name="test_user_creation",
            lineno=1,
            decorators=[],
            parameters=[],
            assertions=[],
            source_code="def test_user_creation(): pass",
        )
        func2 = TestFunctionInfo(
            name="test_user_deletion",
            lineno=5,
            decorators=[],
            parameters=[],
            assertions=[],
            source_code="def test_user_deletion(): pass",
        )

        parsed_file = ParsedTestFile(
            file_path="test_users.py",
            imports=[],
            fixtures=[],
            test_functions=[func1, func2],
            test_classes=[],
            has_syntax_errors=False,
            syntax_error_message=None,
        )

        uncertain = test_analyzer._identify_uncertain_cases(parsed_file)

        # Both functions should be identified as similar
        assert len(uncertain) >= 2
        assert func1 in uncertain
        assert func2 in uncertain

    def test_identify_uncertain_cases_complex_assertions(self, test_analyzer):
        """Test identification of functions with complex assertions."""
        func = TestFunctionInfo(
            name="test_complex",
            lineno=1,
            decorators=[],
            parameters=[],
            assertions=[
                AssertionInfo(lineno=2, assertion_type="equality", values=["a", "1"]),
                AssertionInfo(lineno=3, assertion_type="equality", values=["b", "2"]),
                AssertionInfo(lineno=4, assertion_type="equality", values=["c", "3"]),
                AssertionInfo(lineno=5, assertion_type="equality", values=["d", "4"]),
            ],
            source_code="def test_complex(): pass",
        )

        parsed_file = ParsedTestFile(
            file_path="test_example.py",
            imports=[],
            fixtures=[],
            test_functions=[func],
            test_classes=[],
            has_syntax_errors=False,
            syntax_error_message=None,
        )

        uncertain = test_analyzer._identify_uncertain_cases(parsed_file)

        # Function with many assertions should be identified
        assert func in uncertain

    def test_identify_uncertain_cases_unusual_patterns(self, test_analyzer):
        """Test identification of unusual patterns like time.sleep."""
        func = TestFunctionInfo(
            name="test_with_sleep",
            lineno=1,
            decorators=[],
            parameters=[],
            assertions=[],
            source_code="def test_with_sleep():\n    time.sleep(1)\n    assert True",
        )

        parsed_file = ParsedTestFile(
            file_path="test_example.py",
            imports=[],
            fixtures=[],
            test_functions=[func],
            test_classes=[],
            has_syntax_errors=False,
            syntax_error_message=None,
        )

        uncertain = test_analyzer._identify_uncertain_cases(parsed_file)

        # Function with timing dependency should be identified
        assert func in uncertain

    def test_merge_issues_rules_only(self, test_analyzer):
        """Test issue merging in rules-only mode."""
        rule_issues = [
            Issue(
                file="test.py",
                line=1,
                column=0,
                severity="warning",
                type="issue1",
                message="Rule issue",
                detected_by="rule_engine",
                suggestion=None,
            )
        ]
        llm_issues = [
            Issue(
                file="test.py",
                line=2,
                column=0,
                severity="info",
                type="issue2",
                message="LLM issue",
                detected_by="llm",
                suggestion=None,
            )
        ]

        merged = test_analyzer._merge_issues(rule_issues, llm_issues, "rules-only")

        assert len(merged) == 1
        assert merged[0].detected_by == "rule_engine"

    def test_merge_issues_llm_only(self, test_analyzer):
        """Test issue merging in llm-only mode."""
        rule_issues = [
            Issue(
                file="test.py",
                line=1,
                column=0,
                severity="warning",
                type="issue1",
                message="Rule issue",
                detected_by="rule_engine",
                suggestion=None,
            )
        ]
        llm_issues = [
            Issue(
                file="test.py",
                line=2,
                column=0,
                severity="info",
                type="issue2",
                message="LLM issue",
                detected_by="llm",
                suggestion=None,
            )
        ]

        merged = test_analyzer._merge_issues(rule_issues, llm_issues, "llm-only")

        assert len(merged) == 1
        assert merged[0].detected_by == "llm"

    def test_merge_issues_hybrid_deduplicates(self, test_analyzer):
        """Test that hybrid mode deduplicates similar issues."""
        rule_issue = Issue(
            file="test.py",
            line=5,
            column=4,
            severity="warning",
            type="redundant-assertion",
            message="Redundant assertion",
            detected_by="rule_engine",
            suggestion=None,
        )
        llm_issue = Issue(
            file="test.py",
            line=5,
            column=4,
            severity="warning",
            type="redundant-assertion",
            message="Duplicate assertion found",
            detected_by="llm",
            suggestion=None,
        )

        merged = test_analyzer._merge_issues([rule_issue], [llm_issue], "hybrid")

        # Should only have one issue (rule engine takes precedence)
        assert len(merged) == 1
        assert merged[0].detected_by == "rule_engine"

    def test_calculate_metrics(self, test_analyzer):
        """Test metrics calculation."""
        import time

        parsed_files = [
            ParsedTestFile(
                file_path="test1.py",
                imports=[],
                fixtures=[],
                test_functions=[Mock(), Mock()],  # 2 tests
                test_classes=[],
                has_syntax_errors=False,
                syntax_error_message=None,
            ),
            ParsedTestFile(
                file_path="test2.py",
                imports=[],
                fixtures=[],
                test_functions=[Mock()],  # 1 test
                test_classes=[],
                has_syntax_errors=False,
                syntax_error_message=None,
            ),
        ]

        issues = [Mock(), Mock(), Mock()]  # 3 issues
        start_time = time.time()

        metrics = test_analyzer._calculate_metrics(parsed_files, issues, start_time)

        assert metrics.total_tests == 3
        assert metrics.issues_count == 3
        assert metrics.analysis_time_ms >= 0

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
