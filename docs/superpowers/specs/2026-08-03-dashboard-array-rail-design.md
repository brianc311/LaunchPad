# Connection Dashboard Array Rail — Design

**Date:** 2026-08-03  
**Status:** Approved  
**Integration branch:** `feature/contingency-groups`  
**Depends on:**
- Connection Dashboard (`launchpad/ui/dashboard_view.py`)
- Open GUI URL resolution (`resolve_gui_url` in `host_volume_health.py` — Admin URL, else `https://{host}`)
- Existing dashboard Category filter + search (visible card set)
- Settings persistence for UI prefs

## Problem

Operators open array web GUIs from LaunchPad but today that means finding the card in the grid and using Connect/URL actions. On FlashCopy Consistency Groups, Open GUI is separate. For the **Connection Dashboard**, operators want a **collapsible side menu** of arrays so they can pick a site and open its GUI quickly without changing card selection or SSH Connect.

## Goals

- Collapsible **left rail** on the Connection Dashboard listing arrays.
- Click a row → **Open GUI only** (browser), using `resolve_gui_url` (URL preferred, else host).
- Rail list follows the **same Category + search filter** as the card grid.
- Remember collapsed/expanded across restarts.
- Leave Connect, Monitor, selection, and browser Health pages unchanged.

## Non-goals

- Side rail on FlashCopy Consistency Groups, Capacity, or other Health browser pages.
- Selecting/highlighting cards from the rail.
- SSH Connect from the rail.
- Replacing the card grid or category dropdown.

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Where | Connection Dashboard only |
| Click action | Open GUI only |
| Which sites | Same as current dashboard filter (Category + search) |
| Approach | Collapsible left rail beside the card grid |

## Layout & behavior

- Main body becomes `[array rail | card scroll area]`.
- Expanded rail: scrollable list of site name + host (compact).
- Collapsed: thin strip / toggle (e.g. « / Arrays) so cards reclaim width.
- Click row → open GUI via existing Open GUI path (`resolve_gui_url` + webbrowser).
- No Host and no URL → muted row; click shows a short status message (set Host or URL in Admin); do not crash.
- Empty filtered set → “No arrays match.”
- Rebuild rail whenever Category or search changes (same source as visible cards).

## Persistence

- Setting key (proposed): `dashboard_array_rail_collapsed` (boolean; default expanded / `false`).

## Components

| Piece | Responsibility |
|-------|----------------|
| `dashboard_view.py` | Rail UI, collapse toggle, filter-synced list, click → open GUI |
| `resolve_gui_url` | Unchanged helper for URL vs host |
| Settings get/set | Persist collapsed state |

## Errors

- Unknown / missing card after refresh: rebuild list; ignore stale clicks.
- Open GUI failure: surface message in dashboard status (same style as other launch failures).

## Testing

- Rail lists the same cards as the filtered grid.
- Click invokes Open GUI with URL when set, else `https://{host}`.
- Collapse preference round-trips through settings.
- Cards with neither host nor URL do not open a browser.
- Connect / Monitor / selection behavior unchanged (regression markers or focused UI tests as practical for CustomTkinter).

## Out of scope follow-ups

- Shared rail on Health browser pages.
- Rail actions beyond Open GUI (Connect, Monitor).
- Keyboard navigation polish.
