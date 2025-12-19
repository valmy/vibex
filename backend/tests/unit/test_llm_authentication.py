"""
Unit tests for LLM authentication error handling.

Tests the enhanced authentication validation and error reporting.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.llm.llm_exceptions import AuthenticationError
from app.services.llm.llm_service import LLMService


class TestLLMAuthentication:
    """Test LLM authentication error handling."""

    @pytest.mark.asyncio
    async def test_authentication_success(self) -> None:
        """Test successful authentication with valid API key."""
        # Mock the OpenAI client
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "AUTH_OK"
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        # Create LLM service with mocked client
        service = LLMService()
        service._client = mock_client
        service.api_key = "valid_api_key"

        # Test authentication
        result = await service.validate_authentication()
        assert result is True

    @pytest.mark.asyncio
    async def test_authentication_failure_empty_api_key(self) -> None:
        """Test authentication failure with empty API key."""
        service = LLMService()
        service.api_key = ""

        with pytest.raises(AuthenticationError) as exc_info:
            await service.validate_authentication()

        error_msg = str(exc_info.value)
        assert "No API key configured" in error_msg
        assert "Expected OPENROUTER_API_KEY" in error_msg
        assert "Timestamp:" in error_msg

        # Verify comprehensive error details
        assert "AUTHENTICATION FAILURE" not in error_msg  # This should be in test output, not error
        assert len(error_msg) > 100  # Should be detailed

    @pytest.mark.asyncio
    async def test_authentication_failure_server_rejection(self) -> None:
        """Test authentication failure when server rejects credentials."""
        # Mock the OpenAI client to return non-AUTH_OK response
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Authentication failed: Invalid API key"
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        # Create LLM service with mocked client
        service = LLMService()
        service._client = mock_client
        service.api_key = "invalid_api_key"

        with pytest.raises(AuthenticationError) as exc_info:
            await service.validate_authentication()

        error_msg = str(exc_info.value)
        assert "Authentication failed" in error_msg
        assert "Server response" in error_msg
        assert "Expected: 'AUTH_OK'" in error_msg
        assert "Actual:" in error_msg
        assert "Timestamp:" in error_msg

        # Verify comprehensive error details
        assert len(error_msg) > 150  # Should be very detailed

    @pytest.mark.asyncio
    async def test_authentication_failure_exception(self) -> None:
        """Test authentication failure with unexpected exception."""
        # Mock the OpenAI client to raise an exception
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(side_effect=Exception("Connection timeout"))

        # Create LLM service with mocked client
        service = LLMService()
        service._client = mock_client
        service.api_key = "valid_api_key"

        with pytest.raises(AuthenticationError) as exc_info:
            await service.validate_authentication()

        error_msg = str(exc_info.value)
        assert "Authentication failed" in error_msg
        assert "Connection timeout" in error_msg
        assert "Server:" in error_msg
        assert "Model:" in error_msg
        assert "Timestamp:" in error_msg

        # Verify comprehensive error details
        assert len(error_msg) > 100  # Should be detailed

    @pytest.mark.asyncio
    async def test_authentication_error_comprehensive_details(self) -> None:
        """Test that authentication errors provide comprehensive details."""
        # Mock the OpenAI client to raise an exception with server details
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(
            side_effect=Exception("401 Unauthorized: Invalid API key")
        )

        # Create LLM service with mocked client
        service = LLMService()
        service._client = mock_client
        service.api_key = "invalid_api_key"
        service.base_url = "https://openrouter.ai/api/v1"
        service.model = "gpt-4"

        with pytest.raises(AuthenticationError) as exc_info:
            await service.validate_authentication()

        error_msg = str(exc_info.value)

        # Verify all required comprehensive details are present
        assert "Authentication failed" in error_msg
        assert "401 Unauthorized" in error_msg
        assert "Invalid API key" in error_msg
        assert "Server: https://openrouter.ai/api/v1" in error_msg
        assert "Model: gpt-4" in error_msg
        assert "Timestamp:" in error_msg

        # Verify timestamp format
        timestamp_part = error_msg.split("Timestamp: ")[1]
        assert len(timestamp_part) > 10  # Should contain actual timestamp

        # Verify error is detailed enough for debugging
        assert len(error_msg) > 150

    def test_authentication_error_inheritance(self) -> None:
        """Test that AuthenticationError inherits from DecisionEngineError."""
        from app.services.llm.llm_exceptions import DecisionEngineError

        error = AuthenticationError("Test error")
        assert isinstance(error, DecisionEngineError)
        assert isinstance(error, Exception)


class TestLLMIntegrationAuthentication:
    """Test LLM integration with authentication validation."""

    @pytest.mark.asyncio
    async def test_integration_authentication_validation(self) -> None:
        """Test that integration tests properly validate authentication."""
        # This simulates the authentication validation that happens in the integration test
        service = LLMService()

        # Test with empty API key
        service.api_key = ""
        with pytest.raises(AuthenticationError):
            await service.validate_authentication()

        # Test with valid API key but mocked failure
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Authentication failed"
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        service._client = mock_client
        service.api_key = "valid_key"

        with pytest.raises(AuthenticationError) as exc_info:
            await service.validate_authentication()

        # Verify comprehensive error message
        error_msg = str(exc_info.value)
        assert "Server response" in error_msg
        assert "Expected" in error_msg
        assert "Actual" in error_msg
        assert "Timestamp" in error_msg
