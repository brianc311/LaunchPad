# Williamston (Anderson) — LUN Builder template + Contingency Groups

**Date:** 2026-07-21  
**Status:** Approved for implementation  
**App version target:** next patch on the implementation branch (reconcile with open `1.6.42` PRs at merge time)  
**Depends on:** LUN Builder site-template pattern; Contingency Groups seed + `generate_snap_rows` pattern (Woodland Hills / Windsor)  
**Approach:** Independent seeds in `lun_builder_data.py` and `contingency_groups_data.py` (Woodland Hills shape)

## Problem

Operators need a Williamston / Anderson starting point in both **LUN Builder** and **Contingency Groups**. FlashSystem **7200** inventory screenshots (`v7kand-g3v1`) provide pool `G3_AND_Pool`, a large host catalog (AS400, ESX, VIO, AIX, OEM, clones), mapped volumes, Port Definitions, and on-array FlashCopy consistency groups. LaunchPad’s related planning feature is Contingency Groups (not IBM array Consistency Groups).

## Goals

- Ship **LUN Builder** template `template-williamston-anderson` (**Williamston (Anderson) (Template)**).
- Ship **Contingency Groups** seed `williamston-anderson` with the **full site** inventory.
- Pre-fill LUN defaults: card hint `Williamston (Anderson)`, profile `flashsystem_7200`, pool `G3_AND_Pool`.
- Seed **Active** Port Definition WWPNs into `wwpn1` / `wwpn2`; **multiple host rows** when a host has more than two Active ports; Offline / missing ports → blank (Windsor-style).
- Contingency Groups `storage_hint`: `v7kand-g3v1`.
- Auto-generate LaunchPad `_snap` target rows via `generate_snap_rows()` on seed.
- Reuse existing template UX: Save as new; Delete disabled on the LUN template.

## Non-goals

- Seeding IBM array Consistency Group membership, existing `fcmap*` objects, or live `*_SnapN` / `*_snap` FlashCopy target names as **source** volumes.
- Seeding array canister / system FC ports as host WWPNs.
- New UI chrome beyond card hint / existing template and Contingency Groups behavior.
- Changing Hartford, Jupiter, Pendergrass, Mount Vernon, Windsor, Woodland Hills, or other site seeds.

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Deliverables | Both LUN Builder template and Contingency Groups site |
| Host / LUN scope | Full inventory including Offline hosts |
| WWPN strategy | Active Port Definitions → wwpn1/wwpn2; multi-row if >2 Active; Offline/missing → blank |
| Card hint | `Williamston (Anderson)` |
| Profile / pool | `flashsystem_7200` / `G3_AND_Pool` |
| Contingency Groups `storage_hint` | `v7kand-g3v1` |
| Snap targets | LaunchPad `_snap` via `generate_snap_rows`; do not seed array `*_Snap*` volumes as sources |
| Implementation shape | Independent seeds (Approach A — Woodland Hills mirror) |
| Pool OCR | Treat screenshot OCR `GS_AND_Pool` as live pool `G3_AND_Pool` |

## LUN Builder template

**Id:** `template-williamston-anderson`  
**Name:** Williamston (Anderson) (Template)  
**Location:** Williamston (Anderson)  
**Notes:** Seeded from Anderson FlashSystem 7200 inventory (`v7kand-g3v1`). Active Port Definition WWPNs filled when known; Offline/missing blank. Full mapped-volume inventory. Defaults use card hint Williamston (Anderson), profile flashsystem_7200, pool G3_AND_Pool.

### Defaults (build-level)

- `default_storage_profile`: `flashsystem_7200`
- `default_pool_or_cpg`: `G3_AND_Pool`
- `default_card_hint`: `Williamston (Anderson)`

LUN rows also carry the same profile, pool, and card hint.

### Hosts

All hosts `type=Generic`. Path fields other than name/WWPNs empty. Include Offline hosts. Multi-row WWPN packing matches Windsor.

**Host catalog (from Hosts screenshots; Offline called out):**

| Group | Hosts | Ports (typical) | Notes |
|-------|-------|-----------------|-------|
| AS400 / FC | `AAN1`, `AAN1C`, `FC_AAN1` | 8 | `FC_AAN1` Offline |
| ESX (BIB) | `BIB_ADC_VM01`, `BIB_ADC_VM02` | 2 | Both Offline; VM01 has mappings |
| ESX (AND) | `pen_andesx_vm03`, `pen_andesx_vm04` | 2 | Shared datastores |
| OEM | `pla-wanoemcr01`, `pla-wanoemcr02` | 2 | Shared `pla-wanoemcr01_02_*` volumes |
| VIO | `pandvio01a`…`pandvio10b` | 2 | `pandvio05a`/`05b` Offline |
| AIX / app | `pandap01`, `pandap02`, `pandbt1`…`4`, `pandbtdg1`, `panddb01`, `panddb02`, `pandmfs1`…`4`, `pandmfs10`, `pandmfsdg1`, `pandnim01`, `pandps1`…`4`, `pandpspdg1`, `dandmfs1` | 8 | |
| PSA | `pandpspa1`, `pandpspa2` | 8 | Offline |
| Test / clone | `tandbt1`, `tandbt20`, `tandmfs1`, `tandmfs2`, `tandmfs20`, `tandsps1`, `tandsps2`, `tandeps1`, `tandeps2`, `tandeps20`, `tandeps21`, `tconbt20`, `tconmfs20`, `tconsps20`, `tconsps21` | 8 | Reconcile `tandeps*` vs `tandsps*` OCR against Mapped Volumes during implementation |
| TLA | `TLA_WANMFS01`, `TLA_WANMFS02` | 2 | |

