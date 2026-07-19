# LUN Builder Hartford Template — Design

**Date:** 2026-07-18  
**Status:** Implemented  
**App version target:** 1.6.23  
**Depends on:** LUN Builder (`2026-07-18-lun-builder-design.md`)

## Problem

Operators often start from the Connecticut / Hartford host+WWPN and LUN requirements sheet instead of a blank build. LUN Builder currently only offers empty “New build,” so Hartford must be re-entered by hand or imported each time.

## Goals

- Ship a built-in **Hartford, CT (Template)** that always appears in the LUN Builder picker.
- Template includes **hosts/FC paths** and the **full SPS / MFS / BT LUN plan** from the Connecticut sheet.
- Selecting the template does **not** replace “New build”; it is an alternative starting point.
- Operators create an editable saved copy via **Save as new** (template itself is not deletable).
- Leave `storage_profile` and `pool_or_cpg` **blank** on seeded LUN rows so Preview/Run never assume the wrong array.

## Non-goals

- Auto-reading the live OneDrive `Connecticut_NewHosts_WWNS.xlsx` on every launch.
- Additional site templates beyond Hartford in this change (same pattern can add more later).
- Changing export/import/Preview/Run safety rules.
- Auto-filling pools or storage profiles.

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Content | Hosts + full LUN plan (not hosts-only; not three separate templates) |
| Profile / pool defaults | Blank |
| Delivery | Built-in template catalog (Approach B), not “seed only when empty” |
| Picker | Templates group + Saved builds group |
| Persist template edits | Save blocked / redirected to Save as new; Delete disabled on templates |

## Template content

**Id:** `template-hartford-ct`  
**Name:** Hartford, CT (Template)  
**Location:** Hartford, CT  
**Notes:** Seeded from Connecticut New Hosts / WWPN planning sheet. Set storage profile and pool/CPG before Preview or Run Create.

### Hosts

All LPAR client FC path rows from the sheet, including:

- LPARs: `pconsps3`, `pconsps4`, `pconmfs3`, `pconmfs4`, `pconbt3`, `pconbt4`
- Four paths per LPAR (VIOS pairs / slots / WWPN #1 / WWPN #2 / physical FC / managed system name+serial)
- Fields map to existing LUN Builder host columns (`lpar_name`, `slot`, `state`, `required`, `type`, `remote_lpar`, `remote_slot`, `wwpn1`, `wwpn2`, `physical_fc_slot`, `managed_system_name`, `managed_system_serial`, `notes`)

Exact WWPN and location codes are transcribed from the Connecticut sheet / operator screenshot into `seed_lun_builder_templates()` (source of truth in code + tests). Prefer importing the xlsx into the seed if a readable copy is available during implementation; otherwise use the approved screenshot transcription and lock key rows in tests.

### LUN batches

`storage_profile` and `pool_or_cpg` empty on every row. `cluster` set to SPS / MFS / BT. Host maps:

| Cluster | Rows |
|---------|------|
| SPS | Per LPAR `pconsps3`, `pconsps4`: 3×50GB root, `shared=false`, `host_names=[that LPAR]` |
| SPS | Shared on `[pconsps3, pconsps4]`: 7×100GB `ora1vg`; 2×200GB `archvg`; 1×100GB `sps1redovg1`; 1×100GB `sps1redovg2`; 1×10GB `caavg_private` |
| MFS | Per LPAR `pconmfs3`, `pconmfs4`: 3×50GB root, not shared |
| MFS | Shared on `[pconmfs3, pconmfs4]`: 7×100GB `ora1vg`; 1×200GB `archvg`; 1×100GB `mfs1redovg1`; 1×100GB `mfs1redovg2`; 1×10GB `caavg_private` |
| BT | Per LPAR `pconbt3`, `pconbt4`: 3×50GB root, not shared |
| BT | Shared on `[pconbt3, pconbt4]`: 14×100GB `ora1vg`; 2×100GB `archvg`; 1×100GB `btfs1redovg1`; 1×100GB `btfs2redovg2`; 1×10GB `caavg_private` |

Sizes stored as strings such as `50GB`, `100GB`, `200GB`, `10GB` (existing expand/parse rules apply).

## UX

1. Picker lists **Templates** (e.g. Hartford) then **Saved builds**.
2. Selecting a template loads hosts + LUNs into the editor with a clear banner: template — use **Save as new** to keep a copy.
3. **Save** on a template either no-ops with a status message or triggers the Save-as-new flow.
4. **Delete** is disabled while a template is selected.
5. **Save as new** creates a normal saved build (new id, name like `Hartford, CT` without “(Template)”), editable/deletable thereafter.
6. **New build** remains a blank build.

## Data / APIs

- Add `seed_lun_builder_templates() -> list[dict]` in `lun_builder_data.py`.
- Mark templates with `"is_template": true` (and stable ids prefixed `template-`).
- `GET /api/lun-builds` returns `{ "builds": saved..., "templates": [...], "persisted": bool }` **or** merges templates client-side from a small `/api/lun-builds/templates` endpoint. Prefer returning both `builds` and `templates` on the existing GET to avoid an extra round-trip.
- Templates are **not** written into `lun_builds` settings unless the operator Save-as-news them.
- Upsert/delete APIs reject `is_template` / `template-*` ids with a clear error.

## Files to touch

- `launchpad/lun_builder_data.py` — seed Hartford template
- `launchpad/lun_builder.py` — picker groups, banner, Save/Delete guards
- `launchpad/health_server.py` — include templates in GET; reject template delete/overwrite
- `launchpad/config.py` — `1.6.23`
- `tests/test_lun_builder_data.py` — host counts, LUN batch counts, blank profile/pool
- `tests/test_lun_builder_page.py` / `test_health_server_lun_builder.py` — picker/API contracts

## Manual test plan

1. Open LUN Builder → Hartford template appears under Templates even with zero saved builds.
2. Select Hartford → hosts and LUN rows populate; profile/pool empty.
3. Delete stays disabled; Save prompts Save as new.
4. Save as new → appears under Saved builds; can edit, export, Preview after filling profile/pool.
5. New build still creates an empty build.

## Out of scope / later

- Houston / Windsor / other site templates.
- Auto-sync from OneDrive Excel.
- Pre-selecting a LaunchPad SSH card on the template.
