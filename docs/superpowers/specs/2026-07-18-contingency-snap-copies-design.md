# Contingency Groups `_snap` Copies — Design

**Date:** 2026-07-18  
**Status:** Approved for implementation (pending user review of this file)  
**App version target:** next bump after current (e.g. 1.6.20)  
**Depends on:** Contingency Groups library (`docs/superpowers/specs/2026-07-17-contingency-groups-design.md`)

## Problem

Contingency Groups today catalog source hosts, volumes, and maps. Operators also need planned `_snap` target copies (volumes + FlashCopy + host maps) that can be previewed safely and then created/started on the IBM FlashSystem / SVC array via LaunchPad SSH.

## Goals

- Auto-derive editable `*_snap` volume rows and matching host maps from each source volume.
- **Preview / Dry-run** lists exact CLI steps (no writes).
- **Run Create** (after confirm) creates missing targets, FlashCopy maps, starts FlashCopy, and maps `_snap` volumes to the same hosts/SCSI IDs as sources.
- Resolve target array from group `storage_hint` → LaunchPad SSH card.
- Stop on first SSH error; show a per-step log; no automatic rollback.
- Excel export includes SNAP role for volumes/maps.

## Non-goals

- Waiting until FlashCopy reaches idle/complete (start only).
- Deleting or modifying existing source volumes/maps.
- Multi-array orchestration in one click.
- Non-IBM backends for v1.

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Scope | Full set: `_snap` volumes + FlashCopy + host maps |
| Start copy | Yes — `startfcmap` after `mkfcmap` |
| Safety | Two-step: Preview/Dry-run, then separate Run Create |
| Naming | Suffix exactly `_snap` (e.g. `HRDC_ESXI_DS01_snap`) |
| SCSI | Same hosts and SCSI IDs as the matching source volume |

## Data model extensions

Extend contingency group volumes and maps:

```json
{
  "name": "HRDC_ESXI_DS01_snap",
  "capacity": "4.00 TiB",
  "pool": "Hart_Pool1",
  "uid": "",
  "protocol": "SCSI",
  "role": "snap",
  "source_volume": "HRDC_ESXI_DS01"
}
```

```json
{
  "volume": "HRDC_ESXI_DS01_snap",
  "host": "pen_hrdcesx_vm01",
  "scsi_id": "0",
  "role": "snap"
}
```

| Field | Notes |
|-------|--------|
| `role` | `"source"` (default) or `"snap"` |
| `source_volume` | Required for snap volumes; name of source vdisk |
| Snap maps | `role: "snap"`; volume is the `*_snap` name |

**Generate `_snap` rows**
- For each volume with `role != "snap"` and name not ending in `_snap`, ensure target `NAME_snap` exists.
- Copy capacity/pool/protocol from source when present; UID blank.
- For each source map, ensure a snap map with same host + scsi_id pointing at `NAME_snap`.
- Idempotent: do not duplicate existing snap rows.

**Seeds / migration**
- Seed helpers for Houston, Hartford, Windsor include `_snap` volumes + snap maps.
- Existing saved groups: UI action **Generate _snap rows** adds missing pairs without wiping edits.

## UI (Contingency Groups page)

- Volumes/Maps tables show a `SNAP` badge when `role === "snap"`.
- Buttons:
  - **Generate _snap rows**
  - **Preview / Dry-run**
  - **Run Create** (disabled until a successful preview in the current session, or always enabled but requires confirm + uses last preview hash)
- Preview modal: ordered command list, warnings, copy-to-clipboard, target card name/IP.
- Run Create confirm: explicit warning that volumes will be created and FlashCopy started on the resolved array.
- Footer remains clear that create is operator-initiated (not background automation).

## Create workflow

1. Resolve SSH card from `storage_hint` (match card `name` case-insensitive; fail clearly if missing).
2. Optional light inventory: `lsvdisk` / `lsfcmap` / `lshostvdiskmap` to mark steps as create vs skip-if-exists.
3. Build steps per source→snap pair:

| Step | Purpose | Example shape |
|------|---------|----------------|
| Create target | Target volume | `svctask mkvdisk -name NAME_snap -mdiskgrp POOL -size N -unit gb` (exact flags match site CLI style) |
| Create FC map | FlashCopy relationship | `svctask mkfcmap -source NAME -target NAME_snap -name fc_<safe>` |
| Start FC | Begin copy | `svctask startfcmap fc_<safe>` |
| Host maps | Attach snap LUN | `svctask mkvdiskhostmap -host HOST -scsi ID NAME_snap` |

4. **Preview** returns steps + warnings only.
5. **Run Create** requires `confirm: true`, executes in order over SSH, stops on first non-zero / error output, returns log entries `{ step, cmd, ok, output }`.

**Blocking warnings (Run Create refused until fixed)**
- Missing/unknown `storage_hint`
- Missing pool or size when target must be created and cannot be inferred
- Source volume not found on array when live check runs

**Non-blocking skips**
- Target already exists → skip mkvdisk
- FC map already exists → skip mkfcmap (still attempt start if not started, or skip start if already copying/idle)
- Host map already exists → skip that host map

## APIs

| Method | Path | Body | Result |
|--------|------|------|--------|
| POST | `/api/contingency-groups/generate-snaps` | `{ group_id }` | `{ group, persisted }` |
| POST | `/api/contingency-groups/snap-preview` | `{ group_id }` | `{ card, steps, warnings }` |
| POST | `/api/contingency-groups/snap-create` | `{ group_id, confirm: true }` | `{ ok, log, warnings }` |

All require unlocked settings/SSH backend. 400 on bad input; 503 if locked.

## Excel

- Volumes sheet: add **Role**, **Source Volume** columns.
- Maps sheet: add **Role** column.
- Snap rows included in export.

## Security & safety

- No create without explicit confirm.
- Preview never mutates the array.
- Credentials only from existing LaunchPad card crypto path (same as health refresh).
- Log commands and results for the operator; do not store passwords in logs.

## Files to touch (implementation)

- `launchpad/contingency_groups_data.py` — generate snap rows; seed updates; role fields
- `launchpad/contingency_snap_create.py` — preview/create step builder + SSH runner
- `launchpad/contingency_groups.py` — UI buttons + preview/create modals
- `launchpad/contingency_groups_export.py` — Role columns
- `launchpad/health_server.py` — three new POST routes
- `launchpad/config.py` — version bump
- Tests for generate-snaps, preview step list, skip-if-exists logic

## Manual test plan

1. Open Contingency Groups → Hartford → Generate _snap rows → see `*_snap` volumes + maps.
2. Preview / Dry-run with valid `storage_hint` → command list shown; no array change.
3. Run Create on a lab array → targets created, FC started, host maps present; log shows each step.
4. Re-run Preview/Create → existing objects skipped cleanly.
5. Missing storage_hint → Run blocked with clear error.
6. Excel export shows Role = snap for new rows.

## Out of scope / later

- Wait-for-copy-complete polling UI.
- Incremental/consistent FC policy toggles beyond defaults.
- Automatic rollback / delete on failure.
- Capture `_snap` status from live `lsfcmap` into the group library.
