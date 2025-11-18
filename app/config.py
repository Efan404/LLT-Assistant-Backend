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
    port: int = Field(default=8000, description="Server port")

    # LLM Configuration
    llm_api_key: str = Field(
        default="test-key-for-development", description="LLM API key"
    )
    llm_base_url: str = Field(
        default="https://api.qnaigc.com/v1", description="LLM API base URL"
    )
    llm_model: str = Field(
        default="deepseek/deepseek-v3.2-exp", description="LLM model name"
    )
    llm_timeout: float = Field(default=30.0, description="LLM API timeout in seconds")
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

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",
    }


# Global settings instance
# NOTE: This is a singleton for configuration only, which is acceptable
# as configuration should be immutable after initialization.
settings = Settings()
