"""
LLM client for agent framework using LangChain.

This module provides a LangChain-based client for interacting with
the DeepSeek API. It handles client creation, caching, and provides
utilities for chat completions.
"""

import logging
from functools import lru_cache
from typing import Dict, List, Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.agents.llm.settings import LLMSettings, get_llm_settings

logger = logging.getLogger(__name__)


def create_llm_client(settings: Optional[LLMSettings] = None) -> BaseChatModel:
    """
    Create a LangChain LLM client configured for DeepSeek.

    This function creates a ChatOpenAI instance configured to use the
    DeepSeek API. It uses the OpenAI-compatible interface provided by
    LangChain.

    Args:
        settings: Optional LLM settings. If not provided, loads from environment.

    Returns:
        Configured LangChain ChatOpenAI client

    Raises:
        ValueError: If API key is not configured or invalid
        Exception: If client creation fails

    Example:
        >>> client = create_llm_client()
        >>> response = await client.ainvoke([
        ...     {"role": "user", "content": "Hello!"}
        ... ])
    """
    if settings is None:
        settings = get_llm_settings()

    # Validate API key
    if not settings.validate_api_key():
        raise ValueError(
            "Invalid or missing DEEPSEEK_API_KEY. "
            "Please set it in your .env file or environment variables."
        )

    logger.info(
        f"Creating LLM client with model={settings.deepseek_model}, "
        f"temperature={settings.deepseek_temperature}"
    )

    try:
        # Create ChatOpenAI client configured for DeepSeek
        client = ChatOpenAI(
            model=settings.deepseek_model,
            base_url=settings.deepseek_base_url,
            api_key=settings.deepseek_api_key,
            temperature=settings.deepseek_temperature,
            max_tokens=settings.deepseek_max_tokens,
            timeout=settings.deepseek_timeout,
            max_retries=settings.agent_max_retries,
            # Disable streaming for simpler response handling
            streaming=False,
        )

        logger.info("LLM client created successfully")
        return client

    except Exception as e:
        logger.error(f"Failed to create LLM client: {e}")
        raise


@lru_cache(maxsize=1)
def get_llm_client() -> BaseChatModel:
    """
    Get or create a cached LLM client instance.

    This function returns a singleton LLM client that is reused across
    the application. The client is created lazily on first access.

    Returns:
        Cached LangChain ChatOpenAI client

    Raises:
        ValueError: If API key is not configured
        Exception: If client creation fails
    """
    return create_llm_client()


async def chat_completion(
    messages: List[Dict[str, str]],
    client: Optional[BaseChatModel] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> str:
    """
    Perform a chat completion request.

    This is a convenience function for making simple chat completion
    requests without needing to manage the client directly.

    Args:
        messages: List of message dictionaries with 'role' and 'content'
        client: Optional LLM client. If not provided, uses cached instance.
        temperature: Optional temperature override
        max_tokens: Optional max_tokens override

    Returns:
        Response content as string

    Raises:
        Exception: If LLM request fails

    Example:
        >>> response = await chat_completion([
        ...     {"role": "system", "content": "You are a helpful assistant."},
        ...     {"role": "user", "content": "What is 2+2?"}
        ... ])
        >>> print(response)
        "4"
    """
    if client is None:
        client = get_llm_client()

    # Override settings if provided
    if temperature is not None:
        client = client.bind(temperature=temperature)
    if max_tokens is not None:
        client = client.bind(max_tokens=max_tokens)

    try:
        # Convert messages to LangChain format
        langchain_messages = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "system":
                langchain_messages.append(SystemMessage(content=content))
            elif role == "assistant":
                langchain_messages.append(AIMessage(content=content))
            else:  # user or any other role defaults to HumanMessage
                langchain_messages.append(HumanMessage(content=content))

        # Invoke the model
        response = await client.ainvoke(langchain_messages)

        # Extract content from response
        return response.content

    except Exception as e:
        logger.error(f"Chat completion failed: {e}")
        raise


def clear_client_cache() -> None:
    """
    Clear the cached LLM client.

    This forces a new client to be created on the next call to
    get_llm_client(). Useful for testing or configuration changes.
    """
    get_llm_client.cache_clear()
    logger.info("LLM client cache cleared")
