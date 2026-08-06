# Site Lookup — offline inventory snapshots

**Date:** 2026-08-06  
**Status:** Approved  
**App version target:** next patch after tip (1.6.129+)  
**Depends on:** Site Lookup page/API; HealthServer settings backend; existing `lun_offline_inventory`  
**Approach:** Dedicated Site Lookup disk snapshots + fall back to LUN offline inventory for hosts/volumes when Site Lookup snapshot is missing

## Problem

Site Lookup Live Refresh leaves inventory in **HealthServer memory** only. After LaunchPad restarts, or when an array is unreachable and no in-memory card data remains, operators cannot browse the last known inventory. They want offline retrieval via Site Lookup snapshots **and** continued use of LUN Builder offline inventory.

## Goals

- On each **successful** Site Lookup Live Refresh, persist a per-card **Site Lookup** snapshot to disk.
- Keep existing **LUN offline inventory** writes on successful/failed monitor/`refresh_card` for eligible SVC profiles (unchanged format).
- When selecting a site, prefer (in order):
  1. In-memory card inventory (`source: "cache"`)
  2. Else Site Lookup disk snapshot (`source: "offline"`)
  3. Else LUN offline inventory hosts/volumes for that card (`source: "offline_lun"`) when present
  4. Else empty / “no cached inventory”
- When Live Refresh **fails**, do not overwrite the last good Site Lookup snapshot; LUN offline error recording stays as today.
- Label disk-backed views clearly (Offline vs Offline LUN + last refreshed time).
- Survive LaunchPad restart (same machine, unlocked settings backend).

## Non-goals (v1)

- Changing LUN offline inventory schema or eligibility rules.
- Merging the two stores into one format.
- Syncing snapshots across machines or exporting Tempe HTML packs.
- Auto Live Refresh on a schedule.
- Editing inventory offline.
- Guaranteeing persists when LaunchPad is locked — best-effort skip.

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Site Lookup storage | Dedicated settings key `site_lookup_offline_inventory` |
| LUN offline storage | Keep existing `lun_offline_inventory` (write path unchanged) |
| Site Lookup write trigger | Successful **`refresh_site_lookup`** only |
| Failed Site Lookup refresh | Do **not** clobber Site Lookup snapshot |
| Read path | Memory → Site Lookup offline → LUN offline → empty |
| Site Lookup snapshot scope | card meta, hosts, volumes, mappings, consistency_groups, pools, refreshed_at |
| UI | Badges for `offline` and `offline_lun` distinct from `cache` / live |

## Behavior

### Persist (Site Lookup)

- After successful `refresh_site_lookup` payload, upsert into `site_lookup_offline_inventory` keyed by `card_id`.
- If `_set_setting` missing, skip persist silently.

### Persist (LUN)

- Unchanged: `refresh_card` → `upsert_lun_offline_inventory_from_card` for eligible SVC + monitor-on cards.
- Successful Site Lookup Live Refresh already calls `refresh_card`, so LUN offline continues to update for those cards when eligible.

### Load

- `site_lookup_cache(card_id)`:
  1. Memory via `payload_from_card_cache`; if usable inventory → return (`cache`).
  2. Else Site Lookup disk snapshot → return (`offline`).
  3. Else LUN offline snapshot for card → shape hosts/volumes into Site Lookup payload (`offline_lun`); mappings/pools/CGs empty unless already on that LUN snapshot shape.
  4. Else empty cache payload.

Usable inventory = any of hosts, volumes, mappings, pools, consistency_groups non-empty.

### Live Refresh failure

- UI keeps previous on-screen data.
- Site Lookup disk store untouched.
- LUN offline may record `last_error` via existing refresh_card path (no change).

### UI

- `source === "offline"` → badge “Offline”
- `source === "offline_lun"` → badge “Offline LUN”
- Show `refreshed_at` / LUN `updated_at` when present.
- Live Refresh stays enabled.

## Components

| Piece | Change |
|-------|--------|
| `launchpad/site_lookup_offline.py` | Site Lookup store normalize/upsert/load |
| `launchpad/site_lookup_data.py` | `payload_from_offline_snapshot`; `payload_from_lun_offline`; `payload_has_inventory` |
| `launchpad/health_server.py` | Persist after live success; cache fallback chain |
| `launchpad/site_lookup.py` | Badges/status for `offline` / `offline_lun` |
| Tests | Persist, fallbacks, failure does not clobber; LUN fallback |
| `launchpad/config.py` | Version bump on ship |

## Testing

- Successful Live Refresh writes Site Lookup snapshot; readable after clearing memory.
- Failed Live Refresh leaves Site Lookup snapshot intact.
- Cache returns `offline` when memory empty and Site Lookup snapshot exists.
- Cache returns `offline_lun` when memory + Site Lookup empty but LUN offline has hosts/volumes.
- UI recognizes both offline sources.

## Out of scope reminders

Do not rewrite LUN offline format. Contingency CG fallbacks on live/cache remain as today; Site Lookup offline snapshots store the CG list from the successful live payload.
