# FC WWPN Report — Search + WAG Include Bar

**Date:** 2026-07-23  
**Status:** Approved for implementation  
**App version target:** next patch on the implementation branch  
**Depends on:** FC WWPN Site picker; mappings export; `site_group` / `filter_cards_by_groups`  
**Approach:** Client search first (drives Site picker) + server find fallback; WAG include bar (Approach 1 hybrid)  
**Base branch:** `feature/contingency-groups` (tip with Site picker + modal export + NPIV remote-WWPN fix)

## Problem

Operators need to find a WWPN (or remote WWPN / host / volume) and jump to the site that owns it. The Site picker alone requires knowing the site name. An older PR (#16) had search + WAG filters but was not merged into the combined tip; the current page has Site picker and no search box.

## Goals

- Search box on FC WWPN Report for **WWPN, remote WWPN, host name, and volume name**.
- On match: **set the Site picker** to that site and show only that card (status explains the hit).
- On no match: status **`WWPN not found — can't locate site`** (or equivalent when the query was host/volume text).
- **Hybrid find:** search loaded cards in the browser first; if none match, call **`GET /api/fc-wwpn-find`**.
- **WAG include bar** (WAG1 / WAG2 / Other, default all on) filters which sites appear in the list and in Excel — ready for when those site groups are used more.

## Non-goals (v1)

- Replacing the Site picker with Contingency-group filtering.
- Changing Refresh On Sites command set.
- Full-text search across command raw output beyond structured FC fields.

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| On match | **A** — set Site dropdown to the matching site |
| Match fields | WWPN + remote WWPN (normalized substring) **and** host + volume names |
| Find path | **A + B** — client first, then server `/api/fc-wwpn-find` |
| WAG bar | Include from PR #16 pattern (checkboxes; list + Excel) |

## Behavior

### Search UI

- Input near Site: placeholder `Search WWPN, remote WWPN, host, or volume…`; **Find** button; Enter runs search.
- Normalize WWPN queries: strip spaces and `:`, uppercase; substring match.
- Host / volume: case-insensitive substring on host names and volume / vdisk names (hosts, mappings, fabric host field).

### Match → Site picker

| Outcome | Behavior |
|---------|----------|
| One site (client or server) | Set Site to that card id; render that site; status `Found on {name}` |
| Several sites | Set Site to first match sorted A–Z by name; status `Found on {name} (also on N other site(s))` |
| None after client + server | Site → **None**; status `WWPN not found — can't locate site` (use a slightly broader “not found” wording if query was clearly non-WWPN text, e.g. `No matching site for “…”`) |
| Empty query | Do not run find; leave Site / WAG as-is |

Clearing the search box does not auto-reset Site.

### WAG include bar

- Checkboxes: **WAG1**, **WAG2**, **Other** (default checked).
- Filters SVC-like cards shown in the list using `site_group(card)` ∈ selected set.
- Site picker applies **after** WAG filter (pick one site among included groups).
- Excel (page-level `/api/fc-wwpn-export` and, if low cost, mappings export) passes `groups=wag1,wag2,other` style query like PR #16 / Snapshot Schedule.

### Server find API

```
GET /api/fc-wwpn-find?q=<query>
```

- Sync cards, run the same matcher over FC-eligible cards.
- Response: `{ "query": "...", "matches": [ { "id": <int>, "name": "..." }, ... ] }` sorted by name.
- Empty `q` → `400` `{ "error": "q required" }`.

## Architecture

| Piece | Responsibility |
|-------|----------------|
| `launchpad/fc_wwpn_search.py` (new) | Pure: normalize query; `card_matches_fc_query`; `find_cards_matching_fc_query` |
| `launchpad/fc_wwpn_report.py` | Search UI; client find → Site; miss → fetch find API; WAG bar; export `groups=` |
| `launchpad/fc_wwpn_export.py` / health export paths | Reuse or port `parse_fc_export_groups` + `filter_cards_by_groups` for Excel |
| `launchpad/health_server.py` | `GET /api/fc-wwpn-find`; ensure fc-wwpn-export honors `groups=` |
| `snapshot_schedule_export.py` | Unchanged helpers `site_group`, `filter_cards_by_groups` |
| Tests | Matcher; find API; page contracts (search, WAG, Site on find) |

## Testing

- Matcher: WWPN / remote / host / volume hits; normalization; no false positive on empty q.
- Find API: returns matching card ids; `q` required.
- Page HTML/JS: search control; Find sets Site; WAG checkboxes; export includes `groups`.

## Out of scope follow-ups

- Highlighting matching table rows inside the card (nice-to-have).
- Persisting last search in URL (`?q=`).
