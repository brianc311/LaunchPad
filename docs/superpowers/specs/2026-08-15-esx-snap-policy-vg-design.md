# ESX-snap policy and per-site volume group

**Date:** 2026-08-15  
**Status:** Approved for implementation (pending user review of this file)  
**App version target:** 1.6.174  
**Depends on:** HealthServer mutating pages (FlashCopy CGs Preview → confirm → Run); dashboard header openers off the Tk thread (1.6.173); IBM `SVC_PROFILES`  
**Approach:** New HealthServer page; pick one or many IBM arrays; pick volumes per array; create policy `ESX-snap` (daily, keep 7 days) and volume group `{Site}_ESX-snap`; fail if either object already exists

## Problem

Operators need IBM Spectrum Virtualize **snapshot policies** and **volume groups** on FlashSystem / SVC arrays: policy **ESX-snap** (a snapshot every day, retain 7 days) and a **per-site volume group** that uses that policy, with the operator choosing which volumes belong in the group. That is a different object from FlashCopy consistency groups (`mkfcconsistgrp`). LaunchPad does not issue `mksnapshotpolicy` / `mkvolumegroup` today. Snapshot Schedule is planning-only and must stay that way. LUN Builder’s “volume group” is a plan grouping, not `mkvolumegroup`.

## Goals

- New dashboard / HealthServer page to create **one** array or **many** arrays in one Preview → confirm → Run.
- Policy name is always **`ESX-snap`**: backup unit **day**, interval **1**, retention **7 days**.
- Volume group default name **`{CardName}_ESX-snap`** (sanitized), editable per array before Preview.
- Operator **picks volumes** per array (search + checkboxes).
- If `ESX-snap` or the chosen VG name **already exists** on that array, **stop that array with an error** (do not skip, reuse, or attach).
- Mutating SSH never runs on the Tk UI thread. Opening the page follows the 1.6.173 header-opener worker pattern.
- Bump `APP_VERSION` to **1.6.174**.

## Non-goals

- HPE 3PAR / Primera, Dell, NetApp, DS8884, Hadoop, or Vultr.
- Changing Snapshot Schedule into an array-mutating page (planning-only stays).
- FlashCopy consistency groups, `mkfcconsistgrp`, or Contingency Groups `_snap` copies.
- Safeguarded snapshots (`-safeguarded`).
- Deleting, renaming, suspending, or updating an existing policy or volume group.
- Adding volumes to an existing VG, or assigning `ESX-snap` onto an existing VG.
- Automatic rollback if a later step fails after a successful `mksnapshotpolicy`.
- Persisting volume picks in the LaunchPad DB (session only).
- Creating snapshots immediately (policy schedules them; Run does not call `mksnapshot`).

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Kind | IBM snapshot policy + volume group (`mksnapshotpolicy` / `mkvolumegroup`), not FlashCopy CGs |
| Volumes | Operator picks volumes on the page (search/check) |
| UI | New page (not FlashCopy CGs, LUN Builder, Site Lookup, or Snapshot Schedule) |
| Policy name | Exactly `ESX-snap` (not editable) |
| VG name | Per site; default `{CardName}_ESX-snap`; editable before Preview |
| Already exists | Error; do not reuse or skip |
| Scope v1 | IBM FlashSystem / SVC (`SVC_PROFILES`) only |
| Snapshot Schedule | Unchanged except a cross-link to this page |
| Mutating path | Preview / Dry-run, then confirm Run |

## Behavior

### Surface

- Path: `/esx-snap-policy`
- Dashboard header button label: **ESX-snap Policy** (with FlashCopy CGs / LUN Builder).
- Open via `_open_sync_browser_report` (status on UI thread; `open_esx_snap_policy()` on a worker). Do not decrypt the fleet on the Tk thread.
- Health Dashboard nav: add **ESX-snap Policy**; Snapshot Schedule page gets a link to this page. Footer copy: creating objects on the array is operator-initiated.

### Eligible arrays

