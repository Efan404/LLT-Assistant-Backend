"""Tests for the rule engine."""

import pytest

from app.analyzers.ast_parser import parse_test_file
from app.analyzers.rule_engine import (
    MissingAssertionRule,
    RedundantAssertionRule,
    RuleEngine,
)


class TestRuleEngine:
    """Test cases for rule engine functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.rule_engine = RuleEngine()

    def test_redundant_assertion_detection(self):
        """Test detection of redundant assertions."""
        source_code = """
def test_user_age():
    user = User(age=25)
    assert user.age == 25
    assert user.age == 25  # Redundant
"""

        parsed_file = parse_test_file("test_file.py", source_code)
        issues = self.rule_engine.analyze(parsed_file)

        # Should detect one redundant assertion issue
        redundant_issues = [
            issue for issue in issues if issue.type == "redundant-assertion"
        ]
        assert len(redundant_issues) == 1

        issue = redundant_issues[0]
        assert issue.severity == "warning"
        assert "redundant" in issue.message.lower()

    def test_missing_assertion_detection(self):
        """Test detection of missing assertions."""
        source_code = """
def test_user_creation():
    user = User(name="John")
    # No assertion - not a real test!
"""

        parsed_file = parse_test_file("test_file.py", source_code)
        issues = self.rule_engine.analyze(parsed_file)

        # Should detect one missing assertion issue
        missing_issues = [
            issue for issue in issues if issue.type == "missing-assertion"
        ]
        assert len(missing_issues) == 1

        issue = missing_issues[0]
        assert issue.severity == "error"
        assert "no assertions" in issue.message.lower()

    def test_trivial_assertion_detection(self):
        """Test detection of trivial assertions."""
        source_code = """
def test_something():
    assert True  # Always passes
    assert 1 == 1  # Always passes
"""

        parsed_file = parse_test_file("test_file.py", source_code)
        issues = self.rule_engine.analyze(parsed_file)

        # Should detect two trivial assertion issues
        trivial_issues = [
            issue for issue in issues if issue.type == "trivial-assertion"
        ]
        assert len(trivial_issues) == 2

        for issue in trivial_issues:
            assert issue.severity == "error"
            assert "trivial" in issue.message.lower()

    def test_unused_fixture_detection(self):
        """Test detection of unused fixtures."""
        source_code = """
import pytest

@pytest.fixture
def unused_database():
    return Database()

@pytest.fixture
def used_user():
    return User()

def test_with_user(used_user):
    assert used_user is not None
"""

        parsed_file = parse_test_file("test_file.py", source_code)
        issues = self.rule_engine.analyze(parsed_file)

        # Should detect one unused fixture issue
        unused_fixture_issues = [
            issue for issue in issues if issue.type == "unused-fixture"
        ]
        assert len(unused_fixture_issues) == 1

        issue = unused_fixture_issues[0]
        assert issue.severity == "info"
        assert "unused" in issue.message.lower()
        assert "unused_database" in issue.message

    def test_unused_variable_detection(self):
        """Test detection of unused variables."""
        source_code = """
def test_user():
    name = "test"  # Defined but never used
    user = User()
    assert user.id > 0
"""

        parsed_file = parse_test_file("test_file.py", source_code)
        issues = self.rule_engine.analyze(parsed_file)

        # Should detect one unused variable issue
        unused_var_issues = [
            issue for issue in issues if issue.type == "unused-variable"
        ]
        assert len(unused_var_issues) == 1

        issue = unused_var_issues[0]
        assert issue.severity == "info"
        assert "unused" in issue.message.lower()
        assert "name" in issue.message

    def test_no_issues_in_good_test(self):
        """Test that a well-written test produces no issues."""
        source_code = """
import pytest

@pytest.fixture
def user():
    return User(name="Alice", age=30)

def test_user_properties(user):
    assert user.name == "Alice"
    assert user.age == 30
    assert isinstance(user, User)
"""

        parsed_file = parse_test_file("test_file.py", source_code)
        issues = self.rule_engine.analyze(parsed_file)

        # Should have no issues
        assert len(issues) == 0

    def test_suggestion_generation(self):
        """Test that suggestions are generated for issues."""
        source_code = """
def test_missing_assertion():
    user = User(name="John")
    # No assertion
"""

        parsed_file = parse_test_file("test_file.py", source_code)
        issues = self.rule_engine.analyze(parsed_file)

        # Should have one issue with a suggestion
        assert len(issues) == 1
        issue = issues[0]

        assert issue.suggestion is not None
        assert issue.suggestion.action == "add"
        assert issue.suggestion.explanation is not None
        assert "assert" in issue.suggestion.new_code
