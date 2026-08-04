# Snapcopy Summary Outdated CG Filter — Design

**Date:** 2026-08-04  
**Status:** Approved  
**App version target:** 1.6.106+  
**Depends on:**
- Snapcopy Summary page (`launchpad/snapcopy_summary_page.py`)
- Shared CG summary helpers (`launchpad/fc_cg_summary.py`) — schedule context `days` / `held` / `label`, `snaps_per_week`
- Flash time display/parse (`launchpad/fc_consistgrp_ops.py` — `format_flash_time_display`, live-scan enrichment)
- Existing checked-row Excel export (`POST /api/contingency-groups/fc-cg-summary/export-selected`)

## Problem

Operators need to spot FlashCopy consistency groups whose last flash is older than the site’s expected schedule interval. Today Snapcopy Summary lists Flash time / Policy / Snaps/week but does not flag or filter outdated rows, so overdue CGs are easy to miss in a long table.

## Goals

- On **Snapcopy Summary**, after Refresh, mark each CG **outdated** when flash time age exceeds the site schedule interval.
- Control: **Outdated (N)** toggle in the hero actions that filters the table to outdated rows and shows the count.
- When the toggle is on: show only outdated rows and **auto-check** those rows so **Export Excel** (existing checked-rows path) exports outdated-only.
- Optional mild row styling for outdated rows when the full table is visible.
- Keep System Connectivity unchanged for this feature.

## Non-goals (v1)

- Putting outdated CG alerts on System Connectivity (Call Home / DNS / SNMP / NTP / Firmware / License Key).
- Treating missing flash time, held schedules, or missing schedule days as outdated (leave for later if needed).
- Changing the export API contract beyond existing checked `row_key` selection.
- Desktop/main Connection Dashboard badges for CG outdated state.
- Auto-email or push notifications.

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Placement | Snapcopy Summary only (not System Connectivity) |
| UI pattern | Filter toggle **Outdated (N)** (Approach A) |
| Outdated definition | Flash time age older than site schedule interval days (`schedule.days` / snaps-per-week expectation) |
| Missing flash time / held / no schedule days | **Not** outdated in v1 |
| Export | Existing checked-rows Excel path; toggle auto-checks outdated rows |

## Behavior

### Outdated detection (after Refresh)

For each CG summary row with schedule context for its card:

1. Resolve expected interval days from `schedule.days` (from capacity→schedule context / overrides already used for snaps-per-week).
2. If `schedule.held` is true, or `days` is missing/None, or flash time is missing/unparseable → **not outdated**.
3. Parse flash time back to a timestamp (inverse of / compatible with `format_flash_time_display` compact `YYMMDDHHMMSS` / `YYYYMMDDHHMMSS` and display forms).
4. Age in days = now (UTC) − flash timestamp.
5. Outdated when `age_days > expected_days` (strictly older than one full interval).

Mark each row with `outdated: true|false` (and optionally `age_days`, `expected_days`) in the live payload or compute client-side from existing `flash_time` + schedule days already available to the page.

### UI — Outdated (N) toggle

- Hero control: toggle/button **Outdated (N)** where N = count of outdated rows in the current site-filtered result set.
- Toggle off (default): full table for the selected site scope; optional mild highlight on outdated rows.
- Toggle on:
  - Table shows only outdated rows.
  - Those rows are auto-checked for export.
  - If N = 0, show empty-state hint (“No outdated CGs.”) and leave export selection empty.

### Export Excel

- Reuse existing checked-rows export (`POST /api/contingency-groups/fc-cg-summary/export-selected`).
- No new export API required in v1: outdated-only export = toggle on → rows auto-checked → Export Excel.

## Architecture

| Piece | Responsibility |
|-------|----------------|
| `launchpad/fc_cg_summary.py` and/or small helper | Detect outdated from flash time age vs `schedule.days` |
| Live scan payload (`health_server` / existing CG summary live) | Expose `outdated` (and optional age fields) and/or enough schedule days for client-side check |
| `launchpad/snapcopy_summary_page.py` | **Outdated (N)** toggle; filter; auto-check; optional row styling |
| Export | Unchanged checked-row contract |
| Tests | Outdated detection unit tests; page markers for toggle; version |

## Error / edge handling (v1)

| Case | Result |
|------|--------|
| Held schedule / `HOLD — EXPAND FIRST` / `NO CAPACITY DATA` | Not outdated |
| Missing or unparseable flash time | Not outdated |
| Missing `schedule.days` | Not outdated |
| Age exactly equal to expected days | Not outdated (`age_days > expected_days` only) |

## Testing

- Unit: weekly schedule + flash older than 7 days → outdated; flash within interval → not; held / missing flash / missing days → not.
- Page: **Outdated (N)** control present; export still uses selected row keys.
- Export: checked-only behavior unchanged.
- `APP_VERSION` bump for the ship task.

## Out of scope follow-ups

- Treat missing flash time as outdated.
- Desktop Connection Dashboard badges for outdated CGs.
- Auto-email / notifications.
- Putting CG outdated alerts on System Connectivity.
