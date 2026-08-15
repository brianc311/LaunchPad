# Dashboard UI freeze (search / refresh)

**Date:** 2026-08-14  
**Status:** Approved for implementation  
**App version target:** 1.6.172  
**Depends on:** Connection Dashboard `refresh_cards` / Health server register (current `main` 1.6.171)  
**Approach:** Filter search in place (do not rebuild 38 cards per keystroke); do not decrypt/register all SSH cards on the UI thread during every grid rebuild; keep Refresh Stats SSH-only for Monitor-on cards  
**Base branch:** `main` (1.6.171)

## Problem

LaunchPad’s Connection Dashboard goes **(Not Responding)** when the operator types in Search, changes category, or otherwise triggers a full card rebuild. Windows grays the window because the UI thread destroys and recreates every CustomTkinter card (~38), then decrypts SSH credentials and re-registers them with the Health server. That happens even when **no card has Monitor on**. Footer **Refreshing SSH card stats...** is a separate path (Refresh Stats with at least one Monitor-on card).

## Goals

- Typing in Search must not rebuild the card grid or re-register Health cards.
- Full `refresh_cards` must not call `ensure_health_dashboard_registered` on the UI thread.
- Health-card registration still happens once after dashboard load, off the UI thread.
- Refresh Stats still SSHs only Monitor-on cards; status **Refreshing SSH card stats...** only when that fetch actually starts.
- Bump `APP_VERSION` to **1.6.172**.

## Non-goals

- Virtualized / recycled card list.
- Debouncing a full rebuild as the search solution (filter in place instead).
- Changing Monitor semantics, SSH command suites, or browser report progress bars.
- Rewriting GlowCard internals.

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Search | Filter existing widgets in place |
| Health register | Background thread after load; not on every `refresh_cards` |
| Refresh Stats | Unchanged gate: Monitor-on only |

## Behavior

### Search

`<KeyRelease>` on Search must **not** call `refresh_cards()`. Apply existing `filter_dashboard_cards` to the already-built widgets: `grid` matches in 4 columns, `grid_remove` non-matches. Rebuild the array rail from the filtered set. Update the selection count. Do not destroy widgets, decrypt keys, or touch `ensure_health_dashboard_registered`.

Empty query shows all built cards (current category). Category change still uses `refresh_cards()` (rarer).

### Health register

`_load_monitor_states` (called from `refresh_cards`) only reads `get_monitor_states()`. It must not call `ensure_health_dashboard_registered`.

The existing `after(200, _register_health_cards_main_thread)` hook keeps running after first paint, but the decrypt/register work runs on a **daemon thread**. UI updates (log / status) marshal back with `after(0, ...)`. Failures stay logged; they must not freeze the dashboard.

Opening Health Dashboard / Capacity / other reports still registers as they do today if those paths already call `ensure_health_dashboard_registered`.

### Refresh Stats

Keep the Monitor-on fetchable list. If none: existing **No sites monitoring...** (or credentials message). If some: **Refreshing SSH card stats...** then background SSH as today. Do not SSH Monitor-off cards.

## Architecture

| Unit | Responsibility |
|------|----------------|
| `launchpad/ui/dashboard_view.py` | In-place search filter; `_load_monitor_states` without register; threaded startup register |
| `launchpad/dashboard_array_rail.py` | Reuse `filter_dashboard_cards` (no match-rule change) |
| `launchpad/monitor.py` | Unchanged register helper; called from worker, not from every refresh |
| Tests + version pins | Search does not call `refresh_cards`; register not in `_load_monitor_states`; **1.6.172** |

## Testing

- Dashboard source: Search `KeyRelease` handler is not `refresh_cards`; a filter helper exists; `_load_monitor_states` does not contain `ensure_health_dashboard_registered`.
- Startup register still invoked (thread target / `ensure_health_dashboard_registered` still referenced from the register hook).
- Refresh Stats still skips Monitor-off (existing messages stay).
- Version pins `1.6.172`.
