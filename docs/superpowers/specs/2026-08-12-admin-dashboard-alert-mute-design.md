# Admin + dashboard critical alert mute (shared Alarm off)

**Date:** 2026-08-12  
**Status:** Approved for implementation  
**App version target:** 1.6.160  
**Depends on:** Critical health alert popups / art overlays — `health_alert_state.set_alarm`, `list_popup_alerts`, `/api/health-alerts/alarm`  
**Approach:** Wire Admin Connections + dashboard monitor-row controls to existing `alarm_muted` (same as popup Alarm off)  
**Base branch:** `main` (tip at 1.6.159)  
**Follow-up project:** Dell Report HPE tab/field population (separate spec after this ships)

## Problem

Critical alerts popup often. Operators can already use **Alarm off** on the popup, but there is no always-visible dashboard control and no Admin Connections control, so muting cards is easy to miss.

## Goals

- Expose the **same** per-card mute as today’s popup **Alarm off** in:
  - **Admin → Connections** card form (Alerts On/Off)
  - **Connection Dashboard** card monitor row (always-visible Alerts on/off)
- When muted: no critical dialog popups, no health-alert card overlays, no beep for that card until unmuted.
- Keep popup **Alarm off/on** working and in sync with Admin + dashboard.
- Bump `APP_VERSION` to **1.6.160**.

## Non-goals

- New mute store or card DB column separate from `health_alert_state.alarm_muted`.
- Changing Suppress / Snooze / fingerprint acknowledge rules.
- Email / SMS notifications.
- Dell Report HPE field fix (Project 2).
- Turning off Active Issues listing on Health Dashboard (mute only gates popups per `list_popup_alerts`).

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Scope | Alerts first; Dell HPE second |
| Surfaces | Admin Connections **and** dashboard monitor row |
| Semantics | Same as existing **Alarm off** (`alarm_muted`) |
| Dashboard placement | Always-visible Alerts on/off on monitor row |

## Behavior

### Mute semantics (unchanged engine)

1. `set_alarm(state, card_id, muted=True)` sets `alarm_muted[card_id]`.
2. `list_popup_alerts` skips muted cards (no popup candidates → no dialog, overlay, or beep).
3. Unmute clears that card’s mute entry / sets muted=False.

### Admin Connections

1. On the card create/edit form, add an **Alerts** control: On (default when not muted) / Off (muted).
2. When opening a card for edit, load mute status from `health_alert_state` for that `card_id`.
3. Changing the control (or saving the form, if implemented as part of save) persists via the same path as dashboard alarm toggle (`set_alarm` + save setting). Prefer immediate toggle on change for parity with dashboard, or persist on Save — **implementation preference:** toggle persists immediately like the dashboard API, so operators don’t need a full card Save to mute.
4. New cards: Alerts On until explicitly muted.

### Dashboard monitor row

1. Always show an **Alerts on** / **Alerts off** (or equivalent) control on the monitor row when the card supports health monitoring.
2. Reflect server `alarm_muted` from the health-alert poll / card payload.
3. Clicking toggles via existing `/api/health-alerts/alarm` (or local `set_alarm` + persist used by desktop today).
4. When muted, keep the existing muted hint style if already present (“Alarm muted — no health popups”); align label copy with Admin (“Alerts off”).

### Popup / overlay

- Existing **Alarm off/on** buttons remain.
- After any surface toggles mute, the next poll/refresh updates the other surfaces.

## Architecture

| Unit | Responsibility |
|------|----------------|
| `health_alert_state.set_alarm` / `list_popup_alerts` | Unchanged mute engine |
| `ui/admin_view.py` | Alerts On/Off on Connections card form; load/save mute |
| `ui/card_widget.py` + `ui/dashboard_view.py` | Always-visible monitor-row Alerts control; sync from poll |
| `health_server.py` `/api/health-alerts/alarm` | Already exists; reuse for Health Dashboard if needed |
| `config.APP_VERSION` | `1.6.160` |

## Testing

- Muting via Admin prevents popup candidates for that `card_id` (state / API contract).
- Muting via dashboard monitor-row control sets the same `alarm_muted` entry as popup Alarm off.
- Unmute restores popup eligibility when critical issues remain.
- Page/UI contracts: Admin form exposes Alerts control; card widget exposes monitor-row alerts control strings.
- Version pins expect `1.6.160`.

## Out of scope follow-ups

- Dell Report HPE capacity/fields (Project 2).
- Per-issue Suppress from Admin.
- Global “mute all cards” toolbar.
