from __future__ import annotations

import logging
from contextlib import contextmanager
from collections.abc import Iterator

import pyperclip


class ClipboardManager:
    def __init__(self, logger: logging.Logger | None = None) -> None:
        self.logger = logger or logging.getLogger(__name__)

    def get(self) -> str:
        return pyperclip.paste()

    def set(self, value: str) -> None:
        pyperclip.copy(value)

    @contextmanager
    def preserve(self) -> Iterator[None]:
        original = self.get()
        try:
            yield
        finally:
            self.set(original)
            self.logger.debug("Clipboard restored")

