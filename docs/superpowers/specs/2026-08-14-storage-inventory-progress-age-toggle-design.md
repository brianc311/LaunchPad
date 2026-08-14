# Storage Inventory live progress and Recent / Older / All

**Date:** 2026-08-14  
**Status:** Approved for implementation  
**App version target:** 1.6.169  
**Depends on:** Storage Inventory site cards (1.6.168), `health_alert_state.visible_health_issues` / Active issues since date (default 2026-08-14)  
**Approach:** Poll scan progress during the existing live request; split Issues / Notes into recent vs older using the Health alert cutoff; page toggle Recent | Older | All  
**Base branch:** `main` (1.6.168)

## Problem

Refresh live only shows **Scanning live…** with no count, so a long fleet scan looks stuck. Storage Inventory Issues / Notes still includes leftover Health alerts from before **2026-08-14** that operators already treated as fixed. They need a **Recent / Older / All** view so the default page is current work only.

## Goals

- Real live-scan progress: bar plus **`done / total arrays · current site`**.
- Three-way toggle **Recent | Older | All** next to Site (default **Recent**).
- Recent hides leftover Health alerts (same cutoff/rules as Active issues since date) but still shows live config / this-scan problems.
- Site colors, nested Issues / Notes, and **Devices with Issues** follow the toggle.
- Bump `APP_VERSION` to **1.6.169**.

## Non-goals

- Changing Excel layout, columns, or red-row fill (export stays full **All** notes).
- Changing collectors, eligibility, or site-card collapse/color CSS rules (except which notes feed color).
- Persist the toggle across reload (session default is Recent each load).
- Per-array live HTTP requests from the browser.
- Fake/indeterminate-only progress.
- Changing Admin Branding date/limit UI.

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Age filter | Recent / Older / All using Active issues since date (default 2026-08-14) |
| Config gaps on Recent | Still show (Phone Home / SMTP / Data Protection / DNS / NTP / scan errors) |
| Health alerts | Split with `visible_health_issues` / `issue_is_visible` (same as Health Dashboard) |
| Progress | Real N/M as each array finishes |
| Scan model | One live request; page polls progress in parallel (`ThreadingHTTPServer`) |
| Default toggle | Recent |
| Excel | Unchanged (full `issues` column) |

## Behavior

### Progress

On **Refresh live**:

1. Disable the button.
2. Show a progress bar at 0 and status **`0 / N arrays`** (N = eligible cards; if unknown yet, **Scanning live…** until the first progress payload).
3. `GET /api/storage-inventory/live` runs as today (unlock required; 403 if locked — no bar, show unlock message).
4. In parallel, poll `GET /api/storage-inventory/progress` (~400ms) and set bar to `done / total`, label **`{done} / {total} arrays · {current}`**.
5. When live returns, stop polling, hide the bar, apply payload, re-enable the button.

A second click while a scan is running is ignored (button already disabled). Progress state is reset at scan start. If the live request fails, hide the bar and show the error.

The scan loop publishes after each card: `done` (cards finished), `total`, `current` (site/host being scanned or last finished), `running`.

### Toggle

Hero control next to Site: **Recent | Older | All**. Default **Recent**. Changing it re-renders cards from the current cache (no new scan).

### Note split

When building an inventory row, keep `issues` as today (config notes + all Health alert messages + extras) for Excel.

Also set:

- `issues_recent` — config/this-scan notes + Health messages that `issue_is_visible` would show
- `issues_older` — Health messages that would be hidden on the Health Dashboard (leftover / grandfathered / first seen before cutoff)

If Admin **Limit new issues** is Off, every Health message is recent; `issues_older` is empty; Recent and All match.

Page display:

| Toggle | Notes used for Issues / Notes, site color, and Devices with Issues |
|--------|---------------------------------------------------------------------|
| Recent | `issues_recent` |
| Older | `issues_older` |
| All | `issues` |

`row_has_issues` for color/totals on the page uses the active notes string (non-empty). Orange `unknown` still uses Phone Home / Data Protection / SMTP cells (unchanged). A site can be red on All and green on Recent.

Hide the nested Issues / Notes block when the active notes set is empty.

### Cache

Cache payload includes the new fields on each row. Loading cache applies the current toggle (default Recent).

## Architecture

| Unit | Responsibility |
|------|----------------|
| `launchpad/storage_inventory.py` | Split helper: given config-driven notes + health issue lists → `issues`, `issues_recent`, `issues_older`. Do not change Excel. |
| `launchpad/health_alert_state.py` | Reuse `visible_health_issues` / `issue_is_visible` / cutoff. No new Admin settings. |
| `launchpad/health_server.py` | During `scan_storage_inventory_live`, publish progress; serve `GET /api/storage-inventory/progress`; pass Health visibility into row build. |
| `launchpad/storage_inventory_page.py` | Toggle UI, progress bar, poll, render notes from the selected field. |
| Tests + version pins | Split rules, progress JSON, page markers; `APP_VERSION` **1.6.169**. |

`GET /api/storage-inventory/progress` JSON:

```json
{
  "running": false,
  "done": 0,
  "total": 0,
  "current": ""
}
```

Idle (no scan): `running` false, counts 0. Do not require unlock for progress (so the bar can update); live still requires unlock.

Quote JS `class="..."` with single-quoted strings (same class of bug as 1.6.166 `row-issue`).

## Testing

- Split: config-only → recent; leftover Health only → older; mixed → both fields; limit Off → older empty.
- Progress: after N cards, `done == N`; `running` true during scan (unit with a fake publisher is enough).
- Page: `Recent`, `Older`, `All` controls; progress element ids; poll `/api/storage-inventory/progress`; default Recent.
- Existing Excel tests still see a single Issues / Notes column from `issues`.
- Version pin **1.6.169**.

## Version

Bump `APP_VERSION` to **1.6.169** when this ships.
