"""Optional mouse jiggler to prevent idle sleep while LaunchPad is running."""

from __future__ import annotations

import sys
import threading
from typing import Callable

SETTING_MOUSE_JIGGLER = "mouse_jiggler_enabled"
DEFAULT_JIGGLE_INTERVAL_SEC = 50


def setting_to_enabled(value: str) -> bool:
    """Return True only when the persisted setting is the string ``true``."""
    return value == "true"


def _default_nudge() -> None:
    if sys.platform != "win32":
        return
    import ctypes

    user32 = ctypes.windll.user32
    point = ctypes.wintypes.POINT()
    if not user32.GetCursorPos(ctypes.byref(point)):
        return
    x, y = point.x, point.y
    user32.SetCursorPos(x + 1, y)
    user32.SetCursorPos(x, y)


class MouseJiggler:
    """Periodically nudge the cursor while enabled."""

    def __init__(
        self,
        *,
        interval_sec: float = DEFAULT_JIGGLE_INTERVAL_SEC,
        nudge_fn: Callable[[], None] | None = None,
    ) -> None:
        self._interval_sec = interval_sec
        self._nudge_fn = nudge_fn or _default_nudge
        self.enabled = False
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def nudge(self) -> None:
        self._nudge_fn()

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        thread = self._thread
        if thread is not None and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=self._interval_sec + 1.0)
        self._thread = None

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled
        if enabled:
            self.start()
        else:
            self.stop()

    def _run(self) -> None:
        while not self._stop_event.wait(self._interval_sec):
            if self.enabled:
                self.nudge()