SSH cards whose `device_profile` is in `SVC_PROFILES`. HPE and other families are omitted. Monitor-on is **not** required (same as FlashCopy CGs Manage). Page load lists cards from `/api/cards` (or a dedicated GET); it does **not** SSH every array on open.

### Layout (site-first)

1. **Policy summary (shared):** name `ESX-snap`; daily; keep 7 days; **start time** input default **02:00** (24h), applied to every array in this Run. No other policy knobs.
2. **Array list:** checkboxes (card name, host). **Select all** / **Select none**. Checking an array reveals that array’s VG + volume section.
3. **Per selected array:**
   - VG name field, default `sanitize(card.name) + "_ESX-snap"`, max 63 characters, IBM-safe token.
   - **Load volumes** (SSH that array only): `lsvdisk`, `lssnapshotpolicy`, `lsvolumegroup`.
   - Search box + checkbox table: volume name, capacity, existing volume-group column when `lsvdisk` provides it.
4. **Preview / Dry-run** then **Run Create** (disabled until the current session has a successful Preview with at least one runnable array). Changing arrays, VG names, volume checks, or start time invalidates Preview (LUN Builder pattern).

### Naming

- `sanitize(card.name)`: trim; replace each run of characters other than `A–Z a–z 0–9 _` with `_`; collapse repeat `_`; strip leading/trailing `_`. Empty result → `Site`.
- Default VG = `{sanitize(card.name)}_ESX-snap`, truncated to 63 characters (keep the `_ESX-snap` suffix).
- Policy name and VG name must pass the existing `cli_token` rules (`[A-Za-z0-9_.-]+`, non-empty) before Preview can succeed.
- Operator may edit the VG name; they may not edit the policy name.

### CLI shape (IBM Storage Virtualize 8.5.1+)

Exact flags are confirmed against IBM CLI help during implementation; the **meaning** is fixed. Preferred commands:

| Step | Command |
|------|---------|
| Inventory | `svcinfo lssnapshotpolicy -delim :` · `svcinfo lsvolumegroup -delim :` · `svcinfo lsvdisk -delim :` |
| Create policy | `svctask mksnapshotpolicy -backupunit day -backupinterval 1 -backupstarttime {YYMMDDHHMM} -retentiondays 7 -name ESX-snap` |
| Create VG | `svctask mkvolumegroup -snapshotpolicy ESX-snap -name {vg}` |
| Add volume | `svctask addvolumetovolumegroup -volumegroup {vg} {volume}` |

`{YYMMDDHHMM}` uses the **LaunchPad PC local date** at Preview/Run (`datetime.now()`) plus the start-time field (`HHMM`). Example: start `02:00` on 2026-08-15 → `2608150200`. Preview shows this timestamp. v1 does not read the array clock.

If `lssnapshotpolicy` is missing or the array rejects snapshot-policy commands, that array is a blocking error: snapshot policies need IBM Storage Virtualize **8.5.1 or later**.

Add-volume is always `addvolumetovolumegroup` (not `chvdisk -volumegroup`).

### Existence and other blocking rules (per array)

**Blocking** (array is not runnable; Preview lists an error for that array):

- Policy named `ESX-snap` already exists.
- Volume group with the chosen name already exists.
- No volumes checked.
- A checked volume is missing from live `lsvdisk`.
- A checked volume already belongs to a volume group (`volume_group` / equivalent `lsvdisk` field non-empty).
- Unsafe policy/VG/volume token.
- SSH/auth/profile failure, or firmware too old.

**Not** skip-if-exists. Existence is always an error for this feature.

Unselected arrays are ignored. Selected arrays with blocking errors are **omitted from Run**; other arrays still Preview/Run. Preview **succeeds** when at least one selected array is runnable. If every selected array is blocked, Preview fails and Run stays disabled.

### Preview

Worker SSH per selected array **sequentially**. Build ordered steps per runnable array: create policy → create VG → one add-volume step per checked volume. Show card name, VG name, volume list, and full CLI. Copy-to-clipboard allowed. No writes.

### Run

