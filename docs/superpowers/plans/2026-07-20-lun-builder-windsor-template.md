# Windsor WI LUN Builder Template Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a built-in Windsor, WI LUN Builder template (full site: AS400 + ESX + VIO + MQ + app, Active WWPNs with multi-row hosts, blank `pwinap01` WWPNs, FlashSystem 5200 defaults) beside existing site templates.

**Architecture:** Extend `seed_lun_builder_templates()` to return five templates. Add `_windsor_host(lpar_name, wwpn1, wwpn2)` and Windsor LUN batches via existing `_lun_batch` kwargs. Keep prior templates unchanged. Update tests that assert template count / id set.

**Tech Stack:** Python seed data in `launchpad/lun_builder_data.py`, pytest.

**Spec:** `docs/superpowers/specs/2026-07-20-lun-builder-windsor-template-design.md`

## Global Constraints

- **Base branch:** implement on top of `feature/contingency-groups` (already has Mount Vernon + Done auto-save + `APP_VERSION=1.6.40`). Do not re-implement prior templates.
- Template id: `template-windsor-wi`
- Name: `Windsor, WI (Template)`; location: `Windsor, WI`; `is_template: True`
- Defaults: `default_storage_profile=flashsystem_5200`, `default_pool_or_cpg=Windsor_G3_Pool0`, `default_card_hint=Windsor, WI`
- Every LUN row: same profile/pool/card_hint
- Hosts: 14 rows as in the spec; `type=Generic`; Active WWPNs except blank `pwinap01`
- LUN batches exactly as in the spec table
- Do not seed Offline ports or array canister ports; do not modify prior template seed content
- Bump `APP_VERSION` to `1.6.41` in the final task
- Commit at each task’s commit step

---

## File map

| File | Responsibility |
|------|----------------|
| `launchpad/lun_builder_data.py` | `_windsor_host`, Windsor seed entry |
| `tests/test_lun_builder_data.py` | Windsor contracts; bump `len==4` → `5` |
| `tests/test_health_server_lun_builder.py` | API template id set includes Windsor |
| `launchpad/config.py` | `1.6.41` |

---

### Task 0: Branch / worktree from contingency-groups

**Files:** none (git only)

**Interfaces:**
- Consumes: `feature/contingency-groups` at `1.6.40` with four templates
- Produces: working branch `feature/lun-windsor-template`

- [ ] **Step 1: Create branch from contingency-groups tip**

```powershell
git fetch origin
git worktree add .worktrees/lun-windsor-template -b feature/lun-windsor-template feature/contingency-groups
cd .worktrees/lun-windsor-template
```

- [ ] **Step 2: Confirm four templates and version**

```powershell
python -c "from launchpad.lun_builder_data import seed_lun_builder_templates; from launchpad.config import APP_VERSION; print(APP_VERSION, [t['id'] for t in seed_lun_builder_templates()])"
```

Expected: `1.6.40` and ids including `template-hartford-ct`, `template-jupiter-fl`, `template-pendergrass-ga`, `template-mount-vernon-il`

- [ ] **Step 3: No commit** (setup only)

---

### Task 1: Seed Windsor template data + tests

**Files:**
- Modify: `launchpad/lun_builder_data.py`
- Test: `tests/test_lun_builder_data.py`
- Test: `tests/test_health_server_lun_builder.py`

**Interfaces:**
- Consumes: `_lun_batch` (with profile/pool/card kwargs), `seed_lun_builder_templates`, `expand_lun_batch`, `normalize_build`
- Produces: fifth template dict `template-windsor-wi`; `_windsor_host(lpar_name: str, wwpn1: str = "", wwpn2: str = "") -> dict`

- [ ] **Step 1: Update length / API set and add failing Windsor tests**

In `tests/test_lun_builder_data.py`, inside `test_hartford_template_identity`, change:

```python
assert len(templates) == 4
```

to:

```python
assert len(templates) == 5
```

Add:

