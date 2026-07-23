# Sync Inventory — Live Snap Volumes in Contingency Groups

**Date:** 2026-07-22  
**Status:** Approved for implementation  
**App version target:** next patch on the implementation branch  
**Depends on:** SSH Inventory Sync (`inventory_sync.py`, Sync Inventory API/UI); Contingency Groups `generate_snap_rows`  
**Approach:** Enrich CG during `build_inventory_sync` (Approach 1); name-match only in v1  
**Extends:** [2026-07-21-ssh-inventory-sync-design.md](./2026-07-21-ssh-inventory-sync-design.md)

## Problem

Sync Inventory skips FlashCopy-target-like volumes as LUN Builder sources (correct) and upserts Contingency Groups with sources only, then invents `{source}_snap` rows via `generate_snap_rows()`. Operators cannot see the **live** snap copies that already exist on the array (real names, UIDs, pools) — only placeholders that may not match labels like `volA_Snap1`.

## Goals

- Prefer **live** snap-like volumes in the upserted Contingency Group when they name-match a kept source.
- Keep real **name, capacity, pool, UID**, with `role=snap` and `source_volume` set to the matched source.
- Still call `generate_snap_rows()` so sources **without** a live match get a generated `{source}_snap`.
- Leave LUN Builder behavior unchanged (snap-like volumes remain excluded as sources).
- Surface a `live_snaps` count in Sync status alongside `skipped_snaps`.

## Non-goals (v1)

- Matching via `lsfcmap` / real FlashCopy relationships (follow-up).
- Importing orphan snap-like volumes (no matching kept source).
- Adding snap volumes to LUN Builder rows.
- Syncing IBM `/fc-consistgrp` membership.
- Changing how built-in CG seeds are authored.

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Prefer live vs generated | **A** — live wins; generate only when no match |
| Matching | **Name only** in v1; `lsfcmap` later |
| Orphans | **Skip** (still counted under snap-like / warnings as today) |
| Implementation | Enrich in `build_inventory_sync` + small `generate_snap_rows` fix |

## Behavior

### LUN Builder

Unchanged: exclude volumes matching `is_flashcopy_target_name` from hosts/LUN replace.

### Contingency Groups upsert

1. Build CG sources + source maps from non-snap inventory (as today).
2. For each volume matching `is_flashcopy_target_name`, attempt to derive a candidate source name by stripping the snap token matched by the same heuristic (e.g. `_snap`, `_snap1`, `_Snap`).
3. If the candidate equals a kept source name:
   - Append a CG volume with live **name, capacity, pool, UID**, `role=snap`, `source_volume=<source>`.
   - Count toward `live_snaps`.
4. If no kept source matches: skip (orphan); do not import as source.
5. Call `generate_snap_rows(group)`:
   - If a source already has any volume with `role=snap` linked via `source_volume`, **do not** invent another `{source}_snap`.
   - When adding snap maps for that source, use the **existing** linked snap volume’s name (live or generated), not always `snap_volume_name(source)`.
6. Sources with no linked snap still get generated `{source}_snap` + snap maps as today.

### Name matching (v1)

- Reuse / share the FlashCopy-target name heuristic already used for `skipped_snaps`.
- Matching is case-sensitive on the residual source name against kept source names (volume names from the array are authoritative).
- If multiple live snaps match the same source, keep the first in inventory order and warn (or keep all linked with the same `source_volume` — prefer **one snap per source** in v1: first match wins; extras count as skipped orphans for that source).

### UX feedback

Extend Sync status / `pulled` payload:

- `skipped_snaps` — count of snap-like volume names seen on the array (unchanged meaning).
- `live_snaps` — count of snap-like volumes matched into the CG.

Example:  
`Synced hosts=… volumes=… maps=… skipped_snaps=… live_snaps=…. CG upserted. No create was run.`

### Errors

Unchanged from SSH Inventory Sync: SSH/parse failure → no partial build/CG replace.

## Architecture

| Piece | Responsibility |
|-------|----------------|
| `launchpad/inventory_sync.py` | After building source CG volumes, attach matched live snaps; return `live_snaps` in `pulled` |
| `launchpad/contingency_groups_data.py` (`generate_snap_rows`) | Skip inventing a snap when source already has a linked `role=snap` volume; map using that volume’s name |
| `lun_builder.py` (status string) | Include `live_snaps` from `pulled` |
| HealthServer sync response | Pass through `pulled.live_snaps` (no new endpoint) |

No new SSH commands in v1.

## Testing

- Live snap `volA_Snap1` + source `volA` → CG has snap named `volA_Snap1` with UID/pool from array; no extra `volA_snap`.
- Source with no live snap → still gets generated `volA_snap`.
- Orphan `weird_snap` with no source → not in CG; still reflected in `skipped_snaps`.
- Two live snaps for one source → first wins; second not imported as a second snap for that source.
- LUN Builder output still excludes all snap-like volumes.
- `generate_snap_rows` unit: pre-seeded linked live snap → no duplicate `{source}_snap`; snap maps use live name.

## Out of scope follow-ups

- `lsfcmap`-based source↔target matching.
- Importing orphans with empty `source_volume`.
- Showing live snaps in LUN Builder (read-only) without treating them as create sources.

