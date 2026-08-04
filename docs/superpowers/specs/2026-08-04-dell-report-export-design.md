# Dell Report Excel Export — Design

**Date:** 2026-08-04  
**Status:** Approved  
**App version target:** 1.6.109+ (after HPE array/CPG capacity work at 1.6.108 if that ships first; otherwise next free patch)  
**Reference workbook:** `Walgreens Capacity Report June 15 2026.xlsb` (Dell Technologies Managed Services – Capacity Management Report)  
**Depends on:**
- Capacity Report + existing Capacity Excel export (`capacity_report.py`, `capacity_export.py`)
- Health Dashboard Export menu (`dashboard_view.py`)
- Admin settings persistence (same pattern as `capacity_email_settings` / DB settings)
- Live / cached capacity summaries for IBM FlashSystem/SVC and HPE 3PAR/Primera cards
- Device profile classification already used for inventory vendor columns

## Problem

Operators need a **Dell Managed Services–style** capacity workbook (IBM Report + HP Report layout, utilization “LED” colors, facility grouping, week-over-week columns) that LaunchPad can generate from monitored sites. Today’s Capacity Excel is LaunchPad-native and does not match that stakeholder format. The control must be hideable from Admin when not wanted.

## Goals

- Add a **Dell Report** button on **Capacity Report** (and on **Health Dashboard** Export if it fits).
- Export an `.xlsx` that visually/structurally matches the reference report’s **IBM Report** and **HP Report** sheets.
- Include other vendor/TOC tabs as **empty shells** (no data rows).
- Utilization LED colors: green &lt;70%, amber 70–89%, red ≥90%.
- Persist **weekly capacity snapshots** so Weekly Growth % becomes real once ≥2 weeks of samples exist.
- Record a snapshot on **Dell Report** click and on Capacity **Refresh On Sites** when that ISO week’s sample is missing.
- Derive **Facility** from card/site name heuristics (WAG1 / WAG2 / DC patterns, etc.).
- Admin setting **Show Dell Report button** (default **on**); when off, hide UI and reject/disable the export API.

## Non-goals (v1)

- Emitting true `.xlsb` or preserving Excel macros from the reference file.
- Filling forecast / weekly forecast / host / datastore / ECS / PowerMax / PowerStore / NetApp / Data Domain sheets with live data (tabs may exist empty).
- Cloning the reference file binary as a redistributed template.
- Changing the existing LaunchPad Capacity Excel export format.
- Pixel-perfect logo/artwork beyond practical openpyxl styling (title, Home link text, date headers, column layout, % formats, conditional formatting).

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Scope | **A** — IBM Report + HP Report with data; other tabs empty shells |
| Week-over-week | **C** — persist weekly snapshots for real Weekly Growth |
| LED bands | **A** — green &lt;70%, amber 70–89%, red ≥90% |
| Facility | **A** — derive from card/site name mapping heuristics |
| Snapshot timing | **A** — on Dell Report + Capacity Refresh when week sample missing |
| Builder approach | **1** — template-style `.xlsx` builder (not clone `.xlsb`) |
| Admin | Show/hide Dell Report button (default on) |

## Behavior

### Buttons

- **Capacity Report:** **Dell Report** control near Export Excel / Refresh On Sites.
- **Health Dashboard:** expose the same export under Export (or adjacent) when layout allows.
- Visibility gated by Admin **Show Dell Report button**.
- Requires unlock + same monitor/include rules as capacity export unless otherwise specified (default: monitored-on sites only, matching Capacity Excel `include_off=0` unless operator uses include-off on Capacity Report — Dell Report should honor the Capacity Report include-off toggle when launched from that page; from Dashboard, default monitored-on only).

### Workbook structure (v1)

1. **TOC / Walgreens Report–style home** (or equivalent title sheet): title “Dell Technologies Managed Services - Capacity Management Report” (or LaunchPad-configurable subtitle later), date, links/labels to sheet names.
2. **IBM Report** — populated.
3. **HP Report** — populated (HPE / HP profiles).
4. Sibling tabs from the reference family (PowerMax Report, PowerStore Report, NetApp Report, forecasts, etc.): create **empty** sheets with header row stubs only (or blank), no data.

Exact sibling sheet list can be a fixed allowlist copied from the reference TOC; unused sheets stay empty.

### IBM / HP Report columns

Match reference layout:

