# FlashCopy Consistency Groups management

**Date:** 2026-07-21  
**Status:** Approved for implementation  
**App version target:** Next patch on the implementation branch (after current tip at start of work)  
**Depends on:** Health server browser pages pattern; SSH FlashSystem CLI (`run_ssh_command` / Contingency snap create style); unlocked LaunchPad card credentials

## Problem

Operators manage IBM FlashCopy Consistency Groups (CGs) on FlashSystem arrays in the native GUI (e.g. Woodland Hills `AWD1_AS400_CG` with member `fcmap*` mappings). LaunchPad Contingency Groups can create stand-alone `_snap` FlashCopy maps, but cannot list, create, assign, start, or delete **array** FlashCopy Consistency Groups. Operators need a dedicated LaunchPad surface for live CG management with Preview → confirm safety.

## Goals

- Ship a new top-level browser page: **FlashCopy Consistency Groups**.
- Select target array via **in-page SSH card picker** and via a **Dashboard** shortcut that opens the page (optionally pre-selecting a card).
- Support **full edit** for v1: view inventory, create CG, assign maps, remove maps from CG, prepare+start CG, delete empty CG.
- All mutating actions use **Preview / Dry-run → Confirm → Run** (same safety model as Contingency Groups `_snap`).
- Reuse existing SSH inventory/execute patterns; skip-if-exists where inventory already shows the object.

## Non-goals

- Creating FlashCopy maps / target volumes (Contingency `_snap` or array UI remains the path).
- Merging Woodland Hills into Contingency Groups seeds (separate PR; not this feature).
- Wiring Contingency snap create to auto-assign maps into a CG (optional follow-up).
- Full stop/suspend state machine beyond prepare + start.
- Non-SSH / non-Spectrum-Virtualize arrays.
- Desktop-only CustomTkinter CG tables (browser page is the UI).

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Placement | New top-level page (not inside Contingency Groups) |
| Operations | Full edit: view, start, create, assign/remove maps, delete empty CG |
| Array selection | Both Dashboard shortcut and in-page card picker |
| Safety | Preview then confirm for all mutations |

## Architecture

```
Dashboard "FlashCopy CGs" ──▶ open browser /fc-consistgrp(?card=ID)
                                      │
                         ┌────────────▼────────────┐
                         │ fc_consistgrp page (HTML)│
                         │ card picker · CG table   │
                         │ maps · Preview / Run     │
                         └────────────┬────────────┘
                                      │ API
                         ┌────────────▼────────────┐
                         │ HealthServer            │
                         │ inventory / preview/run │
                         └────────────┬────────────┘
                                      │ SSH
                         ┌────────────▼────────────┐
                         │ fc_consistgrp_ops       │
                         │ parse + build SnapSteps │
                         └─────────────────────────┘
```

### Modules (proposed)

| Module | Responsibility |
|--------|----------------|
| `launchpad/fc_consistgrp.py` | Embedded HTML/CSS/JS page; path constant |
| `launchpad/fc_consistgrp_ops.py` | Parse `lsfcconsistgrp` / `lsfcmap`; build preview/run steps; validate |
| `launchpad/health_server.py` | Register route `/fc-consistgrp`; APIs for inventory, preview, run |
| `launchpad/ui/dashboard_view.py` | Button to open page (register cards / ensure server; optional card hint) |

## UI

### Entry

- Dashboard button **FlashCopy CGs** opens the local health-server page in the default browser.
- Cross-links from Health / Capacity / Contingency / Snapshot Schedule nav bars.
- Page requires LaunchPad unlocked with SSH cards registered (same guidance copy style as Capacity Report).

### Page chrome

1. **Array** dropdown — SSH storage cards (name / hint / IP as available).
2. **Refresh** — re-query CG and map inventory for the selected card.
3. **Consistency Groups** table — name, status, relationship/map count.
4. **Member maps** panel — for selected CG: map name, source, target, status, progress (when present).
5. **Stand-alone maps** — FlashCopy maps not in a CG (assign candidates).
6. **Actions** — Create CG; Assign selected stand-alone map(s); Remove selected member map(s); Start CG; Delete CG.
7. **Preview / Dry-run** and **Run** (enabled after successful preview), with modal showing CLI steps, skips, warnings, and run log.

