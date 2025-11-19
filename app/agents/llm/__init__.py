"""
LLM client and configuration for agent framework.

This package provides LangChain-based LLM client configuration
and utilities for interacting with the DeepSeek API.
"""

from app.agents.llm.client import create_llm_client, get_llm_client
from app.agents.llm.settings import LLMSettings, get_llm_settings

__all__ = [
    "create_llm_client",
    "get_llm_client",
    "LLMSettings",
    "get_llm_settings",
]
