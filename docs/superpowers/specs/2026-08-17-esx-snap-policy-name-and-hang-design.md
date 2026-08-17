# ESX-snap policy: editable name and Load/Preview hang

**Date:** 2026-08-17  
**Status:** Approved for implementation (pending user review of this file)  
**App version target:** 1.6.175  
**Depends on:** ESX-snap Policy page 1.6.174 (`docs/superpowers/specs/2026-08-15-esx-snap-policy-vg-design.md`)  
**Approach:** Editable policy name (default `esx_snap`); stop per-volume-group SSH on Load volumes and Preview; show fetch errors instead of spinning forever

## Problem

1. Policy name is hardcoded **`ESX-snap`**. Operators need **`esx_snap`** now and a field they can change on later Runs.
2. **Load volumes** stays on “Loading volumes…” and **Preview** stays on “Preview…”. Search never enables because the volume table never arrives.

**Hang root cause:** `collect_esx_snap_inventory` calls `svcinfo lsvolumegroupmember` **once per existing volume group** on the array (HealthServer SSH timeout **120s** each). A site with many volume groups never finishes Load volumes; Preview runs the same inventory again.

## Goals

- Policy name is an editable input, default **`esx_snap`**. Existence checks and CLI use the typed name.
- Volume group default **`{CardName}_esx_snap`** (still editable, max 63).
- Load volumes uses **three** SSH commands only: `lssnapshotpolicy`, `lsvolumegroup`, `lsvdisk`. No `lsvolumegroupmember` loop.
- Preview extra-checks **checked volumes only** (not every VG on the array) when `lsvdisk` did not already show a volume-group column.
- Load volumes and Preview show an error if fetch/SSH fails; they must not sit on “Loading…” / “Preview…” forever.
- Bump `APP_VERSION` to **1.6.175**.

## Non-goals

- Changing daily / 7-day / start-time meaning (start time stays editable, default 02:00).
- HPE or other vendors.
- Deleting or updating an existing policy/VG.
- Automatic rollback.
- Restoring the per-VG `lsvolumegroupmember` loop.

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Policy name | Editable; default `esx_snap`; IBM-safe token, max 63 |
| VG default | `{sanitized CardName}_esx_snap` |
| Load volumes SSH | Three commands; no per-VG member listing |
| Membership | Use `lsvdisk` `volume_group` column when present; otherwise Preview looks up **checked** volumes only |
| Hang UI | Fetch/SSH failure shows the error text |

## Behavior

### Policy name

- Page Policy row: `<input id="policy-name" value="esx_snap" maxlength="63">` instead of static `ESX-snap`.
- Changing it invalidates Preview (same as start time / VG / volumes).
- Preview/Run body includes `policy_name`. `preview_hash` includes `policy_name`.
- `mksnapshotpolicy … -name {policy_name}`. `mkvolumegroup -snapshotpolicy {policy_name} -name {vg}`.
- Blocking if that policy name already exists on the array (not a hardcoded `ESX-snap`).
- Page title/header can stay **ESX-snap Policy** (feature name). Lede and confirm text use the typed policy name where they currently say `ESX-snap`.

### Volume group default

- `default_vg_name` suffix is `_esx_snap` (not `_ESX-snap`). Truncation still keeps that suffix inside 63 characters.

### Load volumes (`POST /api/esx-snap-policy/volumes`)

`collect_esx_snap_inventory` must **not** call `_fill_volume_group_members` / `lsvolumegroupmember` in a loop.

Commands (same as 1.6.174 without the member loop):

- `svcinfo lssnapshotpolicy -delim :` (fallback without `-delim`)
- `svcinfo lsvolumegroup -delim :`
- `svcinfo lsvdisk -delim :`

Parse `volume_group` / `volume_group_name` / `volumegroup` from `lsvdisk` when present. Volumes already in a VG: checkbox disabled. Search is a client filter over the returned table; it cannot run until this POST returns.

### Preview membership (checked volumes only)

If a checked volume’s `volume_group` from the list inventory is empty, Preview may run **one** `svcinfo lsvdisk -delim : {volume}` (detail) for that volume and read `volume_group*`. If that field is non-empty, the volume is blocking (already in a VG). Do **not** iterate all volume groups.

Run’s live re-read uses the same bounded inventory: policy list + VG list + (optional) detail only for the volumes in that array’s payload. No per-VG member loop.

### Fetch errors

`loadVolumes` and Preview/Run `fetch` must `try/catch`. On failure, set the status/volume box to the error (not leave “Loading volumes…” / “Preview…”).

## Architecture

| Unit | Change |
|------|--------|
| `launchpad/esx_snap_policy_ops.py` | Default policy `esx_snap`; VG suffix `_esx_snap`; `collect_esx_snap_inventory` without member loop; `build_esx_snap_array_steps` takes `policy_name`; `preview_hash` includes `policy_name`; optional per-volume detail helper |
| `launchpad/esx_snap_policy.py` | Policy name input; payload `policy_name`; fetch error handling |
| `launchpad/health_server.py` | Pass `policy_name` through preview/run; Run re-check uses typed policy name |
| `launchpad/config.py` | **1.6.175** |

## Testing

- Default VG for `Windsor` is `Windsor_esx_snap`.
- Steps use `-name esx_snap` (or the passed policy name) and `-snapshotpolicy` matching that name.
- Existing policy named `esx_snap` blocks; a different existing policy does not block `esx_snap`.
- `collect_esx_snap_inventory` does **not** invoke any command containing `lsvolumegroupmember`.
- Typed policy name in preview hash: changing `policy_name` changes the hash.
- Page source: `id="policy-name"`, `value="esx_snap"`, `maxlength="63"`, `policy_name` in Preview/Run body, `catch` around Load volumes and Preview fetch.
- Version pins **1.6.175**.

## Out of scope follow-ups

- Check-visible / uncheck-visible on the volume filter.
- Persisting last-used policy name in the LaunchPad DB.
