# Health Dashboard Excel — Per-Site Tabs + Section Toggles — Design

**Date:** 2026-08-04  
**Status:** Approved  
**App version target:** 1.6.110+  
**Depends on:**
- Health Dashboard HTML / `Export Excel` (`DASHBOARD_HTML` in `health_server.py`)
- Existing thin export (`launchpad/health_excel_export.py`, `GET /api/health-export`)
- Card payloads with `health_issues` and `command_results` (label, command, summary/output, error)
- Print/PDF selection (`printSelectedIds`) and Site filter (`card_id`)

## Problem

Health **Export Excel** only writes a single **Summary** sheet (card, host, monitor, status, issue count). Operators need a richer workbook: **one tab per selected site** with issues and command results, and **section toggles** so Summary / Issues / Command summaries / Raw output can be turned on or off before export.

## Goals

- Keep the existing **Export Excel** button as the export entry point.
- Add four **section toggles** on the Health Dashboard (persist in `localStorage`):
  - **Summary** — default **on**
  - **Issues** — default **on**
  - **Command summaries** — default **on**
  - **Raw output** — default **off** (large files)
- Build a workbook that includes:
  - Optional **Summary** sheet (today’s columns) when Summary is on.
  - **One sheet per selected site** with the enabled detail sections (Issues, Command summaries, Raw output).
- Site selection for detail tabs matches Print/PDF: checked PDF sites, or the single Site filter when a site is chosen.
- Pass section flags on `/api/health-export` so the server builds only what was requested.

## Non-goals (v1)

- Capacity / pool detail sheets inside Health Excel (Capacity Report / Dell Report cover that).
- Changing Print / Save PDF behavior.
- Admin global kill-switch for Health Excel.
- Live SSH refresh as part of Excel export (use data already on the dashboard cards).
- Perfect sheet-name uniqueness beyond Excel-safe truncation + disambiguation suffix.

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Per-site content | **A** — Issues + command results (summaries / optional raw) |
| Toggles | **A** — Summary · Issues · Command summaries · Raw output |
| Which sites get tabs | **A** — PDF selection, or Site filter if one site selected |
| Entry point | Existing **Export Excel** (Approach **1**) |
| Defaults | Summary / Issues / Command summaries **on**; Raw output **off** |

## Behavior

### UI

- Beside **Export Excel**, show four checkboxes (compact toggle row) with the labels above.
- Persist each preference in `localStorage` (e.g. `launchpad.healthExcel.summary`, `.issues`, `.commandSummaries`, `.rawOutput`).
- On Export Excel click:
  1. Resolve site IDs the same way as Print (site filter wins if set; else PDF-checked set).
  2. If no sites and Site filter is “all” and PDF set is empty: show a clear status/alert (e.g. “Select PDF sites or pick a site before exporting detail tabs”) **or** export Summary-only when Summary is on and no detail sites — **prefer**: if Summary on and no sites selected → Summary-only workbook; if Summary off and no sites → error message.
  3. Call `/api/health-export` with `card_id` list (or omit for all summary cards when Summary-only), plus query/body flags for sections, and `open=1` as today.

### Workbook structure

1. **Summary** sheet (if enabled): existing `HEALTH_SUMMARY_HEADERS` / styling for the cards in scope (selected sites if any; else all listed cards for summary-only export).
2. **Per-site sheets** (one per selected site ID), Excel-safe title from card name (max ~31 chars; disambiguate duplicates with ` (2)` etc.):
   - Header block: card name, host, profile/model, monitor on/off.
   - **Issues** (if on): severity, category, message (and server if present).
   - **Commands** (if Command summaries and/or Raw on): for each `command_results` item:
     - Label, command, error (if any).
     - Summary line when Command summaries on (use existing summarized text if available on the payload; else first-line / `summarize_command_output` server-side).
     - Raw output when Raw on (full `output` text; truncate extremely long cells only if Excel cell limits require it, with a clear “(truncated)” note).

### API

- Extend `GET /api/health-export` (or POST if query length is a concern for many `card_id`s) to accept:
  - `summary=0|1`, `issues=0|1`, `command_summaries=0|1`, `raw=0|1`
  - Site scope: existing `card_id=` for one site; add repeated `card_id=` or `card_ids=1,2,3` for multi-select detail tabs.
- When only Summary is requested and no detail sites: keep current summary behavior.
- When detail sites requested but all detail flags off: still create site sheets with header-only, or skip site sheets — **prefer skip site sheets** and keep Summary if on; if nothing would be written, return 400 with a clear error.

### Empty / edge cases

| Case | Result |
|------|--------|
| No PDF selection, Site = All, Summary on | Summary-only workbook (all cards) |
| No PDF selection, Site = All, Summary off | Error: select sites or enable Summary |
| Site filter set | That one site’s tab (+ Summary filtered to that site if Summary on) |
| Card missing command_results | Site sheet still created; commands section empty / “No command data” |
| Sheet name collision | Suffix ` (2)`, ` (3)`, … |

## Architecture

| Piece | Responsibility |
|-------|----------------|
| `launchpad/health_excel_export.py` | Extend builder: section flags, per-site sheets, safe sheet names |
| `launchpad/health_server.py` (`DASHBOARD_HTML` + `/api/health-export`) | Toggles UI, selection → query params, API parsing |
| Tests | Section flags, multi-site sheets, Summary-only, empty selection error, defaults |

## Testing

- Unit: workbook with Summary + two site sheets; Issues rows; command summary without raw; raw included when flag on.
- Unit: sheet name sanitization / collision.
- Page markers: toggle ids present; Export Excel passes section query params.
- API: Summary-only; selected sites; 400 when nothing to export.
- `APP_VERSION` bump on ship.

## Out of scope follow-ups

- Capacity/pool sections inside Health Excel.
- Admin disable for Health Excel.
- Refresh-on-export live SSH.
- CSV ZIP variant of the detailed export.
