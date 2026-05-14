from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path


def _read_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _read_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    return int(raw)


def _read_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    return float(raw)


@dataclass(frozen=True)
class AppConfig:
    azure_openai_endpoint: str
    azure_openai_api_key: str | None
    azure_openai_api_version: str
    whisper_deployment_name: str
    gpt_deployment_name: str
    push_to_talk_hotkey: str
    enable_polishing: bool
    default_rewrite_mode: str
    sample_rate_hz: int
    channels: int
    audio_dtype: str
    temp_audio_dir: Path
    retry_attempts: int
    retry_backoff_seconds: float
    use_azure_ad_auth: bool

    @classmethod
    def from_env(cls) -> "AppConfig":
        temp_dir = Path(os.getenv("TEMP_AUDIO_DIR", tempfile.gettempdir()))
        return cls(
            azure_openai_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", "").strip(),
            azure_openai_api_key=os.getenv("AZURE_OPENAI_API_KEY", "").strip() or None,
            azure_openai_api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21"),
            whisper_deployment_name=os.getenv("WHISPER_DEPLOYMENT_NAME", "").strip(),
            gpt_deployment_name=os.getenv("GPT_DEPLOYMENT_NAME", "").strip(),
            push_to_talk_hotkey=os.getenv("PUSH_TO_TALK_HOTKEY", "<ctrl>+<shift>+space"),
            enable_polishing=_read_bool("ENABLE_POLISHING", True),
            default_rewrite_mode=os.getenv("DEFAULT_REWRITE_MODE", "clean_prose").strip(),
            sample_rate_hz=_read_int("SAMPLE_RATE_HZ", 16000),
            channels=_read_int("AUDIO_CHANNELS", 1),
            audio_dtype=os.getenv("AUDIO_DTYPE", "float32").strip(),
            temp_audio_dir=temp_dir,
            retry_attempts=_read_int("RETRY_ATTEMPTS", 3),
            retry_backoff_seconds=_read_float("RETRY_BACKOFF_SECONDS", 1.0),
            use_azure_ad_auth=_read_bool("USE_AZURE_AD_AUTH", False),
        )

    def validate(self) -> None:
        missing = []
        if not self.azure_openai_endpoint:
            missing.append("AZURE_OPENAI_ENDPOINT")
        if not self.whisper_deployment_name:
            missing.append("WHISPER_DEPLOYMENT_NAME")
        if not self.gpt_deployment_name:
            missing.append("GPT_DEPLOYMENT_NAME")
        if not self.use_azure_ad_auth and not self.azure_openai_api_key:
            missing.append("AZURE_OPENAI_API_KEY (or set USE_AZURE_AD_AUTH=true)")
        if missing:
            joined = ", ".join(missing)
            raise ValueError(f"Missing required configuration: {joined}")

