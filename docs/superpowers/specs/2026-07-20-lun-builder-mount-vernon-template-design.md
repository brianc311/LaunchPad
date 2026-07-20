# LUN Builder — Mount Vernon, IL site template

**Date:** 2026-07-20  
**Status:** Approved for implementation  
**App version target:** 1.6.40 (after Pendergrass 1.6.39 on the implementation branch)  
**Depends on:** LUN Builder site-template pattern (`2026-07-18-lun-builder-hartford-template-design.md`, Jupiter / Pendergrass specs)

## Problem

Operators need a Mount Vernon, IL starting point in the LUN Builder picker. Inventory screenshots provide hosts (AS400, ESX, VIO, test), volumes, pool `MtVerno_Pool1`, FlashSystem 5200 context, and Port Definitions with Active WWPNs.

## Goals

- Ship a built-in **Mount Vernon, IL (Template)** in the Templates picker group.
- Seed the full site inventory: AS400 + ESX + VIO + `tmtvtst1`.
- Pre-fill defaults: card hint `Mount Vernon, IL`, storage profile `flashsystem_5200`, pool/CPG `MtVerno_Pool1`.
- Seed **Active** initiator WWPNs into `wwpn1` / `wwpn2`; use **multiple host rows** when a host has more than two Active ports (Hartford-style).
- Reuse existing template UX: Save as new; Delete disabled on the template.

## Non-goals

- Seeding Offline ports.
- Exact live ESX zero-padded names (`MTV_ESXI_DS01`) if expanded names are `MTV_ESXI_DS_1`…`_4`.
- New UI chrome beyond card hint / existing template behavior.
- Changing Hartford, Jupiter, or Pendergrass content.

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Host / LUN scope | Full site: AS400 + ESX + VIO + `tmtvtst1` |
| WWPN strategy | Seed Active ports into `wwpn1`/`wwpn2` |
| >2 Active ports | Multiple host rows (pair Active WWPNs) |
| Profile / pool / card | `flashsystem_5200` / `MtVerno_Pool1` / `Mount Vernon, IL` |
| Delivery | Built-in template catalog entry |

## Template content

**Id:** `template-mount-vernon-il`  
**Name:** Mount Vernon, IL (Template)  
**Location:** Mount Vernon, IL  
**Notes:** Seeded from Mount Vernon FlashSystem 5200 inventory. Active Port Definition WWPNs are filled; Offline ports omitted. Defaults use card hint Mount Vernon, IL, profile flashsystem_5200, pool MtVerno_Pool1.

### Defaults (build-level)

- `default_storage_profile`: `flashsystem_5200`
- `default_pool_or_cpg`: `MtVerno_Pool1`
- `default_card_hint`: `Mount Vernon, IL`

LUN rows also carry the same profile, pool, and card hint.

### Hosts

All hosts `type=Generic`. Path fields other than name/WWPNs empty unless noted.

| Host | Rows | WWPN1 | WWPN2 |
|------|------|-------|-------|
| `amv1_as400` | 2 | `C050760B552B0004` | `C050760B552B0006` |
| `amv1_as400` | (row 2) | `C050760B552B0010` | `""` |
| `pen-mtvesx-vm01` | 1 | `51402EC012434DDC` | `51402EC012434DDE` |
| `pen-mtvesx-vm02` | 1 | `51402EC012435D38` | `51402EC012435D3A` |
| `pen-mtvesx-vm03` | 1 | `51402EC01243643C` | `51402EC01243643E` |
| `pmtvvio01a` | 1 | `21000024FF85BB40` | `21000024FF85BB41` |
| `pmtvvio01b` | 1 | `21000024FF85F054` | `21000024FF85F055` |
| `pmtvvio02a` | 1 | `21000024FF860A60` | `21000024FF860A61` |
| `pmtvvio02b` | 1 | `21000024FF86373E` | `21000024FF86373F` |
| `tmtvtst1` | 2 | `C050760B20CA0008` | `C050760B20CA000A` |
| `tmtvtst1` | (row 2) | `C050760B20CA000C` | `C050760B20CA000E` |

Total host rows: **11** (9 unique host names; AS400 and test duplicated for extra Active ports).

AS400 Active set from Port Definitions (10 ports total): `…0004`, `…0006`, `…0010`. Offline ports not seeded.

### LUN batches

Every batch: `storage_profile=flashsystem_5200`, `pool_or_cpg=MtVerno_Pool1`, `card_hint=Mount Vernon, IL`.

| Purpose | Count | Size | Shared | Hosts | `name_prefix` | Cluster | Expected expand stem |
|---------|-------|------|--------|-------|---------------|---------|----------------------|
| `AS400` | 10 | `500GB` | true* | `amv1_as400` | `AVM1` | *(empty)* | `AVM1_AS400_N` |
| `ESXI_DS` | 4 | `4TB` | true | all three `pen-mtvesx-vm0*` | `MTV` | *(empty)* | `MTV_ESXI_DS_N` |
| `root` | 2 | `100GB` | false | each `pmtvvio*` (4 batches) | `pmtv` | `vio` | `pmtvvio##_root_N` |
| `root` | 3 | `100GB` | false | `tmtvtst1` | `""` | `test` | `tmtvtst1_root_N` |

\* Shared with a single host + prefix and empty cluster uses the prefix+purpose naming path so live-like `AVM1_AS400_N` names are produced.  
Non-shared single-host batches ignore `cluster` for name stems (cluster is UI grouping only); VIO must expand to `pmtvvio01a_root_1`-style names.

### Naming notes

- Live ESX volumes use `MTV_ESXI_DS01`…`04`; expanded `_1`…`_4` is acceptable for create planning.
- VIO live names already match the LUN Builder pattern (`pmtvvio01a_root_1`).
- Test host live names match `tmtvtst1_root_1`…`_3`.

## UX

Same as Hartford / Jupiter / Pendergrass:

1. Templates group lists Mount Vernon with other site templates.
2. Banner: template — use Save as new.
3. Save / Delete behavior unchanged for templates.

## Data / APIs

- Extend `seed_lun_builder_templates()` after Hartford / Jupiter / Pendergrass.
- Add `_mount_vernon_host(lpar_name, wwpn1, wwpn2)` (or reuse shared site-host helper with WWPN args).
- Tests assert template id, defaults, host row count/names, seeded WWPNs, LUN batch shapes, and API template id set includes `template-mount-vernon-il`.
- Bump `APP_VERSION` to `1.6.40` on the implementation branch that already includes Pendergrass `1.6.39`.

## Out of scope follow-ups

- Seeding Offline VIO/AS400/test ports
- Zero-padding ESX datastore suffixes to match live `DS01` spelling
- Importing Port Definitions CSV automatically
