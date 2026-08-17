# ESX-snap Add Volume via chvdisk Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add existing volumes with IBM’s `svctask chvdisk -volumegroup`, shipping as **1.6.176**, so Run Create actually puts volumes in the new group.

**Architecture:** Change only the add-volume `SnapStep` in `build_esx_snap_array_steps` (`kind="chvdisk"`, `cmd=svctask chvdisk -volumegroup {vg} {token}`). Preview/Run already execute those steps as returned. No skip-if-exists, no fallback to `addvolumetovolumegroup`.

**Tech Stack:** Python, pytest.

**Spec:** `docs/superpowers/specs/2026-08-17-esx-snap-add-volume-chvdisk-design.md`

## Global Constraints

- APP_VERSION bump to **1.6.176** only in the final version task.
- Add-volume CLI is **only** `svctask chvdisk -volumegroup {vg} {volume}` (one step per checked volume).
- `SnapStep.kind` for those steps is **`chvdisk`**.
- No `addvolumetovolumegroup`. No try-then-fallback.
- No skip-if-exists / attach to leftover Houston objects (`esx_snap` / `test_esx_snap`).
- Policy/VG naming, daily / interval 1 / retention 7 / start `02:00`, membership blocking, and Load volumes SSH unchanged.
- Place imports at the top of modules (no inline imports).
- Windows PowerShell commits (`git commit -m "..."`); commit at each task commit step.
- Prefer TDD. Do not commit `.superpowers/sdd*`, `LaunchPad-Install/`, or install zips.
- Work from a feature branch off current `main`. Branch name: `feature/esx-snap-add-volume-chvdisk`. Create an isolated worktree via using-git-worktrees at execution time.

## File structure

| File | Change |
|------|--------|
| `launchpad/esx_snap_policy_ops.py` | Add-volume `kind`/`cmd` |
| `tests/test_esx_snap_policy_ops.py` | Assert `chvdisk -volumegroup`; forbid `addvolumetovolumegroup` |
| `launchpad/config.py` + version pins | **1.6.176** (Task 2 only) |

---

### Task 1: Ops — `chvdisk -volumegroup` add-volume steps

**Files:**
- Modify: `launchpad/esx_snap_policy_ops.py`
- Modify: `tests/test_esx_snap_policy_ops.py`

**Interfaces:**
- Consumes: existing `build_esx_snap_array_steps`, `SnapStep`
- Produces: each add-volume step has `kind="chvdisk"` and `cmd="svctask chvdisk -volumegroup {vg} {token}"`

- [ ] **Step 1: Write the failing tests**

In `tests/test_esx_snap_policy_ops.py`, update `test_steps_daily_seven_day_policy_and_add_volume` so the add-volume assertions are:

```python
    assert cmds[2] == (
        "svctask chvdisk -volumegroup Windsor_esx_snap WIN_ESX_DS01"
    )
    assert cmds[3] == (
        "svctask chvdisk -volumegroup Windsor_esx_snap WIN_NFS"
    )
    assert steps[2].kind == "chvdisk"
    assert steps[3].kind == "chvdisk"
    assert all("addvolumetovolumegroup" not in step.cmd for step in steps)
    assert POLICY_NAME == "esx_snap"
```

Keep the existing `mksnapshotpolicy` / `mkvolumegroup` command assertions on `cmds[0]` and `cmds[1]`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_esx_snap_policy_ops.py::test_steps_daily_seven_day_policy_and_add_volume -v`

Expected: FAIL (still `addvolumetovolumegroup`)

- [ ] **Step 3: Write minimal implementation**

In `launchpad/esx_snap_policy_ops.py`, replace the add-volume loop with:

```python
    for token in safe_vols:
        steps.append(
            SnapStep(
                kind="chvdisk",
                purpose=f"add volume {token}",
                cmd=f"svctask chvdisk -volumegroup {vg} {token}",
            )
        )
```

Do not change policy/VG create steps, existence checks, or `apply_checked_volume_details`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_esx_snap_policy_ops.py tests/test_health_server_esx_snap_policy.py -v`

Expected: PASS. Grep `launchpad/` and `tests/` for `addvolumetovolumegroup` — no remaining matches in those trees.

- [ ] **Step 5: Commit**

```powershell
git add -- launchpad/esx_snap_policy_ops.py tests/test_esx_snap_policy_ops.py
git commit -m "Add ESX-snap volumes with chvdisk -volumegroup instead of addvolumetovolumegroup."
```

---

### Task 2: Bump APP_VERSION to 1.6.176

**Files:**
- Modify: `launchpad/config.py`
- Modify: `tests/test_capacity_unit_js.py`
- Modify: `tests/test_hadoop_sudo_wire.py`
- Modify: `tests/test_system_connectivity_version.py`
- Grep remaining `assert APP_VERSION == "1.6.175"` under `tests/` and `launchpad/`

**Interfaces:**
- Produces: `APP_VERSION = "1.6.176"`

- [ ] **Step 1:** Change the three pin tests to `"1.6.176"` (leave config at 1.6.175 for RED).

In `tests/test_capacity_unit_js.py` (`test_app_version_153`):

```python
    assert APP_VERSION == "1.6.176"
```

In `tests/test_hadoop_sudo_wire.py` (`test_version_174`):

```python
    assert APP_VERSION == "1.6.176"
```

In `tests/test_system_connectivity_version.py` (`test_app_version_16174`):

```python
    assert APP_VERSION == "1.6.176"
```

- [ ] **Step 2:** `python -m pytest tests/test_capacity_unit_js.py tests/test_hadoop_sudo_wire.py tests/test_system_connectivity_version.py -v` — Expected FAIL (`'1.6.175' == '1.6.176'`).

- [ ] **Step 3:** `APP_VERSION = "1.6.176"` in `launchpad/config.py`. Grep leftover equality pins under `tests/` and `launchpad/`.

- [ ] **Step 4:** `python -m pytest tests/test_esx_snap_policy_ops.py tests/test_health_server_esx_snap_policy.py tests/test_capacity_unit_js.py tests/test_hadoop_sudo_wire.py tests/test_system_connectivity_version.py -v` — Expected PASS.

- [ ] **Step 5:**

```powershell
git add -- launchpad/config.py tests/test_capacity_unit_js.py tests/test_hadoop_sudo_wire.py tests/test_system_connectivity_version.py
git commit -m "Bump version to 1.6.176 for ESX-snap chvdisk add-volume."
```

---

## Spec coverage

| Spec item | Task |
|-----------|------|
| `svctask chvdisk -volumegroup {vg} {volume}` | 1 |
| `SnapStep.kind` is `chvdisk` | 1 |
| No `addvolumetovolumegroup` | 1 |
| No skip-if-exists / fallback | 1 (unchanged) |
| Version 1.6.176 | 2 |
