"""
LLM configuration settings using Pydantic.

This module defines the configuration for LLM clients, loading
settings from environment variables with secure defaults.
"""

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMSettings(BaseSettings):
    """
    LLM configuration loaded from environment variables.

    This class uses Pydantic to load and validate LLM settings from
    the environment. It automatically reads from .env files and
    validates all required fields.

    Attributes:
        deepseek_base_url: API endpoint for DeepSeek
        deepseek_api_key: API key for authentication
        deepseek_model: Model name to use
        deepseek_temperature: Sampling temperature (0.0-1.0)
        deepseek_max_tokens: Maximum tokens in response
        deepseek_timeout: Request timeout in seconds
        enable_agent_framework: Feature flag for agent framework
        agent_cache_ttl: Cache time-to-live in seconds
        agent_max_retries: Maximum retry attempts for failed requests
        agent_log_level: Logging level for agents
    """

    # Required LLM settings
    deepseek_base_url: str = Field(
        description="DeepSeek API base URL",
        validation_alias="DEEPSEEK_BASE_URL",
    )
    deepseek_api_key: str = Field(
        description="DeepSeek API key",
        validation_alias="DEEPSEEK_API_KEY",
    )

    # Optional LLM settings with defaults
    deepseek_model: str = Field(
        default="deepseek-chat",
        description="DeepSeek model name",
        validation_alias="DEEPSEEK_MODEL",
    )
    deepseek_temperature: float = Field(
        default=0.1,
        ge=0.0,
        le=1.0,
        description="LLM temperature for response randomness",
        validation_alias="DEEPSEEK_TEMPERATURE",
    )
    deepseek_max_tokens: int = Field(
        default=2000,
        gt=0,
        description="Maximum tokens in LLM response",
        validation_alias="DEEPSEEK_MAX_TOKENS",
    )
    deepseek_timeout: int = Field(
        default=30,
        gt=0,
        description="Request timeout in seconds",
        validation_alias="DEEPSEEK_TIMEOUT",
    )

    # Agent framework settings
    enable_agent_framework: bool = Field(
        default=False,
        description="Enable new agent-based pipeline",
        validation_alias="ENABLE_AGENT_FRAMEWORK",
    )
    agent_cache_ttl: int = Field(
        default=300,
        gt=0,
        description="Cache TTL in seconds",
        validation_alias="AGENT_CACHE_TTL",
    )
    agent_max_retries: int = Field(
        default=3,
        ge=0,
        description="Maximum retry attempts",
        validation_alias="AGENT_MAX_RETRIES",
    )
    agent_log_level: str = Field(
        default="INFO",
        description="Logging level for agents",
        validation_alias="AGENT_LOG_LEVEL",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    def get_sanitized_dict(self) -> dict:
        """
        Get settings as dictionary with API key redacted.

        This is safe to log or expose in error messages.

        Returns:
            Dictionary of settings with API key masked
        """
        data = self.model_dump()
        if "deepseek_api_key" in data:
            data["deepseek_api_key"] = "***REDACTED***"
        return data

    def validate_api_key(self) -> bool:
        """
        Check if API key is configured (not the example placeholder).

        Returns:
            True if API key appears to be valid
        """
        return (
            self.deepseek_api_key
            and len(self.deepseek_api_key) > 10
            and self.deepseek_api_key != "your_api_key_here"
        )


@lru_cache
def get_llm_settings() -> LLMSettings:
    """
    Get cached LLM settings instance.

    This function uses LRU cache to ensure settings are loaded only once
    and reused across the application.

    Returns:
        LLMSettings instance loaded from environment

    Raises:
        ValidationError: If required environment variables are missing
    """
    return LLMSettings()


def get_optional_llm_settings() -> Optional[LLMSettings]:
    """
    Get LLM settings if available, None otherwise.

    This is useful for graceful degradation when LLM is not configured.

    Returns:
        LLMSettings instance or None if configuration is invalid
    """
    try:
        settings = get_llm_settings()
        if settings.validate_api_key():
            return settings
        return None
    except Exception:
        return None
