# Capacity Excel Alert Banner — Design

**Date:** 2026-08-03  
**Status:** Approved  
**App version target:** 1.6.102+  
**Depends on:**
- `launchpad/capacity_export.py` (`_styled_workbook`, pool detail rows, inventory capacity fills)
- Existing capacity thresholds: ≥80% warn, ≥90% critical (same as Connection Dashboard / Capacity Report)

## Problem

Capacity Excel (`.xlsx`) exports inventory and pool stats but has no top-of-sheet signal when sites or pools are near full. Operators who open Excel first (and skip Capacity Report / Connection Dashboard) can miss ≥80% / ≥90% / ~100% conditions.

## Goals

- When any exported site/pool is ≥80% used, show a **merged banner row above the headers** on both **Storage Capacity** and **Pool Capacity** sheets.
- Severity-specific copy (operator choice B):
  - ≥80% and &lt;90%: `WARNING: Please check storage — capacity over 80%.`
  - ≥90% and &lt;99.5%: `CRITICAL: Please check storage — capacity over 90%.`
  - ≥99.5%: `CRITICAL: Please check storage — drives are full.`
- Append a short count of how many sites/pools are over the ≥80% threshold.
- No banner when everything is under 80%.
- Shift headers, freeze panes, and auto-filter down one row when the banner is present.

## Non-goals (v1)

- Emailing the Excel file or scheduling this banner separately.
- Changing Capacity Report HTML or Connection Dashboard badges (already shipped).
- Color-coding every Used % cell (banner only in v1).
- Per-row alert notes in the inventory grid beyond the top banner.

## Operator decisions (locked)

- Placement: Approach 1 — merged banner row above headers on both sheets.
- Copy: severity-specific (B), with ~100% using the “drives are full” critical line at ≥99.5%.
- Thresholds: unchanged (≥80 warn, ≥90 critical).

## Behavior

### Inputs

- Max used % across:
  - Pool detail rows (`Used %` values), and
  - Site-level capacity when available from capacity summary / fill text when a numeric % can be derived; prefer pool row percents as the primary source when present.
- Count sites and pools with used % ≥ 80 for the banner suffix.

### Banner

- Row 1, merged across all columns on that sheet.
- Fill: amber (`#F59E0B` / Excel-friendly orange) for warn; red (`#EF4444` / Excel-friendly red) for critical.
- Bold white (or dark-on-amber if contrast needs it) text.
- Example:  
  `CRITICAL: Please check storage — capacity over 90%. (2 site(s) / 4 pool(s) over threshold)`

### Layout when banner present

- Headers move to row 2.
- Data starts at row 3.
- `freeze_panes` and `auto_filter` use the header row (row 2), not the banner.

### Layout when no alert

- Keep today’s layout (headers on row 1) unchanged.

## Testing

- Unit tests for banner message selection (82% → warn text; 91% → over 90% critical; 100% → drives are full; &lt;80% → no banner).
- Workbook smoke: with high pool rows, sheet row 1 is merged banner and headers are on row 2; with all under 80%, headers remain on row 1.

## Out of scope follow-ups

- Listing every offending pool name inside the banner.
- Separate Alerts worksheet.
