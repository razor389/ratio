"""Anthropic-backed implementation of the shared LLM provider interface."""

from __future__ import annotations

import os

from ...core.logging import get_logger
from .base import LLMProvider

logger = get_logger(__name__)


class AnthropicProvider(LLMProvider):
    """Use Anthropic Messages API for async text generation."""

    def __init__(self) -> None:
        from anthropic import AsyncAnthropic

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in environment.")
        self.client = AsyncAnthropic(api_key=api_key)

    async def generate_content_async(
        self,
        system_prompt: str,
        user_prompt: str,
        model_name: str | None = None,
        temperature: float = 0.5,
        max_output_tokens: int | None = None,
    ) -> str:
        """Generate text using the configured Anthropic model."""
        resolved_model = model_name or os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
        max_tokens = max_output_tokens or 4096

        logger.info("Calling Anthropic provider", extra={"model_name": resolved_model})
        try:
            message = await self.client.messages.create(
                model=resolved_model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            return message.content[0].text.strip()
        except Exception:
            logger.exception("Anthropic provider call failed", extra={"model_name": resolved_model})
            return ""
