# LUN Builder — Design

**Date:** 2026-07-18  
**Status:** Approved  
**App version target:** 1.6.22  
**Depends on:**
- Health Dashboard / `health_server.py` page routing
- Storage profiles in `launchpad/storage_presets.py`
- Existing Excel export patterns (`openpyxl`) and Contingency-style Save / Preview / Run safety
- FC WWPN inventory (optional host/WWPN pull)

## Problem

Operators build LUNs for IBM FlashSystem / Storwize / SVC and HPE 3PAR / Primera (and plan for DS8884 / XIV) using spreadsheets like the Hartford, CT host/FC + LUN requirements sheet. LaunchPad already monitors storage and can create contingency `_snap` volumes, but there is no reusable **LUN Builder** to:

- Keep a running list of planned builds (save, reopen, add more)
- Capture Hartford-style host/FC path rows and LUN batch specs
- Export clean Excel and CSV for handoff
- Optionally Preview and Run create/map commands on the array when desired

## Goals

- New **LUN Builder** page: site/project builds with persistent Save / Save as new / Delete.
- Editable **Hosts / FC paths** and **LUN specs** tables (multi-system rows in one build).
- Host input via **FC inventory pull**, **manual edit**, and **Excel/CSV import**.
- **Excel (.xlsx)** and **CSV** export suitable as a storage-team working sheet.
- Optional **Preview / Dry-run → confirm → Run Create** for Spectrum Virtualize and HPE 3PAR/Primera.
- Optional **first-time wizard** overlay that teaches Hosts → LUNs → Save/Export/Preview.
- Support the locked storage profile list (including Storwize Generic / G2 / G3).

## Non-goals (v1)

- Auto-creating hosts on the array.
- Fabric zoning or waiting for path discovery.
- Live Run Create on IBM DS8884 or XIV (plan + export + generated CLI text only in v1).
- Replacing Contingency Groups, Snapshot Schedule, or FC WWPN Report.
- Auto-selecting pools/CPGs from live inventory (operator enters or imports them).

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Product shape | Contingency-style library (Approach A) with Excel/CSV import + CLI Preview/Run |
| Build scope | Multi-system allowed in one build (each LUN row has a storage profile / card) |
| Host/WWPN entry | Inventory + manual + Excel/CSV import |
| Organization | By site/project (e.g. Hartford, CT), optional first-time wizard overlay |
| Storwize options | Generic, V7000 G2, V7000 G3 |
| Plans vs execute | Produce plans/exports always; Run Create optional after Preview + confirm |
| Live Run v1 | Spectrum Virtualize family + HPE 3PAR / Primera; DS8884 / XIV plan-first |

## Supported storage profiles (v1 picker)

- HPE - 3PAR 8200  
- HPE - 3PAR 8450  
- HPE - Primera 600 4-way  
- IBM - DS8884  
- IBM - FlashSystem 5200 / 7200 / 7300 / 9200 / 9500  
- IBM - SAN Volume Controller (2145-SV1)  
- IBM - Storwize V7000 Generic / G2 / G3  
- IBM - XIV 114 / 2812  
- IBM - XIV Gen 3- 314  

Map picker labels to existing `DEVICE_PROFILES` / preset keys in `storage_presets.py` (add a Generic Storwize key if missing; reuse G2/G3 keys).

## Data model

Setting key (proposed): `lun_builds`.

### Build header

| Field | Notes |
|-------|--------|
| `id` | Stable slug id |
| `name` | e.g. Hartford, CT |
| `location` | Optional |
| `notes` | Free text |
| `updated_at` | ISO timestamp on save |
| `hosts` | List of host/FC path rows |
| `luns` | List of LUN batch/spec rows |

### Host / FC path row (Hartford-style)

| Field | Example |
|-------|---------|
| `lpar_name` | pconsps3 |
| `slot` | 5 |
| `state` | Off |
| `required` | false |
| `type` | client |
| `remote_lpar` | pconvio01b |
| `remote_slot` | … |
| `wwpn1` / `wwpn2` | c050760c9594000e |
| `physical_fc_slot` | U78DA…-T0 |
| `managed_system_name` | F_PCONSLS3-… |
| `managed_system_serial` | 78A9F81 |
| `notes` | e.g. root LUN notes |

### LUN spec row

