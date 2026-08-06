# Mouse Jiggler Idle Reset — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the desktop mouse jiggler so Windows idle/lock policies reset while LaunchPad is running with jiggler On, using `SetThreadExecutionState` + `SendInput` instead of `SetCursorPos` alone.

**Architecture:** Keep `MouseJiggler` timer/UI. Replace `_default_nudge` with injectable Win32 helpers (`request_keep_awake`, `clear_keep_awake`, `send_relative_mouse_nudge`). On enable: keep-awake + nudge immediately, then every ~50s. On disable/stop: clear keep-awake.

**Tech Stack:** Python `ctypes` / Win32 user32+kernel32, existing CustomTkinter toggle, pytest.

**Spec:** `docs/superpowers/specs/2026-08-06-mouse-jiggler-idle-reset-design.md`

## Global Constraints

- Branch tip: `feature/hpe-capacity-parse` (APP_VERSION starts at `1.6.123`; bump one patch when this feature ships, or share a combined bump with Site Lookup if both ship in one release).
- Windows only for keep-awake / SendInput; non-Windows remains no-op.
- Do not change setting key `mouse_jiggler_enabled` or default Off.
- Interval stays `DEFAULT_JIGGLE_INTERVAL_SEC = 50` unless tests prove a shorter interval is required.
- Windows PowerShell commits (here-string), no bash heredoc.
- Commit at each task’s commit step.

## File structure

| File | Responsibility |
|------|----------------|
| `launchpad/mouse_jiggler.py` | Keep-awake + SendInput nudge; clear on disable |
| `tests/test_mouse_jiggler.py` | Unit coverage for enable/disable/clear/nudge helpers |
| `launchpad/config.py` | Version bump when shipping this alone |

---

### Task 1: Keep-awake helpers + clear on disable + immediate nudge

**Files:**
- Modify: `launchpad/mouse_jiggler.py`
- Modify: `tests/test_mouse_jiggler.py`

**Interfaces:**
- Consumes: existing `MouseJiggler`, `setting_to_enabled`, `SETTING_MOUSE_JIGGLER`
- Produces:
  - `request_keep_awake() -> None`
  - `clear_keep_awake() -> None`
  - `send_relative_mouse_nudge() -> None` (Win32 `SendInput`; no-op elsewhere)
  - `MouseJiggler.__init__(..., keep_awake_fn=None, clear_keep_awake_fn=None)` optional injectables for tests
  - `set_enabled(True)` → start + immediate `keep_awake` + `nudge`
  - `set_enabled(False)` / `stop()` → clear keep-awake

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_mouse_jiggler.py` (keep existing tests):

```python
def test_set_enabled_true_requests_keep_awake_and_nudges_immediately():
    nudges = []
    keeps = []
    clears = []
    j = MouseJiggler(
        interval_sec=60,
        nudge_fn=lambda: nudges.append(1),
        keep_awake_fn=lambda: keeps.append(1),
        clear_keep_awake_fn=lambda: clears.append(1),
    )
    j.set_enabled(True)
    assert keeps == [1]
    assert nudges == [1]
    j.set_enabled(False)
    assert clears == [1]
    j.stop()


def test_stop_clears_keep_awake_even_if_already_disabled():
    clears = []
    j = MouseJiggler(
        interval_sec=60,
        nudge_fn=lambda: None,
        keep_awake_fn=lambda: None,
        clear_keep_awake_fn=lambda: clears.append(1),
    )
    j.stop()
    assert clears == [1]


def test_default_windows_nudge_calls_keep_awake_and_sendinput(monkeypatch):
    from launchpad import mouse_jiggler as mj

    calls = []
    monkeypatch.setattr(mj, "request_keep_awake", lambda: calls.append("keep"))
    monkeypatch.setattr(mj, "send_relative_mouse_nudge", lambda: calls.append("send"))
    mj._default_nudge()
    assert calls == ["keep", "send"]
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
pytest tests/test_mouse_jiggler.py -v
```

Expected: FAIL — `MouseJiggler` unexpected keyword `keep_awake_fn` and/or missing helpers.

- [ ] **Step 3: Implement Win32 helpers and wire `MouseJiggler`**

Replace/extend `launchpad/mouse_jiggler.py` so it matches this shape (preserve module docstring and setting helpers):

```python
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
```

Note: if `nudge_fn` is a custom test lambda that does **not** call keep-awake, `set_enabled(True)` still calls `keep_awake_fn` separately (as in the test). `_default_nudge` also calls `request_keep_awake` so timer ticks keep refreshing execution state.

- [ ] **Step 4: Run tests to verify they pass**

```powershell
pytest tests/test_mouse_jiggler.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```powershell
git add launchpad/mouse_jiggler.py tests/test_mouse_jiggler.py
git commit -m @"
Fix mouse jiggler so Windows idle lock resets via execution state and SendInput.
"@
```

---

### Task 2: Version bump (if shipping jiggler alone)

**Files:**
- Modify: `launchpad/config.py`

**Interfaces:**
- Consumes: current `APP_VERSION`
- Produces: next patch string (e.g. `1.6.124` if tip is `1.6.123`)

Skip this task if Site Lookup ships in the same release and owns the single version bump.

- [ ] **Step 1: Bump version**

In `launchpad/config.py`, set `APP_VERSION` to the next patch after current tip.

- [ ] **Step 2: Smoke import**

```powershell
python -c "from launchpad.config import APP_VERSION; from launchpad.mouse_jiggler import request_keep_awake, clear_keep_awake, send_relative_mouse_nudge; print(APP_VERSION)"
```

Expected: prints new version.

- [ ] **Step 3: Commit**

```powershell
git add launchpad/config.py
git commit -m @"
Bump version after mouse jiggler idle-reset fix.
"@
```

---

## Spec coverage checklist

| Spec requirement | Task |
|------------------|------|
| `SetThreadExecutionState` on nudge | Task 1 |
| `SendInput` mouse move | Task 1 |
| Clear on Off / stop | Task 1 |
| Immediate nudge on On | Task 1 |
| Keep UI / setting / ~50s | Task 1 (unchanged) |
| Non-Windows no-op | Task 1 |
| Version bump | Task 2 (or shared) |
