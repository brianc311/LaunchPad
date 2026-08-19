# Connection dashboard — Alert popups toggle

**Date:** 2026-08-19  
**Status:** Approved for implementation (pending user review of this file)  
**App version target:** 1.6.185  
**Depends on:** Desktop health-alert dialog (`HealthAlertDialog`), card overlays, `db.get_setting` / `set_setting` (same pattern as Mouse jiggler)  
**Approach:** One persisted dashboard switch. Off skips the floating critical window and its beep. Card overlays stay. Browser Health Dashboard unchanged.

## Problem

Critical health alert windows jump in front of LaunchPad while the connection dashboard refreshes. That blocks the operator and makes refresh feel slower. Admin already has a per-card **Alerts** switch; there is no dashboard-wide way to keep the popups off without muting every site in Admin (which also affects Health Dashboard).

## Goals

- Connection dashboard has an **Alert popups** switch in the same toggle row as Compact cards / All monitoring / Mouse jiggler.
- Default **On** (today’s behavior). Missing setting means On.
- **Off:** do not open the floating critical window; do not play the popup beep. Warning art on the card stays. Polling and overlays still run.
- Setting is saved (like Mouse jiggler) and survives LaunchPad restart.
- Admin per-card Alerts On/Off still works independently.
- Bump `APP_VERSION` to **1.6.185**.

## Non-goals

- Changing Health Dashboard browser modals or the browser “show alerts” checkbox.
- Hiding on-card health-alert overlays.
- Changing which issues are collected, acknowledged, snoozed, or shown in Health Dashboard Active Issues.
- Muting all sites via `set_alarm` / Admin Alerts.
- Changing Monitor SSH, stats collection, or Stats Snapshot windows.

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| What to hide | Floating desktop critical window only |
| On-card overlay | Stays |
| Health Dashboard (browser) | Unchanged |
| Persistence | Saved setting; survives restart |
| Default | On |
| Placement | Toggle row after Mouse jiggler, before the selection count |

## Behavior

Persisted key: `alert_popups_enabled` with values `"true"` / `"false"`. Empty or missing → **On**.

When the switch is **On**:

- Unchanged: poll health alerts, beep on new fingerprints, queue and show `HealthAlertDialog`, keep card overlays.

When the switch is **Off**:

- Still poll and still update card overlays and Alarm-muted indicators.
- Do not call `play_health_alert_beep`.
- Do not open `HealthAlertDialog`. If one is already open, close it when the operator turns the switch Off.
- Turning the switch back **On** allows the next poll to show a window again (same rules as today).

Admin per-card mute (`alarm_muted`) still suppresses that site’s popup and overlay as it does today. The dashboard switch is an extra gate only on the floating window and beep.

## Files (expected)

| File | Change |
|------|--------|
| `launchpad/ui/dashboard_view.py` | Switch, load/save setting, skip dialog + beep when Off, close open dialog on Off |
| `launchpad/config.py` | `APP_VERSION` **1.6.185** |
| Version pin tests | Same as prior bumps |
| Tests | Setting default On; Off skips dialog/beep; overlays still requested |

## Test plan

- Fresh DB / missing setting: switch shows On; a critical still pops the window.
- Turn Off: no new floating window; no beep; overlay still appears on the card.
- Restart LaunchPad: switch still Off.
- Turn On: next eligible critical can pop the window again.
- Admin Alerts Off for one card: that site stays muted even when dashboard Alert popups is On.
- Health Dashboard in the browser still shows its own critical modal.
