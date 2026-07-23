# FC WWPN Report — Site Picker (Replace Contingency Group Filter)

**Date:** 2026-07-23  
**Status:** Approved for implementation  
**App version target:** next patch on the implementation branch  
**Depends on:** FC WWPN Report (`fc_wwpn_report.py`); `/api/fc-wwpn-export`  
**Approach:** Client site filter + optional card-scoped Excel export (Approach 1)  
**Base branch:** `feature/contingency-groups` (or tip that includes FC WWPN)

## Problem

The FC WWPN Report dropdown is labeled like a site control but is a **Contingency group** filter: it keeps all cards and strips host/WWPN/LUN rows that do not match the selected Contingency Group. Operators expect **Hartford, CT → show only that site’s card** and **None → show all**. Contingency-group filtering here usually yields empty-looking results and confuses users. The grey “Contingency group” text is a label, not a button (the **Contingency Groups** nav button already exists).

## Goals

- Replace the Contingency-group dropdown with a **Site** picker.
- **None** shows all SVC/FlashSystem site cards; selecting a site shows only that card.
- **Export Excel** exports the selected site only when a site is selected; **None** exports all (same as on-screen).
- Keep the **Contingency Groups** navigation button; remove Contingency-group filtering from this page.

## Non-goals (v1)

- Re-adding Contingency-group filtering on FC WWPN (even as Advanced).
- Changing Refresh On Sites behavior.
- Capacity Report or other pages.
- Making the Site label into a second Contingency Groups button.

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Site picker | Yes — Hartford → that card only; None → all |
| Contingency-group filter | **A** — replace (remove from this page) |
| Implementation | Client site filter (Approach 1) |
| Excel | Follow on-screen selection (selected site only, or all if None) |

## Behavior

### Site dropdown

- Label: **Site**.
- First option: **None** (value empty) = show all sites.
- Remaining options: one per SVC/FlashSystem-like card in the loaded list, by **card name**, sorted A–Z; option value = card id (string/number as used by the page).
- On change: re-render so only the selected card’s section appears (or all if None).
- Status may note the filter, e.g. `Showing 1 of 16 site(s)` when filtered (optional polish; not required if existing status text remains clear).
- Optional URL sync: `?site=<card_id>` so a deep link opens filtered (nice-to-have; include if low cost).

### Removed

- Contingency group `<select>` and all `filterCardByGroup` / groups-cache wiring used only for that filter.
- Do not load Contingency Groups solely to populate this dropdown.

### Navigation

- Keep **Contingency Groups** button → `/contingency-groups`.

### Excel export

- When Site is **None**: export all FC-eligible cards (current default).
- When a site is selected: pass `card_id` (or `card_name`) on `/api/fc-wwpn-export` and build the workbook from that card only.
- If WAG include-bar / `groups=` already exists on the tip being built from, keep that behavior and apply site filter in addition; if not present on base tip, do not invent it in this change.

## Architecture

| Piece | Responsibility |
|-------|----------------|
| `launchpad/fc_wwpn_report.py` | Site picker UI; filter cards in `render()`; Excel fetch includes selected card query param |
| `launchpad/health_server.py` (`/api/fc-wwpn-export`) | Optional `card_id` / `card_name` query; filter card list before workbook |
| Tests | Page strings/wiring; export filters to one card when requested |

## Testing

- Page HTML/JS: label **Site**, option **None**, no Contingency-group filter select wiring / `filterCardByGroup` for CG.
- Selecting a site id leaves one card in the rendered set; None leaves all SVC-like cards.
- Export with `card_id` (or name) includes only that card’s rows; omit param = all.

## Out of scope follow-ups

- Dual controls (Site + Contingency group).
- Server-side site list API separate from `/api/cards`.
