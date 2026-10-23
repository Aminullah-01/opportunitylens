"""Unit tests for Hugging Face Inference Provider client with error isolation."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest

from src.ai.client import HuggingFaceInferenceClient


def test_client_unavailable_without_key():
    """Verify that client reports unavailable when API key is empty or None."""
    client = HuggingFaceInferenceClient(api_key=None)
    # When api_key is None (and no HF_API_KEY in test environment), is_available is False
    client.api_key = ""
    assert client.is_available is False

    text, err = client.generate_chat_completion("System prompt", "User prompt")
    assert text is None
    assert "Operating in deterministic explanation mode" in err


def test_client_available_with_key():
    """Verify that client reports available when valid API key is present."""
    client = HuggingFaceInferenceClient(api_key="hf_test_dummy_token_12345")
    assert client.is_available is True


def test_client_successful_completion():
    """Verify that client returns completion text from mocked inference client."""
    client = HuggingFaceInferenceClient(api_key="hf_test_token")

    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = '{"overall_summary": "Great match", "recommendations": []}'
    mock_response.choices = [mock_choice]

    mock_hf_client = MagicMock()
    mock_hf_client.chat_completion.return_value = mock_response

    with patch.object(client, "_get_client", return_value=mock_hf_client):
        content, error = client.generate_chat_completion("System", "User")
        assert error is None
        assert content == '{"overall_summary": "Great match", "recommendations": []}'
        mock_hf_client.chat_completion.assert_called_once()


def test_client_empty_response():
    """Verify handling when inference client returns choices without content."""
    client = HuggingFaceInferenceClient(api_key="hf_test_token")

    mock_response = MagicMock()
    mock_response.choices = []

    mock_hf_client = MagicMock()
    mock_hf_client.chat_completion.return_value = mock_response

    with patch.object(client, "_get_client", return_value=mock_hf_client):
        content, error = client.generate_chat_completion("System", "User")
        assert content is None
        assert "empty response" in error


def test_client_auth_error_sanitization():
    """Verify that 401 / unauthorized errors are sanitized and do not leak token."""
    secret_key = "hf_SUPER_SECRET_TOKEN_XYZ"
    client = HuggingFaceInferenceClient(api_key=secret_key)

    mock_hf_client = MagicMock()
    mock_hf_client.chat_completion.side_effect = Exception(
        f"401 Client Error: Unauthorized for url with token {secret_key}"
    )

    with patch.object(client, "_get_client", return_value=mock_hf_client):
        content, error = client.generate_chat_completion("System", "User")
        assert content is None
        assert "Authentication failed" in error
        # Verify secret key is never leaked
        assert secret_key not in error


def test_client_rate_limit_sanitization():
    """Verify rate limit error sanitization."""
    client = HuggingFaceInferenceClient(api_key="hf_token")

    mock_hf_client = MagicMock()
    mock_hf_client.chat_completion.side_effect = Exception("429 Too Many Requests: Rate limit exceeded")

    with patch.object(client, "_get_client", return_value=mock_hf_client):
        content, error = client.generate_chat_completion("System", "User")
        assert content is None
        assert "rate limit exceeded" in error.lower()


def test_client_timeout_sanitization():
    """Verify timeout exception sanitization."""
    client = HuggingFaceInferenceClient(api_key="hf_token", timeout=5)

    mock_hf_client = MagicMock()
    mock_hf_client.chat_completion.side_effect = Exception("Request timed out after 5.0 seconds")

    with patch.object(client, "_get_client", return_value=mock_hf_client):
        content, error = client.generate_chat_completion("System", "User")
        assert content is None
        assert "timed out after 5s" in error
