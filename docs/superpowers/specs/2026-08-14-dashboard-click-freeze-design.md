# Dashboard click freeze (All monitoring / header reports)

**Date:** 2026-08-14  
**Status:** Approved for implementation  
**App version target:** 1.6.173  
**Depends on:** Connection Dashboard 1.6.172 (in-place Search; Health register off UI thread on load)  
**Approach:** Never decrypt or register the SSH fleet on the Tk UI thread when the operator clicks a dashboard control; share one in-flight register; All monitoring on flips card switches immediately  
**Base branch:** `main` (1.6.172)

## Problem

After login the dashboard is slow while ~38 GlowCards paint. Clicking **All monitoring on** or **Storage Inventory** (and the other header reports) then makes the window go **white / Not Responding**. Nothing turns on.

Those clicks call `ensure_health_dashboard_registered` on the UI thread *before* any widget update or browser open. That decrypts every SSH password and re-registers every card. Right after login it overlaps the 1.6.172 background register, so Windows times the UI out. Storage Inventory then registers a **second** time in a worker via `sync_from_app()`.

**All monitoring on** also uses `set_all_monitor_enabled(all_cards=True)`, which only toggles cards already in the Health server. If register has not finished, flags do not stick. Select All → **Monitor Checked** works because it waits until register is done, then turns each card on immediately.

Several header openers also call `resolve_ssh_metrics_auth` for every SSH card on the UI thread before starting their worker.

## Goals

- Header report buttons (Storage Inventory, Health Dashboard, Capacity, and the rest) must set a status line and return; decrypt/register/open browser on a worker.
- **All monitoring on** must flip every SSH card’s Monitor switch immediately; persist flags and start SSH refresh on a worker.
- Overlapping `ensure_health_dashboard_registered` calls must wait for the in-flight register instead of decrypting the fleet again.
- Dashboard click handlers must not call `ensure_health_dashboard_registered` or fleet-wide `resolve_ssh_metrics_auth` on the Tk main thread.
- Bump `APP_VERSION` to **1.6.173**.

## Non-goals

- Virtualized / recycled card list, or rewriting GlowCard internals.
- Changing Monitor on/off meaning, SSH command suites, or browser report page behavior.
- Speeding up the first GlowCard paint (destroy/recreate on `refresh_cards` stays as 1.6.172).
- Debouncing Search (already filtered in place).

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Header reports | Status immediately; register/sync + open browser on a worker |
| All monitoring on | Flip card Monitor switches immediately; save flags + SSH in the background |
| Overlapping register | Wait for the in-flight login register; do not decrypt the fleet a second time |
| Monitor / SSH / SI page | Unchanged |

## Behavior

### Shared register

`ensure_health_dashboard_registered` is the single decrypt/register path. If a call is already in progress, later callers wait for it and reuse that result (no second fleet decrypt). Failures still log; they must not freeze the dashboard.

Startup `after(200, _register_health_cards_main_thread)` stays the first register, still on a daemon thread.

### Header reports and Excel exports

Methods such as `_open_storage_inventory`, `_open_health_dashboard_all`, `_open_capacity_report_all`, and the other header/export openers that today call `ensure_health_dashboard_registered` on the UI thread:

1. Set the existing status text (and `update_idletasks` if they already do).
2. Start a daemon worker.
3. On the worker: register/sync (existing `ensure_health_dashboard_registered` / `sync_from_app` / `open_*_for_cards`), then open the browser or run the export.
4. Marshal status (and URL) back with `self.after(0, ...)`.

`filedialog.asksaveasfilename` stays on the UI thread. After the operator picks a path, register/export runs on the worker.

Do not build a full `HealthDashboardEntry` list with `resolve_ssh_metrics_auth` on the UI thread. Do that on the worker, or let `ensure_health_dashboard_registered` / `sync_from_app` populate the Health server and then open.

### All monitoring on

`_toggle_all_monitoring` when turning **on**:

1. Update `self._monitor_states` and each SSH `GlowCard.set_monitor_enabled(True)` on the UI thread (same visual as Monitor Checked).
2. Set status **All monitoring on — refreshing stats for SSH cards...**
3. Worker: wait for/call `ensure_health_dashboard_registered`, then persist flags (`set_all_monitor_enabled(True)` after cards are registered, or per-card `set_card_monitor_enabled` like Monitor Checked).
4. Start SSH refresh the same way Monitor Checked does (`_probe_card_ssh_status` + `_fetch_ssh_stats_worker` per SSH card). Do not run `_fetch_all_ssh_stats` on the UI thread (that decrypts `_ssh_stats_prereq` for every card before workers start).

When turning **off**: flip switches off immediately; persist `False` and clear card stats on a worker. Do not decrypt the fleet on the UI thread.

### Monitor Checked / per-card Monitor

`_set_checked_monitoring` and `_on_card_monitor_toggle` must not call `ensure_health_dashboard_registered` on the UI thread. Persist `set_card_monitor_enabled` and start/stop SSH as today; register happens via the shared in-flight/startup path (or a worker if a click happens before startup register finishes).

## Architecture

| Unit | Responsibility |
|------|----------------|
| `launchpad/monitor.py` | Single-flight `ensure_health_dashboard_registered` (wait + reuse in-flight result) |
| `launchpad/ui/dashboard_view.py` | Header/export/All-monitoring/Monitor click paths: no fleet decrypt/register on Tk thread |
| Tests + version pins | Source markers: those click methods do not call `ensure_health_dashboard_registered`; single-flight register; **1.6.173** |

## Testing

- Click handlers (`_open_storage_inventory`, `_toggle_all_monitoring`, other header/export openers, `_set_checked_monitoring`, `_on_card_monitor_toggle`) must start a `threading.Thread` (or return) before any `ensure_health_dashboard_registered` / fleet `resolve_ssh_metrics_auth`. Those calls may live in a nested worker in the same method.
- `_toggle_all_monitoring` updates widgets / `_monitor_states` before starting a thread; does not call `_fetch_all_ssh_stats`.
- `ensure_health_dashboard_registered` has a single-flight lock/event (overlapping calls do not each decrypt).
- Version pins `1.6.173`.
