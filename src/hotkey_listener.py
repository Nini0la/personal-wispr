from __future__ import annotations

import logging
import threading
from collections.abc import Callable

from pynput import keyboard


_SPECIAL_KEY_ALIASES = {
    "ctrl": "ctrl",
    "control": "ctrl",
    "shift": "shift",
    "alt": "alt",
    "option": "alt",
    "cmd": "cmd",
    "command": "cmd",
    "super": "cmd",
    "space": "space",
    "enter": "enter",
    "return": "enter",
    "esc": "esc",
    "escape": "esc",
}

_PYNPUT_SPECIAL_TOKEN_MAP = {
    keyboard.Key.ctrl: "ctrl",
    keyboard.Key.ctrl_l: "ctrl",
    keyboard.Key.ctrl_r: "ctrl",
    keyboard.Key.shift: "shift",
    keyboard.Key.shift_l: "shift",
    keyboard.Key.shift_r: "shift",
    keyboard.Key.alt: "alt",
    keyboard.Key.alt_l: "alt",
    keyboard.Key.alt_r: "alt",
    keyboard.Key.alt_gr: "alt",
    keyboard.Key.cmd: "cmd",
    keyboard.Key.cmd_l: "cmd",
    keyboard.Key.cmd_r: "cmd",
    keyboard.Key.space: "space",
    keyboard.Key.enter: "enter",
    keyboard.Key.esc: "esc",
}


def _normalize_hotkey_token(token: str) -> str:
    normalized = token.strip().lower().replace("<", "").replace(">", "")
    return _SPECIAL_KEY_ALIASES.get(normalized, normalized)


def parse_hotkey(hotkey: str) -> set[str]:
    tokens = {_normalize_hotkey_token(part) for part in hotkey.split("+") if part.strip()}
    if not tokens:
        raise ValueError("Hotkey cannot be empty.")
    return tokens


def _key_to_token(key: keyboard.Key | keyboard.KeyCode) -> str | None:
    if key in _PYNPUT_SPECIAL_TOKEN_MAP:
        return _PYNPUT_SPECIAL_TOKEN_MAP[key]
    if isinstance(key, keyboard.KeyCode):
        if key.char:
            return key.char.lower()
    return None


class PushToTalkHotkeyListener:
    def __init__(
        self,
        hotkey: str,
        on_hold_start: Callable[[], None],
        on_hold_end: Callable[[], None],
        logger: logging.Logger | None = None,
    ) -> None:
        self.logger = logger or logging.getLogger(__name__)
        self.required_tokens = parse_hotkey(hotkey)
        self.on_hold_start = on_hold_start
        self.on_hold_end = on_hold_end
        self.listener: keyboard.Listener | None = None
        self._pressed_tokens: set[str] = set()
        self._is_active = False
        self._lock = threading.Lock()

    def start(self) -> None:
        self.listener = keyboard.Listener(on_press=self._on_press, on_release=self._on_release)
        self.listener.start()
        self.logger.info("Hotkey listener started for %s", "+".join(sorted(self.required_tokens)))

    def stop(self) -> None:
        if self.listener is not None:
            self.listener.stop()
            self.listener = None
            self.logger.info("Hotkey listener stopped")

    def join(self) -> None:
        if self.listener is not None:
            self.listener.join()

    def _on_press(self, key: keyboard.Key | keyboard.KeyCode) -> None:
        token = _key_to_token(key)
        if token is None:
            return
        with self._lock:
            self._pressed_tokens.add(token)
            if not self._is_active and self.required_tokens.issubset(self._pressed_tokens):
                self._is_active = True
                self.logger.debug("Push-to-talk active")
                self.on_hold_start()

    def _on_release(self, key: keyboard.Key | keyboard.KeyCode) -> None:
        token = _key_to_token(key)
        if token is None:
            return
        with self._lock:
            self._pressed_tokens.discard(token)
            if self._is_active and not self.required_tokens.issubset(self._pressed_tokens):
                self._is_active = False
                self.logger.debug("Push-to-talk released")
                self.on_hold_end()

