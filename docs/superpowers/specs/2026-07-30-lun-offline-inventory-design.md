# LUN Builder Offline Inventory — Design

**Date:** 2026-07-30  
**Status:** Approved  
**Integration branch:** `feature/contingency-groups`  
**Depends on:**
- LUN Builder (`lun_builds`, `lun_builder.py`, `lun_builder_data.py`)
- Health Monitor refresh / `HealthCard.command_results`
- Existing inventory parse helpers (`inventory_sync.py`, FC host/map parsers)
- Settings persistence via `database.py` / `HealthServer` get/set setting

## Problem

Operators use LUN Builder for site plans (especially Pendergrass GA, Hartford CT, Windsor WI) and also need to **see last-known array inventory when SSH is offline**. Today:

- Saved **plans** persist in `lun_builds`.
- Live hosts/WWPNs/volumes only stick after explicit Sync Inventory / Pull FC / Save into a build.
- Monitor refresh keeps inventory in process memory only — lost on restart and unavailable when the site is down.

## Goals

- Automatically keep a durable **offline inventory copy** for every Monitor-on SSH FlashSystem/SVC card.
- Update that copy when a Monitor refresh succeeds; leave the previous copy alone on failure.
- Keep LUN Builder **plan** data (`hosts` / `luns` in `lun_builds`) separate so planning work is never clobbered by inventory refresh.
- In LUN Builder, let the operator view **Plan** (editable) or **Inventory** (read-only offline/online snapshot) with a clear last-updated banner.

## Non-goals

- Auto-merging inventory rows into plan hosts/LUNs.
- Changing Sync Inventory, Pull FC, Import, Export, Preview, or Run Create semantics.
- Offline inventory for non-SSH or non-FlashSystem/SVC profiles.
- Replacing Contingency Groups or Volume Find caches.

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| What to store | **Both** plan (existing) and live inventory snapshot (new) |
| When to update inventory | **Auto on successful Monitor refresh** |
| Scope | **All Monitor-on FlashSystem/SVC cards** (create snapshot even if no LUN plan build exists) |
| Plan vs inventory | Separate stores; inventory never overwrites plan |
| UI | Plan \| Inventory toggle + offline/online last-updated banner |

## Approach

**Separate offline inventory store linked to cards/sites** (not Sync-into-build).

## Data model

### Existing: `lun_builds`

Unchanged. Editable plans (templates → Save as new, manual edits, Sync Inventory when operator chooses it).

### New settings key: `lun_offline_inventory`

JSON map or list keyed by `card_id`. One record per eligible card:

| Field | Notes |
|-------|--------|
| `card_id` | Health card id |
| `site_name` | Card name (e.g. `Pendergrass, GA`) |
| `host` | Management IP / hostname |
| `device_profile` | Profile key |
| `updated_at` | ISO timestamp of last **successful** inventory write |
| `hosts` | Parsed host / WWPN rows suitable for LUN Builder inventory view |
| `volumes` | Parsed volumes and/or host↔LUN map rows for read-only display |
| `last_error` | Optional; set on failed refresh without clearing good hosts/volumes |
| `last_error_at` | Optional ISO timestamp of last failed attempt |

Successful refresh **replaces** `hosts` / `volumes` / `updated_at` and clears `last_error`. Failed refresh updates only error fields.

## Behavior

1. After a successful Monitor refresh for a card that is Monitor-on + SSH + FlashSystem/SVC, parse inventory from that refresh’s command results (reuse existing parse/sync helpers where practical).
2. Upsert `lun_offline_inventory[card_id]`.
3. On failed refresh: do not wipe the prior snapshot; record `last_error` / `last_error_at`.
4. Skip non-eligible cards silently.
5. App restart / site offline: LUN Builder still loads the last snapshot from SQLite.

## UI (LUN Builder)

- Site/build list: badge when an offline inventory snapshot exists (e.g. “Inventory · Updated …”).
- For a selected site/build (or inventory-only card with no plan): toggle **Plan** | **Inventory**.
  - **Plan** — existing editable tables from `lun_builds`.
  - **Inventory** — read-only tables from `lun_offline_inventory`.
- Banner on Inventory view: `Offline copy · last updated {timestamp}` when SSH/monitor is down or stale; `Online · last updated {timestamp}` when the card is currently reachable / just refreshed.
- Cards with inventory but no plan build: still list/view inventory (create plan remains optional via Save as new / templates).

## APIs

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/lun-offline-inventory` | List summaries (card_id, site, updated_at, host/volume counts, last_error) |
| GET | `/api/lun-offline-inventory?card_id=` | Full snapshot for one card |

Writes happen internally from the Monitor refresh path (`upsert_lun_offline_inventory`), not a new operator button. Persistence follows the same unlock/settings rules as `lun_builds`.

## Errors

- Unlock required to write snapshots.
- Partial parse / SSH failure: keep prior good snapshot; set `last_error`.
- Missing card_id on GET: 400.
- Unknown card_id: return `{ "ok": false, "snapshot": null, "error": "…" }` with HTTP 200 (same style as other LUN Builder soft failures).

## Testing

- Upsert replaces prior snapshot for the same `card_id`.
- Failed refresh does not clear hosts/volumes.
- Non-eligible cards are not written.
- API list + by-card shapes.
- UI markers: Plan \| Inventory toggle, banner, list badge.
- Regression: plan Save, templates, Sync Inventory, Pull FC, export unchanged.

## Out of scope follow-ups (optional later)

- “Copy inventory → plan” one-shot action.
- Per-site opt-out of auto inventory cache.
- Excel export of offline inventory alone.
