"""
Pytest configuration for evaluation tests.

Provides fixtures for loading ground truth data and configuring evaluation tests.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List

import pytest


@pytest.fixture(scope="session")
def evaluation_fixtures_dir() -> Path:
    """Provide path to evaluation fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def ground_truth_mergeability(evaluation_fixtures_dir: Path) -> Dict[str, Any]:
    """Load ground truth dataset for mergeability analysis."""
    fixture_path = evaluation_fixtures_dir / "ground_truth_mergeability.json"
    with open(fixture_path, "r") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def ground_truth_assertion_quality(evaluation_fixtures_dir: Path) -> Dict[str, Any]:
    """Load ground truth dataset for assertion quality analysis."""
    fixture_path = evaluation_fixtures_dir / "ground_truth_assertion_quality.json"
    with open(fixture_path, "r") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def ground_truth_test_smells(evaluation_fixtures_dir: Path) -> Dict[str, Any]:
    """Load ground truth dataset for test smell detection."""
    fixture_path = evaluation_fixtures_dir / "ground_truth_test_smells.json"
    with open(fixture_path, "r") as f:
        return json.load(f)


@pytest.fixture
def llm_analyzer_for_eval():
    """
    Provide LLMAnalyzer instance for evaluation tests.

    Note: This requires LLM_API_KEY to be set in environment.
    """
    from app.core.llm_analyzer import LLMAnalyzer

    analyzer = LLMAnalyzer()
    yield analyzer
    # Cleanup is handled by the analyzer's context manager if needed


@pytest.fixture
def skip_if_no_api_key():
    """Skip test if LLM API key is not available."""
    api_key = os.getenv("LLM_API_KEY")
    if not api_key or os.getenv("SKIP_LLM_TESTS", "").lower() == "true":
        pytest.skip("LLM API key not available or LLM tests are disabled")


@pytest.fixture
def evaluation_sample_size() -> int:
    """
    Number of samples to use for evaluation tests.

    Can be overridden with EVALUATION_SAMPLE_SIZE environment variable.
    Defaults to 10 for faster CI/CD runs.
    """
    return int(os.getenv("EVALUATION_SAMPLE_SIZE", "10"))
