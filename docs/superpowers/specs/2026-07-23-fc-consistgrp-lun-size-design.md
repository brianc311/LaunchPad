# FlashCopy CGs — Member map LUN size + CG total

**Date:** 2026-07-23  
**Status:** Approved for implementation  
**App version target:** 1.6.60  
**Depends on:** FlashCopy Consistency Groups page (`/fc-consistgrp`), `collect_fc_consistgrp_inventory`, `parse_lsvdisk_volumes`  
**Approach:** Enrich inventory with `lsvdisk` capacities on Refresh (Approach 1)  
**Base branch:** `feature/contingency-groups` (tip at 1.6.59)

## Problem

Operators viewing **Member maps** on FlashCopy Consistency Groups see map/source/target/status/progress but not LUN size. They need each map’s source volume size and a **CG total** (sum of member source sizes) to understand capacity for the selected consistency group.

## Goals

- Add a **Size** column (source volume capacity) on Member maps and stand-alone maps tables.
- Show a **CG total size** in the Member maps hint when a group is selected.
- Enrich inventory by running `svcinfo lsvdisk -delim :` alongside existing consistgrp/fcmap collection.
- Bump version to **1.6.60**.

## Non-goals

- Target volume size columns.
- Editing or provisioning volumes.
- HPE / non–Spectrum Virtualize FlashCopy UI.
- Changing CG create / assign / remove / start / delete behavior.

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Which size | Source volume capacity |
| Display | Per-row Size + CG total in Member maps hint |
| Stand-alone maps | Same Size column |
| Implementation | Approach 1 — enrich inventory with `lsvdisk` on load/Refresh |

## Behavior

### Inventory

`collect_fc_consistgrp_inventory` (or equivalent) after `lsfcmap`:

1. Run `svcinfo lsvdisk -delim :` (fallback without `-delim :` only if needed for consistency with existing patterns).
2. Parse with `parse_lsvdisk_volumes`.
3. Build `name → capacity` (and parse capacity to bytes when possible via existing size helpers).
4. For each map, set:
   - `source_size`: display string from source volume capacity (empty if unknown)
   - `source_size_bytes`: integer bytes when parseable; otherwise omit/`null`
5. If `lsvdisk` fails: keep groups/maps; leave sizes empty; do not fail the whole inventory.

### UI (`/fc-consistgrp`)

**Member maps**

- Columns: checkbox, Map, Source, Target, **Size**, Status, Progress.
- Size cell: `source_size` or `—`.
- Hint when a CG is selected:  
  `{n} map(s) in {group} · Total size {formatted}`  
  Total = sum of known `source_size_bytes` for maps in that group; format with existing helpers (e.g. `2.40TB`). If no sizes known, omit the total clause or show `Total size —`.

**Stand-alone maps**

- Same **Size** column (source capacity).

### API

No new endpoint. Existing `GET /api/fc-consistgrp/inventory` payload includes enriched map fields.

## Testing

- Enrichment attaches `source_size` / bytes from a fixture `lsvdisk` + `lsfcmap` pair.
- Missing volume → empty size, not an error.
- `lsvdisk` failure → maps still returned without sizes.
- CG total helper sums known bytes only.
- Page HTML/JS contracts: Size column headers; Member maps hint includes Total size text pattern.

## Version

`APP_VERSION = "1.6.60"`
