from __future__ import annotations

import logging
import tempfile
import threading
from pathlib import Path

import numpy as np
import sounddevice as sd
import soundfile as sf


class AudioRecorder:
    def __init__(
        self,
        sample_rate_hz: int,
        channels: int,
        dtype: str,
        temp_audio_dir: Path,
        logger: logging.Logger | None = None,
    ) -> None:
        self.sample_rate_hz = sample_rate_hz
        self.channels = channels
        self.dtype = dtype
        self.temp_audio_dir = temp_audio_dir
        self.logger = logger or logging.getLogger(__name__)

        self._stream: sd.InputStream | None = None
        self._frames: list[np.ndarray] = []
        self._lock = threading.Lock()
        self._is_recording = False

    @property
    def is_recording(self) -> bool:
        with self._lock:
            return self._is_recording

    def start(self) -> None:
        with self._lock:
            if self._is_recording:
                self.logger.debug("Audio recording already active; ignoring start")
                return
            self._frames = []
            self._stream = sd.InputStream(
                samplerate=self.sample_rate_hz,
                channels=self.channels,
                dtype=self.dtype,
                callback=self._on_audio_frame,
            )
            self._stream.start()
            self._is_recording = True
            self.logger.info("Recording started")

    def stop_and_save(self) -> Path:
        with self._lock:
            if not self._is_recording:
                raise RuntimeError("Recording is not active.")
            assert self._stream is not None
            self._stream.stop()
            self._stream.close()
            self._stream = None
            self._is_recording = False

            if not self._frames:
                raise RuntimeError("No audio captured.")

            audio = np.concatenate(self._frames, axis=0)
            self.temp_audio_dir.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                prefix="dictation_",
                suffix=".wav",
                dir=self.temp_audio_dir,
                delete=False,
            ) as tmp:
                tmp_path = Path(tmp.name)
            sf.write(tmp_path, audio, self.sample_rate_hz, subtype="PCM_16")
            self.logger.info("Recording stopped (%s frames) -> %s", len(audio), tmp_path)
            return tmp_path

    def cleanup_file(self, path: Path) -> None:
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            self.logger.warning("Unable to clean temporary audio file %s: %s", path, exc)

    def _on_audio_frame(self, indata: np.ndarray, frames: int, time, status) -> None:  # noqa: ANN001
        if status:
            self.logger.warning("Audio status: %s", status)
        # Copy in callback thread to avoid mutation after next callback.
        self._frames.append(indata.copy())

