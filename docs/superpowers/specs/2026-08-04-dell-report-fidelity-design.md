# Dell Report Fidelity — Design

**Date:** 2026-08-04  
**Status:** Approved  
**App version target:** 1.6.111+  
**Reference workbook:** `Walgreens Capacity Report June 15 2026.xlsb`  
**Supersedes / extends:** `docs/superpowers/specs/2026-08-04-dell-report-export-design.md` (v1 shipped at 1.6.109)  
**Deferred (separate workstream):** Health Excel command-block tabs + full alerts per site (operator chose layout **B**; implement after this Dell pass)

## Problem

The Dell Report button currently opens a workbook with IBM/HP Report **headers but no data rows**, so utilization LED colors never appear. Forecast tabs from the Walgreens reference (`IBM Forecast`, `HP Forecast`) are missing or empty. Operators need an export that matches the stakeholder report: populated IBM/HP Report sheets with LED colors, plus IBM/HP Forecast sheets.

## Goals

- On Dell Report click: **refresh capacity** for **monitored-on** IBM/HPE cards, then build the workbook.
- Populate **IBM Report** and **HP Report** with Facility / Array / Model, prior/current week GiB and utilization %, Weekly Growth %, and **visible LED fills** on utilization cells.
- Add populated **IBM Forecast** and **HP Forecast** sheets (flat current-util projection into 3/6/9/12 Month columns).
- If zero IBM and HP data rows after refresh, return a clear error (do not present an empty “success” file).
- Keep emitting `.xlsx` via the existing template-style builder (not `.xlsb` / macros).

## Non-goals

- Health Excel command-block tabs (queued next).
- **Forecast - Wkly** sheets (omit or leave empty stubs).
- True predictive growth modeling beyond weekly snapshot growth on Report sheets.
- Cloning or redistributing the Walgreens `.xlsb` binary.
- Filling PowerMax / PowerStore / NetApp / Data Domain / ECS report or forecast sheets with live data.
- Pixel-perfect logos, pivot charts, or Excel macros from the reference file.

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Priority | Dell Report fidelity before Health Excel tabs |
| Builder | Harden current `.xlsx` builder (approach 1) |
| Forecast scope | IBM Forecast + HP Forecast only (not Forecast - Wkly) |
| Forecast values | Copy current utilization into Date / 3 / 6 / 9 / 12 Month columns (flat; matches June reference when growth is flat) |
| Capacity refresh | Refresh on Dell Report click, then build |
| Site set | Monitored-on IBM/HPE only |
| Empty result | Clear API/UI error when no rows after refresh |
| LED bands | Unchanged: green &lt;70%, amber 70–89%, red ≥90% |

## Behavior

### Export flow

1. Gate on Admin **Show Dell Report button** (unchanged).
2. Select card IDs with Monitor **on**.
3. Keep cards whose `dell_report_family(device_profile)` is `ibm` or `hp`.
4. Refresh each selected card (`refresh_card` / existing capacity path) so `capacity_summary` / pools are current.
5. Upsert weekly snapshots for the current ISO week when missing (existing store).
6. Build workbook from collected rows.
7. If both IBM and HP row lists are empty → HTTP/UI error with an actionable message (e.g. no monitored IBM/HPE capacity after refresh). Do not open a blank workbook as success.

Dashboard Dell export remains `include_monitor_off=False`. Capacity Report may still pass include-off if already wired; **this design’s site set for the fidelity pass is monitored-on only** unless a later change reopens that.

### IBM Report / HP Report

- Columns (unchanged semantics): Facility, Storage Array, Model Number, Prior Week Usable/Used/Util %, Current Week Usable/Used/Util %, Weekly Growth %.
- Units: GiB; utilization as Excel percent (fraction 0–1 with `%` format).
- Sort by facility, then array name.
- Facility grouping: show facility label on the first row of each facility group (subsequent rows in the group may leave Facility blank), matching the reference pattern.
- Prior week / growth from weekly snapshots when available; otherwise current week filled and prior/growth blank or zero per existing rules.
- **LED styling:** apply **direct cell fills** on prior/current Utilization % cells using `utilization_led_fill`, and keep conditional formatting as a backup so colors are visible in Excel viewers that honor either path.

### IBM Forecast / HP Forecast

Sheet names: `IBM Forecast`, `HP Forecast` (trim trailing spaces from the reference names).

| Column | Content |
|--------|---------|
| Facility | Same grouping behavior as Report |
| Storage Array | Card / array name |
| Model Number | Model string |
| Date (current) | Current utilization fraction |
| 3 Month | Same as current util (flat) |
| 6 Month | Same as current util (flat) |
| 9 Month | Same as current util (flat) |
| 12 Month | Same as current util (flat) |

- One row per array that appears on the corresponding Report sheet.
- LED fills on utilization columns (Date + 3/6/9/12 Month) with the same bands.
- Home link / title row styling consistent with Report sheets where practical.

### Other sheets

- **Home:** list IBM Report, HP Report, IBM Forecast, HP Forecast, then remaining stubs.
- Other vendor Report stubs may remain empty header shells.
- Do not require Forecast - Wkly sheets in this pass.

### Error / UX

- Progress: if refresh is slow, existing status/log patterns are enough; no new spinner required unless already present for Dell export.
- Empty-after-refresh must surface in the UI status/toast and as a non-200 (or explicit error JSON) from `/api/dell-report-export`.

## Files (expected)

| Area | Likely touch |
|------|----------------|
| `launchpad/dell_report_export.py` | Forecast sheets, facility grouping, direct LED fills, Home sheet list |
| `launchpad/health_server.py` | Filter monitored IBM/HPE before refresh; empty-row error |
| `launchpad/dell_report_leds.py` | Reuse (no band change) |
| Tests under `tests/test_dell_report_*.py` | Rows present after mock capacity; forecast sheets; LED fills; empty → error |

## Success criteria

- [ ] Dell Report with ≥1 monitored IBM or HPE site that returns capacity → IBM and/or HP Report have data rows and colored util cells.
- [ ] Workbook includes **IBM Forecast** and **HP Forecast** with the same arrays and flat util columns.
- [ ] Zero qualifying rows after refresh → clear error, no blank success file.
- [ ] APP_VERSION bumped in the implementation plan’s final task (target **1.6.111**).

## Follow-ups (not this spec)

1. Health Excel: one tab per command block + full `showalert` / alert rows per site.
2. Forecast - Wkly sheets.
3. Broader vendor Report/Forecast population.
