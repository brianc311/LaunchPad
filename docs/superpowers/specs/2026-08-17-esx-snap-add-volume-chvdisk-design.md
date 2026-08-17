# ESX-snap add volume via `chvdisk -volumegroup`

**Date:** 2026-08-17  
**Status:** Approved for implementation (pending user review of this file)  
**App version target:** 1.6.176  
**Depends on:** ESX-snap Policy 1.6.175 (`docs/superpowers/specs/2026-08-17-esx-snap-policy-name-and-hang-design.md`)  
**Approach:** Replace the invalid `addvolumetovolumegroup` CLI with IBM’s documented `chvdisk -volumegroup`. No retry/skip-if-exists path.

## Problem

Houston Run Create succeeded at `mksnapshotpolicy` (`esx_snap`) and `mkvolumegroup` (`test_esx_snap`), then failed adding `hou_esx_1`:

```
CMMVC5987E [addvolumetovolumegroup] is not a valid command line option.
```

The array stopped on that error, so `hou_esx_2` was never added. The IBM GUI shows **Volumes (0)** and **Policies (1)** on `test_esx_snap`.

IBM Storage Virtualize 8.5 documents assigning an existing volume with:

```
svctask chvdisk -volumegroup {vg} {volume}
```

The 1.6.174 spec had chosen `addvolumetovolumegroup` and explicitly rejected `chvdisk -volumegroup`. Live Houston CLI disproves that choice.

## Goals

- Preview and Run add-volume steps use `svctask chvdisk -volumegroup {vg} {volume}` (one step per checked volume).
- `SnapStep.kind` for those steps is `chvdisk`.
- Tests assert that command (and do not require `addvolumetovolumegroup`).
- Bump `APP_VERSION` to **1.6.176**.

## Non-goals

- Skip-if-exists / attach volumes to an already-created policy or VG (operator finishes Houston in the IBM GUI, or deletes `esx_snap` and `test_esx_snap` before a LaunchPad retry).
- Trying `addvolumetovolumegroup` first then falling back.
- Changing policy/VG naming, daily / 7-day / 02:00, membership blocking, or Load volumes SSH.
- Automatic rollback.

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Add-volume CLI | `svctask chvdisk -volumegroup {vg} {volume}` only |
| Houston leftover objects | Operator adds `hou_esx_1` / `hou_esx_2` in IBM GUI (Actions → Add Existing Volumes). Existence remains an error on the next LaunchPad Run. |
| Fallback command | None |

## Behavior

`build_esx_snap_array_steps` still emits, in order:

1. `mksnapshotpolicy … -name {policy}`
2. `mkvolumegroup -snapshotpolicy {policy} -name {vg}`
3. For each checked, ungrouped volume: `svctask chvdisk -volumegroup {vg} {token}`

Purpose text can stay “add volume {token}”. Stop that array on the first non-zero CLI error, same as today.

HealthServer Preview/Run only display the steps `build_esx_snap_array_steps` returns; no extra command rewrite.

## Architecture

| Unit | Change |
|------|--------|
| `launchpad/esx_snap_policy_ops.py` | Add-volume `kind`/`cmd` use `chvdisk -volumegroup` |
| `tests/test_esx_snap_policy_ops.py` | Assert `chvdisk -volumegroup` (and `kind="chvdisk"` if asserted) |
| `launchpad/config.py` + version pins | **1.6.176** |

Grep leftover `addvolumetovolumegroup` under `launchpad/` and `tests/` and update those equality assertions.

## Testing

- `test_steps_daily_seven_day_policy_and_add_volume`: commands contain `svctask chvdisk -volumegroup Windsor_esx_snap WIN_ESX_DS01` and `WIN_NFS`; no `addvolumetovolumegroup`.
- HealthServer preview/run tests that stringify steps still pass (they consume ops output).
- Version pins **1.6.176**.

## Operator note (Houston)

Do not re-run Create on Houston until `hou_esx_1` and `hou_esx_2` are in `test_esx_snap` in the IBM GUI, or until `esx_snap` and `test_esx_snap` are deleted on the array. This release does not attach to leftover objects.
