# Dell Report Raw Capacity, Facility Mapping & Weekly Sheets — Design

**Date:** 2026-08-05  
**Status:** Approved  
**App version target:** 1.6.119+  
**Extends:**  
- `docs/superpowers/specs/2026-08-05-dell-report-walgreens-visual-design.md`  
- `docs/superpowers/specs/2026-08-05-dell-report-led-banner-design.md`  
- `docs/superpowers/specs/2026-08-05-hpe-showsys-space-raw-design.md`  
**Reference:** Walgreens HP Report / IBM Report / Forecast screenshots (Facility, Array, Model, date blocks, LED icons, Weekly Growth)

## Problem

1. **CPG off → empty Dell Report.** Export rows use only `capacity_summary` (+ pool rollup). With Include CPG/pools off, HPE often has no pool rollup and Dell skips the site even when **`raw_capacity_summary`** (`showsys -space`) is present from live refresh.
2. **Wrong identity columns.** Facility is almost always `Other`; Storage Array is the LaunchPad card/site label; Model is often a hostname. Pic 1 expects Facility groups (Data center -WAG1/WAG2, Distribution center, Remote), array IDs (e.g. `Vdiprimera101`), and hardware models (e.g. `HPE Primera 600 4-way`).
3. **Missing weekly report sheets.** Workbook has empty `* Forecast - Wkly` stubs only. Operators need live **`IBM Report - Wkly`** / **`HP Report - Wkly`** (one column group per stored ISO week) and populated **Forecast - Wkly** for IBM/HP.
4. **HP Report should mirror Pic 1** from the **live HPE Primera/3PAR capacity scrap** already run on refresh (`showsys -d`, `showsys -space`, `showcpg` when pools included).

## Goals

- When Include CPG/pools is **off**, Dell Report still emits HP (and IBM when raw exists) rows from **raw utilization**.
- When Include CPG/pools is **on**, prefer **system/usable** capacity (existing behavior); pools remain fallback only when needed.
- Facility / Storage Array / Model: **heuristics + per-card overrides** (option C).
- Add and populate **`IBM Report - Wkly`** and **`HP Report - Wkly`**: Facility / Array / Model + **one week block per retained ISO week** (Useable / Used / Util % + LED icons) from snapshot history (option A).
- Populate **`IBM Forecast - Wkly`** and **`HP Forecast - Wkly`** from the same IBM/HP row + snapshot data (not empty shells).
- Keep existing IBM/HP Report and monthly Forecast layouts, banner, and green/yellow LED icons (&lt;80% / ≥80%).
- Source numbers from live capacity refresh / analyze_health scrap — no hand-entered Walgreens customer data.

## Non-goals

- Live PowerMax / PowerStore / NetApp / Data Domain / ECS / Cluster data.
- Byte-identical `.xlsb` / macros / pivots.
- Changing LED threshold back to 70/90 or adding red.
- Inventing prior-week history when only one ISO week of snapshots exists (prior columns stay blank until week 2).
- Replacing Capacity Report UI cards; this is Dell Report export only.
- Full Admin UI redesign beyond a small override editor (table or JSON under Dell Report settings is enough).

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Facility / Array / Model | **C** — heuristics default + per-card overrides |
| Report - Wkly layout | **A** — one column group per stored ISO week |
| CPG off capacity | Prefer **raw** (`raw_capacity_summary`) for Dell rows |
| CPG on capacity | Prefer **system/usable** (`capacity_summary`) |
| HP Report data | Live HPE Primera/3PAR scrap on Dell export refresh |
| Forecast monthly | Unchanged shape (Date + 3/6/9/12 Month + LEDs) |
| Forecast - Wkly | Live for IBM/HP; other vendors stay stubs |
| Report - Wkly sheets | Add `IBM Report - Wkly`, `HP Report - Wkly` next to their Report/Forecast family |

## Capacity selection (Dell rows + snapshots)

For each IBM/HP site during `collect_dell_report_rows` / snapshot upsert:

1. If `include_pools` is **False** (or pools intentionally dropped):  
   - Prefer `raw_capacity_summary` when `total_bytes > 0`.  
   - Else fall back to `capacity_summary` (system).  
   - Do **not** require pool rollup.
2. If `include_pools` is **True**:  
   - Prefer `capacity_summary` (system / usable).  
   - Else pool rollup (`capacity_summary_from_pools`) if present.  
   - Else `raw_capacity_summary` as last resort so the row is not dropped.
