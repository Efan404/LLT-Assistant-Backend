"""
Shared pytest fixtures for the LLT Assistant Backend test suite.

This module provides common fixtures used across unit, integration,
and fuzzing tests to ensure consistency and reduce code duplication.
"""

import os
from pathlib import Path
from typing import Any, Dict
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app.analyzers.ast_parser import parse_test_file
from app.analyzers.rule_engine import RuleEngine
from app.config import Settings
from app.core.analyzer import TestAnalyzer
from app.core.llm_client import LLMClient
from app.main import app


@pytest.fixture(scope="session")
def test_data_dir() -> Path:
    """
    Provide path to test data directory containing sample files.

    Returns:
        Path object pointing to tests/fixtures/ directory
    """
    return Path(__file__).parent / "fixtures"


@pytest.fixture(scope="function")
def test_client() -> TestClient:
    """
    Provide FastAPI test client for API endpoint testing.

    Returns:
        TestClient instance configured with the main app
    """
    return TestClient(app)


@pytest.fixture(scope="function")
def test_settings() -> Settings:
    """
    Provide test-specific application settings.

    Returns:
        Settings instance with test configuration
    """
    return Settings(
        llm_api_key=os.getenv("LLM_API_KEY", "test-key-for-development"),
        llm_base_url=os.getenv("LLM_BASE_URL", "https://api.qnaigc.com/v1"),
        llm_model=os.getenv("LLM_MODEL", "deepseek/deepseek-v3.2-exp"),
        llm_timeout=30.0,
        llm_max_retries=3,
        max_file_size=1048576,
        max_files_per_request=50,
        log_level="DEBUG",  # More verbose logging for tests
        log_format="json",
    )


@pytest.fixture(scope="function")
def llm_client(test_settings: Settings) -> LLMClient:
    """
    Provide LLM client instance for testing.

    Args:
        test_settings: Test configuration settings

    Returns:
        Configured LLMClient instance
    """
    return LLMClient(
        api_key=test_settings.llm_api_key,
        base_url=test_settings.llm_base_url,
        model=test_settings.llm_model,
        timeout=test_settings.llm_timeout,
        max_retries=test_settings.llm_max_retries,
    )


@pytest.fixture(scope="function")
def rule_engine() -> RuleEngine:
    """
    Provide RuleEngine instance for testing.

    Returns:
        Fresh RuleEngine instance
    """
    return RuleEngine()


@pytest.fixture(scope="function")
def test_analyzer(test_settings: Settings) -> TestAnalyzer:
    """
    Provide TestAnalyzer instance for integration testing.

    Args:
        test_settings: Test configuration settings

    Returns:
        Configured TestAnalyzer instance
    """
    return TestAnalyzer(config=test_settings)


@pytest.fixture
def sample_test_code() -> str:
    """
    Provide simple valid pytest test code for testing.

    Returns:
        String containing basic pytest test function
    """
    return """
def test_addition():
    result = 1 + 1
    assert result == 2
"""


@pytest.fixture
def sample_test_with_fixture() -> str:
    """
    Provide pytest test code that uses a fixture.

    Returns:
        String containing test with fixture usage
    """
    return """
import pytest

@pytest.fixture
def sample_data():
    return {"key": "value"}

def test_with_fixture(sample_data):
    assert sample_data["key"] == "value"
"""


@pytest.fixture
def sample_test_class() -> str:
    """
    Provide pytest test code organized in a class.

    Returns:
        String containing test class with multiple tests
    """
    return """
class TestCalculator:
    def test_addition(self):
        assert 1 + 1 == 2

    def test_subtraction(self):
        assert 5 - 3 == 2
"""


@pytest.fixture
def redundant_assertion_code() -> str:
    """
    Provide test code with redundant assertions (for rule engine testing).

    Returns:
        String containing test with duplicate assertions
    """
    return """
def test_example():
    value = 42
    assert value == 42
    assert value == 42  # Redundant assertion
"""


@pytest.fixture
def missing_assertion_code() -> str:
    """
    Provide test code with missing assertions.

    Returns:
        String containing test function without assertions
    """
    return """
def test_example():
    value = 42
    result = value * 2
    # Missing assertion
"""


@pytest.fixture
def trivial_assertion_code() -> str:
    """
    Provide test code with trivial assertions.

    Returns:
        String containing test with always-true assertion
    """
    return """
def test_example():
    assert True  # Trivial assertion
"""


@pytest.fixture
def unused_fixture_code() -> str:
    """
    Provide test code with unused fixture.

    Returns:
        String containing fixture definition that's never used
    """
    return """
import pytest

@pytest.fixture
def unused_fixture():
    return "not used"

@pytest.fixture
def used_fixture():
    return "used"

def test_example(used_fixture):
    assert used_fixture == "used"
"""


@pytest.fixture
def syntax_error_code() -> str:
    """
    Provide test code with syntax errors.

    Returns:
        String containing invalid Python syntax
    """
    return """
def test_example(:
    assert True  # Missing closing parenthesis in function definition
"""


@pytest.fixture
def mock_llm_response() -> Dict[str, Any]:
    """
    Provide mock LLM API response for testing.

    Returns:
        Dictionary mimicking OpenAI-compatible API response
    """
    return {
        "id": "chatcmpl-test-123",
        "object": "chat.completion",
        "created": 1700000000,
        "model": "deepseek/deepseek-v3.2-exp",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": """[
                        {
                            "line": 3,
                            "column": 4,
                            "severity": "warning",
                            "type": "test-smell",
                            "message": "Test could be more specific",
                            "explanation": "Consider adding more descriptive assertions"
                        }
                    ]""",
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
    }


@pytest.fixture
def mock_llm_error_response() -> Dict[str, Any]:
    """
    Provide mock LLM API error response for testing.

    Returns:
        Dictionary mimicking API error response
    """
    return {
        "error": {
            "message": "Rate limit exceeded",
            "type": "rate_limit_error",
            "code": "rate_limit_exceeded",
        }
    }


@pytest.fixture
def sample_analysis_request() -> Dict[str, Any]:
    """
    Provide sample API request payload for analysis endpoint.

    Returns:
        Dictionary with valid analysis request structure
    """
    return {
        "files": [
            {
                "path": "test_example.py",
                "content": "def test_addition():\n    assert 1 + 1 == 2\n",
                "git_diff": None,
            }
        ],
        "mode": "hybrid",
        "config": {},
    }


@pytest.fixture(autouse=True)
def reset_environment():
    """
    Reset environment variables between tests to avoid contamination.

    This fixture runs automatically before each test.
    """
    original_env = os.environ.copy()
    yield
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture(scope="session")
def skip_llm_tests():
    """
    Determine if LLM tests should be skipped based on environment.

    Returns:
        Boolean indicating whether to skip tests requiring real LLM API
    """
    # Skip LLM tests if API key is not configured or if explicitly disabled
    api_key = os.getenv("LLM_API_KEY", "test-key-for-development")
    skip_llm = os.getenv("SKIP_LLM_TESTS", "false").lower() == "true"

    return skip_llm or api_key == "test-key-for-development"
