from __future__ import annotations

import logging
import threading
import time
from pathlib import Path

from dotenv import load_dotenv

from .audio_recorder import AudioRecorder
from .clipboard_manager import ClipboardManager
from .config import AppConfig
from .hotkey_listener import PushToTalkHotkeyListener
from .injector import TextInjector
from .mode_router import ModeRouter
from .rewrite_service import RewriteService
from .transcription_service import TranscriptionService


LOGGER_NAME = "wispr_dictation"


def configure_logging() -> logging.Logger:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    return logging.getLogger(LOGGER_NAME)


class DictationApp:
    def __init__(
        self,
        config: AppConfig,
        recorder: AudioRecorder,
        transcription_service: TranscriptionService,
        rewrite_service: RewriteService,
        mode_router: ModeRouter,
        injector: TextInjector,
        logger: logging.Logger,
    ) -> None:
        self.config = config
        self.recorder = recorder
        self.transcription_service = transcription_service
        self.rewrite_service = rewrite_service
        self.mode_router = mode_router
        self.injector = injector
        self.logger = logger

        self._processing_lock = threading.Lock()
        self._active_worker: threading.Thread | None = None

    def on_hotkey_hold_start(self) -> None:
        try:
            self.recorder.start()
        except Exception as exc:  # noqa: BLE001
            self.logger.error("Failed to start recording: %s", exc)

    def on_hotkey_hold_end(self) -> None:
        if self._active_worker and self._active_worker.is_alive():
            self.logger.warning("Still processing previous dictation; skipping this release")
            try:
                if self.recorder.is_recording:
                    # Stop and drop audio to avoid lingering stream when we are busy.
                    dropped = self.recorder.stop_and_save()
                    self.recorder.cleanup_file(dropped)
            except Exception:  # noqa: BLE001
                pass
            return

        worker = threading.Thread(target=self._process_current_recording, daemon=True)
        self._active_worker = worker
        worker.start()

    def _process_current_recording(self) -> None:
        with self._processing_lock:
            wav_path: Path | None = None
            try:
                wav_path = self.recorder.stop_and_save()
            except Exception as exc:  # noqa: BLE001
                self.logger.error("Failed to stop recording: %s", exc)
                return

            try:
                transcript = self.transcription_service.transcribe_file(wav_path)
                self.logger.info("Transcription complete")
            except Exception as exc:  # noqa: BLE001
                self.logger.error("Transcription failed: %s", exc)
                self._cleanup_tmp_audio(wav_path)
                return

            final_text = transcript
            if self.config.enable_polishing:
                mode = self.mode_router.select_mode()
                try:
                    final_text = self.rewrite_service.rewrite(transcript, mode)
                    self.logger.info("Rewrite complete (mode=%s)", mode)
                except Exception as exc:  # noqa: BLE001
                    final_text = transcript
                    self.logger.warning(
                        "Rewrite failed (mode=%s), falling back to raw transcript: %s", mode, exc
                    )

            try:
                self.injector.inject_text(final_text)
            except Exception as exc:  # noqa: BLE001
                self.logger.error("Text injection failed: %s", exc)
            finally:
                self._cleanup_tmp_audio(wav_path)

    def _cleanup_tmp_audio(self, path: Path | None) -> None:
        if path is None:
            return
        self.recorder.cleanup_file(path)


def build_app(config: AppConfig, logger: logging.Logger) -> DictationApp:
    recorder = AudioRecorder(
        sample_rate_hz=config.sample_rate_hz,
        channels=config.channels,
        dtype=config.audio_dtype,
        temp_audio_dir=config.temp_audio_dir,
        logger=logger,
    )
    transcription = TranscriptionService(config=config, logger=logger)
    rewrite = RewriteService(config=config, logger=logger)
    router = ModeRouter(default_mode=config.default_rewrite_mode, logger=logger)
    clipboard = ClipboardManager(logger=logger)
    injector = TextInjector(clipboard_manager=clipboard, logger=logger)
    return DictationApp(config, recorder, transcription, rewrite, router, injector, logger)


def main() -> None:
    load_dotenv()
    logger = configure_logging()
    config = AppConfig.from_env()
    config.validate()

    app = build_app(config=config, logger=logger)
    listener = PushToTalkHotkeyListener(
        hotkey=config.push_to_talk_hotkey,
        on_hold_start=app.on_hotkey_hold_start,
        on_hold_end=app.on_hotkey_hold_end,
        logger=logger,
    )

    listener.start()
    logger.info("Dictation app running. Hold %s to talk. Press Ctrl+C to exit.", config.push_to_talk_hotkey)

    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        listener.stop()


if __name__ == "__main__":
    main()