| Area | Columns |
|------|---------|
| Identity | Facility, Storage Array, Model Number |
| Prior week | Usable, Used, Utilization % |
| Current week | Usable, Used, Utilization % |
| Growth | Weekly Growth % |

- Units: follow reference sheet conventions (**GiB** for IBM/HP report sheets in the sample).
- Utilization stored/displayed as Excel percent (0–1 or % format matching sample).
- Dual date headers for prior vs current week values.
- When only one weekly sample exists: fill **current** week; prior week and growth blank or `0`.
- When ≥2 samples: prior = previous ISO-week snapshot; current = latest; Weekly Growth = `(current_used - prior_used) / prior_used` (define clearly in plan; handle prior_used=0).

### LEDs (conditional formatting)

Apply to Utilization % cells (current and prior if filled):

- Green fill: utilization &lt; 0.70  
- Amber fill: 0.70 ≤ utilization &lt; 0.90  
- Red fill: utilization ≥ 0.90  

### Facility mapping

Heuristic mapper from card name / site string, e.g.:

- Contains `WAG1` / `wag1` → `Data center -WAG1`
- Contains `WAG2` / `wag2` → `Data center -WAG2`
- DC / distribution patterns → `Distribution center` when matched
- Else → `Unknown` or a single `Other` bucket (plan picks one; keep stable)

Editable per-card Facility is out of scope for v1 (may follow later).

### Row sourcing

- **IBM Report:** SSH cards with IBM FlashSystem / Storwize / SVC / XIV / DS8000-style profiles (existing inventory vendor = IBM).
- **HP Report:** HPE / HP 3PAR / Primera profiles (vendor = HPE).
- Capacity numbers from system-level capacity summary (aligned with array usable/used — after HPE array-capacity preference ships, use that; do not use All-CPGs rollup for HP site totals).
- Sort/group by Facility then array name like the sample.

### Weekly snapshots

- Persist under AppData (JSON or SQLite setting blob): per card_id / array key, ISO week, usable_bytes, used_bytes, model, facility, vendor family (`ibm` \| `hp`), captured_at.
- On Dell Report export and on Capacity Refresh On Sites: if no snapshot for current ISO week for that card, write one from latest capacity.
- Retention: keep at least last N weeks (e.g. 12) for growth; trim older in the same write path.

### Admin setting

- Setting key e.g. `dell_report_enabled` (bool, default `true`).
- Admin UI checkbox: **Show Dell Report button**.
- Capacity Report / Dashboard read setting (API or embedded flag) to show/hide.
- Export endpoint returns 403/disabled message when setting is false.

## Architecture

| Piece | Responsibility |
|-------|----------------|
| `launchpad/dell_report_export.py` (new) | Build styled workbook; LED rules; sheet stubs |
| `launchpad/dell_report_snapshots.py` (new) | Load/save weekly snapshots; growth calc |
| `launchpad/dell_report_facility.py` (new) | Name → Facility heuristics |
| `launchpad/dell_report_settings.py` (new) | Admin enable flag normalize/load/save |
| HealthServer API | `GET/POST` settings; `GET /api/dell-report-export` (or similar) |
| `capacity_report.py` | Dell Report button + include_off passthrough |
| `dashboard_view.py` | Optional Export entry when enabled |
| Admin UI | Checkbox for show/hide |
| Tests | Facility map, growth, LED thresholds, empty stubs, disabled setting, version |

## Error / edge handling (v1)

| Case | Result |
|------|--------|
| No IBM/HPE capacity yet | Sheets with headers only; status message in UI |
| Admin disabled | Buttons hidden; API refuses export |
| Missing model/serial | Use card fields / inventory columns; blank if unknown |
| prior_used = 0 | Weekly Growth blank or `0` (plan locks one) |
| Non-IBM/HPE cards | Do not appear on IBM/HP sheets |

## Testing

- Unit: facility heuristics; growth with 1 vs 2 weeks; LED band helpers.
- Workbook smoke: IBM/HP have rows; a stub tab exists with no data rows; utilization cells have conditional formatting rules.
- API/UI: enabled shows button; disabled hides and blocks export.
- Snapshot: refresh without current-week sample creates one; second week yields non-zero growth when used changed.
- Manual: compare layout to reference IBM/HP Report side-by-side in Excel.

## Out of scope follow-ups

- Filling PowerMax / PowerStore / NetApp / host / datastore sheets.
- True `.xlsb` output.
- Per-card editable Facility field.
- Forecast sheets and charts.
- Emailing Dell Report on a schedule.
