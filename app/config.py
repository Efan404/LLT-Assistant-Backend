"""Configuration management for LLT Assistant Backend."""

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # API Configuration
    app_name: str = Field(
        default="LLT Assistant Backend", description="Application name"
    )
    app_version: str = Field(default="0.1.0", description="Application version")
    debug: bool = Field(default=False, description="Debug mode")

    # Server Configuration
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8886, description="Server port")

    # LLM Configuration
    llm_api_key: str = Field(
        validation_alias="LLM_API_KEY",
        description="LLM API key (from LLM_API_KEY env var)",
    )
    llm_base_url: str = Field(
        default="https://api.deepseek.com",
        validation_alias="LLM_BASE_URL",
        description="LLM API base URL (from LLM_BASE_URL env var)",
    )
    llm_model: str = Field(
        default="deepseek-chat", description="LLM model name"
    )
    llm_timeout: float = Field(
        default=120.0,
        validation_alias="LLM_TIMEOUT",
        description="LLM API timeout in seconds"
    )
    llm_max_retries: int = Field(default=3, description="Maximum LLM API retries")

    # Analysis Configuration
    max_file_size: int = Field(
        default=1024 * 1024, description="Maximum file size in bytes"
    )
    max_files_per_request: int = Field(
        default=50, description="Maximum files per analysis request"
    )

    # Logging Configuration
    log_level: str = Field(default="INFO", description="Logging level")
    log_format: str = Field(default="json", description="Log format (json or text)")

    # CORS Configuration
    cors_origins: list[str] = Field(
        default=["*"],
        description="Allowed CORS origins (use specific domains in production)",
    )

    # Task / Redis Configuration
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL for task management",
    )

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",
        "populate_by_name": True,
    }


# Global settings instance
# NOTE: This is a singleton for configuration only, which is acceptable
# as configuration should be immutable after initialization.
settings = Settings()
