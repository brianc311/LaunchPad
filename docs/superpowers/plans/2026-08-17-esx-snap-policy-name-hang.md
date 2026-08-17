# ESX-snap Editable Name and Load/Preview Hang Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the snapshot policy name editable (default `esx_snap`) and stop Load volumes / Preview hanging on per-volume-group SSH, shipping as **1.6.175**.

**Architecture:** Remove `_fill_volume_group_members` from `collect_esx_snap_inventory` (three SSH commands only). Preview/Run optionally detail-lookup **checked** volumes when `lsvdisk` omitted `volume_group`. `build_esx_snap_array_steps` and `preview_hash` take the typed `policy_name`. The page sends `policy_name` and `try/catch`es fetch.

**Tech Stack:** Python, HealthServer HTML/JS, pytest.

**Spec:** `docs/superpowers/specs/2026-08-17-esx-snap-policy-name-and-hang-design.md`

## Global Constraints

- APP_VERSION bump to **1.6.175** only in the final version task.
- Policy name editable; default **`esx_snap`**; IBM-safe token (`cli_token`); max 63.
- VG default `{sanitized CardName}_esx_snap` (suffix `_esx_snap`, keep suffix when truncating to 63).
- Load volumes: `lssnapshotpolicy`, `lsvolumegroup`, `lsvdisk` only. **No** `lsvolumegroupmember` loop.
- Membership: use `lsvdisk` `volume_group*` when present; otherwise Preview/Run detail-lookup **checked volumes only**.
- Existence checks use the **typed** policy name, not hardcoded `ESX-snap`.
- Daily / interval 1 / retention 7 / start default `02:00` unchanged.
- Fetch/SSH failure must show error text (not leave “Loading volumes…” / “Preview…”).
- Page title/header stays **ESX-snap Policy**.
- Place imports at the top of modules (no inline imports).
- Windows PowerShell commits (`git commit -m "..."`); commit at each task commit step.
- Prefer TDD. Do not commit `.superpowers/sdd*`, `LaunchPad-Install/`, or install zips.
- Work from a feature branch off current `main`. Branch name: `feature/esx-snap-policy-name-hang`. Create an isolated worktree via using-git-worktrees at execution time.

## File structure

| File | Change |
|------|--------|
| `launchpad/esx_snap_policy_ops.py` | Default names; no member loop; `policy_name`; detail helper; hash |
| `tests/test_esx_snap_policy_ops.py` | Update assertions; hang + policy-name tests |
| `launchpad/health_server.py` | Pass `policy_name`; detail-lookup checked vols; run recheck uses typed name |
| `tests/test_health_server_esx_snap_policy.py` | Hash includes policy_name; default VG; existing `esx_snap` |
| `launchpad/esx_snap_policy.py` | Policy input; payload; try/catch |
| `tests/test_esx_snap_policy_page.py` | policy-name / catch / policy_name body |
| `launchpad/config.py` + version pins | **1.6.175** (Task 3 only) |

---

### Task 1: Ops — default `esx_snap`, drop member loop, typed policy, checked-volume detail

**Files:**
- Modify: `launchpad/esx_snap_policy_ops.py`
- Modify: `tests/test_esx_snap_policy_ops.py`

**Interfaces:**
- Consumes: existing parsers, `cli_token`, `SnapStep`
- Produces:
  - `POLICY_NAME = "esx_snap"`
  - `VG_SUFFIX = "_esx_snap"`
  - `build_esx_snap_array_steps(..., policy_name: str = "")` — empty/`None` uses `POLICY_NAME`; CLI `-name {policy}` and `-snapshotpolicy {policy}`; existence uses that name; `len(policy) > VG_MAX_LEN` is blocking
  - `preview_hash(start_time, arrays, policy_name: str = "")` — canonical payload includes `"policy_name"`
  - `collect_esx_snap_inventory` does **not** call `_fill_volume_group_members` or any `lsvolumegroupmember` command
  - `apply_checked_volume_details(run_cmd, volumes: list[dict], volume_names: list[str]) -> list[dict]` — for each requested name whose `volume_group` is empty, run `svcinfo lsvdisk -delim : {token}` (fallback without `-delim`), merge `volume_group*` onto that row; skip names that already have a group; do not iterate VGs
  - Delete `_fill_volume_group_members`

- [ ] **Step 1: Write the failing tests**

Update `tests/test_esx_snap_policy_ops.py`:

