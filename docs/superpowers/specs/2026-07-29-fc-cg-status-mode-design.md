# FlashCopy CGs Status Mode (Multi-Site Tabs + Excel)

**Date:** 2026-07-29  
**Status:** Approved for implementation  
**App version target:** 1.6.80  
**Depends on:** FlashCopy Consistency Groups page (`/fc-consistgrp`), HealthServer unlock/live SSH, monitor-on FlashSystem/SVC cards  
**Approach:** Dual mode on existing FlashCopy CGs page — Manage | Status (Approach 1)  
**Base branch:** `feature/contingency-groups`

## Problem

Operators use the IBM GUI Consistency Groups list to see which FlashCopy CGs are **Idle or Copied**, **Stopped**, or **Copying**, often across many sites. LaunchPad’s FlashCopy CGs page today is single-array manage-focused and has no status tabs or status-filtered Excel export across sites.

## Goals

- Add a **Status** mode on `/fc-consistgrp` beside existing **Manage** mode.
- Status mode: site filter (**All** / None meaning all sites) + Refresh live across eligible FlashSystem cards.
- Tabs: **All** | **Idle or Copied** | **Stopped** | **Copying**.
- **Export Excel** exports only the rows visible on the **active tab**.
- Bump `APP_VERSION` to **1.6.80**.

## Non-goals

- Stand-alone maps (“Not in a Group”) in Status mode.
- Row checkboxes / selective export (current-tab export only).
- Start/stop/delete CG actions from Status mode.
- HPE / DS8884 collectors.
- Changing Manage-mode create/assign/remove/start/delete behavior (aside from mode toggle visibility).
- Dark-theme link contrast, Call Home fallback, firmware seed UX (separate slices).

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Placement | Enhance existing FlashCopy CGs page |
| Architecture | Dual mode: Manage \| Status |
| Site scope | Site filter or All sites; scan eligible FlashSystem/SVC cards |
| Tabs | All / Idle or Copied / Stopped / Copying |
| Export | Excel = current tab’s rows only |
| Row grain | One row per CG per card |

## Behavior

### Mode toggle

- **Manage** — current single-array picker, inventory tables, Preview→Run mutations.
- **Status** — multi-card live scan UI; hide manage mutation sections while Status is active (or leave them hidden behind Manage).

Default: Manage (unchanged for existing operators) unless deep-link query later (optional, not required).

### Status mode controls

- Site `<select>`: empty/None = all sites; otherwise filter cards by site.
- **Refresh live** — requires LaunchPad unlock; scans monitor-on eligible cards.
- **Export Excel** — downloads workbook from last successful Status scan, filtered to the active tab; if no scan yet, prompt to Refresh first.

### Status tabs and bucketing

Normalize `lsfcconsistgrp` status (case-insensitive, trim):

| Bucket (tab) | Match examples |
|--------------|----------------|
| Idle or Copied | `idle_or_copied`, `idle or copied`, GUI “Idle or Copied” |
| Stopped | `stopped` |
| Copying | `copying` |
| All | every CG row |

Unknown/other statuses appear under **All** only; raw Status column still shows the array value.

### Table columns

| Column | Source |
|--------|--------|
| Site | Health card site |
| Card | Card name |
| Host | Card host/IP |
| CG name | `lsfcconsistgrp` name |
| Status | Raw status string |
| Maps | Map count when available |
| Flash time | When available on CG record; else blank |
| Error | Per-card collect error if any |

Sort: Site, Card, CG name (A–Z).

### Collectors

For each eligible monitor-on FlashSystem/SVC card in scope:

1. Run `svcinfo lsfcconsistgrp -delim :` (fallback without `-delim` as today).
2. Parse with existing `parse_lsfcconsistgrp` (extend only if Flash time needs an extra field already present in output).
3. Emit one Status row per CG.
4. On SSH/parse failure for a card: record error for that card and continue others (do not abort the whole scan).

No mutation commands in Status mode.

### Export

- Format: `.xlsx`
- Sheet name: `FC CG Status` (or equivalent short name)
- Columns match the Status table
- Row set = active tab filter applied to cached Status scan payload

## Architecture

- `launchpad/fc_consistgrp.py` — mode toggle, Status panel (site, refresh, tabs, table, export), JS filter/render
- `launchpad/health_server.py` — multi-card Status live scan API + export API; reuse card eligibility used by FlashCopy CGs
- `launchpad/fc_consistgrp_ops.py` (or small helper) — status bucket normalizer; optional Flash time field passthrough
- Cache last Status scan on the server (or session) for export, similar to System Connectivity

## Tests

- Unit: status bucketing for Idle or Copied / Stopped / Copying / unknown→All only
- Page: Manage/Status mode markers; status tab labels; export control present in Status mode
- API/export: filtered rows for active tab; Excel sheet/columns
- Version assert `1.6.80`

## Follow-up (out of scope)

1. Stand-alone map status view.
2. Checkbox multi-select export.
3. Status actions (start/stop) with Preview→Run.
4. Deep-link `?mode=status`.
