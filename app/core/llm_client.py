"""LLM client for OpenAI-compatible API."""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class LLMClientError(Exception):
    """Base exception for LLM client errors."""

    pass


class LLMRateLimitError(LLMClientError):
    """Raised when LLM API rate limit is exceeded."""

    pass


class LLMTimeoutError(LLMClientError):
    """Raised when LLM API request times out."""

    pass


class LLMAPIError(LLMClientError):
    """Raised for general LLM API errors."""

    def __init__(
        self, message: str, status_code: int = None, response_data: Any = None
    ):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data


class LLMClient:
    """Async client for LLM API."""

    def __init__(
        self,
        api_key: str = None,
        base_url: str = None,
        model: str = None,
        timeout: float = None,
        max_retries: int = None,
    ):
        self.api_key = api_key or settings.llm_api_key
        self.base_url = base_url or settings.llm_base_url
        self.model = model or settings.llm_model
        self.timeout = timeout or settings.llm_timeout
        self.max_retries = max_retries or settings.llm_max_retries

        # Initialize HTTP client
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "User-Agent": f"LLT-Assistant-Backend/0.1.0",
            },
        )

        logger.info(f"Initialized LLM client for model: {self.model}")

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 2000,
        stream: bool = False,
    ) -> str:
        """
        Send a chat completion request to LLM API.

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens in response
            stream: Whether to use streaming mode

        Returns:
            LLM response content as string

        Raises:
            LLMRateLimitError: If rate limit is exceeded
            LLMTimeoutError: If request times out
            LLMAPIError: For other API errors
        """
        url = f"{self.base_url.rstrip('/')}/chat/completions"

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }

        logger.debug(f"Sending LLM request to {url}")

        for attempt in range(self.max_retries + 1):
            try:
                response = await self.client.post(url, json=payload)

                # Handle rate limiting
                if response.status_code == 429:
                    if attempt < self.max_retries:
                        retry_after = self._get_retry_after(response)
                        logger.warning(
                            f"Rate limited, retrying after {retry_after}s (attempt {attempt + 1})"
                        )
                        await asyncio.sleep(retry_after)
                        continue
                    else:
                        raise LLMRateLimitError("Rate limit exceeded after all retries")

                # Handle server errors
                if response.status_code >= 500:
                    if attempt < self.max_retries:
                        wait_time = 2**attempt  # Exponential backoff
                        logger.warning(
                            f"Server error {response.status_code}, retrying after {wait_time}s"
                        )
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        raise LLMAPIError(
                            f"Server error {response.status_code} after all retries",
                            status_code=response.status_code,
                        )

                # Handle client errors
                if response.status_code >= 400:
                    error_data = None
                    try:
                        error_data = response.json()
                    except:
                        error_data = response.text

                    raise LLMAPIError(
                        f"Client error {response.status_code}: {response.text}",
                        status_code=response.status_code,
                        response_data=error_data,
                    )

                # Parse successful response
                response_data = response.json()

                if "choices" in response_data and len(response_data["choices"]) > 0:
                    content = response_data["choices"][0]["message"]["content"]

                    # Log token usage if available
                    if "usage" in response_data:
                        usage = response_data["usage"]
                        logger.info(
                            f"LLM API usage - prompt_tokens: {usage.get('prompt_tokens', 0)}, "
                            f"completion_tokens: {usage.get('completion_tokens', 0)}, "
                            f"total_tokens: {usage.get('total_tokens', 0)}"
                        )

                    return content.strip()
                else:
                    raise LLMAPIError("Invalid response format: no choices returned")

            except httpx.TimeoutException:
                if attempt < self.max_retries:
                    wait_time = 2**attempt
                    logger.warning(f"Request timeout, retrying after {wait_time}s")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    raise LLMTimeoutError(
                        f"Request timed out after {self.timeout}s and all retries"
                    )

            except httpx.ConnectError as e:
                if attempt < self.max_retries:
                    wait_time = 2**attempt
                    logger.warning(
                        f"Connection error, retrying after {wait_time}s: {e}"
                    )
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    raise LLMAPIError(f"Connection error after all retries: {e}")

            except Exception as e:
                if not isinstance(e, LLMClientError):
                    logger.error(f"Unexpected error in LLM request: {e}")
                    raise LLMAPIError(f"Unexpected error: {e}")
                else:
                    raise

        raise LLMAPIError("All retry attempts exhausted")

    def _get_retry_after(self, response: httpx.Response) -> float:
        """Extract retry-after time from response headers."""
        retry_after = response.headers.get("retry-after")
        if retry_after:
            try:
                return float(retry_after)
            except ValueError:
                pass

        # Default retry time
        return 60.0

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()


# Convenience function for creating LLM client with settings
def create_llm_client() -> LLMClient:
    """Create an LLM client using settings."""
    return LLMClient(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        model=settings.llm_model,
        timeout=settings.llm_timeout,
        max_retries=settings.llm_max_retries,
    )