1. `test_sanitize_and_default_vg_name`: expect `Windsor_esx_snap`, `Site_esx_snap`, `Windsor_FS9200_esx_snap`, suffix `_esx_snap`.
2. `test_steps_daily_seven_day_policy_and_add_volume`: `-name esx_snap`, `-snapshotpolicy esx_snap`, VG `Windsor_esx_snap`, `POLICY_NAME == "esx_snap"`. Pass `vg_name="Windsor_esx_snap"`.
3. `test_existence_and_membership_block_array`: `policies={"esx_snap"}` blocks; `policies={"ESX-snap"}` with empty otherwise does **not** block `esx_snap`; VG name `Windsor_esx_snap`.
4. `test_preview_hash_stable_and_order_independent`: pass `policy_name="esx_snap"` on all three; add a fourth hash with `policy_name="other"` that differs.
5. Replace `test_collect_fills_volume_group_from_lsvolumegroupmember` with:

```python
def test_collect_inventory_does_not_call_lsvolumegroupmember():
    calls: list[str] = []

    def run_cmd(command: str) -> str:
        calls.append(command)
        if "lsvolumegroupmember" in command:
            raise AssertionError(command)
        if "lssnapshotpolicy" in command:
            return POLICY_SAMPLE
        if "lsvolumegroup" in command:
            return VG_SAMPLE
        if "lsvdisk" in command:
            return VDISK_SAMPLE
        raise AssertionError(command)

    result = collect_esx_snap_inventory(run_cmd)
    assert result["ok"] is True
    assert not any("lsvolumegroupmember" in c for c in calls)
    assert by_name_ds02_still_has_column_from_lsvdisk(result)


def test_apply_checked_volume_details_only_looks_up_empty_membership():
    from launchpad.esx_snap_policy_ops import apply_checked_volume_details

    volumes = parse_lsvdisk_membership(VDISK_NO_VG_COL)
    calls: list[str] = []

    def run_cmd(command: str) -> str:
        calls.append(command)
        if "lsvolumegroupmember" in command:
            raise AssertionError(command)
        if "lsvdisk" in command and "WIN_ESX_DS02" in command:
            return "id:name:volume_group_name\n0:WIN_ESX_DS02:Already_VG\n"
        return ""

    apply_checked_volume_details(run_cmd, volumes, ["WIN_ESX_DS02"])
    by_name = {row["name"]: row for row in volumes}
    assert by_name["WIN_ESX_DS02"]["volume_group"] == "Already_VG"
    assert all("WIN_ESX_DS01" not in c for c in calls)
    assert all("lsvolumegroupmember" not in c for c in calls)


def test_typed_policy_name_in_steps_and_too_long():
    volumes = parse_lsvdisk_membership(VDISK_SAMPLE)
    steps, _, runnable = build_esx_snap_array_steps(
        vg_name="Windsor_esx_snap",
        volume_names=["WIN_ESX_DS01"],
        start_time="02:00",
        policies=set(),
        volume_groups=set(),
        volumes=volumes,
        policy_name="siteA_esx",
        now=datetime(2026, 8, 15, 9, 0, 0),
    )
    assert runnable is True
    assert "-name siteA_esx" in steps[0].cmd
    assert "-snapshotpolicy siteA_esx" in steps[1].cmd
    _, warnings, runnable = build_esx_snap_array_steps(
        vg_name="Windsor_esx_snap",
        volume_names=["WIN_ESX_DS01"],
        start_time="02:00",
        policies=set(),
        volume_groups=set(),
        volumes=volumes,
        policy_name="P" * 64,
    )
    assert runnable is False
    assert any("63" in w for w in warnings)
```

Helper `by_name_ds02_still_has_column_from_lsvdisk` is not required — inline: `VDISK_SAMPLE` still has `Already_VG` on DS02 from the list column.

