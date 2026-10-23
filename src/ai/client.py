"""Hugging Face Inference Provider client for OpportunityLens."""

from __future__ import annotations

import logging
from typing import Any, List, Optional, Tuple

from src.config import ai_config

logger = logging.getLogger(__name__)


class HuggingFaceInferenceClient:
    """Isolated client for Hugging Face Inference Providers with error isolation."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        timeout: Optional[int] = None,
        max_tokens: Optional[int] = None,
    ):
        self.api_key = api_key if api_key is not None else ai_config.hf_api_key
        self.model_name = (
            model_name if model_name is not None else ai_config.model_name
        )
        self.timeout = (
            timeout if timeout is not None else ai_config.timeout_seconds
        )
        self.max_tokens = (
            max_tokens if max_tokens is not None else ai_config.max_output_tokens
        )
        self._client: Optional[Any] = None

    @property
    def is_available(self) -> bool:
        """Check if AI inference is enabled and API key is present."""
        return bool(ai_config.ai_enabled and self.api_key and self.api_key.strip())

    def _get_client(self) -> Any:
        """Lazy load and initialize Hugging Face InferenceClient."""
        if self._client is None:
            from huggingface_hub import InferenceClient

            self._client = InferenceClient(
                model=self.model_name,
                token=self.api_key,
                timeout=self.timeout,
            )
        return self._client

    def generate_chat_completion(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> Tuple[Optional[str], Optional[str]]:
        """Send chat prompt to Hugging Face model and return raw completion text.

        Args:
            system_prompt: Trusted system instructions.
            user_prompt: User prompt containing bounded untrusted evidence.

        Returns:
            Tuple of (completion_text, error_message).
        """
        if not self.is_available:
            return (
                None,
                "AI inference is disabled or no HF_API_KEY is configured. "
                "Operating in deterministic explanation mode.",
            )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        try:
            client = self._get_client()
            response = client.chat_completion(
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=0.2,  # Low temperature for grounded factual consistency
            )

            if response and response.choices and len(response.choices) > 0:
                content = response.choices[0].message.content
                return content, None

            return None, "Model returned an empty response."

        except Exception as exc:
            err_str = str(exc).lower()
            # Sanitize error message to avoid leaking any token or url
            if "401" in err_str or "unauthorized" in err_str or "forbidden" in err_str:
                sanitized = "Authentication failed: Invalid or expired Hugging Face token."
            elif "429" in err_str or "rate limit" in err_str:
                sanitized = "Hugging Face Inference rate limit exceeded. Please try again later."
            elif "timed out" in err_str or "timeout" in err_str:
                sanitized = f"Inference request timed out after {self.timeout}s."
            elif "503" in err_str or "loading" in err_str:
                sanitized = "Model is currently loading on Hugging Face. Please retry in a moment."
            else:
                sanitized = "Unable to complete AI inference request. Provider temporarily unavailable."

            logger.warning("Hugging Face inference error: %s", sanitized)
            return None, sanitized
