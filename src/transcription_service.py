from __future__ import annotations

import logging
import time
from pathlib import Path

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI
from openai import APIConnectionError, APITimeoutError, RateLimitError

from .config import AppConfig


class TranscriptionService:
    def __init__(self, config: AppConfig, logger: logging.Logger | None = None) -> None:
        self.config = config
        self.logger = logger or logging.getLogger(__name__)
        self.client = self._build_client(config)

    def transcribe_file(self, wav_path: Path) -> str:
        attempts = self.config.retry_attempts
        last_error: Exception | None = None

        for attempt in range(1, attempts + 1):
            try:
                with wav_path.open("rb") as audio_file:
                    response = self.client.audio.transcriptions.create(
                        file=audio_file,
                        model=self.config.whisper_deployment_name,
                    )
                text = (response.text or "").strip()
                if not text:
                    raise RuntimeError("Transcription response was empty.")
                return text
            except (APIConnectionError, APITimeoutError, RateLimitError, RuntimeError) as exc:
                last_error = exc
                self.logger.warning(
                    "Transcription attempt %s/%s failed: %s", attempt, attempts, exc
                )
                if attempt < attempts:
                    delay = self.config.retry_backoff_seconds * attempt
                    time.sleep(delay)

        assert last_error is not None
        raise RuntimeError(f"Transcription failed after {attempts} attempts: {last_error}") from last_error

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