WWPN values: transcribed from Host → Port Definitions screenshots during implementation. Hosts with no Port Definitions capture keep blank WWPNs.

### LUN batches

Every batch: `storage_profile=flashsystem_7200`, `pool_or_cpg=G3_AND_Pool`, `card_hint=Williamston (Anderson)`.

Seed **full** mapped-volume inventory from screenshots. Group into batches by live name/size pattern so expand naming (`name_prefix`, purpose, shared, cluster) matches inventory as closely as practical. Shared volumes use one batch with multiple hosts (not duplicate volume definitions).

**Representative families (implementation completes exact counts/sizes/names from assets):**

| Family | Example live names | Typical size | Hosts | Shared |
|--------|-------------------|--------------|-------|--------|
| AS400 AAN1 | `AAN1_*` (~28×) | ~120 GiB | `AAN1` | false / as mapped |
| AS400 AAN1C | `AAN1C_*` (4×) | ~125 GiB | `AAN1C` | false |
| AS400 FC_AAN1 | `FC_AAN1_*` (~28×) | ~120 GiB | `FC_AAN1` | false |
| ESX datastores | `ADC-Data01`…`03`, `Andesx-DS01`…`03`, `RHEL-Networker01` | 1 TiB / 4 TiB / 100 GiB | `pen_andesx_vm03` + `vm04` | true |
| OEM series | `pla-wanoemcr01_02_*` (5GB / 250GB / 300GB / 501–504 / FRA / data / redo) | mixed | `pla-wanoemcr01` + `02` | true |
| pandap | `pandap01_0`…`4` | 70 / 50 GiB | `pandap01` | false |
| pand* / tand* roots & data | `*_0`…`*_N`, `*_db_*`, `*_data_*`, `*_shared_*`, `*_asm*`, `*_HA`, clones | mixed (20–100 GiB common; 64 GiB DB/shared) | matching host | as mapped |
| VIO roots | `pandvio##_0`… | ~50 GiB | each VIO | false |

Do **not** seed FlashCopy targets (`*_Snap*`, live clone-only snap destinations) as source LUN batches. Clone **source** volumes that appear as ordinary mapped volumes (e.g. `tandbt_clone_root*`) **are** included when they are real provisioned volumes on the pool.

UID column: optional on LUN Builder batches; prefer Contingency Groups for UID capture when known.

## Contingency Groups site

**Id:** `williamston-anderson`  
**Name / location:** `Williamston (Anderson)`  
**storage_hint:** `v7kand-g3v1`  
**notes:** empty  
**updated_at:** seed timestamp (same style as other seeds)

### Hosts

Same unique host set as the LUN template. `port_count` reflects Active WWPN capacity (e.g. 8-port hosts → `port_count=8`). Fill `wwpns` lists from the same Port Definitions transcription used for LUN multi-row packing. Status Online/Offline, host_type Generic, protocol SCSI (existing `_host` defaults).

### Source volumes

Pool `G3_AND_Pool` for all. Capacities and names match Mapped Volumes inventory. Seed UIDs when fully readable from screenshots; otherwise leave UID empty.

Do **not** seed array FlashCopy targets as source volumes.

### Maps (source role)

Mirror live host↔volume mappings from Host Mappings / Mapped Volumes screenshots (e.g. ESX shared volumes on both `pen_andesx_vm03` and `vm04`; OEM volumes on both `pla-wanoemcr01` and `02`; per-host VIO/AIX volumes on the owning host only). SCSI IDs from mapping screenshots when available; otherwise assign sequential ids per host in screenshot order.

### Snap generation

Call `generate_snap_rows()` on the group before returning from `seed_contingency_groups()`, matching Woodland Hills / Hartford / Houston / Windsor. Targets use LaunchPad suffix `_snap`, not live `*_SnapN` names.

## UX

**LUN Builder:** same as other site templates (Templates picker, banner, Save as new / Delete disabled).

**Contingency Groups:** new card appears with other seeded sites; wizard / `_snap` Preview and Run Create unchanged.

## Data / APIs

- Extend `seed_lun_builder_templates()` with Williamston (Anderson) entry + `_anderson_host` (or shared Windsor-style helper with WWPN args).
- Extend `seed_contingency_groups()` with `_williamston_anderson()` wrapped in `generate_snap_rows`.
- Tests: template id, defaults, host names (including Offline), multi-row WWPN packing where known, LUN batch profile/pool/card_hint, API template id set; Contingency Groups id, `storage_hint`, host/volume/map presence, snap rows present, sample UIDs when seeded.
- Bump `APP_VERSION` on the implementation branch; resolve collisions with parallel `1.6.42` work at merge.

## Inventory source of truth

Primary assets live under the Cursor project `assets/` folder (Hosts_1–3, Pools, Volume_*, Port Definitions / `*_Ports*`, ConsistencyGroups / `CG_*`). Implementation must re-read those images (not truncated OCR summaries) when filling exact WWPN, UID, count, and SCSI ID tables.

## Out of scope follow-ups

- Aligning `_snap` target names with live IBM CG / `*_SnapN` naming
- Seeding IBM FlashCopy Consistency Groups into the `/fc-consistgrp` feature (separate from Contingency Groups)
- Exporting a machine-readable host/WWPN workbook to replace screenshot transcription
