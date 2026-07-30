# Snapshot Schedule — Mark Planned Day Complete

**Date:** 2026-07-30  
**Status:** Approved for implementation  
**App version target:** 1.6.83  
**Depends on:** Snapshot Schedule overrides (`snapshot_schedule_overrides`), calendar UI  
**Approach:** Persist `completed_dates` on each card override (Approach 1)  
**Base branch:** `feature/contingency-groups`  
**Sequencing:** Implement after Feature A (CG summary Flash time + Progress, v1.6.82)

## Problem

Operators use Snapshot Schedule as a planning board. After they finish a site’s snaps for a planned day, the calendar still looks the same as “not done yet.” They want to mark that day complete so it turns solid green and stays that way until the next cycle.

## Goals

- Click a **planned** calendar day to mark it **done** → **solid green**.
- Persist per Health Card in overrides as `completed_dates: ["YYYY-MM-DD", ...]`.
- Toggle off (un-complete) by clicking again.
- Auto-prune completed dates that are no longer in the site’s current planned set (“until next cycle”).
- Bump `APP_VERSION` to **1.6.83**.

## Non-goals

- Detecting completion from the storage array automatically.
- Marking held sites or non-planned days.
- Excel color formatting for completed days in v1 (persist for UI only; Excel follow-up optional).
- CG summary Flash time / Progress (Feature A).

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| What to mark | Planned calendar **day** (not whole-card only) |
| Appearance | Solid green when complete |
| Persistence | Until next cycle (prune when date leaves planned set) |
| Storage | `completed_dates` on existing per-card override object |

## Behavior

### UI

- Overall and per-site calendars: planned days are clickable to toggle complete.
- Completed + planned → solid green CSS (distinct from scheduled green→amber gradient and orange held).
- Legend/hint text updated to mention completed days.
- Held / empty plan: no complete action.

### Data

Override object gains:

```json
{
  "mode": "auto",
  "held": false,
  "completed_dates": ["2026-07-30"]
}
```

- Normalize: unique sorted `YYYY-MM-DD` strings; drop invalid.
- On load/save/render: **prune** any completed date not in that card’s currently generated planned occurrence dates.

### Persist

- Same GET/PUT `/api/snapshot-schedule-overrides` path; unlock required for durable DB write (existing behavior).

## Architecture

| File | Responsibility |
|------|----------------|
| `launchpad/snapshot_schedule_overrides.py` | Normalize `completed_dates`; optional `prune_completed_dates(completed, planned)` |
| `launchpad/snapshot_schedule.py` | Toggle UI, solid-green style, wire prune into render/save |
| `launchpad/config.py` | `1.6.83` |
| Tests | Normalize, prune, page markers, version |

## Tests

- Normalize keeps valid dates, drops junk, dedupes.
- Prune removes dates absent from planned set; keeps intersection.
- Page exposes completed CSS/toggle and `completed_dates` in override JS payload.
- Version `1.6.83`.

## Follow-up (out of scope)

1. Excel green / “Completed” column.
2. Bulk “mark all due today.”
3. Array-verified snap completion.
