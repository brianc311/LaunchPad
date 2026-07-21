# Woodland Hills, CA — LUN Builder template + Contingency Groups

**Date:** 2026-07-20  
**Status:** Approved for implementation  
**App version target:** 1.6.42 (after Windsor 1.6.41 on `feature/contingency-groups`)  
**Depends on:** LUN Builder site-template pattern; Contingency Groups seed + `generate_snap_rows` pattern

## Problem

Operators need a Woodland Hills, CA starting point in both **LUN Builder** and **Contingency Groups**. FlashSystem 5200 inventory screenshots provide pool `WOO_Pool1`, hosts (AS400, ESX, VIO), volumes, host mappings, Port Definitions, and an on-array FlashCopy consistency group `AWD1_AS400_CG`. LaunchPad’s related planning feature is named Contingency Groups (not IBM array Consistency Groups).

## Goals

- Ship **LUN Builder** template `template-woodland-hills-ca` (**Woodland Hills, CA (Template)**).
- Ship **Contingency Groups** seed `woodland-hills-ca` with the **full site** inventory (ESX + AS400 + VIO).
- Pre-fill LUN defaults: card hint `Woodland Hills, CA`, profile `flashsystem_5200`, pool `WOO_Pool1`.
- Leave all host WWPNs **blank** (operator fills via Port Definitions / Pull from FC WWPN).
- Contingency Groups `storage_hint`: `v5kwoo-g3c1`.
- Auto-generate LaunchPad `_snap` target rows via `generate_snap_rows()` on seed.
- Reuse existing template UX: Save as new; Delete disabled on the LUN template.

## Non-goals

- Seeding IBM array Consistency Group membership, existing `fcmap*` objects, or live `*_SnapN` FlashCopy target names.
- Seeding Active Port Definition WWPNs (explicitly deferred; blank like Jupiter / Pendergrass).
- Seeding array canister / system FC ports as host WWPNs.
- Changing Hartford, Houston, Windsor Contingency Groups or other LUN templates.

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Deliverables | Both LUN Builder template and Contingency Groups site |
| Contingency Groups scope | Full site (ESX + AS400 + VIO) |
| Card hint | `Woodland Hills, CA` (not the longer FlashSystem string) |
| WWPN strategy | Blank on both features |
| Profile / pool | `flashsystem_5200` / `WOO_Pool1` |
| Contingency Groups `storage_hint` | `v5kwoo-g3c1` |
| Snap targets | LaunchPad `_snap` via `generate_snap_rows`; do not seed array `*_SnapN` volumes as sources |
| Implementation shape | Independent seeds in `lun_builder_data.py` and `contingency_groups_data.py` |

## LUN Builder template

**Id:** `template-woodland-hills-ca`  
**Name:** Woodland Hills, CA (Template)  
**Location:** Woodland Hills, CA  
**Notes:** Seeded from Woodland Hills FlashSystem 5200 inventory. WWPNs are blank — set Port Definitions / Pull from FC WWPN before create. Defaults use card hint Woodland Hills, CA, profile flashsystem_5200, pool WOO_Pool1.

### Defaults (build-level)

- `default_storage_profile`: `flashsystem_5200`
- `default_pool_or_cpg`: `WOO_Pool1`
- `default_card_hint`: `Woodland Hills, CA`

LUN rows also carry the same profile, pool, and card hint.

### Hosts

All hosts `type=Generic`. WWPN1 / WWPN2 empty. Path fields other than name empty.

| Host | Rows | Notes |
|------|------|-------|
| `AWD1_New_as400` | 4 | Live host has 8 Active ports; four blank `wwpn1`/`wwpn2` rows reserve port capacity |
| `PEN-WODESX-VM01` | 1 | |
| `PEN-WODESX-VM02` | 1 | |
| `PEN-WODESX-VM03` | 1 | |
| `PEN-WODESX-VM04` | 1 | |
| `pwoovio01a` | 1 | |
| `pwoovio01b` | 1 | |
| `pwoovio02a` | 1 | |
| `pwoovio02b` | 1 | |

Total host rows: **12** (9 unique host names).

### LUN batches

Every batch: `storage_profile=flashsystem_5200`, `pool_or_cpg=WOO_Pool1`, `card_hint=Woodland Hills, CA`.

| Purpose | Count | Size | Shared | Hosts | `name_prefix` | Cluster | Expected expand stem |
|---------|-------|------|--------|-------|---------------|---------|----------------------|
| `AS400` | 6 | `500GB` | true* | `AWD1_New_as400` | `AWD1` | *(empty)* | `AWD1_AS400_N` |
| `ESX_DataStore` | 4 | `4TB` | true | all four `PEN-WODESX-VM0*` | `WOO` | *(empty)* | `WOO_ESX_DataStore_N` |
| `root` | 2 | `100GB` | false | each `pwoovio01a`, `01b`, `02a`, `02b` | `pwoo` | `vio` | `pwoovio##_root_N` |

