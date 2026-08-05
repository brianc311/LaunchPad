# Dell Report Walgreens Visual Fidelity — Design

**Date:** 2026-08-05  
**Status:** Approved  
**App version target:** 1.6.117+  
**Reference workbook:** `Walgreens Capacity Report June 15 2026.xlsb`  
**Extends:** `docs/superpowers/specs/2026-08-04-dell-report-fidelity-design.md`  
**Problem context:** Operators need the LaunchPad Dell Report to **look like** the stakeholder Walgreens workbook for IBM/HP Report and Forecast (headings, colors, wording, pictures, tab strip), without requiring live data on other vendor tabs.

## Problem

Current Dell Report `.xlsx` has the right four live sheets (IBM/HP Report + Forecast) and LED fills, but layout/wording/column offset differ from the June Walgreens reference. Logos and the full tab order (PowerMax, PowerStore, Forecast - Wkly stubs, etc.) are missing. Stakeholders compare exports side-by-side with the Walgreens file.

## Goals

- Match **IBM Report**, **HP Report**, **IBM Forecast**, **HP Forecast** visual layout to the reference: header band, Home link, Date/Values week labels, column headers wording, column offset (data starts at column B), facility grouping, utilization LED fills.
- Embed **header logo image(s)** when assets are available under the app package.
- Create **empty sibling tabs** with the same sheet **names and relative order** as the reference’s report/forecast family (including Forecast - Wkly stubs where present), with matching title/header styling and **no data rows**.
- Keep emitting **`.xlsx`** via openpyxl (not `.xlsb` / macros / pivots).
- Continue populating IBM/HP data from monitored LaunchPad capacity + weekly snapshots (existing fidelity behavior).

## Non-goals

- Byte-identical `.xlsb` or Excel macros / pivot caches.
- Live PowerMax / PowerStore / NetApp / Data Domain / ECS / Host / Cluster / Datastore data.
- Cloning Walgreens customer data into the repo.
- Changing LED bands (green &lt;70%, amber 70–89%, red ≥90%).
- Changing capacity collection / showsys -space work.

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Live data sheets | IBM Report, HP Report, IBM Forecast, HP Forecast only |
| Other tabs | Empty shells; same names/order/heading style as reference report family |
| Pictures | Bundle logo asset(s) in repo; embed on Report/Forecast (and stubs if practical) |
| Output | `.xlsx` |
| Header wording | Match reference (“Useable Capacity (GiB)”, etc.) |
| Column layout | Match reference: blank col A band / data from column B; prior/current week date row |
| Sheet name trim | Prefer trimmed names (`IBM Forecast` not trailing space) for stability; Home index lists clean names |

## Reference layout (IBM/HP Report)

Observed from the June `.xlsb` (1-based Excel rows; pyxlsb 0-based cols shown as letters):

- Rows 1–6: logo / spacer band (images in reference).
- Row 7: **Home** (link-style), **Date**, **Values**.
- Row 8: prior-week date under Date group, current-week date under Values group.
- Row 9: headers — Facility, Storage Array, Model Number, Useable Capacity (GiB), Used Capacity (GiB), Utilization % , (repeat Useable/Used/Util for current week), Weekly Growth %.
- Row 10+: data; Facility blank after first row in a facility group.

Forecast sheets: Home, “Sum of Utilization %”, Date; headers Facility / Storage Array / Model Number / date (or Date label) / 3 Month / 6 Month / 9 Month / 12 Month; flat util values with LED fills.

## Behavior

### 1) Sheet order

Workbook sheet order (approximate reference report family; omit raw “\* Storage” data dumps and VMware bulk sheets unless needed for navigation):

1. Home (LaunchPad index — keep; reference uses “Walgreens Report” as TOC — map Home as our TOC)
2. PowerMax Report, PowerMax Forecast, PowerMax Forecast - Wkly  
3. PowerStore Report, PowerStore Forecast, PowerStore Forecast - Wkly  
4. PowerScale Report, PowerScale Forecast, PowerScale Forecast - Wkly  
5. NetApp Report, NetApp Forecast, NetApp Forecast - Wkly  
6. **IBM Report**, **IBM Forecast**, IBM Forecast - Wkly  
7. **HP Report**, **HP Forecast**, HP Forecast - Wkly  
8. Data Domain Report, Data Domain Forecast, Data Domain Forecast - Wkly  
9. Cluster Report, Cluster Forecast, Cluster Forecast - Wkly (optional stubs)  
10. Host Report, Datastore Report (optional stubs)  
11. ECS Report, ECS Forecast, ECS Forecast - Wkly  

v1 minimum: include all **Report / Forecast / Forecast - Wkly** pairs listed in the reference for PowerMax through ECS + IBM + HP. Skip pure “\* Storage” inventory sheets and Host Counts / VM Report unless trivial to stub.

### 2) IBM/HP Report + Forecast content

- Reuse `collect_dell_report_rows` / snapshots / LED fills.
- Rewrite `_write_sheet_header` / `_write_forecast_sheet_header` / row writers to use reference column indices and labels.
- Forecast Date column: current util (flat) as today; header may show report date.

### 3) Logos

- Store PNG(s) under e.g. `launchpad/assets/dell_report/` (Dell Technologies / Managed Services logos extracted or supplied).
- If asset missing, leave spacer rows (layout still matches); do not fail export.
- Prefer extracting from the reference once into assets (not shipping the `.xlsb`).

### 4) Stubs

- Same header chrome as Report (title/Home/Date/Values/column headers) or a simplified matching title bar; **zero data rows**.

### 5) Home

- List all sheet names in workbook order with the report title and date.

## Testing

- Workbook sheet names include IBM/HP Report/Forecast and stub Forecast - Wkly names in order.
- IBM/HP Report header cells match expected labels (Useable Capacity…).
- Data rows start at expected column (Facility in column B).
- Logo: if asset present, worksheet has at least one image; if absent, export still succeeds.
- Existing LED / empty-row / collect-row tests still pass.

## Success criteria

- Side-by-side with Walgreens file: IBM/HP Report and Forecast look the same structurally (headers, week labels, colors, logos when assets present).
- Other vendor tabs exist empty with matching headings.
- Live IBM/HPE capacity still fills IBM/HP sheets after refresh.

## Follow-ups

- Forecast - Wkly live history.
- Vendor data for PowerMax/etc.
- Optional “Walgreens Report” TOC sheet clone instead of Home rename.
