# Array FlashCopy CG Summary — Flash Time + Progress

**Date:** 2026-07-30  
**Status:** Approved for implementation  
**App version target:** 1.6.82  
**Depends on:** Contingency Groups Array FlashCopy CG summary (`build_cg_summaries`, export helper)  
**Approach:** Extend shared `build_cg_summaries`; display on Contingency summary table + Excel only (Approach 1)  
**Base branch:** `feature/contingency-groups`

## Problem

Operators watching live FlashCopy CGs on Contingency Groups see status `copying` but not **when** the CG was started (Flash time) or **how far** background copy has progressed. Spectrum Virtualize does not expose a reliable CG “end” timestamp.

## Goals

- Add **Flash time** and **Progress** columns to Contingency **Array FlashCopy CG summary** (table + Excel).
- Flash time from array CG `flash_time` (start / point-in-time).
- Progress = **minimum** of member map `progress` values while status is copying.
- Bump `APP_VERSION` to **1.6.82**.

## Non-goals

- End / completion date column (array does not provide it).
- FlashCopy CGs Manage or Status mode column changes.
- Extra SSH commands beyond existing inventory collect.
- Snapshot Schedule “day done” (separate Feature B).

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Fields | Flash time + Progress % (no end date) |
| Progress aggregation | **Minimum** of member map progress |
| Scope | Contingency CG summary table + Excel only |
| Implementation | Extend shared `build_cg_summaries` |

## Behavior

### Columns (order)

Name | Status | **Flash time** | **Progress** | Maps | Host maps | Size | Policy | Snaps/week

| Column | Source / rule |
|--------|----------------|
| Flash time | CG `flash_time`; empty → display `—` |
| Progress | If status matches copying (case-insensitive): min of parseable member `progress` values → display `N%`. If not copying, or no parseable progress → `—` |

### Progress parsing

- Read each member map’s `progress` string.
- Strip whitespace and trailing `%`; accept int/float.
- Ignore non-numeric values.
- Among valid values, take **minimum**.
- Store as number (`progress_pct`) in summary row; UI/Excel format as percent text.

### Excel

- Same two columns in `SUMMARY_HEADERS` / `SUMMARY_FIELDS`.
- Sheet name remains `FC CG Summary`.

## Architecture

| File | Change |
|------|--------|
| `launchpad/fc_cg_summary.py` | `flash_time`, `progress_pct` on `build_cg_summaries` rows |
| `launchpad/contingency_groups.py` | Headers + `renderFcCgSummaryRows` |
| `launchpad/fc_cg_summary_export.py` | Headers/fields for Flash time, Progress |
| `launchpad/config.py` | `1.6.82` |
| Tests | Builder, page markers, export headers, version |

## Tests

- Builder: flash_time passthrough; min progress while copying; None when idle/stopped/empty.
- Page: Flash time / Progress headers and field usage in render.
- Export: headers include Flash time, Progress.
- Version `1.6.82`.

## Follow-up (out of scope)

1. Show same columns on FlashCopy CGs Manage / Status.
2. Average progress option.
3. Map-detail progress drill-down.