\* Shared with a single host + prefix and empty cluster uses the prefix+purpose naming path for live-like `AWD1_AS400_N` names.

Do **not** seed FlashCopy targets `AWD1_AS400_N_SnapN` as LUN batches.

## Contingency Groups site

**Id:** `woodland-hills-ca`  
**Name / location:** `Woodland Hills, CA`  
**storage_hint:** `v5kwoo-g3c1`  
**notes:** empty  
**updated_at:** seed timestamp (same style as other seeds)

### Hosts

| Host | `port_count` | `wwpns` |
|------|--------------|--------|
| `AWD1_New_as400` | 8 | `[]` |
| `PEN-WODESX-VM01` | 2 | `[]` |
| `PEN-WODESX-VM02` | 2 | `[]` |
| `PEN-WODESX-VM03` | 2 | `[]` |
| `PEN-WODESX-VM04` | 2 | `[]` |
| `pwoovio01a` | 2 | `[]` |
| `pwoovio01b` | 2 | `[]` |
| `pwoovio02a` | 2 | `[]` |
| `pwoovio02b` | 2 | `[]` |

Status Online, host_type Generic, protocol SCSI (existing `_host` defaults).

### Source volumes

Pool `WOO_Pool1` for all. Capacities match inventory. Seed UIDs only where fully known from Mapped Volumes screenshots; otherwise leave UID empty.

| Volume | Capacity | UID (if known) |
|--------|----------|----------------|
| `AWD1_AS400_1`…`6` | `500.00 GiB` | *(blank unless captured)* |
| `WOO_ESX_DataStore_1` | `4.00 TiB` | `60050768128100A7D000000000000000` |
| `WOO_ESX_DataStore_2` | `4.00 TiB` | `60050768128100A7D000000000000001` |
| `WOO_ESX_DataStore_3` | `4.00 TiB` | `60050768128100A7D000000000000002` |
| `WOO_ESX_DataStore_4` | `4.00 TiB` | `60050768128100A7D000000000000017` |
| `pwoovio01a_root_1`…`2` | `100.00 GiB` | *(blank unless captured)* |
| `pwoovio01b_root_1`…`2` | `100.00 GiB` | *(blank unless captured)* |
| `pwoovio02a_root_1`…`2` | `100.00 GiB` | *(blank unless captured)* |
| `pwoovio02b_root_1` | `100.00 GiB` | `60050768128100A7D00000000000000F` |
| `pwoovio02b_root_2` | `100.00 GiB` | `60050768128100A7D000000000000010` |

Do **not** seed array targets `AWD1_AS400_N_SnapN` as source volumes.

### Maps (source role)

| Volumes | Hosts | SCSI IDs |
|---------|-------|----------|
| `AWD1_AS400_1`…`6` | `AWD1_New_as400` | `0`…`5` |
| `WOO_ESX_DataStore_1`…`4` | all four `PEN-WODESX-VM0*` | `0`…`3` (same id per volume on every ESX host) |
| `pwoovio##_root_1`…`2` | matching `pwoovio##` only | `0`, `1` |

### Snap generation

Call `generate_snap_rows()` on the group before returning from `seed_contingency_groups()`, matching Hartford / Houston / Windsor. Targets use LaunchPad suffix `_snap` (e.g. `AWD1_AS400_1_snap`), not live `*_SnapN` names.

## UX

**LUN Builder:** same as other site templates (Templates picker, banner, Save as new / Delete disabled).

**Contingency Groups:** new card appears with other seeded sites; wizard / `_snap` Preview and Run Create unchanged.

## Data / APIs

- Extend `seed_lun_builder_templates()` after Windsor with Woodland Hills entry + blank-WWPN host helper (Jupiter-style).
- Extend `seed_contingency_groups()` with `_woodland_hills_ca()` wrapped in `generate_snap_rows`.
- Tests: template id, defaults, host row count/names, blank WWPNs, LUN batch shapes, API template id set; Contingency Groups id, storage_hint, host/volume/map counts, snap rows present, known UIDs.
- Bump `APP_VERSION` to `1.6.42`.

## Out of scope follow-ups

- Filling WWPNs from Port Definitions screenshots later
- Aligning `_snap` target names with live `*_SnapN` / `AWD1_AS400_CG`
- Capturing remaining AS400 / VIO UIDs from a full UID export