Requires `confirm: true` and a Preview in this session whose payload hash still matches (arrays, VG names, volume names, start time). Confirm text states objects will be created on the listed arrays.

For each runnable array, in order:

1. Re-read `lssnapshotpolicy` and `lsvolumegroup` (and volume membership if cheap). If policy or VG now exists, **fail that array** with a clear error; **do not** run mutate commands for it; **continue** the next array.
2. Run steps in order over the existing HealthServer SSH helper. Stop **that array** on the first non-zero / CLI error. No rollback. If policy was created and VG then fails, the next Run will error because `ESX-snap` exists — the per-array log must say that so the operator can delete the policy on the array if they want a retry.
3. Collect `{ array, step, cmd, ok, output }` for the result modal.

Do not start overlapping mutate SSH to the same array.

### Volume picker

Case-insensitive substring filter on volume name (Site Lookup style). Check visible matches / uncheck visible. Volumes already in a VG stay listed with the checkbox **disabled**. Preview still errors if a checked name is already in a volume group (stale payload).

## Architecture

| Unit | Responsibility |
|------|----------------|
| `launchpad/esx_snap_policy_ops.py` | Sanitize names; parse `lssnapshotpolicy` / `lsvolumegroup` / `lsvdisk` membership; build Preview/Run steps; existence errors; payload hash |
| `launchpad/esx_snap_policy.py` | Page HTML/JS (`ESX_SNAP_POLICY_PATH`, `ESX_SNAP_POLICY_HTML`) |
| `launchpad/health_server.py` | GET page; GET eligible cards; POST load-volumes; POST preview; POST run (`confirm`); `open_esx_snap_policy()` |
| `launchpad/ui/dashboard_view.py` | Header button; `_open_sync_browser_report` worker |
| `launchpad/config.py` | `APP_VERSION` **1.6.174** |

Reuse `cli_token` / `SnapStep` from contingency/FC CG ops. Do not put CLI assembly in `health_server.py` beyond routing and SSH I/O. Do not call `ensure_health_dashboard_registered` or fleet decrypt on the Tk thread.

## APIs

| Method | Path | Body | Result |
|--------|------|------|--------|
| GET | `/esx-snap-policy` | — | HTML page |
| GET | `/api/esx-snap-policy/cards` | — | `{ cards: [{ id, name, host, device_profile, default_vg_name }] }` eligible IBM SSH cards only |
| POST | `/api/esx-snap-policy/volumes` | `{ card_id }` | `{ ok, volumes, policies, volume_groups, error? }` live inventory for one card |
| POST | `/api/esx-snap-policy/preview` | `{ start_time, arrays: [{ card_id, vg_name, volume_names }] }` | `{ ok, arrays: [{ card_id, runnable, warnings, steps }], preview_hash }` |
| POST | `/api/esx-snap-policy/run` | same plus `{ confirm: true, preview_hash }` | `{ ok, arrays: [{ card_id, ok, log }] }` |

`run` without `confirm: true` or with a mismatched/missing `preview_hash` does not SSH mutate commands. Volume load / preview / run use the same per-card SSH path as FlashCopy CGs (credentials from the registered Health card).

## Testing

- Name sanitization: spaces → `_`; empty → `Site`; suffix kept when truncating to 63.
- Step builder: daily/7-day policy, VG with `-snapshotpolicy ESX-snap`, one add command per volume; `backupstarttime` from date + `02:00`.
- Existence: policy present → array not runnable; VG present → not runnable; volume already in a VG → not runnable; zero volumes → not runnable.
- Many: one blocked array does not block a second runnable array in the same Preview/Run result.
- `run` without confirm or with wrong hash performs no mutate.
- Page source includes Preview and Run Create; dashboard `tool_specs` includes **ESX-snap Policy**; opener starts a worker before register/decrypt.
- Version pins **1.6.174**.

## Out of scope follow-ups (do not implement in 1.6.174)

- Editing start time per array.
- Reuse/attach when objects exist.
- HPE snapshot schedules.
- Deleting `ESX-snap` or the site VG from LaunchPad.
