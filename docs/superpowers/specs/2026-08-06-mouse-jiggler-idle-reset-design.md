# Mouse Jiggler — Reset Windows idle (execution state + SendInput)

**Date:** 2026-08-06  
**Status:** Approved (operator); awaiting written-spec review  
**App version target:** next patch after tip (1.6.123+)  
**Extends / corrects:** `docs/superpowers/specs/2026-07-24-jiggler-site-dropdown-design.md` (jiggler section only — Site dropdown / Health Excel unchanged)  
**Depends on:** Existing `launchpad/mouse_jiggler.py`, desktop dashboard toggle, `SETTING_MOUSE_JIGGLER`  
**Approach:** Keep UI/interval; fix Windows nudge so idle lock resets via `SetThreadExecutionState` + `SendInput` (not `SetCursorPos` alone)

## Problem

LaunchPad’s mouse jiggler is On, but the PC still locks. The current Windows nudge only calls `GetCursorPos` / `SetCursorPos` (±1 px). Many Windows idle and lock policies **do not treat `SetCursorPos` as user input**, so the session idle timer keeps running.

## Goals

- When jiggler is **On** and LaunchPad is running, periodically reset system/display idle so the session does not lock under normal Windows power/lock policies.
- On each nudge (Windows):
  1. `SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED)`
  2. A tiny **`SendInput`** mouse move (and restore), not only `SetCursorPos`
- When jiggler is turned **Off** (or the jiggler thread stops cleanly): clear the execution-state request (`ES_CONTINUOUS` alone / clear continuous flags) so normal idle resumes.
- Keep existing desktop toggle, persistence (`mouse_jiggler_enabled`), default Off, and ~50s interval (may shorten slightly if needed; do not spam).
- Non-Windows: keep no-op nudge (unchanged).

## Non-goals (v1)

- Preventing lock when LaunchPad is closed or jiggler is Off.
- A separate Windows service / tray-only agent outside LaunchPad.
- Replacing the desktop toggle or Health indicator UX from the earlier jiggler delivery.
- Guaranteeing defeat of every MDM / third-party kiosk lock that ignores execution state and synthetic input (document: best-effort using supported Win32 APIs).

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Primary fix | `SetThreadExecutionState` **and** `SendInput` mouse nudge |
| Keep | Existing On/Off UI + ~50s interval |
| Scope | While LaunchPad process is running and jiggler On |
| Off behavior | Clear execution state; stop timer |

## Behavior

### When enabled

- Existing `MouseJiggler` loop continues on `DEFAULT_JIGGLE_INTERVAL_SEC` (~50).
- Each tick calls the Windows nudge implementation:
  - Call `SetThreadExecutionState` with continuous + system + display required.
  - Inject a 1px (or equivalent) relative mouse move via `SendInput`, then move back (or a single small relative move that does not visibly disturb the user).
  - Must not steal focus or open menus.
- When switching On: call execution state (and a nudge) **immediately**, then continue on the interval, so idle does not win before the first timer tick.

### When disabled / stopped

- Stop the timer thread as today.
- Call `SetThreadExecutionState(ES_CONTINUOUS)` (clear display/system required) so the OS returns to normal idle accounting.
- Idempotent: multiple Off / stop calls are safe.

### Persistence / UI

- No change required to setting key or default Off.
- Dashboard switch remains the operator control.

## Architecture

| Piece | Responsibility |
|-------|----------------|
| `launchpad/mouse_jiggler.py` | Replace `_default_nudge` Win32 path; add clear-on-disable hook in `set_enabled(False)` / `stop` |
| Tests | Mockable nudge / execution-state helpers; Off clears state; non-win32 no-op |
| Desktop wiring | Unchanged aside from any import of new clear helper if needed |

### Constants (conceptual)

```text
ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002
```

Prefer wrapping Win32 calls behind small functions so unit tests can inject fakes without loading real `ctypes.windll` behavior in CI.

## Testing

- Unit: enabling starts loop; disabling stops and invokes clear-execution-state helper; Windows nudge function calls both execution-state and SendInput helpers (mocked).
- Regression: setting string `true` / other still maps correctly; interval default unchanged unless intentionally adjusted.
- Manual: jiggler On → leave idle past prior lock time → session stays unlocked while LaunchPad runs; Off → idle lock returns as before.

## Success criteria

1. With jiggler On, Windows no longer locks solely because `SetCursorPos` was ignored.
2. Turning jiggler Off clears the keep-awake request.
3. Closing LaunchPad (process exit) ends keep-awake with the process (daemon thread / process lifetime).

## Out of scope follow-ups

- Linux/macOS keep-awake equivalents.
- Configurable interval in the UI.
