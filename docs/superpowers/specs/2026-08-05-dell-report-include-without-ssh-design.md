# Dell Report Include-Without-SSH — Design

**Date:** 2026-08-05  
**Status:** Approved (pending operator review of this written spec)  
**App version target:** 1.6.121+  
**Extends:** `docs/superpowers/specs/2026-08-05-dell-report-raw-facility-wkly-design.md`  
**Problem context:** Some IBM/HPE cards (e.g. `IBM - SVCPVCW1 - WAG1`, `IBM - XIV Danville - Remote`, `No Access - Wag1_XIV_13557 - WAG1`) never get live capacity because SSH fails, so Dell Report drops them. Operators need an explicit opt-in to keep those rows on the report.

## Problem

Dell Report collection skips any IBM/HPE site without a usable capacity summary (`total_bytes > 0`) after refresh. Unreachable or “No Access” arrays therefore never appear on IBM/HP Report, Forecast, or Wkly sheets, even when stakeholders expect Facility / Array / Model rows for them.

## Goals

- Per-card **Include on Dell Report** checkbox (default off) for IBM/HPE profiles.
- When checked and live capacity is missing: emit a report row with **blank** Useable / Used / Utilization / Weekly Growth (and blank week capacity cells on Report - Wkly).
- Still fill **Facility / Storage Array / Model** from card name + existing heuristics and `card_overrides`.
- Apply to **any** IBM/HPE card, not only the three named sites.
- Live cards with capacity continue to appear without requiring the checkbox.

## Non-goals

- Manual GiB entry for forced rows.
- Filling blanks from last known snapshot (option B rejected).
- Auto-including cards based on name patterns (“No Access”).
- Including non-IBM/HPE vendors on Dell Report.
- Writing fake weekly capacity snapshots for blank forced rows.

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Capacity when SSH fails | **A** — blank cells |
| UI | Per-card checkbox on dashboard card (**Dell Report**) |
| Default | Off |
| Scope | All IBM/HPE profile cards |
| Snapshot store | Do not upsert capacity for blank forced rows |

## Behavior

### Persistence

Store a per-`card_id` boolean, e.g. in app settings:

```json
{
  "enabled": true,
  "card_overrides": { ... },
  "include_card_ids": ["12", "34", "56"]
}
```

Or a dedicated setting key / card metadata flag — implementation may choose the cleanest existing pattern (card monitor flag style vs Dell settings blob). Requirement: survives restart; loadable during Dell export.

### Card UI

- On each card widget for `dell_report_family(device_profile) in {"ibm","hp"}`, show checkbox **Dell Report** (tooltip/helper: include on Dell Report even without SSH capacity).
- Hide or disable for other device profiles.
- Toggle persists immediately or via existing card save pattern (match monitor toggle UX if practical).

### Export / collect

1. Build site list as today (monitored IBM/HPE refresh).
2. For each site:
   - If live capacity selected successfully → normal row + current-week snapshot refresh (existing behavior).
   - Else if `include_on_dell_report` for that `card_id` → append a **forced blank** row:
     - `facility` / `array_name` / `model` from `resolve_dell_identity` (site name; empty summary name).
     - All capacity/util/growth fields `None` / blank in Excel.
     - `card_id` set for Wkly sheet identity columns; week capacity cells stay blank when no snapshot exists.
   - Else → skip (unchanged).
3. Do **not** call `upsert_week_snapshot` for forced blank rows (no zero-byte fake history).
4. Forced blank rows still appear on IBM/HP Report, Report - Wkly, Forecast, and Forecast - Wkly (util columns blank / flat blank).

### Monitor / refresh

- Checkbox does not require Monitor On; if product currently only exports monitored-on cards, forced-include cards should still be considered for export when checked (either include them in the export ID set even if monitor off, or document that Monitor must stay on — **prefer: checked cards are eligible for Dell export regardless of monitor**, as long as they are IBM/HPE). Confirm against current `include_monitor_off=False` policy: extend so `include_card_ids` are always in the Dell export set.

## Testing

- Unreachable IBM card with include off → absent from workbook.
- Same card with include on → present on IBM Report with Facility/Array/Model filled and capacity cells empty.
- Live capacity card unchanged (appears with numbers; checkbox optional).
- Forced include does not create a current-week snapshot with 0 bytes.
- Non-IBM/HPE card: no Dell Report checkbox / include ignored.
- Persistence: save, reload, export still includes checked cards.

## Success criteria

Operator can check **Dell Report** on SVCPVCW1, XIV Danville, Wag1_XIV_13557 (and any other IBM/HPE card) and see them on IBM tabs with identity columns filled and capacity blank, without SSH.
