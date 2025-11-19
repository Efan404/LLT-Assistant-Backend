"""
Unit tests for LLM settings.

Tests configuration loading, validation, and security features.
"""

import os
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from app.agents.llm.settings import (
    LLMSettings,
    get_llm_settings,
    get_optional_llm_settings,
)


class TestLLMSettings:
    """Test cases for LLMSettings configuration."""

    def test_settings_from_env_vars(self) -> None:
        """Test loading settings from environment variables."""
        with patch.dict(
            os.environ,
            {
                "DEEPSEEK_BASE_URL": "https://api.deepseek.com",
                "DEEPSEEK_API_KEY": "sk-test-key-12345",
                "DEEPSEEK_MODEL": "deepseek-chat",
                "DEEPSEEK_TEMPERATURE": "0.2",
                "DEEPSEEK_MAX_TOKENS": "1500",
            },
        ):
            # Clear cache
            get_llm_settings.cache_clear()

            settings = LLMSettings()

            assert settings.deepseek_base_url == "https://api.deepseek.com"
            assert settings.deepseek_api_key == "sk-test-key-12345"
            assert settings.deepseek_model == "deepseek-chat"
            assert settings.deepseek_temperature == 0.2
            assert settings.deepseek_max_tokens == 1500

    def test_settings_with_defaults(self) -> None:
        """Test settings use default values when not specified."""
        with patch.dict(
            os.environ,
            {
                "DEEPSEEK_BASE_URL": "https://api.deepseek.com",
                "DEEPSEEK_API_KEY": "sk-test-key",
            },
            clear=True,
        ):
            get_llm_settings.cache_clear()

            settings = LLMSettings()

            # Check defaults
            assert settings.deepseek_model == "deepseek-chat"
            assert settings.deepseek_temperature == 0.1
            assert settings.deepseek_max_tokens == 2000
            assert settings.deepseek_timeout == 30
            assert settings.enable_agent_framework is False
            assert settings.agent_cache_ttl == 300
            assert settings.agent_max_retries == 3

    def test_missing_required_fields_raises_error(self) -> None:
        """Test that missing required fields raise validation error."""
        with patch.dict(os.environ, {}, clear=True):
            get_llm_settings.cache_clear()

            with pytest.raises(ValidationError):
                LLMSettings()

    def test_get_sanitized_dict(self) -> None:
        """Test that API key is redacted in sanitized dict."""
        with patch.dict(
            os.environ,
            {
                "DEEPSEEK_BASE_URL": "https://api.deepseek.com",
                "DEEPSEEK_API_KEY": "sk-secret-key-12345",
            },
            clear=True,
        ):
            get_llm_settings.cache_clear()

            settings = LLMSettings()
            sanitized = settings.get_sanitized_dict()

            assert sanitized["deepseek_api_key"] == "***REDACTED***"
            assert "sk-secret" not in str(sanitized)

    def test_validate_api_key_valid(self) -> None:
        """Test API key validation for valid keys."""
        with patch.dict(
            os.environ,
            {
                "DEEPSEEK_BASE_URL": "https://api.deepseek.com",
                "DEEPSEEK_API_KEY": "sk-valid-key-with-sufficient-length",
            },
            clear=True,
        ):
            get_llm_settings.cache_clear()

            settings = LLMSettings()
            assert settings.validate_api_key() is True

    def test_validate_api_key_invalid(self) -> None:
        """Test API key validation for invalid keys."""
        with patch.dict(
            os.environ,
            {
                "DEEPSEEK_BASE_URL": "https://api.deepseek.com",
                "DEEPSEEK_API_KEY": "your_api_key_here",
            },
            clear=True,
        ):
            get_llm_settings.cache_clear()

            settings = LLMSettings()
            assert settings.validate_api_key() is False

    def test_validate_api_key_too_short(self) -> None:
        """Test API key validation for too short keys."""
        with patch.dict(
            os.environ,
            {
                "DEEPSEEK_BASE_URL": "https://api.deepseek.com",
                "DEEPSEEK_API_KEY": "short",
            },
            clear=True,
        ):
            get_llm_settings.cache_clear()

            settings = LLMSettings()
            assert settings.validate_api_key() is False

    def test_temperature_validation(self) -> None:
        """Test temperature must be between 0.0 and 1.0."""
        with patch.dict(
            os.environ,
            {
                "DEEPSEEK_BASE_URL": "https://api.deepseek.com",
                "DEEPSEEK_API_KEY": "sk-test-key",
                "DEEPSEEK_TEMPERATURE": "1.5",
            },
            clear=True,
        ):
            get_llm_settings.cache_clear()

            with pytest.raises(ValidationError):
                LLMSettings()

    def test_max_tokens_validation(self) -> None:
        """Test max_tokens must be positive."""
        with patch.dict(
            os.environ,
            {
                "DEEPSEEK_BASE_URL": "https://api.deepseek.com",
                "DEEPSEEK_API_KEY": "sk-test-key",
                "DEEPSEEK_MAX_TOKENS": "-100",
            },
            clear=True,
        ):
            get_llm_settings.cache_clear()

            with pytest.raises(ValidationError):
                LLMSettings()

    def test_timeout_validation(self) -> None:
        """Test timeout must be positive."""
        with patch.dict(
            os.environ,
            {
                "DEEPSEEK_BASE_URL": "https://api.deepseek.com",
                "DEEPSEEK_API_KEY": "sk-test-key",
                "DEEPSEEK_TIMEOUT": "0",
            },
            clear=True,
        ):
            get_llm_settings.cache_clear()

            with pytest.raises(ValidationError):
                LLMSettings()

    def test_agent_framework_settings(self) -> None:
        """Test agent framework configuration options."""
        with patch.dict(
            os.environ,
            {
                "DEEPSEEK_BASE_URL": "https://api.deepseek.com",
                "DEEPSEEK_API_KEY": "sk-test-key",
                "ENABLE_AGENT_FRAMEWORK": "true",
                "AGENT_CACHE_TTL": "600",
                "AGENT_MAX_RETRIES": "5",
                "AGENT_LOG_LEVEL": "DEBUG",
            },
            clear=True,
        ):
            get_llm_settings.cache_clear()

            settings = LLMSettings()

            assert settings.enable_agent_framework is True
            assert settings.agent_cache_ttl == 600
            assert settings.agent_max_retries == 5
            assert settings.agent_log_level == "DEBUG"

    def test_get_llm_settings_cached(self) -> None:
        """Test that get_llm_settings returns cached instance."""
        with patch.dict(
            os.environ,
            {
                "DEEPSEEK_BASE_URL": "https://api.deepseek.com",
                "DEEPSEEK_API_KEY": "sk-test-key",
            },
            clear=True,
        ):
            get_llm_settings.cache_clear()

            settings1 = get_llm_settings()
            settings2 = get_llm_settings()

            # Should be the same instance
            assert settings1 is settings2

    def test_get_optional_llm_settings_valid(self) -> None:
        """Test get_optional_llm_settings with valid config."""
        with patch.dict(
            os.environ,
            {
                "DEEPSEEK_BASE_URL": "https://api.deepseek.com",
                "DEEPSEEK_API_KEY": "sk-valid-key-12345",
            },
            clear=True,
        ):
            get_llm_settings.cache_clear()

            settings = get_optional_llm_settings()

            assert settings is not None
            assert isinstance(settings, LLMSettings)

    def test_get_optional_llm_settings_invalid_key(self) -> None:
        """Test get_optional_llm_settings with invalid API key."""
        with patch.dict(
            os.environ,
            {
                "DEEPSEEK_BASE_URL": "https://api.deepseek.com",
                "DEEPSEEK_API_KEY": "your_api_key_here",
            },
            clear=True,
        ):
            get_llm_settings.cache_clear()

            settings = get_optional_llm_settings()

            # Should return None for placeholder key
            assert settings is None

    def test_get_optional_llm_settings_missing_config(self) -> None:
        """Test get_optional_llm_settings with missing config."""
        with patch.dict(os.environ, {}, clear=True):
            get_llm_settings.cache_clear()

            settings = get_optional_llm_settings()

            # Should return None when config is missing
            assert settings is None
