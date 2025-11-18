"""
Unit tests for LLMClient class.

Tests cover API interactions, retry logic, error handling,
and integration with real LLM API.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import httpx
import pytest

from app.core.llm_client import (
    LLMAPIError,
    LLMClient,
    LLMClientError,
    LLMRateLimitError,
    LLMTimeoutError,
    create_llm_client,
)


@pytest.fixture
def llm_client_config():
    """Provide test configuration for LLM client."""
    return {
        "api_key": "test-api-key",
        "base_url": "https://api.test.com/v1",
        "model": "test-model",
        "timeout": 30.0,
        "max_retries": 3,
    }


@pytest.fixture
def mock_httpx_client():
    """Provide mock httpx.AsyncClient."""
    client = AsyncMock(spec=httpx.AsyncClient)
    client.aclose = AsyncMock()
    return client


@pytest.fixture
def sample_messages():
    """Provide sample messages for chat completion."""
    return [
        {"role": "system", "content": "You are a test analyzer."},
        {"role": "user", "content": "Analyze this test code."},
    ]


@pytest.fixture
def successful_response():
    """Provide mock successful API response."""
    response = Mock(spec=httpx.Response)
    response.status_code = 200
    response.json.return_value = {
        "id": "test-id-123",
        "choices": [
            {"message": {"role": "assistant", "content": "This is a test response"}}
        ],
        "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
    }
    return response


class TestLLMClient:
    """Test suite for LLMClient class."""

    def test_client_initialization(self, llm_client_config):
        """Test that LLM client initializes with correct configuration."""
        client = LLMClient(**llm_client_config)

        assert client.api_key == "test-api-key"
        assert client.base_url == "https://api.test.com/v1"
        assert client.model == "test-model"
        assert client.timeout == 30.0
        assert client.max_retries == 3
        assert client.client is not None

    def test_client_initialization_with_defaults(self):
        """Test client initialization with default settings."""
        client = LLMClient()

        # Should use values from settings
        assert client.api_key is not None
        assert client.base_url is not None
        assert client.model is not None

    @pytest.mark.asyncio
    async def test_successful_chat_completion(
        self, llm_client_config, sample_messages, successful_response
    ):
        """Test successful chat completion request."""
        client = LLMClient(**llm_client_config)

        with patch.object(
            client.client, "post", return_value=successful_response
        ) as mock_post:
            result = await client.chat_completion(sample_messages)

            # Verify request was made
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert "chat/completions" in call_args[0][0]

            # Verify payload structure
            payload = call_args[1]["json"]
            assert payload["model"] == "test-model"
            assert payload["messages"] == sample_messages
            assert "temperature" in payload
            assert "max_tokens" in payload

            # Verify response
            assert result == "This is a test response"

        await client.close()

    @pytest.mark.asyncio
    async def test_rate_limit_with_retry(
        self, llm_client_config, sample_messages, successful_response
    ):
        """Test that client retries on rate limit (429) and eventually succeeds."""
        client = LLMClient(**llm_client_config)

        # First call returns 429, second call succeeds
        rate_limit_response = Mock(spec=httpx.Response)
        rate_limit_response.status_code = 429
        rate_limit_response.headers = {"retry-after": "1"}

        responses = [rate_limit_response, successful_response]

        with patch.object(client.client, "post", side_effect=responses) as mock_post:
            with patch("asyncio.sleep", return_value=None):  # Speed up test
                result = await client.chat_completion(sample_messages)

                # Should have made 2 requests
                assert mock_post.call_count == 2
                assert result == "This is a test response"

        await client.close()

    @pytest.mark.asyncio
    async def test_rate_limit_exhausted_retries(
        self, llm_client_config, sample_messages
    ):
        """Test that client raises error when rate limit persists after all retries."""
        client = LLMClient(**llm_client_config)

        rate_limit_response = Mock(spec=httpx.Response)
        rate_limit_response.status_code = 429
        rate_limit_response.headers = {}

        with patch.object(client.client, "post", return_value=rate_limit_response):
            with patch("asyncio.sleep", return_value=None):
                with pytest.raises(LLMRateLimitError, match="Rate limit exceeded"):
                    await client.chat_completion(sample_messages)

        await client.close()

    @pytest.mark.asyncio
    async def test_server_error_with_retry(
        self, llm_client_config, sample_messages, successful_response
    ):
        """Test that client retries on server errors (5xx)."""
        client = LLMClient(**llm_client_config)

        server_error_response = Mock(spec=httpx.Response)
        server_error_response.status_code = 500

        responses = [server_error_response, successful_response]

        with patch.object(client.client, "post", side_effect=responses):
            with patch("asyncio.sleep", return_value=None):
                result = await client.chat_completion(sample_messages)

                assert result == "This is a test response"

        await client.close()

    @pytest.mark.asyncio
    async def test_server_error_exhausted_retries(
        self, llm_client_config, sample_messages
    ):
        """Test that client raises error when server errors persist."""
        client = LLMClient(**llm_client_config)

        server_error_response = Mock(spec=httpx.Response)
        server_error_response.status_code = 503

        with patch.object(client.client, "post", return_value=server_error_response):
            with patch("asyncio.sleep", return_value=None):
                with pytest.raises(LLMAPIError, match="Server error 503"):
                    await client.chat_completion(sample_messages)

        await client.close()

    @pytest.mark.asyncio
    async def test_client_error_raises_immediately(
        self, llm_client_config, sample_messages
    ):
        """Test that client errors (4xx) raise immediately without retry."""
        client = LLMClient(**llm_client_config)

        client_error_response = Mock(spec=httpx.Response)
        client_error_response.status_code = 400
        client_error_response.text = "Bad request"
        client_error_response.json.return_value = {"error": "Invalid payload"}

        with patch.object(client.client, "post", return_value=client_error_response):
            with pytest.raises(LLMAPIError) as exc_info:
                await client.chat_completion(sample_messages)

            assert exc_info.value.status_code == 400
            assert "Bad request" in str(exc_info.value)

        await client.close()

    @pytest.mark.asyncio
    async def test_timeout_with_retry(
        self, llm_client_config, sample_messages, successful_response
    ):
        """Test that client retries on timeout."""
        client = LLMClient(**llm_client_config)

        responses = [httpx.TimeoutException("Timeout"), successful_response]

        with patch.object(client.client, "post", side_effect=responses):
            with patch("asyncio.sleep", return_value=None):
                result = await client.chat_completion(sample_messages)

                assert result == "This is a test response"

        await client.close()

    @pytest.mark.asyncio
    async def test_timeout_exhausted_retries(self, llm_client_config, sample_messages):
        """Test that client raises error when timeout persists."""
        client = LLMClient(**llm_client_config)

        with patch.object(
            client.client, "post", side_effect=httpx.TimeoutException("Timeout")
        ):
            with patch("asyncio.sleep", return_value=None):
                with pytest.raises(LLMTimeoutError, match="timed out"):
                    await client.chat_completion(sample_messages)

        await client.close()

    @pytest.mark.asyncio
    async def test_connection_error_with_retry(
        self, llm_client_config, sample_messages, successful_response
    ):
        """Test that client retries on connection errors."""
        client = LLMClient(**llm_client_config)

        responses = [httpx.ConnectError("Connection failed"), successful_response]

        with patch.object(client.client, "post", side_effect=responses):
            with patch("asyncio.sleep", return_value=None):
                result = await client.chat_completion(sample_messages)

                assert result == "This is a test response"

        await client.close()

    @pytest.mark.asyncio
    async def test_connection_error_exhausted_retries(
        self, llm_client_config, sample_messages
    ):
        """Test that client raises error when connection errors persist."""
        client = LLMClient(**llm_client_config)

        with patch.object(
            client.client, "post", side_effect=httpx.ConnectError("Connection failed")
        ):
            with patch("asyncio.sleep", return_value=None):
                with pytest.raises(LLMAPIError, match="Connection error"):
                    await client.chat_completion(sample_messages)

        await client.close()

    @pytest.mark.asyncio
    async def test_invalid_response_format(self, llm_client_config, sample_messages):
        """Test handling of invalid response format."""
        client = LLMClient(**llm_client_config)

        invalid_response = Mock(spec=httpx.Response)
        invalid_response.status_code = 200
        invalid_response.json.return_value = {"no": "choices"}

        with patch.object(client.client, "post", return_value=invalid_response):
            with pytest.raises(LLMAPIError, match="Invalid response format"):
                await client.chat_completion(sample_messages)

        await client.close()

    def test_get_retry_after_from_header(self, llm_client_config):
        """Test extracting retry-after time from response headers."""
        client = LLMClient(**llm_client_config)

        response = Mock(spec=httpx.Response)
        response.headers = {"retry-after": "30"}

        retry_time = client._get_retry_after(response)
        assert retry_time == 30.0

    def test_get_retry_after_default(self, llm_client_config):
        """Test default retry-after when header is missing."""
        client = LLMClient(**llm_client_config)

        response = Mock(spec=httpx.Response)
        response.headers = {}

        retry_time = client._get_retry_after(response)
        assert retry_time == 60.0

    @pytest.mark.asyncio
    async def test_close_method(self, llm_client_config):
        """Test that close method properly closes HTTP client."""
        client = LLMClient(**llm_client_config)

        with patch.object(
            client.client, "aclose", new_callable=AsyncMock
        ) as mock_close:
            await client.close()
            mock_close.assert_called_once()

    @pytest.mark.asyncio
    async def test_context_manager(
        self, llm_client_config, sample_messages, successful_response
    ):
        """Test using LLM client as async context manager."""
        async with LLMClient(**llm_client_config) as client:
            with patch.object(client.client, "post", return_value=successful_response):
                result = await client.chat_completion(sample_messages)
                assert result == "This is a test response"

        # Client should be closed after exiting context

    def test_create_llm_client_factory(self):
        """Test factory function for creating LLM client."""
        client = create_llm_client()

        assert isinstance(client, LLMClient)
        assert client.api_key is not None
        assert client.base_url is not None

    @pytest.mark.asyncio
    async def test_exponential_backoff(
        self, llm_client_config, sample_messages, successful_response
    ):
        """Test that exponential backoff is used for retries."""
        client = LLMClient(**llm_client_config)

        server_error = Mock(spec=httpx.Response)
        server_error.status_code = 500

        responses = [server_error, server_error, successful_response]
        sleep_times = []

        async def mock_sleep(duration):
            sleep_times.append(duration)

        with patch.object(client.client, "post", side_effect=responses):
            with patch("asyncio.sleep", side_effect=mock_sleep):
                result = await client.chat_completion(sample_messages)

                # Verify exponential backoff: 1s, 2s
                assert len(sleep_times) == 2
                assert sleep_times[0] == 1  # 2^0
                assert sleep_times[1] == 2  # 2^1

        await client.close()


class TestLLMClientIntegration:
    """Integration tests using real LLM API (conditional on API key)."""

    @pytest.mark.asyncio
    @pytest.mark.llm
    @pytest.mark.requires_api_key
    async def test_real_api_call(self, skip_llm_tests):
        """Test real API call (skipped if no API key or disabled)."""
        if skip_llm_tests:
            pytest.skip("Skipping LLM integration test (no API key or disabled)")

        client = create_llm_client()

        try:
            messages = [
                {"role": "system", "content": "You are a helpful assistant."},
                {
                    "role": "user",
                    "content": "Say 'test successful' if you can read this.",
                },
            ]

            result = await client.chat_completion(
                messages=messages, temperature=0.1, max_tokens=50
            )

            # Verify we got a response
            assert result is not None
            assert isinstance(result, str)
            assert len(result) > 0

        finally:
            await client.close()

    @pytest.mark.asyncio
    @pytest.mark.llm
    @pytest.mark.requires_api_key
    async def test_real_api_with_context_manager(self, skip_llm_tests):
        """Test real API using context manager."""
        if skip_llm_tests:
            pytest.skip("Skipping LLM integration test (no API key or disabled)")

        async with create_llm_client() as client:
            messages = [{"role": "user", "content": "Respond with the word 'success'"}]

            result = await client.chat_completion(
                messages=messages, temperature=0.0, max_tokens=10
            )

            assert result is not None
            assert isinstance(result, str)
