# Site Lookup — Unified live inventory browser

**Date:** 2026-07-22  
**Status:** Approved for implementation  
**App version target:** next patch on the implementation branch  
**Depends on:** HealthServer report pages; `/api/cards`; SSH inventory parsers (`inventory_sync` / FC suite from SSH Inventory Sync); Contingency Groups store for CG fallback  
**Approach:** Hub + site detail tabs (Approach 1)

## Problem

Operators keep separate per-site HTML “Storage Site Lookup” snapshots (hosts, volumes, mappings, consistency groups). Those files differ in layout, go stale immediately, and do not scale when more sites are added. LaunchPad already has cards, SSH, and related reports, but no single place to browse live site inventory with search and multi-tab compare.

## Goals

- Add a **Site Lookup** HealthServer page opened from the desktop dashboard (same pattern as Capacity / FC WWPN).
- **Hub** with a dropdown of all FlashSystem / Storwize / SVC cards; **Open** loads that site in a **new browser tab**.
- **Detail** view with one shared UI: nameplate, live stats, tabs (Hosts / Volumes / Mappings / Consistency groups), and search over host and volume names.
- **Hybrid data:** paint from cached card/FC data first; **Refresh** pulls full inventory over live SSH.
- **CG rule:** prefer live CG data from Refresh; fall back to Contingency Groups for that card/hint when live CGs are empty.
- Adding sites later = registering Health Cards — no new HTML files per site.

## Non-goals (v1)

- Importing or shipping the Downloads `storage_site_lookup_*.html` files as the data source.
- System / nodes / FC ports / pools panels (Woodland Hills–style system tab) — deferred.
- HPE 3PAR / non–Spectrum Virtualize profiles in the dropdown.
- Editing inventory from Site Lookup (read-only browser).
- Auto-opening every site; global cross-site search spanning all cards at once.
- Fixing LUN Builder purpose-breakdown wall-of-text (separate follow-up).

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Surface | New LaunchPad page `/site-lookup` |
| Approach | Hub + detail in new tabs (Approach 1) |
| Data | Hybrid: cache first, SSH Refresh (Approach C) |
| Tabs | Hosts, Volumes, Mappings, Consistency groups + header stats |
| CGs | Live on Refresh; else Contingency Groups (Approach C) |
| Site list | All FlashSystem / Storwize / SVC cards (Approach A) |
| Static HTML packs | Not used |

## Behavior

### Hub (`/site-lookup`)

- Load `GET /api/cards`, filter to Spectrum Virtualize / FlashSystem family profiles (`SVC_PROFILES` or equivalent).
- Dropdown shows card name (host/model as secondary text when available).
- **Open** → `window.open('/site-lookup?card=<id>')` (new tab).
- Short hint that sites open in a new tab.

### Detail (`/site-lookup?card=<id>`)

- Resolve card by id; reject missing/invalid/non-SVC profiles with a friendly message and link to hub.
- **Nameplate:** card name, model badge, host (and serial when exposed by API).
- **Stats:** Hosts · Volumes · Mappings · Consistency groups — update after initial paint and after Refresh.
- **Tabs:** Hosts | Volumes | Mappings | Consistency groups — sticky-header tables; empty states when no rows or no filter matches.
- **Search:** one case-insensitive substring filter over **host names and volume names**; Mappings tab keeps rows that match host or volume name.
- **Refresh:** `POST /api/site-lookup/refresh` with `{ card_id }` → live SSH suite → replace in-page inventory and stats; show last-refreshed time; disable control while in-flight.
- Header links: back to hub; cross-links to Health / Capacity / FC WWPN consistent with other reports.

### Live SSH suite (Refresh)

Reuse inventory/sync parsers where possible (same commands as SSH Inventory Sync):

| Purpose | Command |
|---------|---------|
| Hosts | `svcinfo lshost -delim :` |
| Volumes | `svcinfo lsvdisk -delim :` |
| Maps | `svcinfo lshostvdiskmap -delim :` |
| CGs | `svcinfo lsconsistgrp -delim :` (and member detail if needed for the CG tab); on empty/unsupported → Contingency Groups fallback |

On Refresh **failure** (timeout, auth, unreachable): keep the last painted cached view; show an error banner; **do not** clear tables. Concurrent Refresh clicks are ignored while a request is in flight.

### Cached first paint

- Prefer existing card FC inventory (`fc_hosts`, `fc_mappings`, etc.) and any already-available volume/CG-shaped data from `/api/cards` or Contingency Groups.
- Stats may be partial until Refresh completes (e.g. volumes thinner than after SSH); UI must still be usable.

### Consistency groups

1. After successful Refresh, if live CG list is non-empty → use it for the CG tab and count.
2. Else load Contingency Groups sites matching the card hint / card name and show those groups/volumes/maps as available.
3. If both empty → CG tab empty state with a short explanation.

## Architecture

| Piece | Responsibility |
|-------|----------------|
| HealthServer route `GET /site-lookup` | Serve Site Lookup HTML (hub + detail modes) |
| `POST /api/site-lookup/refresh` | Card resolve → SSH suite → normalized payload |
| Shared inventory parsers | CLI → hosts / volumes / maps / CGs (reuse `inventory_sync` / FC parsers) |
| Contingency Groups store | Fallback CG payload by card hint |
| Dashboard | **Site Lookup** button → register cards → `open_site_lookup()` |
| `/api/cards` | Hub list + initial detail paint (expose serial in API if nameplate needs it) |

### Normalized detail payload (conceptual)

```text
{
  card: { id, name, host, model, serial? },
  stats: { hosts, volumes, mappings, cgs },
  hosts: [...],
  volumes: [...],
  mappings: [...],
  consistency_groups: [...],
  source: "cache" | "ssh" | "ssh+cg_fallback",
  refreshed_at: iso8601 | null,
  error: string | null
}
```

## UX notes

- One shared dark theme (Perrysburg / Anderson nameplate + stats + tabs). No per-site CSS forks.
- Read-only: no create/edit/delete of hosts or volumes from this page.
- Compare sites by opening multiple detail tabs from the hub.

## Testing

- Unit: profile filter for dropdown; payload normalization; CG fallback when live CGs empty.
- API: refresh success (mocked SSH); refresh failure returns error without wiping prior data shape; bad `card_id`.
- Smoke: hub lists cards; detail with `?card=` renders; search filters host and volume (and mapping) rows.
- No real-array requirement in CI.

## Out of scope follow-ups

- System / pools / FC ports tab.
- LUN Plan purpose-breakdown readability when every volume is its own purpose.
- Optional hide/show for noisy cards in the dropdown.
