from __future__ import annotations

import logging
import time

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI
from openai import APIConnectionError, APITimeoutError, RateLimitError

from .config import AppConfig


REWRITE_MODE_PROMPTS: dict[str, str] = {
    "clean_prose": (
        "Rewrite the text into clean prose with corrected grammar and punctuation. "
        "Remove filler words and stutters while preserving intent and tone."
    ),
    "casual_chat": (
        "Rewrite for an informal chat message. Keep it concise and natural. "
        "Remove filler words and preserve the original meaning."
    ),
    "email": (
        "Rewrite as a professional email message. Keep tone polite and direct. "
        "Do not invent facts. Remove filler words and obvious speech disfluencies."
    ),
    "technical": (
        "Rewrite for technical clarity. Preserve terminology, precision, and meaning. "
        "Fix grammar and remove filler words without over-editing."
    ),
    "raw_transcript": (
        "Return the transcript with minimal edits only: fix obvious punctuation and casing, "
        "do not rephrase content."
    ),
}


class RewriteService:
    def __init__(self, config: AppConfig, logger: logging.Logger | None = None) -> None:
        self.config = config
        self.logger = logger or logging.getLogger(__name__)
        self.client = self._build_client(config)

    def rewrite(self, transcript: str, mode: str) -> str:
        if mode == "raw_transcript":
            return transcript

        prompt = REWRITE_MODE_PROMPTS.get(mode, REWRITE_MODE_PROMPTS["clean_prose"])
        attempts = self.config.retry_attempts
        last_error: Exception | None = None

        for attempt in range(1, attempts + 1):
            try:
                completion = self.client.chat.completions.create(
                    model=self.config.gpt_deployment_name,
                    temperature=0.2,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are a dictation assistant. Improve readability while preserving "
                                "meaning, voice, and intent. Avoid excessive rewriting."
                            ),
                        },
                        {"role": "system", "content": f"Mode: {mode}. Instruction: {prompt}"},
                        {"role": "user", "content": transcript},
                    ],
                )
                text = (completion.choices[0].message.content or "").strip()
                if not text:
                    raise RuntimeError("Rewrite response was empty.")
                return text
            except (APIConnectionError, APITimeoutError, RateLimitError, RuntimeError) as exc:
                last_error = exc
                self.logger.warning("Rewrite attempt %s/%s failed: %s", attempt, attempts, exc)
                if attempt < attempts:
                    delay = self.config.retry_backoff_seconds * attempt
                    time.sleep(delay)

        assert last_error is not None
        raise RuntimeError(f"Rewrite failed after {attempts} attempts: {last_error}") from last_error

    def _build_client(self, config: AppConfig) -> AzureOpenAI:
        if config.use_azure_ad_auth:
            token_provider = get_bearer_token_provider(
                DefaultAzureCredential(),
                "https://cognitiveservices.azure.com/.default",
            )
            return AzureOpenAI(
                azure_endpoint=config.azure_openai_endpoint,
                api_version=config.azure_openai_api_version,
                azure_ad_token_provider=token_provider,
            )
        return AzureOpenAI(
            azure_endpoint=config.azure_openai_endpoint,
            api_key=config.azure_openai_api_key,
            api_version=config.azure_openai_api_version,
        )