Also update `test_collect_inventory_parses_and_flags_missing_policy_cli` so the fake `run_cmd` **raises** if `lsvolumegroupmember` appears (and remove the current member-return branch).

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_esx_snap_policy_ops.py -v`

Expected: FAIL (defaults still `_ESX-snap` / `ESX-snap`; member loop still called; `apply_checked_volume_details` missing)

- [ ] **Step 3: Write minimal implementation**

In `launchpad/esx_snap_policy_ops.py`:

```python
POLICY_NAME = "esx_snap"
VG_SUFFIX = "_esx_snap"
```

`_canonical_preview_payload` / `preview_hash`:

```python
def preview_hash(start_time: str, arrays: list[dict], policy_name: str = "") -> str:
    blob = json.dumps(
        {
            "policy_name": str(policy_name or "").strip() or POLICY_NAME,
            **_canonical_preview_payload(start_time, arrays),
        },
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()
```

(Keep `_canonical_preview_payload` as today; merge `policy_name` at hash time so `sort_keys=True` still works.)

Delete `_fill_volume_group_members`. In `collect_esx_snap_inventory`, after `parse_lsvdisk_membership`, return immediately (no member fill).

`build_esx_snap_array_steps`: add `policy_name: str = ""`. Resolve `raw = str(policy_name or "").strip() or POLICY_NAME`, then `cli_token(raw)`, then `len(policy) > VG_MAX_LEN` error. Existence: `if policy in policies`. Commands use that `policy`. Purpose strings can say “snapshot policy” instead of hardcoded ESX-snap.

Add:

```python
def apply_checked_volume_details(
    run_cmd: Callable[[str], str],
    volumes: list[dict],
    volume_names: list[str],
) -> list[dict]:
    by_name = {str(row.get("name") or ""): row for row in volumes}
    for name in volume_names:
        token_name = str(name or "").strip()
        row = by_name.get(token_name)
        if row is None or volume_group_of(row):
            continue
        try:
            token = cli_token(token_name)
        except ValueError:
            continue
        out = run_cmd(f"svcinfo lsvdisk -delim : {token}")
        if not str(out or "").strip():
            out = run_cmd(f"svcinfo lsvdisk {token}")
        parsed = parse_lsvdisk_membership(out)
        group = ""
        for item in parsed:
            if item.get("name") == token_name:
                group = volume_group_of(item)
                break
        if not group and parsed:
            group = volume_group_of(parsed[0])
        if group:
            row["volume_group"] = group
    return volumes
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_esx_snap_policy_ops.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add -- launchpad/esx_snap_policy_ops.py tests/test_esx_snap_policy_ops.py
git commit -m "Stop ESX-snap per-VG SSH and default the policy name to esx_snap."
```

---

### Task 2: HealthServer + page — typed policy, bounded Preview, fetch errors

**Files:**
- Modify: `launchpad/health_server.py`
- Modify: `launchpad/esx_snap_policy.py`
- Modify: `tests/test_health_server_esx_snap_policy.py`
- Modify: `tests/test_esx_snap_policy_page.py`

**Interfaces:**
- Consumes: Task 1 `POLICY_NAME`, `preview_hash(..., policy_name=)`, `build_esx_snap_array_steps(..., policy_name=)`, `apply_checked_volume_details`, `default_vg_name` (`Windsor_esx_snap`)
- Produces: preview/run JSON includes `policy_name`; HealthServer calls `apply_checked_volume_details` after list inventory using that array’s `volume_names`; page `#policy-name`; fetch `try/catch`

- [ ] **Step 1: Write the failing tests**

`tests/test_esx_snap_policy_page.py` add/adjust:

```python
def test_policy_name_input_and_payload():
    html = ESX_SNAP_POLICY_HTML
    assert 'id="policy-name"' in html
    assert 'value="esx_snap"' in html
    assert "policy_name" in html
    policy_at = html.find('id="policy-name"')
    max_at = html.find('maxlength="63"', policy_at)
    assert max_at != -1


def test_load_and_preview_fetch_catch_errors():
    html = ESX_SNAP_POLICY_HTML
    load_at = html.find("async function loadVolumes")
    preview_at = html.find('getElementById("preview-btn").onclick')
    assert "catch" in html[load_at:load_at + 1200]
    assert "catch" in html[preview_at:preview_at + 1500]
```

Keep `assert "ESX-snap" in html` (title **ESX-snap Policy** still matches).

`tests/test_health_server_esx_snap_policy.py`:

- `test_cards_are_ibm_only_with_default_vg`: `default_vg_name == "Windsor_esx_snap"`.
- All `preview_hash(...)` calls must pass `policy_name` (use `"esx_snap"` or `payload["policy_name"]`).
- `EXISTING_POLICY` for the blocked-array test must be `esx_snap` (not `ESX-snap`) so default policy still blocks that array.
- `test_run_without_confirm_or_bad_hash` and `test_run_recheck_*` include `"policy_name": "esx_snap"` in payload and hash.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_esx_snap_policy_page.py tests/test_health_server_esx_snap_policy.py -v`

Expected: FAIL (no `#policy-name`; hash mismatch; Windsor default still old until Task 1 is on the branch — Task 1 lands first so cards test may already pass VG default; page tests fail)

- [ ] **Step 3: Write minimal implementation**

`health_server.py` import `apply_checked_volume_details` at the existing ops import block.

`preview_esx_snap_policy`:

```python
        policy_name = str(payload.get("policy_name") or "").strip() or POLICY_NAME
```

After a successful `_esx_snap_inventory`, before `build_esx_snap_array_steps`:

```python
            volumes = list(inventory["volumes"])
            apply_checked_volume_details(
                self._snap_run_command(card), volumes, volume_names
            )
            steps, warnings, runnable = build_esx_snap_array_steps(
                vg_name=vg_name,
                volume_names=volume_names,
                start_time=start_time,
                policies=set(inventory["policies"]),
                volume_groups=set(inventory["volume_groups"]),
                volumes=volumes,
                policy_name=policy_name,
            )
```

Hash:

```python
            "preview_hash": preview_hash(start_time, list(raw_arrays), policy_name),
```

`run_esx_snap_policy`: same `policy_name` resolution; `preview_hash(..., policy_name)`; live recheck `if policy_name in set(live["policies"]) or vg_name in set(live["volume_groups"])`; warning text uses `policy_name` not hardcoded `ESX-snap`. After live inventory, `apply_checked_volume_details` is **not** required for the existence gate (policy/VG names). Do not call `lsvolumegroupmember`. Live inventory is `_esx_snap_inventory` only (three commands).

`esx_snap_policy.py`:

- Policy row: `Name <input id="policy-name" value="esx_snap" maxlength="63" aria-label="Policy name"> · daily · keep 7 days · start …`
- `const policyEl = document.getElementById("policy-name");`
- `policyEl.addEventListener("input", invalidatePreview);`
- Preview/Run body: `policy_name: policyEl.value`
- Confirm: `` `Create ${policyEl.value || "esx_snap"} policy and volume groups on the listed arrays? This mutates the arrays.` ``
- Lede may keep “ESX-snap Policy” meaning; where it says “policy ESX-snap” change to “a snapshot policy (default esx_snap)”.
- Wrap `loadVolumes` fetch in `try { ... } catch (err) { const target = document.getElementById("vols-" + cardId); if (target) { target.innerHTML = '<p class="warning">' + (err.message || err) + '</p>'; volumesByCard[cardId] = target.innerHTML; } }`
- Wrap Preview fetch in `try { ... } catch (err) { statusEl.textContent = "Preview failed: " + (err.message || err); }`
- Wrap Run fetch in `try/catch` similarly (status text).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_esx_snap_policy_ops.py tests/test_esx_snap_policy_page.py tests/test_health_server_esx_snap_policy.py tests/test_dashboard_ui_freeze.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add -- launchpad/health_server.py launchpad/esx_snap_policy.py tests/test_health_server_esx_snap_policy.py tests/test_esx_snap_policy_page.py
git commit -m "Wire editable esx_snap policy name and fail Load/Preview instead of hanging."
```

---

### Task 3: Bump APP_VERSION to 1.6.175

**Files:**
- Modify: `launchpad/config.py`
- Modify: `tests/test_capacity_unit_js.py`
- Modify: `tests/test_hadoop_sudo_wire.py`
- Modify: `tests/test_system_connectivity_version.py`
- Grep remaining `assert APP_VERSION == "1.6.174"` under `tests/` and `launchpad/`

**Interfaces:**
- Produces: `APP_VERSION = "1.6.175"`

- [ ] **Step 1:** Change the three pin tests to `"1.6.175"` (leave config at 1.6.174 for RED).
- [ ] **Step 2:** `python -m pytest tests/test_capacity_unit_js.py tests/test_hadoop_sudo_wire.py tests/test_system_connectivity_version.py -v` — Expected FAIL.
- [ ] **Step 3:** `APP_VERSION = "1.6.175"` in `launchpad/config.py`. Grep leftover equality pins.
- [ ] **Step 4:** `python -m pytest tests/test_esx_snap_policy_ops.py tests/test_esx_snap_policy_page.py tests/test_health_server_esx_snap_policy.py tests/test_dashboard_ui_freeze.py tests/test_capacity_unit_js.py tests/test_hadoop_sudo_wire.py tests/test_system_connectivity_version.py -v` — Expected PASS.
- [ ] **Step 5:**

```powershell
git add -- launchpad/config.py tests/test_capacity_unit_js.py tests/test_hadoop_sudo_wire.py tests/test_system_connectivity_version.py
git commit -m "Bump version to 1.6.175 for ESX-snap policy name and Load hang."
```

---

## Spec coverage

| Spec item | Task |
|-----------|------|
| Default policy `esx_snap`; VG `_esx_snap` | 1 |
| Typed policy in steps, existence, hash | 1, 2 |
| No `lsvolumegroupmember` on collect | 1 |
| Checked-volume detail lookup | 1, 2 |
| Policy input + payload + invalidate | 2 |
| Fetch try/catch | 2 |
| Version 1.6.175 | 3 |