```python
def _windsor_template() -> dict:
    return next(
        t for t in seed_lun_builder_templates() if t["id"] == "template-windsor-wi"
    )


def test_windsor_template_identity_and_defaults():
    win = _windsor_template()
    assert win["name"] == "Windsor, WI (Template)"
    assert win["location"] == "Windsor, WI"
    assert win["is_template"] is True
    assert win["default_storage_profile"] == "flashsystem_5200"
    assert win["default_pool_or_cpg"] == "Windsor_G3_Pool0"
    assert win["default_card_hint"] == "Windsor, WI"
    assert normalize_build(win)["is_template"] is True


def test_windsor_hosts_and_active_wwpns():
    win = _windsor_template()
    hosts = win["hosts"]
    assert len(hosts) == 14
    names = [h["lpar_name"] for h in hosts]
    assert names.count("AWN1") == 2
    assert names.count("pwinmq01") == 2
    assert names.count("pwinvio01b") == 2
    assert names.count("pwinvio02b") == 2
    assert set(names) == {
        "AWN1",
        "PEN_WINESX_VM01",
        "PEN_WINESX_VM02",
        "PEN_WINESX_VM03",
        "pwinap01",
        "pwinmq01",
        "pwinvio01a",
        "pwinvio01b",
        "pwinvio02a",
        "pwinvio02b",
    }
    assert all(h.get("type") == "Generic" for h in hosts)

    ap01 = next(h for h in hosts if h["lpar_name"] == "pwinap01")
    assert ap01["wwpn1"] == "" and ap01["wwpn2"] == ""

    awn_rows = [h for h in hosts if h["lpar_name"] == "AWN1"]
    assert {(r["wwpn1"], r["wwpn2"]) for r in awn_rows} == {
        ("C050760B518B0000", "C050760B518B0002"),
        ("C050760B518B0004", "C050760B518B0006"),
    }
    mq_rows = [h for h in hosts if h["lpar_name"] == "pwinmq01"]
    assert {(r["wwpn1"], r["wwpn2"]) for r in mq_rows} == {
        ("C050760B53990018", "C050760B5399001A"),
        ("C050760B5399001C", "C050760B5399001E"),
    }
    esx01 = next(h for h in hosts if h["lpar_name"] == "PEN_WINESX_VM01")
    assert esx01["wwpn1"] == "51402EC012CFD072"
    assert esx01["wwpn2"] == "51402EC012CFD2BE"
    vio01a = next(h for h in hosts if h["lpar_name"] == "pwinvio01a")
    assert vio01a["wwpn1"] == "21000024FF86027C"
    assert vio01a["wwpn2"] == "21000024FF86027D"


def test_windsor_lun_batches_and_names():
    win = _windsor_template()
    luns = win["luns"]
    # 1 AS400 + 1 ESX + 2 ap + 1 mq + 3 vio(01a/02a/02b) + 1 vio01b = 9
    assert len(luns) == 9
    assert all(lun.get("storage_profile") == "flashsystem_5200" for lun in luns)
    assert all(lun.get("pool_or_cpg") == "Windsor_G3_Pool0" for lun in luns)
    assert all(lun.get("card_hint") == "Windsor, WI" for lun in luns)

    as400 = next(lun for lun in luns if lun["purpose"] == "AWN1")
    assert as400["count"] == 6 and as400["size"] == "500GB"
    assert as400["shared"] is True and as400["name_prefix"] == "AS400"
    assert as400["host_names"] == ["AWN1"]

    esx = next(lun for lun in luns if lun["purpose"] == "ESX_DataStore")
    assert esx["count"] == 3 and esx["size"] == "4TB"
    assert esx["shared"] is True and esx["name_prefix"] == "WIN"
    assert esx["host_names"] == [
        "PEN_WINESX_VM01",
        "PEN_WINESX_VM02",
        "PEN_WINESX_VM03",
    ]

    ap_root = next(
        lun
        for lun in luns
        if lun["host_names"] == ["pwinap01"] and lun["purpose"] == "root"
    )
    assert ap_root["count"] == 3 and ap_root["size"] == "50GB"
    ap_data = next(
        lun
        for lun in luns
        if lun["host_names"] == ["pwinap01"] and lun["purpose"] == "data"
    )
    assert ap_data["count"] == 2 and ap_data["size"] == "100GB"

    mq = next(lun for lun in luns if lun["host_names"] == ["pwinmq01"])
    assert mq["purpose"] == "root" and mq["count"] == 3 and mq["size"] == "50GB"

    vio01b = next(lun for lun in luns if lun["host_names"] == ["pwinvio01b"])
    assert vio01b["count"] == 5 and vio01b["size"] == "100GB"

    expanded = [
        name for lun in luns for name in (r["name"] for r in expand_lun_batch(lun))
    ]
    assert "AS400_AWN1_1" in expanded
    assert "AS400_AWN1_6" in expanded
    assert "WIN_ESX_DataStore_1" in expanded
    assert "WIN_ESX_DataStore_3" in expanded
    assert "pwinap01_root_1" in expanded
    assert "pwinap01_data_1" in expanded
    assert "pwinmq01_root_1" in expanded
    assert "pwinvio01a_root_1" in expanded
    assert "pwinvio01b_root_1" in expanded
    assert "pwinvio01b_root_5" in expanded
    assert "pwinvio02b_root_2" in expanded
    assert len(expanded) == len(set(expanded))
    # 6 + 3 + 3 + 2 + 3 + 2 + 2 + 2 + 5 = 28
    assert len(expanded) == 28
```

