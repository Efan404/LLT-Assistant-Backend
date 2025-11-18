"""
Sample pytest test file with intentional quality issues.

This file is used to test the analyzer's ability to detect various test smells.
"""

import time

import pytest


@pytest.fixture
def unused_fixture():
    """This fixture is defined but never used."""
    return "unused value"


@pytest.fixture
def used_fixture():
    """This fixture is actually used."""
    return "used value"


def test_redundant_assertions():
    """Test with duplicate assertions."""
    value = 42
    assert value == 42
    assert value == 42  # Duplicate assertion


def test_missing_assertion():
    """Test that performs operations but has no assertions."""
    value = 10
    result = value * 2
    calculated = result + 5
    # Missing assertion - test does nothing


def test_trivial_assertion():
    """Test with trivial always-true assertion."""
    assert True
    assert 1 == 1


def test_with_sleep():
    """Test with timing dependency."""
    time.sleep(0.1)  # Bad practice - timing dependency
    value = 42
    assert value == 42


def test_multiple_issues(used_fixture):
    """Test with multiple quality issues."""
    # Trivial assertion
    assert True

    # Redundant assertions
    value = used_fixture
    assert value == "used value"
    assert value == "used value"

    # Unused variable
    unused_var = 123


def test_complex_redundancy():
    """Test with complex redundant logic."""
    data = {"key": "value"}
    assert data["key"] == "value"
    assert "key" in data
    assert data.get("key") == "value"  # Redundant - already checked above


class TestWithIssues:
    """Test class with various quality problems."""

    def test_empty(self):
        """Empty test with no assertions."""
        pass

    def test_only_setup(self):
        """Test that only performs setup."""
        value = 100
        result = value / 10


def test_hardcoded_values():
    """Test with hardcoded sensitive values (smell)."""
    api_key = "sk-1234567890abcdef"  # Hardcoded secret
    url = "https://example.com"
    assert len(api_key) > 0
