# Dell Report Banner + LED Icons — Design

**Date:** 2026-08-05  
**Status:** Approved  
**App version target:** 1.6.118+  
**Extends:** `docs/superpowers/specs/2026-08-05-dell-report-walgreens-visual-design.md`  
**Reference:** Walgreens Capacity Report / operator screenshots (Dell left, sheet title center, Walgreens right; circular Utilization LEDs)

## Problem

LaunchPad Dell Report (1.6.117) uses solid cell fills for utilization and stacks logos on the left. Stakeholders need the Walgreens banner layout and **icon-set LEDs** (green/yellow circles beside %), not full-cell fills.

## Goals

- Banner on IBM/HP Report and Forecast (and stubs where logos already apply): **Dell logo left**, **sheet title centered**, **Walgreens logo right**.
- Utilization % columns use Excel **icon set** LEDs: **green if util &lt; 80%**, **yellow if util ≥ 80%** (two-color; no red band).
- Remove (or stop relying on) solid green/amber/red cell fills on Utilization % as the primary LED signal.
- Keep GiB numbers, facility grouping, Date/Values week labels, and live IBM/HP data collection.

## Non-goals

- Changing LED bands back to 70/90.
- Red LED for ≥90%.
- Weekly Growth icon bars (optional follow-up).
- Pixel-perfect AutoFilter/pivot recreation beyond easy wins (filter + banded rows OK if cheap).

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Banner | Dell left / sheet name center / Walgreens right |
| LED style | Excel icon set circles (not cell fill as primary) |
| Thresholds | green &lt; 0.80; yellow ≥ 0.80 |
| Red band | None |
| Sheets | IBM Report, HP Report, IBM Forecast, HP Forecast (+ stubs keep banner if logos applied) |

## Behavior

1. Identify Dell vs Walgreens assets among `launchpad/assets/dell_report/logo_*.png` (use known sizes / filenames; Dell typically logo_1 or logo_4, Walgreens the red-script asset).
2. `_add_logos(ws, sheet_title=...)` places left/right images and writes centered title (e.g. “IBM Report”) in Dell blue.
3. Replace direct util cell fills + old 70/90 CF with `IconSetRule` (or equivalent openpyxl API) on util columns; show icon + value.
4. Update `utilization_led_fill` / tests to the new two-band rule if still used as fallback; prefer icons for Report/Forecast util columns.
5. Bump APP_VERSION to **1.6.118**.

## Testing

- Workbook IBM Report has ≥2 images and a cell containing “IBM Report” in the banner band.
- Utilization cells use icon-set CF (or document openpyxl representation); values ≥0.80 and &lt;0.80 covered by tests where assertable.
- Existing collect/API tests still pass.

## Success criteria

- Side-by-side with stakeholder pic: banner logos + title, yellow/green LEDs at 80% cutover.
