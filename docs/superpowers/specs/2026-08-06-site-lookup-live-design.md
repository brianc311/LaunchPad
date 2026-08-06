# Site Lookup — Live Tempe-style browser

**Date:** 2026-08-06  
**Status:** Approved (operator); awaiting written-spec review  
**App version target:** next patch after tip (1.6.123+)  
**Supersedes for v1 scope:** `docs/superpowers/specs/2026-07-22-site-lookup-design.md` (hub/detail + SVC-only + no pools). Prefer this doc when they conflict.  
**Depends on:** HealthServer report pages; `/api/cards`; capacity scrapes / pool parsers; SSH inventory parsers (`inventory_sync` / FC suite); Contingency Groups store for CG fallback  
**Approach:** Host Tempe layout at `/site-lookup`; array picker = all LaunchPad SSH storage cards; Live Refresh = capacity/pools (A) + hosts/volumes/maps/CGs (B)

## Problem

Operators use static per-site HTML “Storage Site Lookup” files (e.g. Tempe) for hosts, volumes, consistency groups, and pools. Those files go stale, are not wired to LaunchPad cards, and cannot Live Refresh. LaunchPad already has cards, capacity scrapes, and host/volume SSH inventory, but no single Tempe-style page that covers **all arrays** with live data.

## Goals

- Dashboard **Site Lookup** button opens a HealthServer page (same pattern as Capacity / FC WWPN).
- Page path `/site-lookup` with **Tempe-like** dark layout: search/suggest, header nameplate + stats, tabs **Hosts / Volumes / Consistency Groups / Pools**.
- Array chooser lists **all LaunchPad SSH storage cards** (name + host).
- **Live Refresh** for the selected card:
  - **A:** header capacity context + **pools** from capacity scrap (fast path where available).
  - **B:** **hosts, volumes, mappings/CGs** (and port/WWPN enrichment when scrapes already provide them) via live SSH inventory suite.
- Status while refreshing; show last-updated time.
- Empty tabs with a short explanation when a vendor/profile cannot supply that data.
- Read-only browser — no inventing per-site static HTML packs.

## Non-goals (v1)

- Editing arrays, hosts, volumes, or pools from the lookup page.
- Pixel-perfect Tempe sample data for every site (layout/tabs match; live numbers differ).
- Shipping Downloads `storage_site_lookup_*.html` as the live data source.
- A separate System / Nodes / FC Ports top-level tab (port data may appear on host rows when available).
- Global cross-site search spanning all cards at once in one table.
- Auto-opening every site on launch.

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Surface | `/site-lookup` from dashboard button |
| Layout | Tempe-style (Approach 1) |
| Site list | **All** LaunchPad SSH storage cards |
| Live Refresh | **A and B** (capacity/pools + hosts/volumes/CGs/maps) |
| Tabs | Hosts · Volumes · Consistency Groups · Pools |
| Static HTML packs | Not used as data source |
| Edit inventory | No (read-only) |

## Behavior

### Entry

- Desktop dashboard button **Site Lookup** registers current cards and opens the browser to the Site Lookup URL (mirror Capacity / FC WWPN).
- Page shows search/suggest + array picker over `/api/cards` (all SSH storage cards with a usable id/name/host).

### Selecting a site

- Choosing a card (dropdown and/or search “Look Up”) paints the Tempe-style result: header (site name, system/model, online/degraded/unknown badge when known), stats row (hosts / volumes / pools counts; node count when available), tabs, tables/pool cards.
- Prefer a **fast first paint** from cached card/capacity/FC data when present; mark source as cache until Refresh succeeds.

### Live Refresh

- Control: **Live Refresh** (or **Refresh**) on the detail view.
- `POST /api/site-lookup/refresh` with `{ "card_id": "<id>" }`.
- Server runs, for that card:
  1. **A — capacity/pools:** reuse capacity / pool parsing already used by Capacity Report (and related scrapes). Fill Pools tab + any capacity bits on the header.
  2. **B — inventory:** reuse SSH inventory suite where the profile supports it (`lshost`, `lsvdisk`, `lshostvdiskmap`, `lsconsistgrp`, and related FC host/WWPN fields as available). Fill Hosts / Volumes / Consistency Groups (and mapping rows as the CG or volume tabs need).
- Disable the button while in flight; show progress/status text; set `refreshed_at` on success.
- On failure: keep last painted data; show error banner; **do not** clear tables.
- Concurrent Refresh for the same session is ignored or coalesced while one request is in flight.

### Consistency groups

1. After successful Refresh, if live CG list is non-empty → use it.
2. Else fall back to Contingency Groups for that card/hint when available.
3. Else empty state with a short explanation.

### Non–Spectrum Virtualize cards

- Still appear in the picker (all SSH cards).
- Refresh runs whatever A/B scrapes the profile supports (e.g. HPE pools/capacity may work; IBM DS/XIV may be thinner).
- Unsupported tabs show empty + “not available for this profile” (or similar).

### Search filter

- Case-insensitive substring over host names and volume names (and mapping/CG rows that reference matching host/volume names), matching Tempe’s filter spirit.

## Architecture

| Piece | Responsibility |
|-------|----------------|
| `launchpad/site_lookup.py` | `SITE_LOOKUP_PATH`, Tempe-adapted HTML/JS |
| `launchpad/site_lookup_data.py` | Pure helpers: card filter, cache→payload, SSH/capacity→payload, CG fallback, stats |
| HealthServer `GET /site-lookup` | Serve page |
| `POST /api/site-lookup/refresh` | Resolve card → A+B scrapes → normalized JSON |
| Capacity / pool parsers | Layer A |
| Inventory / FC parsers | Layer B |
| Contingency Groups store | CG fallback |
| Dashboard + `monitor.py` | Button → register cards → `open_site_lookup()` |

### Normalized payload (conceptual)

```text
{
  card: { id, name, host, model, profile, serial? },
  stats: { hosts, volumes, pools, nodes? },
  hosts: [...],
  volumes: [...],
  consistency_groups: [...],
  pools: [...],
  source: "cache" | "ssh" | "ssh+cg_fallback" | "partial",
  refreshed_at: iso8601 | null,
  error: string | null
}
```

## UX notes

- Dark theme aligned with Tempe (`--bg` / panel / accent), not a second visual language.
- Pool tab uses Tempe-style pool cards (name, bar, capacity figures) when data exists.
- **Locked UX:** one page with search/picker + in-place result (Tempe). Operators can open multiple browser windows/tabs of `/site-lookup` to compare sites; no separate hub→new-tab flow required in v1.

## Testing

- Unit: payload normalization; CG fallback; empty unsupported-profile tabs; pool shaping from capacity fixtures.
- API: refresh success (mocked SSH/capacity); failure keeps prior shape + error; bad `card_id`.
- Page: path `/site-lookup`; tabs Hosts/Volumes/Consistency Groups/Pools; Live Refresh wiring; dashboard open helper.
- No real-array requirement in CI.

## Success criteria

1. Dashboard opens Site Lookup in the browser.
2. All SSH storage cards appear in the picker.
3. Live Refresh fills pools (A) and hosts/volumes/CGs when scrapes succeed (B).
4. Tempe-like tabs and header; empty tabs explained when data missing.
5. Refresh failure does not wipe prior tables.

## Out of scope follow-ups

- Dedicated FC Ports / Nodes system tab.
- Editing or provisioning from Site Lookup.
- Offline Tempe demo pack mode.
