# LUN Builder — Six missing site templates

**Date:** 2026-07-22  
**Status:** Approved for implementation  
**App version target:** next patch on the implementation branch tip (likely `1.6.45` if Site Lookup is `1.6.44`)  
**Depends on:** LUN Builder site-template pattern (`exact_name`, `seed_lun_builder_templates`); Sync Inventory available for later live replace  
**Approach:** One catalog batch of six built-in templates (Approach 1)

## Problem

Six FlashSystem sites have Storage Site Lookup HTML inventories but no LUN Builder picker templates. Operators need offline starting points (hosts + mapped volumes) without duplicating sites that already ship as templates.

## Goals

- Add six built-in templates transcribed from the canonical Downloads HTML files.
- Seed full host lists with **blank WWPNs** (Port Definitions not in these HTMLs; Sync Inventory / SSH can fill later).
- Seed **one LUN row per mapped volume** with `exact_name=True`, maps → `host_names` / shared / SCSI when consistent.
- Pre-fill per-site profile, pool, and card hint.
- Skip FlashCopy-target-like volume names as sources (`*_snap` / `*_Snap*` heuristic).

## Non-goals

- Replacing or rewriting Hartford, Jupiter, Pendergrass, Mount Vernon, Windsor, or Williamston Anderson templates.
- Seeding WWPNs from Port Definitions.
- Contingency Groups seed modules.
- Site Lookup page or Sync Inventory code changes.
- Importing HTML files into the shipped app.

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Sites | Six missing only (Approach A) |
| WWPN | Blank on all host rows (Approach A) |
| Content depth | Full hosts + per-volume exact_name LUNs (Approach A) |
| Delivery | One catalog batch in `seed_lun_builder_templates()` (Approach 1) |
| Snap volumes | Skip as sources |

## Sites

| Template id | Name / location | Profile | Default pool | Card hint | Source HTML |
|-------------|-----------------|---------|--------------|-----------|-------------|
| `template-perrysburg-oh` | Perrysburg, OH | `flashsystem_7200` | `G3_PER_Pool` | `Perrysburg, OH` | `storage_site_lookup_perrysburg.html` |
| `template-moreno-valley-ca` | Moreno Valley, CA | `flashsystem_5200` | `MOR_G3_Pool` | `Moreno Valley, CA` | `storage_site_lookup_morenovalley.html` |
| `template-nazareth-pa` | Nazareth, PA | `flashsystem_5200` | `V5kNAZ_Pool1` | `Nazareth, PA` | `storage_site_lookup_nazareth.html` |
| `template-valparaiso-in` | Valparaiso, IN | `flashsystem_7300` | `VAL_POOL` | `Valparaiso, IN` | `storage_site_lookup_valparaiso.html` |
| `template-waxahachie-tx` | Waxahachie, TX | `flashsystem_5200` | `Wax_Pool1` | `Waxahachie, TX` | `storage_site_lookup_waxahachie.html` |
| `template-woodland-hills-ca` | Woodland Hills, CA | `flashsystem_5200` | `WOO_Pool1` | `Woodland Hills, CA` | `storage_site_lookup_woodlandhills.html` |

Use canonical filenames (no `_1` / `_2` suffix). Prefer the Downloads copy at implementation time.

## Content rules

### Hosts

- Every host named in the HTML (including Offline).
- `type=Generic`; path fields empty; `wwpn1` / `wwpn2` empty strings.
- One LUN Builder host row per unique host name (no multi-row WWPN packing — WWPNs are blank).

### LUN batches

- One batch per source volume: `exact_name=True`, `count=1`, purpose/name = live volume name.
- Capacity/size string from HTML when present; otherwise empty.
- `host_names` from host↔volume maps; `shared=True` when two or more hosts map the volume.
- `scsi_or_lun_id` when all maps for that volume share one SCSI id; else blank.
- Each row: site `storage_profile`, `pool_or_cpg`, `card_hint`.
- Exclude volume names matching the Sync Inventory snap heuristic.

### Build defaults

- `default_storage_profile`, `default_pool_or_cpg`, `default_card_hint` as in the table above.
- `is_template=True`; notes state HTML seed + blank WWPNs + Sync Inventory can refresh.

## Architecture

| Piece | Responsibility |
|-------|----------------|
| `launchpad/lun_builder_data.py` | Host/LUN helpers + six entries in `seed_lun_builder_templates()` |
| `launchpad/config.py` | Version bump |
| `tests/test_lun_builder_*` or new `tests/test_lun_templates_six_sites.py` | Id/defaults/host+LUN presence/blank WWPN asserts |

## Testing

- Each new `template-*` id present after seed.
- Defaults match the table (profile, pool, card hint).
- Host count ≥ 1 and LUN count ≥ 1 per template.
- All seeded host WWPNs blank.
- Existing templates unchanged (spot-check Hartford / Jupiter ids still present).

## Out of scope follow-ups

- Contingency Groups for these six sites.
- Merging Anderson into the same tip before this branch if not already present.
