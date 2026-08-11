# Dell array snapshots and Forecast projection

**Date:** 2026-08-11  
**Status:** Approved for implementation  
**App version target:** 1.6.152  
**Depends on:** Dell Report collect/export (`dell_report_export.py`, `dell_report_snapshots.py`, `dell_report_capacity.py`), Capacity layers (`capacity_summary` vs pools vs raw)  
**Approach:** Array-only snapshots + gated growth + project IBM/HP Forecast (Approach 1)  
**Base branch:** `main` (tip at 1.6.151)

## Problem

Dell Weekly Growth and Forecast are often wrong for two independent reasons:

1. **Mixed layers.** Weekly snapshots store whatever `select_dell_capacity_summary` picked (system, pool rollup, or raw). Prior week and current week can be different layers, so usable jumps 2–3× and growth shows 196% / 242% that is not real used growth.
2. **IBM/HP Forecast ignore growth.** `_write_forecast_grouped_rows` copies current util into Date, 3 Month, 6 Month, 9 Month, and 12 Month. Forecast is always flat, even when Weekly Growth is real. Only Forecast - Wkly uses `_project_util`.

A 0% week (same used both weeks) must stay 0% / flat. That is correct, not a bug.

## Goals

- Dell weekly snapshots always store **array/system** usable/used (`capacity_summary`, non-rollup), independent of CPG/pools and raw toggles.
- Stamp each snapshot `layer: "system"`.
- Weekly Growth only when prior and current are both `layer == "system"` and `prior_used > 0`. Otherwise **blank** (not `0%`).
- IBM Forecast / HP Forecast: Date = current util; 3/6/9/12 Month = `_project_util` at **13 / 26 / 39 / 52** weeks.
- Cap projected util at 100%. Widen the Forecast Date column so percents are not `####`.
- Bump `APP_VERSION` to **1.6.152**.

## Non-goals (v1)

- Storing pool and raw layers in the same snapshot file.
- Rewriting or converting old untagged snapshots to system.
- Changing Capacity Report page totals or the CPG/raw toggles.
- Changing Forecast - Wkly horizons (+1/+4/+8/+12 weeks).
- Inventing growth when two system weeks have the same used bytes (0% is correct).
- Changing LED thresholds.

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Scope | Array snapshots + gated growth **and** IBM/HP Forecast projection |
| Snapshot source | Always array/system, not pools/raw, not the CPG toggle |
| Untagged prior | Blank growth (not 0%, not compare anyway, no wipe) |
| 3/6/9/12 Month | 13 / 26 / 39 / 52 weeks |
| Implementation | Approach 1: array-only snapshot + gated growth + project Forecast |

## Behavior

### Snapshot source

New selector (name in plan): return `_usable(capacity_summary, allow_pool_rollup=False)` only. Do **not** fall back to pools or raw.

- If that summary is missing or `total_bytes <= 0`: do **not** upsert this card/week. Existing include-without-capacity rows stay blank.
- `maybe_upsert_dell_snapshot_for_card` and `collect_dell_report_rows` use this selector for bytes written to the store (not `select_dell_capacity_summary(..., include_pools=...)`).

IBM/HP Report current/prior cells continue to come from the snapshot store after upsert, so current week is array once this ships.

### Snapshot record

Keep existing fields (`usable_bytes`, `used_bytes`, model, facility, family, array_name, captured_at, week). Add:

```text
layer: "system"
```

Old records without `layer` stay on disk unchanged.

### Weekly Growth

`weekly_growth_fraction` stays `(current - prior) / prior` when `prior_used > 0`.

`_row_from_snapshots` sets `weekly_growth` only when **both** prior and current dicts have `layer == "system"`. If prior is missing, untagged, or not system → `weekly_growth is None` (Excel blank).

### IBM / HP Forecast

In `_write_forecast_grouped_rows`:

| Column | Value |
|--------|--------|
| Date (first util col) | `curr_util` |
| 3 Month | `_project_util(curr_util, growth, 13)` |
| 6 Month | `_project_util(..., 26)` |
| 9 Month | `_project_util(..., 39)` |
| 12 Month | `_project_util(..., 52)` |

`_project_util`:

- `curr_util is None` → None
- `weekly_growth is None` → **None** for projected columns (Date still has current util). Do not copy util into month / +N week columns.
- Else `max(0.0, min(1.0, curr_util * (1 + growth) ** weeks))`

Forecast - Wkly keeps +1/+4/+8/+12 and uses the same capped `_project_util` (so `None` growth blanks those horizon cells too, instead of copying util).

Widen `_FORECAST_COL_WIDTHS` Date column enough for `0.0%` (avoid `####`).

## Architecture

| Unit | Change |
|------|--------|
| `launchpad/dell_report_capacity.py` | Array-only snapshot selector |
| `launchpad/dell_report_snapshots.py` | Persist `layer`; growth gate helper if not in export |
| `launchpad/dell_report_export.py` | Collect/upsert use array selector; `_row_from_snapshots` gates growth; `_project_util` cap + None; Forecast rows project; Date col width |
| `launchpad/config.py` | `APP_VERSION` → `1.6.152` |
| Tests | Snapshot layer, growth gate, forecast horizons, 100% cap |

## Testing

- Array summary present → snapshot `layer == "system"` and bytes from that summary, not pools/raw.
- Only pools/raw present → no new snapshot for that week.
- Prior untagged + current system → `weekly_growth is None`.
- Both system, prior_used=100, curr_used=125 → growth `0.25`.
- Both system, same used → growth `0.0` (flat forecast months).
- Forecast Date = curr_util; 3 Month with 0.01/week ≈ `curr_util * (1.01 ** 13)`.
- `_project_util(0.9, 0.5, 13)` ≤ `1.0`.
- Version pin `1.6.152`.

## Version

Bump `APP_VERSION` to **1.6.152** when the feature ships.
