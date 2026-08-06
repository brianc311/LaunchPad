"""Optional mouse jiggler to prevent idle sleep while LaunchPad is running."""

from __future__ import annotations

import ctypes
import sys
import threading
from typing import Callable

SETTING_MOUSE_JIGGLER = "mouse_jiggler_enabled"
DEFAULT_JIGGLE_INTERVAL_SEC = 50

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002


def setting_to_enabled(value: str) -> bool:
    """Return True only when the persisted setting is the string ``true``."""
    return value == "true"


def request_keep_awake() -> None:
    if sys.platform != "win32":
        return
    ctypes.windll.kernel32.SetThreadExecutionState(
        ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED
    )


def clear_keep_awake() -> None:
    if sys.platform != "win32":
        return
    ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)


def send_relative_mouse_nudge() -> None:
    """Inject a tiny relative mouse move via SendInput (resets idle on Windows)."""
    if sys.platform != "win32":
        return

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [
            ("dx", ctypes.c_long),
            ("dy", ctypes.c_long),
            ("mouseData", ctypes.c_ulong),
            ("dwFlags", ctypes.c_ulong),
            ("time", ctypes.c_ulong),
            ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
        ]

    class INPUT(ctypes.Structure):
        class _I(ctypes.Union):
            _fields_ = [("mi", MOUSEINPUT)]

        _anonymous_ = ("i",)
        _fields_ = [("type", ctypes.c_ulong), ("i", _I)]

    INPUT_MOUSE = 0
    MOUSEEVENTF_MOVE = 0x0001
    extra = ctypes.c_ulong(0)

    def _move(dx: int, dy: int) -> None:
        inp = INPUT()
        inp.type = INPUT_MOUSE
        inp.mi = MOUSEINPUT(dx, dy, 0, MOUSEEVENTF_MOVE, 0, ctypes.pointer(extra))
        ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))

    _move(1, 0)
    _move(-1, 0)


def _default_nudge() -> None:
    request_keep_awake()
    send_relative_mouse_nudge()


class MouseJiggler:
    """Periodically nudge the cursor while enabled."""

    def __init__(
        self,
        *,
        interval_sec: float = DEFAULT_JIGGLE_INTERVAL_SEC,
        nudge_fn: Callable[[], None] | None = None,
        keep_awake_fn: Callable[[], None] | None = None,
        clear_keep_awake_fn: Callable[[], None] | None = None,
    ) -> None:
        self._interval_sec = interval_sec
        self._nudge_fn = nudge_fn or _default_nudge
        self._keep_awake_fn = keep_awake_fn or request_keep_awake
        self._clear_keep_awake_fn = clear_keep_awake_fn or clear_keep_awake
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
        self._clear_keep_awake_fn()

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled
        if enabled:
            self.start()
            self._keep_awake_fn()
            self.nudge()
        else:
            self.stop()

    def _run(self) -> None:
        while not self._stop_event.wait(self._interval_sec):
            if self.enabled:
                self.nudge()
