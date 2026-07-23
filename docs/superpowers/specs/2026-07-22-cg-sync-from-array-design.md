# Contingency Groups — Ensure Sites + Sync from Array

**Date:** 2026-07-22  
**Status:** Approved for implementation  
**App version target:** next patch on the implementation branch  
**Depends on:** Contingency Groups page; SSH Inventory Sync (`inventory_sync` / Sync Inventory API); live-snap CG enrichment if present on tip  
**Approach:** Reuse Sync Inventory mapper; CG-page ensure stubs + Sync selected only (Approach 1)  
**Base branch:** Stack on Sync Inventory tip (e.g. `feature/sync-live-snaps-cg`), not bare Contingency Groups without inventory sync

## Problem

The Contingency Groups picker only lists **saved** groups. Built-in seeds are three sites (Hartford, Houston, Windsor), so operators do not see every monitored array. Sync Inventory today lives on LUN Builder and upserts a CG as a side effect — there is no Sync control on the Contingency Groups page to pull live SSH hosts/volumes/maps into the selected group.

## Goals

- On Contingency Groups load (unlocked): ensure a **stub** Contingency Group for every **monitored** FlashSystem / Storwize / SVC Health Card that does not already match an existing group.
- Add **Sync from array** on Contingency Groups: SSH inventory for the card linked to the **selected** group only; replace that group’s hosts/volumes/maps using the same shaping as Sync Inventory (including live-snap preference when available on tip).
- Do **not** replace LUN Builder builds from this button.
- Grow the Group dropdown to cover all monitored SVC/FlashSystem cards.

## Non-goals (v1)

- Sync-all cards in one click.
- IBM `/fc-consistgrp` (FlashCopy Consistency Groups) UI.
- Rewriting or deleting the three git-seeded CG seed modules as the only source of truth (stubs/upserts live in settings).
- Changing LUN Builder Sync Inventory behavior beyond reuse.
- Auto-creating stubs for non-SVC / non-FC profiles.

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Dropdown “all sites” | **A** — every monitored FlashSystem/SVC Health Card |
| Sync scope | **1** — selected group only |
| Stub creation | **A** — auto-ensure on page load when unlocked |
| Implementation | Reuse Sync Inventory mapper (Approach 1) |
| Button label | **Sync from array** (Contingency Group — not IBM Consistency Groups) |

## Behavior

### Ensure stubs (page load)

When Contingency Groups loads and settings are unlocked:

1. List Health Cards that are monitored and SVC/FlashSystem-family (same profile gate as Sync Inventory / FC WWPN).
2. For each such card, if no existing Contingency Group matches by id slug, name, location, or `storage_hint`, append a stub:
   - `name` / `location` = card display name
   - `storage_hint` = card name (or existing storage label used elsewhere for that card)
   - empty hosts / volumes / maps
   - stable `id` from slug of card name
3. Persist the merged group list.
4. If locked / browser-only: still expose stubs in the in-memory list for the session when possible; do not claim persisted save.

Do not wipe or replace filled groups that already match a card.

### Sync from array (selected group)

1. Operator selects a Contingency Group and clicks **Sync from array**.
2. Require unlocked settings (same as other CG mutations).
3. Resolve Health Card:
   - Prefer `storage_hint`, then group `name` / `location`
   - Prompt for card name if unresolved or ambiguous
4. Reject non-SVC/FlashSystem profiles with a clear error; no mutation.
5. Run the same live SSH inventory suite as Sync Inventory (`lshost`, WWPNs, `lsvdisk`, `lshostvdiskmap`).
6. Shape via `build_inventory_sync` (and live-snap CG path if present on tip).
7. Upsert **only** the Contingency Group: replace hosts/volumes/maps (and generated/linked snaps); keep group id/name unless intentionally updating storage_hint from card.
8. **Do not** modify LUN Builder builds.
9. Status example: `Synced hosts=… volumes=… maps=… live_snaps=…. CG updated.`

### Errors

Fail closed (no partial replace of the selected group) on card not found, wrong profile, or SSH/parse failure — same posture as Sync Inventory.

## Architecture

| Piece | Responsibility |
|-------|----------------|
| `contingency_groups_data.py` | `ensure_groups_for_cards(groups, cards) -> list` — stub merge / match helpers |
| `health_server.py` | Ensure on GET (or ensure endpoint); `POST /api/contingency-groups/sync-inventory` with `{ group_id, card_name? }` |
| `contingency_groups.py` | Sync from array button; ensure on load; status copy |
| `inventory_sync.py` (+ live-snap tip) | Reused shaping; no LUN build write from this API |

Illustrative API:

`POST /api/contingency-groups/sync-inventory`  
Body: `{ "group_id": "...", "card_name": "..." }`  
Response: `{ "group": ..., "groups": ..., "pulled": { "hosts", "volumes", "maps", "skipped_snaps", "live_snaps?" }, "warnings": [...] }`

## Testing

- Ensure: N monitored SVC cards → at least N matching groups after ensure; existing filled group not duplicated / not emptied.
- Sync API success: selected group hosts/volumes/maps replaced; other groups unchanged; LUN builds untouched.
- Sync API SSH failure: selected group unchanged.
- Page HTML includes Sync from array and calls the new endpoint.

## Out of scope follow-ups

- Sync all monitored cards.
- Matching cards to groups via Site Lookup metadata beyond name/hint.
- Removing obsolete stub groups when cards are deleted (manual Delete remains).
