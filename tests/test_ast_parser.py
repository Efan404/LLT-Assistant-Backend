"""Tests for the AST parser."""

import pytest

from app.analyzers.ast_parser import TestFunctionInfo, parse_test_file


class TestASTParser:
    """Test cases for AST parser functionality."""

    def test_parse_simple_test_function(self):
        """Test parsing a simple test function."""
        source_code = """
def test_user_creation():
    user = User(name="John")
    assert user.name == "John"
"""

        result = parse_test_file("test_file.py", source_code)

        assert not result.has_syntax_errors
        assert len(result.test_functions) == 1

        test_func = result.test_functions[0]
        assert test_func.name == "test_user_creation"
        assert len(test_func.assertions) == 1
        assert test_func.assertions[0].assertion_type == "equality"

    def test_parse_test_with_fixture(self):
        """Test parsing a test function with fixture."""
        source_code = """
import pytest

@pytest.fixture
def user_fixture():
    return User(name="Test")

def test_with_fixture(user_fixture):
    assert user_fixture.name == "Test"
"""

        result = parse_test_file("test_file.py", source_code)

        assert not result.has_syntax_errors
        assert len(result.fixtures) == 1
        assert result.fixtures[0].name == "user_fixture"

        assert len(result.test_functions) == 1
        test_func = result.test_functions[0]
        assert "user_fixture" in test_func.parameters

    def test_parse_test_class(self):
        """Test parsing a test class."""
        source_code = """
class TestUser:
    def test_user_age(self):
        user = User(age=25)
        assert user.age == 25

    def test_user_name(self):
        user = User(name="Alice")
        assert user.name == "Alice"
"""

        result = parse_test_file("test_file.py", source_code)

        assert not result.has_syntax_errors
        assert len(result.test_classes) == 1

        test_class = result.test_classes[0]
        assert test_class.name == "TestUser"
        assert len(test_class.methods) == 2

    def test_detect_trivial_assertion(self):
        """Test detection of trivial assertions."""
        source_code = """
def test_with_trivial_assertion():
    assert True
    assert 1 == 1
"""

        result = parse_test_file("test_file.py", source_code)

        assert not result.has_syntax_errors
        assert len(result.test_functions) == 1

        test_func = result.test_functions[0]
        assert len(test_func.assertions) == 2

        # Both assertions should be marked as trivial
        for assertion in test_func.assertions:
            assert assertion.is_trivial

    def test_handle_syntax_error(self):
        """Test handling of files with syntax errors."""
        source_code = """
def test_with_error(
    # Missing closing parenthesis
    assert True
"""

        result = parse_test_file("test_file.py", source_code)

        assert result.has_syntax_errors
        assert result.syntax_error_message is not None
        assert len(result.test_functions) == 0

    def test_parse_imports(self):
        """Test parsing import statements."""
        source_code = """
import pytest
from datetime import datetime
import os.path as path

def test_imports():
    assert True
"""

        result = parse_test_file("test_file.py", source_code)

        assert not result.has_syntax_errors
        assert len(result.imports) == 3

        # Check specific imports
        import_aliases = [(imp.name, imp.alias) for imp in result.imports]
        assert ("pytest", None) in import_aliases
        assert ("datetime", None) in import_aliases
        assert ("os.path", "path") in import_aliases