In `tests/test_health_server_lun_builder.py`, update `test_api_get_lun_builds_includes_site_templates`:

```python
    template_ids = {t["id"] for t in payload["templates"]}
    assert template_ids == {
        "template-hartford-ct",
        "template-jupiter-fl",
        "template-pendergrass-ga",
        "template-mount-vernon-il",
        "template-windsor-wi",
    }
```

- [ ] **Step 2: Run tests to verify RED**

```powershell
python -m pytest tests/test_lun_builder_data.py -k "hartford or windsor or mount_vernon" tests/test_health_server_lun_builder.py::test_api_get_lun_builds_includes_site_templates -v
```

Expected: FAIL — Windsor missing / `len(templates)` still 4.

- [ ] **Step 3: Add `_windsor_host` and append Windsor seed**

Place after `_mount_vernon_host` (or after the last site-host helper):

```python
def _windsor_host(lpar_name: str, wwpn1: str = "", wwpn2: str = "") -> dict:
    return {
        "lpar_name": lpar_name,
        "slot": "",
        "state": "",
        "required": False,
        "type": "Generic",
        "remote_lpar": "",
        "remote_slot": "",
        "wwpn1": wwpn1,
        "wwpn2": wwpn2,
        "physical_fc_slot": "",
        "managed_system_name": "",
        "managed_system_serial": "",
        "notes": "",
    }
```

In `seed_lun_builder_templates()`, after Mount Vernon is built and before `return [...]`, append Windsor:

