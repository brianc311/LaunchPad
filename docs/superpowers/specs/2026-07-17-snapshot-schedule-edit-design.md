# Snapshot Schedule Editing — Design

**Date:** 2026-07-17  
**Status:** Implemented  
**App version target:** 1.6.18 (or next bump after current)

## Problem

The Snapshot Schedule page computes frequency, interval, and start dates from pool used % and a threshold. Operators need to override that plan per site: set interval/start/time, hold a site, and place one-off date/times on the calendar — without pushing jobs to the storage array.

## Goals

- Per-site **Auto** vs **Custom** schedule mode.
- In Custom: recurring rule (interval days, start date, time of day) plus optional one-off events (date + time + optional label).
- **Hold** available in Auto and Custom (freeze calendar without full custom setup).
- Persist overrides in LaunchPad DB when unlocked (same pattern as notes); local cache when locked.
- Page calendars and Excel export use the same override data.
- Remain planning-only: LaunchPad does not create snapshots on devices.

## Non-goals

- SSH / CLI creation or update of FlashSystem / Storwize / SVC / Vultr snapshot policies.
- Shared multi-user realtime collaboration beyond single LaunchPad DB.
- Timezone conversion UI (times are local wall-clock as entered).

## Data model

Setting key: `snapshot_schedule_overrides`  
Value: JSON object mapping `card_id` (string) → override object.

```json
{
  "card-uuid": {
    "mode": "auto",
    "held": false,
    "interval_days": 7,
    "start_date": "2026-07-20",
    "time": "02:00",
    "one_offs": [
      { "date": "2026-08-01", "time": "14:30", "label": "Change window" }
    ]
  }
}
```

| Field | Type | Notes |
|-------|------|--------|
| `mode` | `"auto"` \| `"custom"` | Default missing key → treat as auto |
| `held` | boolean | If true, no calendar dates (HOLD) |
| `interval_days` | int ≥ 2 | Used when `mode === "custom"` and not held |
| `start_date` | `YYYY-MM-DD` | Used when custom |
| `time` | `HH:MM` (24h) | Recurring run time; default `02:00` when entering Custom |
| `one_offs` | array | Only applied when `mode === "custom"` and not held |

**Mode switch behavior:** Switching Custom → Auto does **not** delete the override object; `mode` becomes `auto` and dormant custom fields are kept so switching back restores them. An explicit “Reset to auto defaults” may clear the card’s override entry.

**Hold behavior:**
- Auto + held: badge HOLD; calendar empty; capacity still shown.
- Custom + held: same; custom fields retained for when Hold is cleared.

## UI (Snapshot Schedule page)

On each site card:

1. **Mode** control: Auto | Custom.
2. **Hold** checkbox (both modes).
3. When Custom (and not held): editors for interval days, start date, time; **Add one-off** (date, time, optional label); list with remove.
4. Badges: `CUSTOM`, `HOLD` as applicable.
5. Notes textarea unchanged (separate `snapshot_schedule_notes`).

Calendars:

- Auto (not held): current day-marker behavior (no time).
- Custom (not held): recurring dates from start + interval at `time`; one-offs overlaid with distinct style; tooltips show time (and label if set).
- Overall month view includes custom times in tooltips.

Validation: block save on invalid date/time; show inline error on the card.

## APIs

Mirror notes endpoints:

| Method | Path | Behavior |
|--------|------|----------|
| GET | `/api/snapshot-schedule-overrides` | `{ overrides, persisted: true }` when unlocked; empty / not persisted when locked |
| POST | `/api/snapshot-schedule-overrides` | Body: `{ card_id, override }` or `{ overrides: { ... } }` |

- Wired via existing settings backend when LaunchPad is unlocked.
- Debounced client POST (~400ms), with `localStorage` key e.g. `launchpad.snapshotSchedule.overrides` as cache/fallback.

## Schedule computation

Keep JS (`snapshot_schedule.py` embedded) and Python (`snapshot_schedule_export.py`) aligned:

1. Compute capacity / auto row as today.
2. Apply override:
   - If `held` → status HOLD, no dates.
   - Else if `mode === "custom"` → use override interval/start/time + one_offs for calendar and Frequency/Interval/Starts.
   - Else → auto math unchanged.

## Excel export

`/api/snapshot-schedule-export` and desktop export:

- Apply same overrides.
- Columns: keep existing; add **Mode**, **Time**, **Held**, **One-offs** (semicolon-separated `date time label` summaries).
- Frequency / Interval Days / Starts reflect effective schedule after overrides.

## Files to touch (implementation)

- `launchpad/snapshot_schedule.py` — UI + client logic
- `launchpad/snapshot_schedule_export.py` — row builder + headers
- `launchpad/health_server.py` — GET/POST overrides + export integration
- `launchpad/app.py` — settings backend wiring if needed (same as notes)
- `launchpad/config.py` — version bump

## Testing (manual)

1. Unlock LaunchPad → open Snapshot Schedule → switch a site to Custom → set interval/start/time → calendar updates → reopen page → values persist.
2. Add/remove one-offs; confirm distinct calendar markers and Excel One-offs column.
3. Hold on Auto and Custom; calendars empty; Excel shows Held.
4. Custom → Auto → Custom again restores previous custom fields.
5. Locked LaunchPad: edits stay local; unlocked: merge to DB.
6. Footer still states planning-only (no auto snapshot creation).

## Out of scope / later

- Click-day-on-calendar to add one-off (optional enhancement; v1 uses form controls).
- Per-site timezone.
- Pushing schedules to devices.
