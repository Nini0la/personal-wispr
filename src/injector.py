from __future__ import annotations

import logging
import platform
import time

import pyautogui

from .clipboard_manager import ClipboardManager


class TextInjector:
    def __init__(
        self,
        clipboard_manager: ClipboardManager | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.clipboard_manager = clipboard_manager or ClipboardManager(logger=logger)
        self.logger = logger or logging.getLogger(__name__)
        pyautogui.FAILSAFE = False
        pyautogui.PAUSE = 0

    def inject_text(self, text: str) -> None:
        if not text.strip():
            self.logger.info("Nothing to inject; text was empty")
            return

        with self.clipboard_manager.preserve():
            self.clipboard_manager.set(text)
            # Short delay gives the system clipboard manager time to update.
            time.sleep(0.05)
            if platform.system() == "Darwin":
                pyautogui.hotkey("command", "v")
            else:
                pyautogui.hotkey("ctrl", "v")
            self.logger.info("Injected text into active application")