| Field | Notes |
|-------|--------|
| `name` / `purpose` | e.g. ora1vg, root, caavg_private |
| `count` | Integer ≥ 1 |
| `size` | e.g. 100GB / 100 GiB (normalize on export/run) |
| `shared` | boolean |
| `storage_profile` | One of the supported profiles |
| `pool_or_cpg` | IBM pool / HPE CPG / DS extent pool / XIV pool as applicable |
| `host_names` | Hosts to map (from build hosts or free text) |
| `scsi_or_lun_id` | Optional starting ID or explicit map rules |
| `card_hint` | LaunchPad SSH card name for Preview/Run |
| `cluster` / `group` | Optional label (SPS / MFS / BT) for sheet grouping |

Expand `count × size` into individual planned volume names at Preview/export time using a clear naming rule (e.g. `{purpose}_{nn}` or operator-supplied pattern).

## UX

### Entry

- Health Dashboard button → `/lun-builder`.
- Build picker + **New build**.
- Primary tables always available (site/project model).
- Dismissible **first-time wizard**: Site → Hosts → LUN batches → Review (Save / Export / Preview).

### Actions

- **Save**, **Save as new**, **Delete**
- **Import Excel/CSV** (review merge vs replace)
- **Export Excel**, **Export CSV**
- **Pull from FC WWPN** (optional merge into hosts)
- **Preview / Dry-run**, **Run Create** (gated on successful preview this session; save-before-ops)

### Create & Map panel

- Select LUN rows (and resolve cards via `card_hint` / profile).
- Checklist: create volumes → map to hosts (vendor-specific).
- Modal log for Preview/Run results (preserve `[hidden]` modal CSS pattern).

## Export / import

### Excel

Styled `.xlsx` with at least:

1. **Hosts** — Hartford-style columns  
2. **LUN Plan** — specs and/or expanded volume list  
3. **By System** — grouped by `storage_profile` / card  

### CSV

Equivalent flat export (single CSV or multiple named CSVs). Prefer one hosts CSV + one LUNs CSV, or a ZIP if multi-file is cleaner.

### Import

Accept Hartford-like sheets or simpler LUN-only CSVs; show parse warnings; do not auto-run create.

## Preview / Run engine

### Live Run (v1)

| Family | Profiles | Commands (illustrative) |
|--------|----------|-------------------------|
| Spectrum Virtualize | FlashSystem *, Storwize Generic/G2/G3, SVC | `mkvdisk` + `mkvdiskhostmap` (SVC CLI; same family as Contingency create) |
| HPE 3PAR / Primera | 8200, 8450, Primera 600 | `createvv` + `createvlun` (3PAR CLI; Primera uses the same family unless presets differ) |

Safety (match Contingency `_snap`):

- Sanitize CLI tokens
- Skip-if-exists where inventory can detect
- Preview required before Run; `confirm: true` on create API
- No automatic host create

### Plan-only (v1)

| Family | Behavior |
|--------|----------|
| DS8884 | Export + generated `dscli` text in Preview |
| XIV | Export + generated XIV CLI text in Preview |

## APIs (proposed)

- `GET/POST` lun builds CRUD (or single settings upsert like contingency groups)
- `POST /api/lun-builds/import`
- `GET /api/lun-builds-export?format=xlsx|csv&id=…`
- `POST /api/lun-builds/preview`
- `POST /api/lun-builds/create` with `{ confirm: true }`

Exact route naming may follow existing contingency/health_server conventions.

## Files to touch (implementation sketch)

- `launchpad/lun_builder.py` — page HTML/JS  
- `launchpad/lun_builder_data.py` — normalize, expand batches, validation  
- `launchpad/lun_builder_export.py` — xlsx + csv  
- `launchpad/lun_builder_create.py` — preview/run step builder + SSH runner  
- `launchpad/health_server.py` — routes + dashboard link  
- `launchpad/config.py` — version bump  
- `tests/test_lun_builder_*.py`

## Manual test plan

1. Create Hartford-like build; add hosts and LUN batches for SPS/MFS/BT; Save; reopen.  
2. Export Excel and CSV; open Excel and confirm Hosts + LUN Plan sheets.  
3. Import a CSV/Excel and merge into a new build.  
4. Preview FlashSystem or 3PAR steps with a valid card; Run Create only after Preview (lab array).  
5. DS8884/XIV rows show generated CLI in Preview but do not enable live Run.  
6. First-time wizard can be completed and dismissed without blocking advanced table edit.

## Out of scope / later

- Live Run for DS8884 / XIV  
- Drag-from-live volume browser as the only LUN entry path  
- Automatic pool/CPG picker from `lsmdiskgrp` / `showcpg`  
- Cross-link that auto-pushes built LUNs into Contingency Groups  