### Status / empty states

- No cards / locked: explain unlock + open from Dashboard.
- Card selected but inventory error: show SSH/CLI error text.
- Empty CG list: allow Create.

## CLI inventory and mutations

Commands use `svcinfo` / `svctask` prefixes for FlashSystem / Spectrum Virtualize compatibility.

### Inventory

| Purpose | Command |
|---------|---------|
| List CGs | `svcinfo lsfcconsistgrp -delim :` (fallback without `-delim` if needed) |
| List maps | `svcinfo lsfcmap -delim :` |

Parse into structures:

- CG: `id`, `name`, `status`, `map_count` (or derived from maps)
- Map: `id`, `name`, `source`, `target`, `status`, `progress`, `consistgrp` (empty → stand-alone)

### Mutations (Preview + Run)

| Action | Commands |
|--------|----------|
| Create CG | `svctask mkfcconsistgrp -name NAME` |
| Assign map to CG | `svctask chfcmap -consistgrp CGNAME MAPNAME` |
| Remove map from CG | `svctask chfcmap -consistgrp null MAPNAME` (document exact stand-alone form if code/firmware differs; verify in implementation against IBM CLI for the deployed code level) |
| Prepare + Start CG | `svctask prestartfcconsistgrp CGNAME` then `svctask startfcconsistgrp CGNAME` |
| Delete CG | `svctask rmfcconsistgrp CGNAME` — only when CG has no member maps (UI + server both enforce) |

### Preview / Run contract

Mirror Contingency snap create:

- Build ordered `SnapStep`-like steps (`kind`, `purpose`, `cmd`, `skip`, `reason`).
- Preview returns steps + warnings; does not execute.
- Run requires explicit confirm flag; executes non-skipped steps over SSH on the selected card; returns per-step log.
- Skip when inventory already shows CG/map membership as requested.
- Warnings for: delete non-empty CG, assign map already in another CG, missing names, unsafe CLI tokens.

## APIs (sketch)

| Method | Path | Body / query | Result |
|--------|------|--------------|--------|
| GET | `/fc-consistgrp` | — | HTML page |
| GET | `/api/fc-consistgrp/inventory` | `card_id` | `{ card, groups, maps, stand_alone, warnings }` |
| POST | `/api/fc-consistgrp/preview` | `{ card_id, action, ... }` | `{ ok, steps, warnings }` |
| POST | `/api/fc-consistgrp/run` | `{ card_id, action, confirm: true, ... }` | `{ ok, log, warnings }` |

Action payloads (examples):

- `create_group`: `{ name }`
- `assign_maps`: `{ group_name, map_names: [] }`
- `remove_maps`: `{ map_names: [] }`
- `start_group`: `{ group_name }`
- `delete_group`: `{ group_name }`

## Safety and unlock

- Inventory and mutations require unlocked crypto + resolvable SSH auth for the card.
- Run without `confirm: true` is rejected.
- Delete empty-only enforced server-side even if UI is bypassed.
- No persistent LaunchPad seed of array CG membership required for v1 (live inventory is source of truth).

## Testing

- Unit: parsers for `lsfcconsistgrp` / `lsfcmap` sample tables.
- Unit: step builders for create / assign / remove / start / delete (including skip-if-exists and delete-non-empty refusal).
- API tests with mocked SSH / inventory (preview without confirm; run with confirm; delete blocked when maps present).
- No requirement for live array in CI.

## Out of scope follow-ups

- Contingency `_snap` create option: “add maps to CG X”
- Stop CG / stop map controls
- Excel export of CG inventory
- Deep-link seed for Woodland Hills `AWD1_AS400_CG` as a favorite
