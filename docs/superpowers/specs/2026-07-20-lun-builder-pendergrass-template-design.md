# LUN Builder — Pendergrass, GA site template

**Date:** 2026-07-20  
**Status:** Approved for implementation  
**App version target:** 1.6.39 (after Jupiter 1.6.38 on the implementation branch)  
**Depends on:** LUN Builder Hartford / Jupiter template pattern (`2026-07-18-lun-builder-hartford-template-design.md`, `2026-07-20-lun-builder-jupiter-template-design.md`)

## Problem

Operators need a Pendergrass, GA starting point in the LUN Builder picker. Inventory screenshots provide two ESX hosts, five shared volumes, pool `G3_PEN_Pool1`, and FlashSystem 5200 context. Host initiator WWPNs are not on the Hosts list in a form we can seed; array canister FC ports from the Ports view must not be stored as host WWPNs.

## Goals

- Ship a built-in **Pendergrass, GA (Template)** in the Templates picker group.
- Seed two ESX hosts and three shared LUN batches matching inventory sizes.
- Pre-fill defaults: card hint `Pendergrass, GA`, storage profile `flashsystem_5200`, pool/CPG `G3_PEN_Pool1`, name prefix `PEN`.
- Leave **WWPN 1 / WWPN 2 blank** on every host; operators fill later from Port Definitions or **Pull from FC WWPN**.
- Reuse Hartford/Jupiter template UX: Save as new for editable copies; Delete disabled on the template.

## Non-goals

- Storing array-side FC canister ports as host `wwpn1` / `wwpn2`.
- Exact live volume name spelling (`PEN_ESX_VOL_01`) if the existing LUN name builder produces an equivalent create plan.
- New UI chrome beyond card hint / existing template behavior.
- Auto-merge into user-owned saved builds.
- Changing Hartford or Jupiter content.

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| WWPN strategy | Blank; fill later |
| Host scope | `pen_penesx_vm05`, `pen_penesx_vm06` |
| Profile / pool / card | `flashsystem_5200` / `G3_PEN_Pool1` / `Pendergrass, GA` |
| LUN mapping | All five volumes shared to both hosts |
| Delivery | Built-in template catalog entry beside Hartford / Jupiter |

## Template content

**Id:** `template-pendergrass-ga`  
**Name:** Pendergrass, GA (Template)  
**Location:** Pendergrass, GA  
**Notes:** Seeded from Pendergrass FlashSystem 5200 inventory. WWPNs are blank — set Port Definitions / Pull from FC WWPN before create. Defaults use card hint Pendergrass, GA, profile flashsystem_5200, pool G3_PEN_Pool1.

### Defaults (build-level)

- `default_storage_profile`: `flashsystem_5200`
- `default_pool_or_cpg`: `G3_PEN_Pool1`
- `default_card_hint`: `Pendergrass, GA`

LUN rows also carry the same profile, pool, and card hint so Preview works after Save as new without re-applying defaults.

### Hosts

One host row per name. Fields:

- `lpar_name` = storage host name
- `wwpn1` / `wwpn2` = `""`
- `type` = `Generic` (matches FlashSystem host type in inventory)
- Other path fields empty (`slot`, `remote_lpar`, etc.)

Host names:

- `pen_penesx_vm05`
- `pen_penesx_vm06`

### LUN batches

`name_prefix`: `PEN` on every batch. `shared`: true. `host_names`: both ESX hosts. `cluster`: `esx`.

| Purpose | Count | Size |
|---------|-------|------|
| `ESX_VOL` | 3 | `2TB` |
| `ESX_VOL` | 1 | `4TB` |
| `ESX_VOL_COREDUMP` | 1 | `100GB` |

Two separate `ESX_VOL` batches are required because sizes differ (cannot be one count batch).

Naming follows existing `_volume_name_base` / `expandLunBatch` rules (e.g. `PENesx_ESX_VOL_1`). Live inventory used `PEN_ESX_VOL_01`…`_04` and `PEN_ESX_VOL_COREDUMP`; the template naming is acceptable for create planning.

## UX

Same as Hartford / Jupiter:

1. Templates group lists Pendergrass beside existing site templates.
2. Banner: template — use Save as new.
3. Save / Delete behavior unchanged for templates.
4. After Save as new, operator fills WWPNs (and may adjust counts/sizes) before Preview / Run Create.

## Data / APIs

- Extend `seed_lun_builder_templates()` in `launchpad/lun_builder_data.py` to include Pendergrass (after Hartford and Jupiter when Jupiter is on the branch).
- Reuse blank-WWPN host helper pattern (e.g. `_pendergrass_host(name)` or a shared `_site_host(name)`).
- Tests assert template id, location, defaults, host count/names, blank WWPNs, shared mapping, and LUN batch shapes/sizes.
- Bump `APP_VERSION` to `1.6.39` on the implementation branch that already includes Jupiter `1.6.38`.

## Out of scope follow-ups

- Capturing array canister WWPNs from the Ports screenshot
- Importing Port Definitions CSV to fill WWPNs automatically
- Renaming expanded volumes to match live `PEN_ESX_VOL_0N` spelling exactly
