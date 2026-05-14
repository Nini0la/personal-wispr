from __future__ import annotations

import logging
import platform
import subprocess
import ctypes
from dataclasses import dataclass


@dataclass(frozen=True)
class RouteRule:
    keywords: tuple[str, ...]
    mode: str


class ActiveApplicationDetector:
    def __init__(self, logger: logging.Logger | None = None) -> None:
        self.logger = logger or logging.getLogger(__name__)

    def detect(self) -> str | None:
        system = platform.system()
        if system == "Darwin":
            return self._detect_macos()
        if system == "Windows":
            return self._detect_windows()
        if system == "Linux":
            return self._detect_linux()
        return None

    def _detect_macos(self) -> str | None:
        try:
            from AppKit import NSWorkspace  # type: ignore

            app = NSWorkspace.sharedWorkspace().frontmostApplication()
            if app is not None:
                name = app.localizedName()
                if name:
                    # Keep reading to also include focused window context.
                    app_name = str(name)
                else:
                    app_name = ""
            else:
                app_name = ""
        except Exception as exc:  # noqa: BLE001
            self.logger.debug("AppKit app detection failed: %s", exc)
            app_name = ""

        try:
            result = subprocess.run(
                [
                    "osascript",
                    "-e",
                    (
                        'tell application "System Events"\n'
                        "set p to first process whose frontmost is true\n"
                        "set appName to name of p\n"
                        'set windowName to ""\n'
                        "try\n"
                        "set windowName to name of front window of p\n"
                        "end try\n"
                        'return appName & " | " & windowName\n'
                        "end tell"
                    ),
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            name = result.stdout.strip()
            if name:
                return name
            return app_name or None
        except Exception as exc:  # noqa: BLE001
            self.logger.debug("AppleScript app detection failed: %s", exc)
            return app_name or None

    def _detect_windows(self) -> str | None:
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return None

        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return None

        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        title = buffer.value.strip()
        return title or None

    def _detect_linux(self) -> str | None:
        try:
            result = subprocess.run(
                ["xdotool", "getwindowfocus", "getwindowname"],
                capture_output=True,
                text=True,
                check=True,
            )
            name = result.stdout.strip()
            return name or None
        except Exception:  # noqa: BLE001
            return None


class ModeRouter:
    def __init__(
        self,
        default_mode: str = "clean_prose",
        app_detector: ActiveApplicationDetector | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.default_mode = default_mode
        self.app_detector = app_detector or ActiveApplicationDetector(logger=logger)
        self.logger = logger or logging.getLogger(__name__)
        self.rules = [
            RouteRule(("slack", "discord"), "casual_chat"),
            RouteRule(("gmail", "outlook", "mail"), "email"),
            RouteRule(("code", "vscode", "visual studio code", "jetbrains", "pycharm"), "technical"),
            RouteRule(("docs", "notion", "word", "pages"), "clean_prose"),
        ]

    def select_mode(self) -> str:
        app_name = self.app_detector.detect()
        if not app_name:
            self.logger.debug("No active app detected; using default mode %s", self.default_mode)
            return self.default_mode

        normalized = app_name.lower()
        for rule in self.rules:
            if any(keyword in normalized for keyword in rule.keywords):
                self.logger.info("Mode %s selected for active app: %s", rule.mode, app_name)
                return rule.mode

        self.logger.info("No mode rule matched app '%s'; using %s", app_name, self.default_mode)
        return self.default_mode
