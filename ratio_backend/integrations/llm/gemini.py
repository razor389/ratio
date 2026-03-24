"""Gemini-backed implementation of the shared LLM provider interface."""

from __future__ import annotations

import os

import google.generativeai as genai
from google.generativeai.types import GenerationConfig, HarmBlockThreshold, HarmCategory

from ...core.logging import get_logger
from .base import LLMProvider

logger = get_logger(__name__)


class GeminiProvider(LLMProvider):
    """Use the Gemini SDK for async text generation."""

    def __init__(self) -> None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not found in environment. Please set it in your .env file.")
        genai.configure(api_key=api_key)

    async def generate_content_async(
        self,
        system_prompt: str,
        user_prompt: str,
        model_name: str | None = None,
        temperature: float = 0.5,
        max_output_tokens: int | None = None,
    ) -> str:
        """Generate text using the configured Gemini model."""
        resolved_model = model_name or os.getenv("GEMINI_MODEL", "gemini-2.5-pro")
        model = genai.GenerativeModel(model_name=resolved_model, system_instruction=system_prompt)
        config = GenerationConfig(
            response_mime_type="text/plain",
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )
        safety_settings = {
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        }

        logger.info("Calling Gemini provider", extra={"model_name": resolved_model})
        try:
            response = await model.generate_content_async(
                [user_prompt],
                generation_config=config,
                safety_settings=safety_settings,
            )
            if response.candidates and response.candidates[0].finish_reason == 2 and hasattr(response, "text"):
                logger.warning("Gemini response hit max tokens", extra={"model_name": resolved_model})
                return response.text.strip()
            return response.text.strip()
        except ValueError:
            logger.exception("Gemini provider returned empty or blocked output", extra={"model_name": resolved_model})
            return ""
        except Exception:
            logger.exception("Gemini provider call failed", extra={"model_name": resolved_model})
            return ""
