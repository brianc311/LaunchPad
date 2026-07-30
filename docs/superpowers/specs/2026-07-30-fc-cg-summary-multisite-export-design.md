# Array FlashCopy CG Summary — Multi-Site Select + Excel Site Tabs

**Date:** 2026-07-30  
**Status:** Approved for implementation  
**App version target:** 1.6.85  
**Depends on:** Contingency Groups Array FlashCopy CG summary, `build_cg_summaries`, Flash time/Progress enrichment, Status eligibility helpers  
**Approach:** Multi-site live scan + client checkboxes + export checked rows as one sheet per site (Approach A)  
**Base branch:** `feature/contingency-groups`

## Problem

Operators need the rich Array FlashCopy CG summary (Flash time, Progress, Maps, Size, Policy, Snaps/week) across sites, with the ability to **select** CGs and export Excel with **one worksheet per site**. Today the panel is single linked-array only and export is all rows on one sheet.

## Goals

- Multi-site Refresh on Contingency **Array FlashCopy CG summary** (site filter or All).
- Row checkboxes + header **Select all**.
- **Export Excel** = **checked rows only**; workbook = **one sheet per site**.
- Keep existing summary columns (plus Site).
- Bump `APP_VERSION` to **1.6.85**.

## Non-goals

- Start/stop/delete from this panel.
- Changing FlashCopy CGs Status mode UI.
- CSV export.
- Auto-selecting all rows on every refresh.
- Changing the separate Contingency Groups planning workbook export.

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Scope | Multi-site Status-style scan |
| Placement | Contingency Groups → Array FlashCopy CG summary |
| Architecture | Approach A — dedicated multi-site scan + checkboxes |
| Export rows | Checked only (require ≥1) |
| Excel layout | One worksheet per site |
| Scan/export timing | Refresh fills cache; Export uses cache (Refresh first if empty) |

## Behavior

### Controls

- **Site** `<select>`: empty = all eligible cards; optional `card_id` / site filter (Host Volume / Status pattern).
- **Refresh CG summary** — unlock required; scans eligible cards; updates table + server cache.
- **Select all** checkbox in table header; per-row checkboxes.
- **Export Excel** — if no rows checked → status hint; if no cache → prompt to Refresh; else download/open xlsx (`open=1`).

### Eligibility

Same as FlashCopy CGs Status: `monitor_on` + SSH + `is_svc_fc_profile` (no HPE/DS8884).

### Table columns

Checkbox | Site | Name | Status | Flash time | Progress | Maps | Host maps | Size | Policy | Snaps/week

Row identity for selection: stable key e.g. `{card_id}:{cg_name}` (or `card_id` + `name`).

### Excel

- One sheet per distinct **Site** among selected rows (sanitize sheet name ≤31 chars, unique).
- Columns match the table (without checkbox).
- Sheet order: sites A–Z.
- Filename e.g. `FC_CG_Summary_MultiSite_<stamp>.xlsx`.

### Contingency group picker

This panel no longer requires a selected Contingency group for Refresh (multi-site is independent). Rest of Contingency page unchanged.

## Architecture

| File | Responsibility |
|------|----------------|
| `launchpad/health_server.py` | `scan_fc_cg_summary_live`, cache, export filtered by selection |
| `launchpad/fc_cg_summary_export.py` | Multi-sheet export by site |
| `launchpad/contingency_groups.py` | Site filter, checkboxes, select-all, live + export JS |
| `launchpad/config.py` | `1.6.85` |
| Tests | Scan/export/page/version |

### APIs

- `GET /api/contingency-groups/fc-cg-summary/live?card_id=` (optional) → `{ rows, errors }`
- Export: `POST /api/contingency-groups/fc-cg-summary/export` with JSON `{ "selected": ["cardId:cgName", ...], "open": true }` **or** GET with repeated query params — **prefer POST** for large selections.
- Reuse `fc_consistgrp_inventory` / `build_cg_summaries` per card (includes Flash time enrichment).

### Install note

Operator install/build output folder: `C:\Users\BrianColley\LaunchPad\LaunchPad-install` (or project `LaunchPad-Install` zip path used by `build.bat`).

## Tests

- Live scan: unlock; eligibility; row fields including site + selection key.
- Export: rejects empty selection / empty cache; one sheet per site; only selected rows.
- Page: Select all, checkbox markers, live + export paths.
- Version `1.6.85`.

## Follow-up (out of scope)

1. Wire same multi-sheet export into FlashCopy CGs Status.
2. Persist checkbox selection across refreshes.
3. CSV zip per site.
