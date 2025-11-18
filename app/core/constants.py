"""Application-wide constants.

This module centralizes magic numbers and configuration values
to improve maintainability and reduce duplication.
"""

from enum import Enum


class AnalysisMode(str, Enum):
    """Analysis mode enumeration."""

    RULES_ONLY = "rules-only"
    LLM_ONLY = "llm-only"
    HYBRID = "hybrid"


class Severity(str, Enum):
    """Issue severity levels."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


# Analysis configuration
DEFAULT_ANALYSIS_MODE = AnalysisMode.HYBRID
MAX_FILES_PER_REQUEST = 50
MAX_FILE_SIZE_BYTES = 1024 * 1024  # 1MB

# LLM configuration
LLM_DEFAULT_TEMPERATURE = 0.3
LLM_DEFAULT_MAX_TOKENS = 2000
LLM_CONFIDENCE_THRESHOLD = 0.7
LLM_DEFAULT_TIMEOUT = 30.0
LLM_DEFAULT_MAX_RETRIES = 3

# Retry configuration
RETRY_INITIAL_BACKOFF_SECONDS = 2
RETRY_MAX_BACKOFF_SECONDS = 60
RETRY_BACKOFF_MULTIPLIER = 2

# Uncertain case detection thresholds
MIN_ASSERTIONS_FOR_COMPLEX = 3
MIN_DECORATORS_FOR_UNUSUAL = 3
MIN_NAME_PARTS_FOR_SIMILARITY = 2

# Issue types
ISSUE_TYPE_REDUNDANT_ASSERTION = "redundant-assertion"
ISSUE_TYPE_MISSING_ASSERTION = "missing-assertion"
ISSUE_TYPE_TRIVIAL_ASSERTION = "trivial-assertion"
ISSUE_TYPE_UNUSED_FIXTURE = "unused-fixture"
ISSUE_TYPE_UNUSED_VARIABLE = "unused-variable"
ISSUE_TYPE_MERGEABLE_TESTS = "mergeable-tests"
ISSUE_TYPE_WEAK_ASSERTION = "weak-assertion"
ISSUE_TYPE_TEST_SMELL = "test-smell"

# Detection sources
DETECTED_BY_RULE_ENGINE = "rule_engine"
DETECTED_BY_LLM = "llm"

# Suggestion actions
ACTION_REMOVE = "remove"
ACTION_ADD = "add"
ACTION_REPLACE = "replace"
ACTION_REVIEW = "review"