3. Pass `include_pools` from the export API / Capacity Report toggle into collect (today export already refreshes with `include_pools`; collect must honor the same choice when choosing summaries).

`ExportSite` already carries `raw_capacity_summary`; wire it into `_capacity_summary_for_site` (or a sibling selector used only for Dell).

## Facility / Array / Model

### Heuristics (`facility_from_name`)

Keep existing WAG1 → `Data center -WAG1`, WAG2 → `Data center -WAG2`, distribution/`dc`/`v5k`/`v7k` → `Distribution center`.

**Add:** if name contains `remote` (case-insensitive) → `Remote` (before falling through to `Other`).

### Defaults for Array / Model

- **Storage Array:** system name from the chosen capacity summary (`summary["name"]`) when non-empty; else card/site `name`.
- **Model Number:** device profile display label when available (e.g. `HPE Primera 600 4-way` from presets); else scrap/product string; else `device_profile` id.

### Overrides

Extend Dell Report settings (same settings blob or adjacent key) with optional per-`card_id` map:

```json
{
  "enabled": true,
  "card_overrides": {
    "<card_id>": {
      "facility": "Data center -WAG2",
      "array_name": "Vdiprimera101",
      "model": "HPE Primera 600 4-way"
    }
  }
}
```

Any field present overrides the heuristic/default for that card. Missing fields keep computed values. Persist via existing Admin Dell Report save path (minimal UI: enough to edit overrides; can be structured fields or validated JSON in v1 if a full grid is heavy).

## Sheet behavior

### IBM Report / HP Report

Unchanged column chrome (Facility, Storage Array, Model Number, prior week Useable/Used/Util, current week Useable/Used/Util, Weekly Growth %). Fill from live collect + snapshots using capacity selection and identity mapping above. LEDs and banner unchanged.

### IBM Report - Wkly / HP Report - Wkly (new live sheets)

- Insert into `ORDERED_SHEET_NAMES` in the IBM/HP family, e.g. after Report (or after Forecast) consistently:  
  `IBM Report`, `IBM Report - Wkly`, `IBM Forecast`, `IBM Forecast - Wkly` (and same for HP).  
  Exact order: prefer **Report → Report - Wkly → Forecast → Forecast - Wkly** so Wkly sits next to its parent.
- Columns: Facility, Storage Array, Model Number, then for each retained ISO week (oldest→newest, up to snapshot retention): Useable Capacity (GiB), Used Capacity (GiB), Utilization % with icon LEDs.
- Date labels above each week group (same Date/Values spirit as Report).
- One row per array; Facility grouping blanks after first row in a group.
- Weeks with no snapshot for that card: blank cells for that week group.

### IBM Forecast / HP Forecast

Keep monthly 3/6/9/12 layout + LEDs; use same identity + capacity source so Pic 3 matches Pic 1 identity columns.

### IBM Forecast - Wkly / HP Forecast - Wkly

Populate (no longer empty stubs for IBM/HP). Columns: Facility, Array, Model, current util (latest week), then fixed forward horizons **+1 / +4 / +8 / +12 weeks** (util % + LEDs), using the same week-over-week growth extrapolation as monthly forecast when prior/current snapshots exist; if growth is missing, repeat current util across horizons (honest flat fallback). Other vendors’ Forecast - Wkly remain empty shells.

### Other stubs

PowerMax / PowerStore / … unchanged empty header shells.

## Home / navigation

Home index lists the new `* Report - Wkly` sheet names. No requirement for Walgreens-style bottom nav buttons (optional polish, not required).

## Testing

- Collect with `include_pools=False` and only `raw_capacity_summary` → HP row emitted with raw GiB/util.
- Collect with `include_pools=True` prefers system over raw when both present.
- `facility_from_name("Anderson, SC - Remote")` → `Remote`.
- Card override wins over heuristic for facility/array/model.
- Workbook contains `IBM Report - Wkly` and `HP Report - Wkly`; HP sheet has week columns matching snapshot weeks.
- IBM/HP Forecast - Wkly sheets are not empty stubs when rows exist (have data rows).
- Existing LED / banner / empty-workbook / settings enable tests still pass.

## Success criteria

- CPG off: HP Report / Forecast / Report - Wkly / Forecast - Wkly show Primera (and other HP) capacity from live raw scrap.
- CPG on: system/usable numbers as today.
- Facility / Array / Model match Pic 1 after heuristics + overrides.
- Report - Wkly is option A (per-week columns from snapshots).
- First week after deploy: current week filled; prior Report week and multi-week Wkly history grow as snapshots accumulate.
