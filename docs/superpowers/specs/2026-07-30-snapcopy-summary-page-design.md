# Snapcopy Summary — Dedicated Page + Data Cleanup

**Date:** 2026-07-30  
**Status:** Approved for implementation  
**App version target:** 1.6.86  
**Depends on:** Multi-site FC CG summary live scan + selected Excel export (v1.6.85)  
**Approach:** Dedicated HealthServer page; remove embedded panel from Consistency Groups  
**Base branch:** `feature/contingency-groups`

## Problem

The Array FlashCopy CG summary on Consistency Groups makes that page too busy. Operators also see wrong **Site** values (`General` from card category), sparse **Flash time**, empty **Policy** when Snapshot Schedule exists, and need a clear path to the array GUI by IP. Export must remain reliable (checked rows → multi-sheet Excel).

## Goals

- New **Snapcopy Summary** page with the full multi-site CG summary UI (site filter, Refresh, checkboxes, Export).
- **Snapcopy Summary** button on Consistency Groups opens that page; embedded summary section is **removed**.
- **Site** = storage **card name**; host IP is an `https://` link (new tab) to the array GUI.
- **Flash time** filled from array detail / map start when available; “—” only when truly absent.
- **Policy** = Snapshot Schedule label for the site, plus array CG policy fields when present.
- Export: checked rows only; one Excel sheet per site (card name); clear status if nothing checked / cache empty.
- Bump `APP_VERSION` to **1.6.86**.

## Non-goals

- LaunchPad dashboard button for Snapcopy Summary.
- SSH Connect from the IP link (GUI URL only).
- Start / stop / delete CGs from this page.
- Changing Contingency planning **Export Excel** / **Export All Excel**.
- Changing FlashCopy CGs Status mode beyond shared data helpers if needed.
- CSV export.

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Placement | Dedicated page; remove from Consistency Groups |
| Entry point | Consistency Groups button only |
| Architecture | New page module + reuse live/export APIs |
| Site column | Card name (not category) |
| IP link | `https://{host}` in new tab (array GUI) |
| Policy | Schedule label + optional array fields |
| Flash time | Enrich from array when possible |
| Export | Checked rows only; multi-sheet by site |

## Behavior

### Consistency Groups

- Add button **Snapcopy Summary** near existing FlashCopy CGs / Health Dashboard links.
- Remove section `Array FlashCopy CG summary` (HTML, table, related JS).

### Snapcopy Summary page

- Path: `/snapcopy-summary`.
- Controls: Site `<select>` (All sites + eligible cards by **card name**), **Refresh**, **Export Excel**, select-all + row checkboxes.
- Link back to Consistency Groups (`/contingency-groups` or current Contingency path).
- Unlock required for live scan (same as today).
- Eligibility: `is_fc_consistgrp_status_eligible` (monitor on + SSH + SVC/FlashSystem).

### Table columns

Checkbox | Site | Host | Name | Status | Flash time | Progress | Maps | Host maps | Size | Policy | Snaps/week

- **Site**: card name text.
- **Host**: `https://{host}` link (`target=_blank`, `rel=noopener`) to the array GUI.
- Row key unchanged: `{card_id}:{cg_name}`.
- Excel includes Site and Host (Host as plain URL or IP string).

### Policy string

1. If Snapshot Schedule context for the card/site yields a label (e.g. `WEEKLY`, `EVERY 5 DAYS`), use it as the primary Policy text.
2. If array CG fields (copy_rate, autodelete, relationship, starting_status, policy) are non-empty, append with ` · ` separators.
3. If neither exists, show blank / “—” in UI.

### Flash time

- Keep / harden enrichment from detailed `lsfcconsistgrp` and member map `start_time` when concise list omits flash time.
- Display raw array timestamp when present; “—” only when enrichment finds nothing.

### Export

- Require ≥1 checked row; status hint otherwise (“Select at least one CG to export.”).
- Require prior Refresh / cache; status hint otherwise.
- `POST /api/contingency-groups/fc-cg-summary/export-selected` with selected `row_key`s; multi-sheet workbook; sheet titles from card-name site.
- Reject zero matching keys (existing guard).

## Architecture

| Piece | Responsibility |
|-------|----------------|
| `launchpad/snapcopy_summary_page.py` (new) | HTML/CSS/JS for Snapcopy Summary |
| `launchpad/health_server.py` | Serve page; adjust live-scan row fields (site, policy, host for links) |
| `launchpad/contingency_groups.py` | Remove embedded summary; add Snapcopy Summary button |
| `launchpad/fc_cg_summary.py` / ops | Policy composition with schedule label; flash enrichment as needed |
| `launchpad/fc_cg_summary_export.py` | Unchanged multi-sheet contract (site = card name) |
| `launchpad/config.py` | `1.6.86` |
| Tests | Page markers, scan field cleanup, export, version |

Reuse existing routes:

- `GET /api/contingency-groups/fc-cg-summary/live`
- `POST /api/contingency-groups/fc-cg-summary/export-selected`

## Error handling

- Locked: live scan fails with unlock error (403).
- Per-card inventory errors: appear in `errors[]`; other sites still load.
- Export empty selection / no cache / no matching keys: 400/404 with clear message; UI surfaces status text.

## Testing

- Consistency Groups HTML: Snapcopy Summary button present; summary section markers absent.
- Snapcopy Summary page: route served; controls + export path markers; IP link uses `https://`.
- Live scan unit/API: `site` equals card name, not category; policy includes schedule label when schedule provided; flash_time from enrichment when group blank.
- Export: checked-only multi-sheet; empty selection / missing cache / unknown keys rejected.
- `APP_VERSION == "1.6.86"`.

## Out of scope follow-ups

- Optional `http://` fallback if HTTPS GUI fails (operators can edit URL).
- Dashboard shortcut.
- Auto-select all on Refresh.
