# SSH Inventory Sync — LUN Builder + Contingency Groups

**Date:** 2026-07-21  
**Status:** Approved for implementation  
**App version target:** next patch on the implementation branch  
**Depends on:** LUN Builder; Contingency Groups + `generate_snap_rows`; Health Card SSH / FC inventory plumbing  
**Approach:** Extend LUN Builder Pull into full **Sync Inventory** (Approach A)

## Problem

Site templates and Contingency Groups seeds are built by hand from GUI screenshots. That is slow, error-prone (OCR, missing Port Definitions), and drifts from the live array. Operators need LaunchPad hosts, LUNs, mappings, and Contingency Groups to **match what SSH returns** from the FlashSystem.

## Goals

- Add **Sync Inventory** on LUN Builder: pick a Health Card → live SSH → replace the current build’s hosts and LUN rows from array inventory.
- Upsert a **Contingency Groups** site keyed by card hint (name/location), with source volumes, real SCSI maps, then `generate_snap_rows()`.
- Exact live volume names, capacities, pools, UIDs, host WWPNs, and SCSI IDs from CLI — not screenshots.
- Skip FlashCopy-target-like volumes as sources; generate LaunchPad `_snap` rows after import.
- Keep built-in catalog templates immutable; Sync writes saved builds / CG sites only.

## Non-goals (v1)

- Syncing into `/fc-consistgrp` (IBM FlashCopy Consistency Groups UI).
- HPE 3PAR / non–Spectrum Virtualize profiles.
- Overwriting git-seeded built-in LUN templates or Contingency Groups seed modules.
- Merge mode (preserving local-only edits) — v1 is replace-only.
- Auto-committing generated Python seed files.

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Surfaces | LUN Builder + Contingency Groups |
| Approach | Extend Pull → Sync Inventory (Approach A) |
| Data source | Live SSH refresh on button press |
| Apply mode | Replace hosts/LUNs (and CG hosts/volumes/maps) |
| Snap handling | Sources only + `generate_snap_rows()` |
| CG destination | Upsert site by card hint |
| Built-in templates | Unchanged by Sync |

## Behavior

### Trigger

- LUN Builder UI: **Sync Inventory** button (evolves or replaces **Pull from FC WWPN**).
- Operator selects a Health Card (same card-hint / name resolution as existing pull).
- Card device profile must be Spectrum Virtualize / FlashSystem family (`SVC_PROFILES`).

### Live SSH suite

Run against the selected card (via existing `run_remote_ssh_command` / suite helpers):

| Purpose | Command |
|---------|---------|
| Hosts | `svcinfo lshost -delim :` |
| Host WWPNs | Per-host detail and/or fabric path consistent with today’s FC host WWPN mapping |
| Volumes | `svcinfo lsvdisk -delim :` |
| Maps | `svcinfo lshostvdiskmap -delim :` |

On total suite failure: **hard error**; do not replace the build or CG site. Partial command failures: hard error unless a documented subset still yields a complete host+volume+map picture (prefer fail closed in v1).

### LUN Builder (replace)

1. Clear current build `hosts` and `luns`.
2. Seed **hosts** from `lshost` + WWPNs: `type=Generic`; pack Active WWPNs into `wwpn1`/`wwpn2`; extra host rows when >2 WWPNs (Windsor-style).
3. Seed **LUN rows** as one batch per source volume:
   - Live name as exact volume name (`count=1`, exact-name / purpose = live name).
   - `host_names` and `shared` from maps; `scsi_or_lun_id` from map SCSI ID when a single consistent id applies (or leave blank on LUN row if multi-host ids differ — CG maps carry per-host SCSI IDs).
   - Size, pool, profile, card_hint from volume + card defaults.
4. Set build defaults: `default_storage_profile`, `default_pool_or_cpg` (dominant pool among imported volumes), `default_card_hint` from card.
5. **Exclude** volumes whose names match FlashCopy-target heuristics (e.g. `*_snap`, `*_Snap*`, case-insensitive). Count exclusions in warnings.

If the open build is a built-in template (`is_template`), Sync still applies in-memory / Save-as-new flow — never persist over `template-*` ids in settings.

### Contingency Groups (upsert by card hint)

1. Resolve site key from card hint / card name (same string used as LUN `card_hint` / CG name+location).
2. If a group with that name/location (or stable id slug) exists, **replace** its hosts/volumes/maps; else create.
3. Hosts: name, status, `port_count`, `wwpns[]` from live data.
4. Volumes: sources only; capacity, pool, UID from `lsvdisk`.
5. Maps: volume ↔ host ↔ SCSI ID from `lshostvdiskmap`.
6. `storage_hint`: card identity already used for capacity/FC (e.g. monitor card name like `v7kand-g3v1` when that is the card’s storage label).
7. Wrap with `generate_snap_rows()` before save.

### UX feedback

Return and display:

- Hosts / volumes / maps imported counts
- Snap-like volumes skipped
- Warnings (missing WWPNs, unmapped volumes, etc.)
- CG site id/name upserted

## Architecture

| Piece | Responsibility |
|-------|----------------|
| `launchpad/inventory_sync.py` (new) | Pure mappers: CLI tables → LUN hosts/luns + CG group dict; snap-name exclusion; pool default |
| `flashsystem_fc.py` / volume parsers | Parse `lsvdisk` / enrich host WWPNs as needed |
| `HealthServer.sync_inventory` | Card resolve → live SSH → map → replace build → upsert CG → response |
| `lun_builder.py` UI | Sync Inventory button, card picker, status summary |
| Contingency Groups API/settings | Upsert path reused by sync |

API shape (illustrative):

`POST /api/lun-builds/sync-inventory`  
Body: `{ "build_id": "...", "card_name": "..." }`  
Response: `{ "build": ..., "builds": ..., "group": ..., "groups": ..., "pulled": { "hosts", "volumes", "maps", "skipped_snaps" }, "warnings": [...] }`

Keep `pull-fc` working or redirect it to the host-only subset; prefer one primary button labeled Sync Inventory that performs the full replace.

## Error handling

| Condition | Behavior |
|-----------|----------|
| Card not found | 4xx + message; no mutation |
| Non-SVC profile | 4xx + message; no mutation |
| SSH / parse failure | 5xx or 4xx with error; **no** partial replace |
| Empty inventory | Succeed with zeros + warning; replace with empty hosts/luns only if that is explicit — prefer warn and refuse empty replace if hosts and volumes both empty |

## Testing

- Fixture-based unit tests for mappers (hosts multi-WWPN, exact LUN names, shared maps, SCSI IDs, snap exclusion, `generate_snap_rows`).
- API test: successful sync replaces build and upserts CG; failed SSH leaves prior build/CG unchanged.
- UI wiring covered lightly (button calls new endpoint) if existing lun_builder page tests pattern allows.

## Out of scope follow-ups

- IBM Consistency Group membership sync into `/fc-consistgrp`
- Export synced inventory as committed seed modules
- Merge mode and interactive preview/confirm dialog
- Richer FC-target detection via `lsfcmap` / `lsconsistgrp`
