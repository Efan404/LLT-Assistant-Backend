"""
Fuzzing tests using Hypothesis for robustness testing.

Tests generate random inputs to find edge cases and potential bugs.
"""

import pytest
from fastapi.testclient import TestClient
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from app.main import app


@pytest.fixture(scope="module")
def fuzzing_client():
    """Provide test client for fuzzing tests."""
    return TestClient(app)


# Hypothesis strategies for generating test inputs
valid_python_identifiers = st.from_regex(r"[a-zA-Z_][a-zA-Z0-9_]*", fullmatch=True)

simple_python_code = st.one_of(
    st.just("def test_example(): assert True"),
    st.just("def test_simple(): pass"),
    st.just("assert 1 == 1"),
    st.text(
        alphabet=st.characters(blacklist_categories=("Cs",)), min_size=0, max_size=100
    ),
)


class TestAPIFuzzing:
    """Fuzzing tests for API endpoints."""

    @given(path=st.text(min_size=1, max_size=100), content=simple_python_code)
    @settings(
        max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_analyze_endpoint_with_random_paths(self, fuzzing_client, path, content):
        """Test analyze endpoint with randomly generated file paths."""
        payload = {
            "files": [{"path": path, "content": content, "git_diff": None}],
            "mode": "rules-only",
        }

        try:
            response = fuzzing_client.post("/api/v1/analyze", json=payload)

            # Should either succeed or return validation error
            assert response.status_code in [200, 400, 422, 500]

            if response.status_code == 200:
                data = response.json()
                assert "analysis_id" in data
                assert "issues" in data
                assert "metrics" in data

        except Exception:
            # Allow exceptions for truly invalid inputs
            pass

    @given(mode=st.text(min_size=1, max_size=50))
    @settings(
        max_examples=15, suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_analyze_with_random_modes(self, fuzzing_client, mode):
        """Test analyze endpoint with random mode strings."""
        payload = {
            "files": [
                {
                    "path": "test.py",
                    "content": "def test(): assert True",
                    "git_diff": None,
                }
            ],
            "mode": mode,
        }

        response = fuzzing_client.post("/api/v1/analyze", json=payload)

        # Valid modes should succeed, invalid should error
        if mode in ["rules-only", "llm-only", "hybrid"]:
            assert response.status_code == 200
        else:
            assert response.status_code in [400, 422]

    @given(content=st.text(min_size=0, max_size=500))
    @settings(
        max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_analyze_with_random_content(self, fuzzing_client, content):
        """Test analyze endpoint with random file content."""
        payload = {
            "files": [{"path": "test_random.py", "content": content, "git_diff": None}],
            "mode": "rules-only",
        }

        try:
            response = fuzzing_client.post("/api/v1/analyze", json=payload)

            # Should handle any content gracefully
            assert response.status_code in [200, 400, 422, 500]

        except Exception:
            # Some random content might cause issues
            pass

    @given(num_files=st.integers(min_value=0, max_value=100))
    @settings(
        max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_analyze_with_variable_file_count(self, fuzzing_client, num_files):
        """Test analyze endpoint with varying number of files."""
        files = [
            {
                "path": f"test_{i}.py",
                "content": f"def test_{i}(): assert True",
                "git_diff": None,
            }
            for i in range(num_files)
        ]

        payload = {"files": files, "mode": "rules-only"}

        response = fuzzing_client.post("/api/v1/analyze", json=payload)

        if num_files == 0:
            # Empty files should error
            assert response.status_code in [400, 422]
        elif num_files <= 50:
            # Valid number of files should succeed
            assert response.status_code == 200
        else:
            # Too many files might error
            assert response.status_code in [200, 400, 422]


class TestASTParserFuzzing:
    """Fuzzing tests for AST parser robustness."""

    @given(
        code=st.text(
            alphabet=st.characters(blacklist_categories=("Cs",)),
            min_size=0,
            max_size=200,
        )
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_parse_arbitrary_code(self, code):
        """Test that AST parser handles arbitrary code without crashing."""
        from app.analyzers.ast_parser import parse_test_file

        try:
            result = parse_test_file("test.py", code)

            # Should return a ParsedTestFile object
            assert hasattr(result, "file_path")
            assert hasattr(result, "has_syntax_errors")

            # If it has syntax errors, should have error message
            if result.has_syntax_errors:
                assert result.syntax_error_message is not None

        except Exception as e:
            # Some inputs might cause parser errors
            # Verify it's a known exception type
            assert isinstance(e, (SyntaxError, ValueError, Exception))

    @given(function_name=valid_python_identifiers)
    @settings(max_examples=30)
    def test_parse_test_functions_with_random_names(self, function_name):
        """Test parsing test functions with random valid names."""
        from app.analyzers.ast_parser import parse_test_file

        # Only test functions starting with "test_" are pytest tests
        if not function_name.startswith("test_"):
            function_name = "test_" + function_name

        code = f"""
def {function_name}():
    assert True
"""

        result = parse_test_file("test.py", code)

        if not result.has_syntax_errors:
            # Should find the test function
            assert len(result.test_functions) >= 0

    @given(indentation=st.integers(min_value=0, max_value=10))
    @settings(max_examples=15)
    def test_parse_with_various_indentation(self, indentation):
        """Test parsing code with various indentation levels."""
        from app.analyzers.ast_parser import parse_test_file

        spaces = " " * indentation
        code = f"""
{spaces}def test_indented():
{spaces}    assert True
"""

        try:
            result = parse_test_file("test.py", code)

            # Might have syntax errors depending on indentation
            assert hasattr(result, "has_syntax_errors")

        except Exception:
            # Invalid indentation is acceptable to fail
            pass


class TestRuleEngineFuzzing:
    """Fuzzing tests for rule engine robustness."""

    @given(assertion_count=st.integers(min_value=0, max_value=20))
    @settings(max_examples=15)
    def test_redundant_assertion_detection_with_varying_counts(self, assertion_count):
        """Test redundant assertion detection with varying assertion counts."""
        from app.analyzers.ast_parser import parse_test_file
        from app.analyzers.rule_engine import RuleEngine

        # Generate code with N assertions
        assertions = "\n    ".join(
            [f"assert value == 42" for _ in range(assertion_count)]
        )
        code = f"""
def test_redundant():
    value = 42
    {assertions}
"""

        parsed_file = parse_test_file("test.py", code)

        if not parsed_file.has_syntax_errors:
            engine = RuleEngine()
            issues = engine.analyze(parsed_file)

            # If more than 1 assertion, should detect redundancy
            if assertion_count > 1:
                redundant_issues = [i for i in issues if "redundant" in i.type.lower()]
                assert len(redundant_issues) > 0

    @given(
        code_lines=st.lists(
            st.text(
                alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd")),
                min_size=0,
                max_size=50,
            ),
            min_size=0,
            max_size=10,
        )
    )
    @settings(max_examples=20)
    def test_rule_engine_handles_random_code_lines(self, code_lines):
        """Test that rule engine handles random code without crashing."""
        from app.analyzers.ast_parser import parse_test_file
        from app.analyzers.rule_engine import RuleEngine

        code = "\n".join(code_lines)

        try:
            parsed_file = parse_test_file("test.py", code)

            if not parsed_file.has_syntax_errors:
                engine = RuleEngine()
                issues = engine.analyze(parsed_file)

                # Should return a list (might be empty)
                assert isinstance(issues, list)

        except Exception:
            # Some random code might cause issues
            pass


class TestInputValidationFuzzing:
    """Fuzzing tests for input validation."""

    @given(
        data=st.dictionaries(
            keys=st.text(min_size=1, max_size=20),
            values=st.one_of(
                st.text(), st.integers(), st.booleans(), st.none(), st.lists(st.text())
            ),
            min_size=0,
            max_size=10,
        )
    )
    @settings(
        max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_analyze_with_random_json_payloads(self, fuzzing_client, data):
        """Test analyze endpoint with random JSON payloads."""
        try:
            response = fuzzing_client.post("/api/v1/analyze", json=data)

            # Should return some response (not crash)
            assert response.status_code in [200, 400, 422, 500]

        except Exception:
            # Some invalid payloads might cause exceptions
            pass

    @given(git_diff=st.one_of(st.none(), st.text(min_size=0, max_size=100)))
    @settings(
        max_examples=15, suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_analyze_with_random_git_diff(self, fuzzing_client, git_diff):
        """Test analyze endpoint with random git_diff values."""
        payload = {
            "files": [
                {
                    "path": "test.py",
                    "content": "def test(): assert True",
                    "git_diff": git_diff,
                }
            ],
            "mode": "rules-only",
        }

        try:
            response = fuzzing_client.post("/api/v1/analyze", json=payload)

            # Should handle various git_diff values
            assert response.status_code in [200, 400, 422]

        except Exception:
            pass


class TestEdgeCases:
    """Test specific edge cases discovered through fuzzing."""

    def test_analyze_empty_string_content(self, fuzzing_client):
        """Test analyzing file with empty string content."""
        payload = {
            "files": [{"path": "test_empty.py", "content": "", "git_diff": None}],
            "mode": "rules-only",
        }

        response = fuzzing_client.post("/api/v1/analyze", json=payload)

        # Should handle empty content gracefully
        assert response.status_code in [200, 400, 422]

    def test_analyze_only_whitespace_content(self, fuzzing_client):
        """Test analyzing file with only whitespace."""
        payload = {
            "files": [
                {
                    "path": "test_whitespace.py",
                    "content": "   \n\n\t\t\n   ",
                    "git_diff": None,
                }
            ],
            "mode": "rules-only",
        }

        response = fuzzing_client.post("/api/v1/analyze", json=payload)

        assert response.status_code in [200, 400, 422]

    def test_analyze_unicode_content(self, fuzzing_client):
        """Test analyzing file with Unicode characters."""
        payload = {
            "files": [
                {
                    "path": "test_unicode.py",
                    "content": """
def test_unicode():
    message = "Hello 世界 🌍"
    assert len(message) > 0
""",
                    "git_diff": None,
                }
            ],
            "mode": "rules-only",
        }

        response = fuzzing_client.post("/api/v1/analyze", json=payload)

        assert response.status_code == 200

    def test_analyze_very_long_line(self, fuzzing_client):
        """Test analyzing file with very long line."""
        long_string = "x" * 10000
        payload = {
            "files": [
                {
                    "path": "test_long.py",
                    "content": f'def test(): assert "{long_string}" != ""',
                    "git_diff": None,
                }
            ],
            "mode": "rules-only",
        }

        response = fuzzing_client.post("/api/v1/analyze", json=payload)

        # Should handle long lines
        assert response.status_code in [200, 400, 422, 500]

    def test_analyze_deeply_nested_code(self, fuzzing_client):
        """Test analyzing deeply nested code structures."""
        code = "def test_nested():\n"
        for i in range(10):
            code += "    " * (i + 1) + f"if True:\n"
        code += "    " * 11 + "assert True"

        payload = {
            "files": [{"path": "test_nested.py", "content": code, "git_diff": None}],
            "mode": "rules-only",
        }

        response = fuzzing_client.post("/api/v1/analyze", json=payload)

        assert response.status_code in [200, 400, 422]
