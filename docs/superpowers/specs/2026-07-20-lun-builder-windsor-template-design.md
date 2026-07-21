# LUN Builder — Windsor, WI site template

**Date:** 2026-07-20  
**Status:** Approved for implementation  
**App version target:** 1.6.41 (after Mount Vernon 1.6.40 on the implementation branch)  
**Depends on:** LUN Builder site-template pattern (Hartford / Jupiter / Pendergrass / Mount Vernon specs)

## Problem

Operators need a Windsor, WI starting point in the LUN Builder picker. Inventory screenshots provide hosts (AS400, ESX, VIO, MQ, app), volumes, pool `Windsor_G3_Pool0`, FlashSystem 5200 context, and Port Definitions with Active WWPNs (except `pwinap01`).

## Goals

- Ship a built-in **Windsor, WI (Template)** in the Templates picker group.
- Seed the full site inventory, including offline/unmapped `pwinap01`.
- Pre-fill defaults: card hint `Windsor, WI`, storage profile `flashsystem_5200`, pool/CPG `Windsor_G3_Pool0`.
- Seed **Active** initiator WWPNs into `wwpn1` / `wwpn2`; use **multiple host rows** when a host has more than two Active ports.
- Leave `pwinap01` WWPNs blank (no Port Definitions screenshot provided).
- Reuse existing template UX: Save as new; Delete disabled on the template.

## Non-goals

- Seeding Offline ports or array canister FC ports as host WWPNs.
- Exact live `pwinvio01b_1`…`_5` spelling if expanded names include `_root_`.
- New UI chrome beyond card hint / existing template behavior.
- Changing Hartford, Jupiter, Pendergrass, or Mount Vernon content.

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Host / LUN scope | Full inventory including `pwinap01` |
| WWPN strategy | Seed Active ports; multi-row when >2 Active |
| `pwinap01` WWPNs | Blank |
| Card hint | `Windsor, WI` (not the longer FlashSystem string) |
| Profile / pool | `flashsystem_5200` / `Windsor_G3_Pool0` |
| Delivery | Built-in template catalog entry |

## Template content

**Id:** `template-windsor-wi`  
**Name:** Windsor, WI (Template)  
**Location:** Windsor, WI  
**Notes:** Seeded from Windsor FlashSystem 5200 inventory (Windsor_Cluster site). Active Port Definition WWPNs are filled except `pwinap01` (blank). Offline ports omitted. Defaults use card hint Windsor, WI, profile flashsystem_5200, pool Windsor_G3_Pool0.

### Defaults (build-level)

- `default_storage_profile`: `flashsystem_5200`
- `default_pool_or_cpg`: `Windsor_G3_Pool0`
- `default_card_hint`: `Windsor, WI`

LUN rows also carry the same profile, pool, and card hint.

### Hosts

All hosts `type=Generic`. Path fields other than name/WWPNs empty.

| Host | Rows | WWPN1 | WWPN2 |
|------|------|-------|-------|
| `AWN1` | 2 | `C050760B518B0000` | `C050760B518B0002` |
| `AWN1` | (row 2) | `C050760B518B0004` | `C050760B518B0006` |
| `PEN_WINESX_VM01` | 1 | `51402EC012CFD072` | `51402EC012CFD2BE` |
| `PEN_WINESX_VM02` | 1 | `51402EC012CFD090` | `51402EC012CFD2C4` |
| `PEN_WINESX_VM03` | 1 | `51402EC012C90280` | `51402EC012C904A4` |
| `pwinap01` | 1 | `""` | `""` |
| `pwinmq01` | 2 | `C050760B53990018` | `C050760B5399001A` |
| `pwinmq01` | (row 2) | `C050760B5399001C` | `C050760B5399001E` |
| `pwinvio01a` | 1 | `21000024FF86027C` | `21000024FF86027D` |
| `pwinvio01b` | 2 | `21000024FF86025C` | `21000024FF86025D` |
| `pwinvio01b` | (row 2) | `21000024FF86025E` | `""` |
| `pwinvio02a` | 1 | `21000024FF860A7C` | `21000024FF860A7D` |
| `pwinvio02b` | 2 | `21000024FF86048C` | `21000024FF86048D` |
| `pwinvio02b` | (row 2) | `21000024FF86048E` | `""` |

Total host rows: **14** (10 unique host names).

### LUN batches

Every batch: `storage_profile=flashsystem_5200`, `pool_or_cpg=Windsor_G3_Pool0`, `card_hint=Windsor, WI`.

| Purpose | Count | Size | Shared | Hosts | `name_prefix` | Cluster | Expected expand stem |
|---------|-------|------|--------|-------|---------------|---------|----------------------|
| `AWN1` | 6 | `500GB` | true* | `AWN1` | `AS400` | *(empty)* | `AS400_AWN1_N` |
| `ESX_DataStore` | 3 | `4TB` | true | all three `PEN_WINESX_VM0*` | `WIN` | *(empty)* | `WIN_ESX_DataStore_N` |
| `root` | 3 | `50GB` | false | `pwinap01` | `pwin` | `app` | `pwinap01_root_N` |
| `data` | 2 | `100GB` | false | `pwinap01` | `pwin` | `app` | `pwinap01_data_N` |
| `root` | 3 | `50GB` | false | `pwinmq01` | `pwin` | `mq` | `pwinmq01_root_N` |
| `root` | 2 | `100GB` | false | each `pwinvio01a`, `pwinvio02a`, `pwinvio02b` | `pwin` | `vio` | `pwinvio##_root_N` |
| `root` | 5 | `100GB` | false | `pwinvio01b` | `pwin` | `vio` | `pwinvio01b_root_N` |

\* Shared with a single host + prefix and empty cluster uses the prefix+purpose naming path for live-like `AS400_AWN1_N` names.  
Non-shared single-host batches ignore `cluster` for name stems (UI grouping only).

### Naming notes

- Live ESX volumes use `WIN_ESX_DataStore_1`…`3`; expanded names match that pattern.
- Live `pwinvio01b` volumes are `pwinvio01b_1`…`_5` without a middle purpose token; the template uses purpose `root` so names become `pwinvio01b_root_1`…`_5`, acceptable for create planning.

## UX

Same as other site templates:

1. Templates group lists Windsor with existing site templates.
2. Banner: template — use Save as new.
3. Save / Delete behavior unchanged for templates.

## Data / APIs

- Extend `seed_lun_builder_templates()` after Mount Vernon.
- Add `_windsor_host(lpar_name, wwpn1="", wwpn2="")`.
- Tests assert template id, defaults, host row count/names, seeded WWPNs (including blank `pwinap01`), LUN batch shapes, and API template id set includes `template-windsor-wi`.
- Bump `APP_VERSION` to `1.6.41` on the implementation branch that already includes Mount Vernon `1.6.40`.

## Out of scope follow-ups

- Filling `pwinap01` WWPNs later from Port Definitions
- Renaming `pwinvio01b` expanded volumes to drop `_root_`
- Importing Port Definitions CSV automatically
