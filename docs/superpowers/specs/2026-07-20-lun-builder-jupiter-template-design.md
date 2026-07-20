# LUN Builder Jupiter, FL Template — Design

**Date:** 2026-07-20  
**Status:** Approved for implementation  
**App version target:** 1.6.38  
**Depends on:** LUN Builder Hartford template pattern (`2026-07-18-lun-builder-hartford-template-design.md`)

## Problem

Operators need a Jupiter, FL starting point in the LUN Builder picker, similar to Hartford, CT. Inventory screenshots provide host names, pool, volume purposes/sizes, and FlashSystem 5200 context, but host WWPNs are not available from Mapped Volumes views on this array.

## Goals

- Ship a built-in **Jupiter, FL (Template)** in the Templates picker group.
- Seed **VIO root hosts** and **AIX/DB/res hosts** plus matching LUN batches.
- Pre-fill defaults: card hint `Jupiter, FL`, storage profile `flashsystem_5200`, pool/CPG `JUP_G3_Pool`, name prefix `pjup`.
- Leave **WWPN 1 / WWPN 2 blank** on every host; operators fill later from Port Definitions, VIOS/HBA data, or **Pull from FC WWPN**.
- Reuse Hartford template UX: Save as new for editable copies; Delete disabled on the template.

## Non-goals

- Seeding AS400 / `FC_AJP1` / VMware datastore volume sets (can add later).
- Embedding snapshot objects or snapshot schedules in LUN Builder.
- Auto-discovering WWPNs from FlashSystem GUI screenshots.
- Changing Preview/Run safety rules or requiring WWPNs before Save as new.

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| WWPN strategy | Blank; fill later |
| Host scope | VIO `pjupvio01a/b`–`04a/b` plus `pjupmhcdb2`, `pjupmhcdg2`, `pjupres01` |
| Profile / pool / card | `flashsystem_5200` / `JUP_G3_Pool` / `Jupiter, FL` |
| Delivery | Built-in template catalog entry beside Hartford |

## Template content

**Id:** `template-jupiter-fl`  
**Name:** Jupiter, FL (Template)  
**Location:** Jupiter, FL  
**Notes:** Seeded from Jupiter FlashSystem 5200 inventory. WWPNs are blank — set Port Definitions / Pull from FC WWPN before create. Defaults use card hint Jupiter, FL, profile flashsystem_5200, pool JUP_G3_Pool.

### Defaults (build-level)

- `default_storage_profile`: `flashsystem_5200`
- `default_pool_or_cpg`: `JUP_G3_Pool`
- `default_card_hint`: `Jupiter, FL`

LUN rows also carry the same profile, pool, and card hint so Preview works after Save as new without re-applying defaults.

### Hosts

One host row per name (not Hartford multi-path LPAR rows). Fields:

- `lpar_name` = storage host name
- `wwpn1` / `wwpn2` = `""`
- `type` = `Generic` (matches FlashSystem host type in inventory)
- Other path fields empty (`slot`, `remote_lpar`, etc.)

Host names:

- `pjupvio01a`, `pjupvio01b`, `pjupvio02a`, `pjupvio02b`, `pjupvio03a`, `pjupvio03b`, `pjupvio04a`, `pjupvio04b`
- `pjupmhcdb2`, `pjupmhcdg2`, `pjupres01`

### LUN batches

`name_prefix`: `pjup` on every batch. `shared`: false (single-host maps).

| Host(s) | Purpose | Count | Size |
|---------|---------|-------|------|
| Each `pjupvio*` | `root` | 2 | `100GB` |
| `pjupmhcdb2` | `root` | 3 | `50GB` |
| `pjupmhcdb2` | `data` | 9 | `100GB` |
| `pjupmhcdg2` | `root` | 3 | `50GB` |
| `pjupmhcdg2` | `data` | 9 | `100GB` |
| `pjupres01` | `data` | 5 | `100GB` |

Naming follows existing `_volume_name_base` / `expandLunBatch` rules (e.g. `pjupvio01a_root_1`, `pjupmhcdb2_data_1`). Live inventory used `pjupres01_1`…`_5` without a middle purpose token; the template uses purpose `data` so names become `pjupres01_data_1`…`_5`, which is acceptable for create planning.

### Cluster field

Optional cluster labels for grouping in the UI:

- VIO hosts: `vio`
- `pjupmhcdb2` / `pjupmhcdg2`: `db`
- `pjupres01`: `res`

## UX

Same as Hartford:

1. Templates group lists Jupiter beside Hartford.
2. Banner: template — use Save as new.
3. Save / Delete behavior unchanged for templates.
4. After Save as new, operator fills WWPNs (and may adjust counts) before Preview / Run Create.

## Data / APIs

- Extend `seed_lun_builder_templates()` in `launchpad/lun_builder_data.py` to return Hartford **and** Jupiter.
- Add a small host helper (e.g. `_jupiter_host(name)`) with blank WWPNs.
- Tests assert template id, location, defaults, host count/names, blank WWPNs, and key LUN batch shapes.
- Bump `APP_VERSION` to `1.6.38`.

## Out of scope follow-ups

- AS400 / VMware Jupiter batches
- Snapshot checklist integration
- Importing Port Definitions CSV to fill WWPNs automatically