```python
    win_hosts = [
        _windsor_host("AWN1", "C050760B518B0000", "C050760B518B0002"),
        _windsor_host("AWN1", "C050760B518B0004", "C050760B518B0006"),
        _windsor_host("PEN_WINESX_VM01", "51402EC012CFD072", "51402EC012CFD2BE"),
        _windsor_host("PEN_WINESX_VM02", "51402EC012CFD090", "51402EC012CFD2C4"),
        _windsor_host("PEN_WINESX_VM03", "51402EC012C90280", "51402EC012C904A4"),
        _windsor_host("pwinap01", "", ""),
        _windsor_host("pwinmq01", "C050760B53990018", "C050760B5399001A"),
        _windsor_host("pwinmq01", "C050760B5399001C", "C050760B5399001E"),
        _windsor_host("pwinvio01a", "21000024FF86027C", "21000024FF86027D"),
        _windsor_host("pwinvio01b", "21000024FF86025C", "21000024FF86025D"),
        _windsor_host("pwinvio01b", "21000024FF86025E", ""),
        _windsor_host("pwinvio02a", "21000024FF860A7C", "21000024FF860A7D"),
        _windsor_host("pwinvio02b", "21000024FF86048C", "21000024FF86048D"),
        _windsor_host("pwinvio02b", "21000024FF86048E", ""),
    ]
    win_kwargs = {
        "storage_profile": "flashsystem_5200",
        "pool_or_cpg": "Windsor_G3_Pool0",
        "card_hint": "Windsor, WI",
    }
    win_esx = ["PEN_WINESX_VM01", "PEN_WINESX_VM02", "PEN_WINESX_VM03"]
    win_luns: list[dict] = [
        _lun_batch(
            "AWN1", 6, "500GB", True, ["AWN1"], "",
            name_prefix="AS400", **win_kwargs,
        ),
        _lun_batch(
            "ESX_DataStore", 3, "4TB", True, win_esx, "",
            name_prefix="WIN", **win_kwargs,
        ),
        _lun_batch(
            "root", 3, "50GB", False, ["pwinap01"], "app",
            name_prefix="pwin", **win_kwargs,
        ),
        _lun_batch(
            "data", 2, "100GB", False, ["pwinap01"], "app",
            name_prefix="pwin", **win_kwargs,
        ),
        _lun_batch(
            "root", 3, "50GB", False, ["pwinmq01"], "mq",
            name_prefix="pwin", **win_kwargs,
        ),
    ]
    for vio in ("pwinvio01a", "pwinvio02a", "pwinvio02b"):
        win_luns.append(
            _lun_batch(
                "root", 2, "100GB", False, [vio], "vio",
                name_prefix="pwin", **win_kwargs,
            )
        )
    win_luns.append(
        _lun_batch(
            "root", 5, "100GB", False, ["pwinvio01b"], "vio",
            name_prefix="pwin", **win_kwargs,
        )
    )
```

Append to the returned list:

```python
        {
            "id": "template-windsor-wi",
            "name": "Windsor, WI (Template)",
            "location": "Windsor, WI",
            "notes": (
                "Seeded from Windsor FlashSystem 5200 inventory (Windsor_Cluster site). "
                "Active Port Definition WWPNs are filled except pwinap01 (blank). "
                "Offline ports omitted. Defaults use card hint Windsor, WI, "
                "profile flashsystem_5200, pool Windsor_G3_Pool0."
            ),
            "is_template": True,
            "default_storage_profile": "flashsystem_5200",
            "default_pool_or_cpg": "Windsor_G3_Pool0",
            "default_card_hint": "Windsor, WI",
            "hosts": win_hosts,
            "luns": win_luns,
        },
```

- [ ] **Step 4: Run tests GREEN**

```powershell
python -m pytest tests/test_lun_builder_data.py tests/test_health_server_lun_builder.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add launchpad/lun_builder_data.py tests/test_lun_builder_data.py tests/test_health_server_lun_builder.py
git commit -m "Add Windsor WI LUN Builder template."
```

---

### Task 2: Version bump and regression

**Files:**
- Modify: `launchpad/config.py`

**Interfaces:**
- Consumes: Task 1 template seed
- Produces: `APP_VERSION = "1.6.41"`

- [ ] **Step 1: Bump version**

```python
APP_VERSION = "1.6.41"
```

- [ ] **Step 2: Full suite**

```powershell
python -m pytest tests
```

Expected: all PASS.

- [ ] **Step 3: Commit**

```powershell
git add launchpad/config.py
git commit -m "Bump version to 1.6.41 for Windsor template."
```

---

## Spec coverage checklist

| Requirement | Task |
|-------------|------|
| Branch from contingency-groups / five templates | Task 0 + 1 |
| `template-windsor-wi` identity + notes | Task 1 |
| Defaults card/profile/pool | Task 1 |
| 14 host rows, Active WWPNs, blank `pwinap01` | Task 1 |
| 9 LUN batches + expanded name samples (28 vols) | Task 1 |
| Prior templates unchanged; all five in API | Task 1 |
| Version `1.6.41` | Task 2 |
