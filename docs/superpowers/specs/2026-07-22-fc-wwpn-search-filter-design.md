# FC WWPN Report — Search + WAG Include Filters

**Date:** 2026-07-22  
**Status:** Approved for implementation  
**App version target:** next patch on the implementation branch  
**Depends on:** FC WWPN Report UI (`fc_wwpn_report.py`); Snapshot Schedule include-bar pattern (`site_group` / `filter_cards_by_groups`); `/api/fc-wwpn-export`  
**Approach:** Client-side search + include filters; Excel respects include groups via query params (Approach 1)

## Problem

Operators on the FC WWPN Report need to find the right site by WWPN, remote/fabric WWPN, host name, or volume name. Today there is no search — only a Contingency-group dropdown. They also need the Snapshot Schedule **Include in list / Excel** bar (WAG1 / WAG2 / Other sites) so they can hide WAG1/WAG2 (or other sites) from the on-screen report and from Excel export. That bar is missing from FC WWPN.

## Goals

- Add one search box on FC WWPN that matches local port WWPNs, remote/fabric WWPNs, host names, and mapped volume names.
- Hide non-matching sites; scroll/highlight the first match; show a showing-count status.
- Add WAG1 / WAG2 / Other sites include checkboxes (same labels/hint as Snapshot Schedule); all checked by default.
- Excel export respects the include bar via `groups=` query params (same semantics as Snapshot Schedule export).
- Keep existing Contingency-group filter; combine with include bar and search.

## Non-goals (v1)

- Capacity Report or other web reports (follow-up).
- Server-side search API.
- Filtering Excel by the search text (search is screen-only in v1).
- Changing how WAG1/WAG2 membership is detected beyond reusing `site_group()`.
- Changing Refresh On Sites behavior (still refreshes monitored SVC/FC sites; filters apply to display/export of already-loaded data).

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Scope | FC WWPN Report only |
| Search UX | One box; hide non-matches; highlight first match |
| Include bar | Screen **and** Excel |
| Search vs Excel | Search does **not** filter Excel in v1 |
| Grouping | Reuse Snapshot Schedule `site_group` / `filter_cards_by_groups` |

## Behavior

### Include bar

- UI: “Include in list / Excel” with checkboxes **WAG1**, **WAG2**, **Other sites**, all checked by default.
- Hint: “Uncheck a group to hide it from the schedule and export.” (or FC-specific equivalent: “…from the report and export.” — prefer report wording on this page).
- A card belongs to `wag1` / `wag2` / `other` via existing `site_group(card)` (haystack over name, category, host, model, device_profile).
- Unchecking a group hides those sites from the rendered list.
- If all groups are unchecked, the list is empty (same empty-set semantics as Snapshot Schedule).

### Search

- One text input; placeholder e.g. `Search WWPN, remote WWPN, host, or volume…`.
- Case-insensitive substring match.
- WWPN comparison normalizes by stripping spaces/colons and uppercasing (query and haystack).
- A site matches if **any** of the following contains the query (after WWPN normalize where applicable):
  - Local FC port WWPNs on the card
  - Host WWPNs / fabric remote WWPNs present in FC inventory for that card
  - Host names
  - Mapped volume / vdisk names
- Empty query: no search filter (all sites that pass other filters remain).
- Non-matching sites are hidden; first matching site scrolls into view and receives a temporary highlight class.
- Status reflects visibility, e.g. `Showing 2 of 14 site(s)` and, when searching, a short match note if useful.

### Combined visibility

A site is shown only if it passes **all** active filters:

1. Include bar group membership  
2. Search query (if non-empty)  
3. Existing Contingency-group filter (when a group is selected)

Filters do not mutate stored card/FC data.

### Excel export

- Export button builds `/api/fc-wwpn-export?open=1&groups=…` from checked boxes (`wag1`, `wag2`, `other`, comma-separated), mirroring Snapshot Schedule.
- Server filters the card list with `filter_cards_by_groups` before `build_fc_wwpn_workbook`.
- Filename may include a group label when a subset is selected (optional polish; not required if existing stamp-only name is kept).
- Search text is **not** applied to Excel in v1.

## Architecture

| Piece | Responsibility |
|-------|----------------|
| `launchpad/fc_wwpn_report.py` | Include bar + search UI; client-side filter/render; Excel URL with `groups` |
| `launchpad/health_server.py` (`/api/fc-wwpn-export`) | Parse `groups`; filter cards; build workbook |
| `launchpad/snapshot_schedule_export.py` | Reuse `site_group` / `filter_cards_by_groups` (import; do not duplicate rules) |
| Optional small helper in `fc_wwpn_report` JS or a tiny Python unit for normalize/match if extracted for tests | Search matching |

Prefer extracting a tiny pure JS-callable pattern in-page (or a Python helper used only if export ever needs search later). For v1, matching lives in the report page JS with page tests asserting wiring; add a focused unit for normalize/match if a shared Python helper is introduced for clarity.

## Testing

- FC WWPN page HTML/JS contains Include bar ids/labels and a search input.
- Export with `groups=wag1` only includes cards classified as wag1.
- Export with empty/all-unchecked groups yields empty workbook card set / empty sheets consistent with filter semantics.
- Matcher cases (if helper extracted): WWPN with and without colons; host name; volume name; empty query matches all.
- Contingency-group filter still applied when a group is selected (regression smoke via existing page behavior).

## Out of scope follow-ups

- Same include bar on Capacity Report and other web reports.
- Search-filtered Excel export.
- Shared report chrome component across all reports.
- `lsfcmap`-style smarter identity matching.
