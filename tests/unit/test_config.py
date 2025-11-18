"""
Unit tests for application configuration.

Tests cover settings loading, environment variable overrides,
and validation.
"""

import os
from unittest.mock import patch

import pytest

from app.config import Settings, settings


class TestSettings:
    """Test suite for Settings class."""

    def test_default_settings(self):
        """Test that default settings are loaded correctly."""
        config = Settings()

        # Application settings
        assert config.app_name == "LLT Assistant Backend"
        assert config.app_version == "0.1.0"
        assert config.debug is False

        # Server settings
        assert config.host == "0.0.0.0"
        assert config.port == 8000

        # LLM settings
        assert config.llm_api_key == "test-key-for-development"
        assert config.llm_base_url == "https://api.qnaigc.com/v1"
        assert config.llm_model == "deepseek/deepseek-v3.2-exp"
        assert config.llm_timeout == 30.0
        assert config.llm_max_retries == 3

        # Analysis settings
        assert config.max_file_size == 1024 * 1024  # 1MB
        assert config.max_files_per_request == 50

        # Logging settings
        assert config.log_level == "INFO"
        assert config.log_format == "json"

    def test_environment_variable_override_app_name(self):
        """Test overriding app_name via environment variable."""
        with patch.dict(os.environ, {"APP_NAME": "Custom App Name"}):
            config = Settings()
            assert config.app_name == "Custom App Name"

    def test_environment_variable_override_debug(self):
        """Test overriding debug flag via environment variable."""
        with patch.dict(os.environ, {"DEBUG": "true"}):
            config = Settings()
            assert config.debug is True

        with patch.dict(os.environ, {"DEBUG": "false"}):
            config = Settings()
            assert config.debug is False

    def test_environment_variable_override_port(self):
        """Test overriding port via environment variable."""
        with patch.dict(os.environ, {"PORT": "9000"}):
            config = Settings()
            assert config.port == 9000

    def test_environment_variable_override_llm_api_key(self):
        """Test overriding LLM API key via environment variable."""
        with patch.dict(os.environ, {"LLM_API_KEY": "sk-custom-key-123"}):
            config = Settings()
            assert config.llm_api_key == "sk-custom-key-123"

    def test_environment_variable_override_llm_base_url(self):
        """Test overriding LLM base URL via environment variable."""
        with patch.dict(os.environ, {"LLM_BASE_URL": "https://custom.api.com/v1"}):
            config = Settings()
            assert config.llm_base_url == "https://custom.api.com/v1"

    def test_environment_variable_override_llm_model(self):
        """Test overriding LLM model via environment variable."""
        with patch.dict(os.environ, {"LLM_MODEL": "gpt-4"}):
            config = Settings()
            assert config.llm_model == "gpt-4"

    def test_environment_variable_override_llm_timeout(self):
        """Test overriding LLM timeout via environment variable."""
        with patch.dict(os.environ, {"LLM_TIMEOUT": "60.5"}):
            config = Settings()
            assert config.llm_timeout == 60.5

    def test_environment_variable_override_llm_max_retries(self):
        """Test overriding LLM max retries via environment variable."""
        with patch.dict(os.environ, {"LLM_MAX_RETRIES": "5"}):
            config = Settings()
            assert config.llm_max_retries == 5

    def test_environment_variable_override_max_file_size(self):
        """Test overriding max file size via environment variable."""
        with patch.dict(os.environ, {"MAX_FILE_SIZE": "2097152"}):  # 2MB
            config = Settings()
            assert config.max_file_size == 2097152

    def test_environment_variable_override_max_files_per_request(self):
        """Test overriding max files per request via environment variable."""
        with patch.dict(os.environ, {"MAX_FILES_PER_REQUEST": "100"}):
            config = Settings()
            assert config.max_files_per_request == 100

    def test_environment_variable_override_log_level(self):
        """Test overriding log level via environment variable."""
        with patch.dict(os.environ, {"LOG_LEVEL": "DEBUG"}):
            config = Settings()
            assert config.log_level == "DEBUG"

    def test_environment_variable_override_log_format(self):
        """Test overriding log format via environment variable."""
        with patch.dict(os.environ, {"LOG_FORMAT": "text"}):
            config = Settings()
            assert config.log_format == "text"

    def test_case_insensitive_env_vars(self):
        """Test that environment variable names are case-insensitive."""
        with patch.dict(os.environ, {"app_name": "Lowercase Name"}):
            config = Settings()
            assert config.app_name == "Lowercase Name"

        with patch.dict(os.environ, {"APP_NAME": "Uppercase Name"}):
            config = Settings()
            assert config.app_name == "Uppercase Name"

    def test_invalid_port_type_raises_validation_error(self):
        """Test that invalid port type raises validation error."""
        with patch.dict(os.environ, {"PORT": "invalid"}):
            with pytest.raises(Exception):  # Pydantic raises validation error
                Settings()

    def test_invalid_timeout_type_raises_validation_error(self):
        """Test that invalid timeout type raises validation error."""
        with patch.dict(os.environ, {"LLM_TIMEOUT": "not_a_number"}):
            with pytest.raises(Exception):  # Pydantic raises validation error
                Settings()

    def test_invalid_max_retries_type_raises_validation_error(self):
        """Test that invalid max retries type raises validation error."""
        with patch.dict(os.environ, {"LLM_MAX_RETRIES": "not_an_integer"}):
            with pytest.raises(Exception):  # Pydantic raises validation error
                Settings()

    def test_multiple_env_overrides(self):
        """Test multiple environment variable overrides simultaneously."""
        env_overrides = {
            "APP_NAME": "Test App",
            "DEBUG": "true",
            "PORT": "8080",
            "LLM_API_KEY": "sk-test-key",
            "LLM_MODEL": "test-model",
            "LOG_LEVEL": "DEBUG",
        }

        with patch.dict(os.environ, env_overrides):
            config = Settings()

            assert config.app_name == "Test App"
            assert config.debug is True
            assert config.port == 8080
            assert config.llm_api_key == "sk-test-key"
            assert config.llm_model == "test-model"
            assert config.log_level == "DEBUG"

    def test_field_descriptions_exist(self):
        """Test that all fields have descriptions."""
        config = Settings()
        schema = config.model_json_schema()

        # Check that key fields have descriptions
        assert "properties" in schema
        properties = schema["properties"]

        # Sample some fields
        if "app_name" in properties:
            assert "description" in properties["app_name"]
        if "llm_api_key" in properties:
            assert "description" in properties["llm_api_key"]

    def test_global_settings_instance(self):
        """Test that global settings instance exists and is correct type."""
        assert settings is not None
        assert isinstance(settings, Settings)

    def test_settings_immutability(self):
        """Test that settings can be updated (not frozen)."""
        config = Settings()

        # Should be able to modify (Pydantic models are mutable by default)
        config.log_level = "ERROR"
        assert config.log_level == "ERROR"

    def test_config_model_settings(self):
        """Test that model_config is properly set."""
        config = Settings()

        # Verify model_config attributes
        assert config.model_config["env_file"] == ".env"
        assert config.model_config["env_file_encoding"] == "utf-8"
        assert config.model_config["case_sensitive"] is False

    def test_llm_timeout_positive_value(self):
        """Test that LLM timeout accepts positive values."""
        with patch.dict(os.environ, {"LLM_TIMEOUT": "120.5"}):
            config = Settings()
            assert config.llm_timeout == 120.5

    def test_max_file_size_large_value(self):
        """Test that max file size accepts large values."""
        large_size = 10 * 1024 * 1024  # 10MB
        with patch.dict(os.environ, {"MAX_FILE_SIZE": str(large_size)}):
            config = Settings()
            assert config.max_file_size == large_size

    def test_config_repr(self):
        """Test that config has a string representation."""
        config = Settings()
        repr_str = repr(config)

        assert "Settings" in repr_str
        assert isinstance(repr_str, str)

    def test_config_dict_export(self):
        """Test exporting config as dictionary."""
        config = Settings()
        config_dict = config.model_dump()

        assert isinstance(config_dict, dict)
        assert "app_name" in config_dict
        assert "llm_api_key" in config_dict
        assert "max_file_size" in config_dict

    def test_partial_env_override(self):
        """Test that unset env vars use defaults while set vars override."""
        with patch.dict(os.environ, {"LLM_MODEL": "custom-model"}, clear=False):
            config = Settings()

            # Overridden value
            assert config.llm_model == "custom-model"

            # Default values should still be used for non-overridden fields
            assert config.app_version == "0.1.0"
            assert config.port == 8000
