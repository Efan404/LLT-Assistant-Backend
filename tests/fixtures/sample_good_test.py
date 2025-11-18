"""
Sample well-written pytest test file for testing purposes.

This file contains examples of properly structured tests.
"""

import pytest


@pytest.fixture
def sample_data():
    """Provide sample data for tests."""
    return {"name": "Test User", "age": 30, "email": "test@example.com"}


def test_simple_assertion():
    """Test basic arithmetic operation."""
    result = 2 + 2
    assert result == 4


def test_string_operations():
    """Test string manipulation."""
    text = "hello world"
    assert text.upper() == "HELLO WORLD"
    assert len(text) == 11


def test_with_fixture(sample_data):
    """Test using a fixture."""
    assert sample_data["name"] == "Test User"
    assert sample_data["age"] == 30


class TestCalculator:
    """Test suite for calculator operations."""

    def test_addition(self):
        """Test addition operation."""
        assert 5 + 3 == 8

    def test_subtraction(self):
        """Test subtraction operation."""
        assert 10 - 4 == 6

    def test_multiplication(self):
        """Test multiplication operation."""
        assert 6 * 7 == 42
