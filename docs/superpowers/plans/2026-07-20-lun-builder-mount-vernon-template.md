# Mount Vernon IL LUN Builder Template Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a built-in Mount Vernon, IL LUN Builder template (full site: AS400 + ESX + VIO + test, Active WWPNs with multi-row hosts, FlashSystem 5200 defaults) beside Hartford, Jupiter, and Pendergrass.

**Architecture:** Extend `seed_lun_builder_templates()` to return four templates. Add `_mount_vernon_host(lpar_name, wwpn1, wwpn2)` and Mount Vernon LUN batches via existing `_lun_batch` kwargs. Keep prior templates unchanged. Update tests that assert template count / id set.

**Tech Stack:** Python seed data in `launchpad/lun_builder_data.py`, pytest.

**Spec:** `docs/superpowers/specs/2026-07-20-lun-builder-mount-vernon-template-design.md`

## Global Constraints

- **Base branch:** implement on top of `feature/lun-pendergrass-template` (already has Pendergrass + `APP_VERSION=1.6.39`). Do not re-implement prior templates.
- Template id: `template-mount-vernon-il`
- Name: `Mount Vernon, IL (Template)`; location: `Mount Vernon, IL`; `is_template: True`
- Defaults: `default_storage_profile=flashsystem_5200`, `default_pool_or_cpg=MtVerno_Pool1`, `default_card_hint=Mount Vernon, IL`
- Every LUN row: same profile/pool/card_hint
- Hosts: 11 rows as in the spec (multi-row for `amv1_as400` and `tmtvtst1`); `type=Generic`; Active WWPNs only
- LUN batches exactly as in the spec table (AS400 10×500GB; ESX 4×4TB shared; 4 VIO root 2×100GB; tmtvtst1 root 3×100GB)
- Do not seed Offline ports; do not modify Hartford/Jupiter/Pendergrass seed content
- Bump `APP_VERSION` to `1.6.40` in the final task
- Commit at each task’s commit step

---

## File map

| File | Responsibility |
|------|----------------|
| `launchpad/lun_builder_data.py` | `_mount_vernon_host`, Mount Vernon seed entry |
| `tests/test_lun_builder_data.py` | Mount Vernon contracts; bump `len==3` → `4` |
| `tests/test_health_server_lun_builder.py` | API template id set includes Mount Vernon |
| `launchpad/config.py` | `1.6.40` |

---

### Task 0: Branch / worktree from Pendergrass

**Files:** none (git only)

**Interfaces:**
- Consumes: `feature/lun-pendergrass-template` at `1.6.39`
- Produces: working branch `feature/lun-mount-vernon-template`

- [ ] **Step 1: Create branch from Pendergrass tip**

```powershell
git fetch origin
git worktree add .worktrees/lun-mount-vernon-template -b feature/lun-mount-vernon-template feature/lun-pendergrass-template
cd .worktrees/lun-mount-vernon-template
```

- [ ] **Step 2: Confirm three templates present**

```powershell
python -c "from launchpad.lun_builder_data import seed_lun_builder_templates; print([t['id'] for t in seed_lun_builder_templates()])"
```

Expected: `['template-hartford-ct', 'template-jupiter-fl', 'template-pendergrass-ga']`

- [ ] **Step 3: No commit** (setup only)

---

### Task 1: Seed Mount Vernon template data + tests

**Files:**
- Modify: `launchpad/lun_builder_data.py`
- Test: `tests/test_lun_builder_data.py`
- Test: `tests/test_health_server_lun_builder.py`

**Interfaces:**
- Consumes: `_lun_batch` (with profile/pool/card kwargs), `seed_lun_builder_templates`, `expand_lun_batch`, `normalize_build`
- Produces: fourth template dict `template-mount-vernon-il`; `_mount_vernon_host(lpar_name: str, wwpn1: str = "", wwpn2: str = "") -> dict`

- [ ] **Step 1: Update length / API set and add failing Mount Vernon tests**

In `tests/test_lun_builder_data.py`, inside `test_hartford_template_identity`, change:

```python
assert len(templates) == 3
```

to:

```python
assert len(templates) == 4
```

Add:

```python
def _mount_vernon_template() -> dict:
    return next(
        t for t in seed_lun_builder_templates() if t["id"] == "template-mount-vernon-il"
    )


def test_mount_vernon_template_identity_and_defaults():
    mtv = _mount_vernon_template()
    assert mtv["name"] == "Mount Vernon, IL (Template)"
    assert mtv["location"] == "Mount Vernon, IL"
    assert mtv["is_template"] is True
    assert mtv["default_storage_profile"] == "flashsystem_5200"
    assert mtv["default_pool_or_cpg"] == "MtVerno_Pool1"
    assert mtv["default_card_hint"] == "Mount Vernon, IL"
    assert normalize_build(mtv)["is_template"] is True


def test_mount_vernon_hosts_and_active_wwpns():
    mtv = _mount_vernon_template()
    hosts = mtv["hosts"]
    assert len(hosts) == 11
    names = [h["lpar_name"] for h in hosts]
    assert names.count("amv1_as400") == 2
    assert names.count("tmtvtst1") == 2
    assert set(names) == {
        "amv1_as400",
        "pen-mtvesx-vm01",
        "pen-mtvesx-vm02",
        "pen-mtvesx-vm03",
        "pmtvvio01a",
        "pmtvvio01b",
        "pmtvvio02a",
        "pmtvvio02b",
        "tmtvtst1",
    }
    assert all(h.get("type") == "Generic" for h in hosts)

    as400_rows = [h for h in hosts if h["lpar_name"] == "amv1_as400"]
    assert {(r["wwpn1"], r["wwpn2"]) for r in as400_rows} == {
        ("C050760B552B0004", "C050760B552B0006"),
        ("C050760B552B0010", ""),
    }
    tst_rows = [h for h in hosts if h["lpar_name"] == "tmtvtst1"]
    assert {(r["wwpn1"], r["wwpn2"]) for r in tst_rows} == {
        ("C050760B20CA0008", "C050760B20CA000A"),
        ("C050760B20CA000C", "C050760B20CA000E"),
    }
    esx01 = next(h for h in hosts if h["lpar_name"] == "pen-mtvesx-vm01")
    assert esx01["wwpn1"] == "51402EC012434DDC"
    assert esx01["wwpn2"] == "51402EC012434DDE"
    vio01a = next(h for h in hosts if h["lpar_name"] == "pmtvvio01a")
    assert vio01a["wwpn1"] == "21000024FF85BB40"
    assert vio01a["wwpn2"] == "21000024FF85BB41"


def test_mount_vernon_lun_batches_and_names():
    mtv = _mount_vernon_template()
    luns = mtv["luns"]
    # 1 AS400 + 1 ESX + 4 VIO + 1 test = 7
    assert len(luns) == 7
    assert all(lun.get("storage_profile") == "flashsystem_5200" for lun in luns)
    assert all(lun.get("pool_or_cpg") == "MtVerno_Pool1" for lun in luns)
    assert all(lun.get("card_hint") == "Mount Vernon, IL" for lun in luns)

    as400 = next(lun for lun in luns if lun["purpose"] == "AS400")
    assert as400["count"] == 10 and as400["size"] == "500GB"
    assert as400["shared"] is True
    assert as400["name_prefix"] == "AVM1"
    assert as400["host_names"] == ["amv1_as400"]

    esx = next(lun for lun in luns if lun["purpose"] == "ESXI_DS")
    assert esx["count"] == 4 and esx["size"] == "4TB"
    assert esx["shared"] is True
    assert esx["name_prefix"] == "MTV"
    assert esx["host_names"] == [
        "pen-mtvesx-vm01",
        "pen-mtvesx-vm02",
        "pen-mtvesx-vm03",
    ]

    vio = [
        lun
        for lun in luns
        if lun["purpose"] == "root" and lun["host_names"][0].startswith("pmtvvio")
    ]
    assert len(vio) == 4
    assert all(lun["count"] == 2 and lun["size"] == "100GB" for lun in vio)
    assert all(lun["name_prefix"] == "pmtv" for lun in vio)

    tst = next(lun for lun in luns if lun["host_names"] == ["tmtvtst1"])
    assert tst["purpose"] == "root" and tst["count"] == 3 and tst["size"] == "100GB"
    assert tst["name_prefix"] == ""

    expanded = [
        name for lun in luns for name in (r["name"] for r in expand_lun_batch(lun))
    ]
    assert "AVM1_AS400_1" in expanded
    assert "AVM1_AS400_10" in expanded
    assert "MTV_ESXI_DS_1" in expanded
    assert "MTV_ESXI_DS_4" in expanded
    assert "pmtvvio01a_root_1" in expanded
    assert "pmtvvio02b_root_2" in expanded
    assert "tmtvtst1_root_1" in expanded
    assert "tmtvtst1_root_3" in expanded
    assert len(expanded) == len(set(expanded))
    # 10 + 4 + 8 + 3 = 25
    assert len(expanded) == 25
```

In `tests/test_health_server_lun_builder.py`, update `test_api_get_lun_builds_includes_site_templates`:

```python
    template_ids = {t["id"] for t in payload["templates"]}
    assert template_ids == {
        "template-hartford-ct",
        "template-jupiter-fl",
        "template-pendergrass-ga",
        "template-mount-vernon-il",
    }
```

- [ ] **Step 2: Run tests to verify RED**

```powershell
python -m pytest tests/test_lun_builder_data.py -k "hartford or mount_vernon or pendergrass" tests/test_health_server_lun_builder.py::test_api_get_lun_builds_includes_site_templates -v
```

Expected: FAIL — Mount Vernon missing / `len(templates)` still 3.

- [ ] **Step 3: Add `_mount_vernon_host` and append Mount Vernon seed**

Place after `_pendergrass_host`:

```python
def _mount_vernon_host(lpar_name: str, wwpn1: str = "", wwpn2: str = "") -> dict:
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

In `seed_lun_builder_templates()`, after the Pendergrass block is built and before `return [...]`, build Mount Vernon and include it as the fourth list element:

```python
    mtv_hosts = [
        _mount_vernon_host("amv1_as400", "C050760B552B0004", "C050760B552B0006"),
        _mount_vernon_host("amv1_as400", "C050760B552B0010", ""),
        _mount_vernon_host("pen-mtvesx-vm01", "51402EC012434DDC", "51402EC012434DDE"),
        _mount_vernon_host("pen-mtvesx-vm02", "51402EC012435D38", "51402EC012435D3A"),
        _mount_vernon_host("pen-mtvesx-vm03", "51402EC01243643C", "51402EC01243643E"),
        _mount_vernon_host("pmtvvio01a", "21000024FF85BB40", "21000024FF85BB41"),
        _mount_vernon_host("pmtvvio01b", "21000024FF85F054", "21000024FF85F055"),
        _mount_vernon_host("pmtvvio02a", "21000024FF860A60", "21000024FF860A61"),
        _mount_vernon_host("pmtvvio02b", "21000024FF86373E", "21000024FF86373F"),
        _mount_vernon_host("tmtvtst1", "C050760B20CA0008", "C050760B20CA000A"),
        _mount_vernon_host("tmtvtst1", "C050760B20CA000C", "C050760B20CA000E"),
    ]
    mtv_kwargs = {
        "storage_profile": "flashsystem_5200",
        "pool_or_cpg": "MtVerno_Pool1",
        "card_hint": "Mount Vernon, IL",
    }
    mtv_esx = ["pen-mtvesx-vm01", "pen-mtvesx-vm02", "pen-mtvesx-vm03"]
    mtv_luns: list[dict] = [
        _lun_batch(
            "AS400", 10, "500GB", True, ["amv1_as400"], "",
            name_prefix="AVM1", **mtv_kwargs,
        ),
        _lun_batch(
            "ESXI_DS", 4, "4TB", True, mtv_esx, "",
            name_prefix="MTV", **mtv_kwargs,
        ),
    ]
    for vio in ("pmtvvio01a", "pmtvvio01b", "pmtvvio02a", "pmtvvio02b"):
        mtv_luns.append(
            _lun_batch(
                "root", 2, "100GB", False, [vio], "vio",
                name_prefix="pmtv", **mtv_kwargs,
            )
        )
    mtv_luns.append(
        _lun_batch(
            "root", 3, "100GB", False, ["tmtvtst1"], "test",
            name_prefix="", **mtv_kwargs,
        )
    )
```

Return structure — keep existing three dicts unchanged, append:

```python
        {
            "id": "template-mount-vernon-il",
            "name": "Mount Vernon, IL (Template)",
            "location": "Mount Vernon, IL",
            "notes": (
                "Seeded from Mount Vernon FlashSystem 5200 inventory. "
                "Active Port Definition WWPNs are filled; Offline ports omitted. "
                "Defaults use card hint Mount Vernon, IL, profile flashsystem_5200, pool MtVerno_Pool1."
            ),
            "is_template": True,
            "default_storage_profile": "flashsystem_5200",
            "default_pool_or_cpg": "MtVerno_Pool1",
            "default_card_hint": "Mount Vernon, IL",
            "hosts": mtv_hosts,
            "luns": mtv_luns,
        },
```

**Note on `_lun_batch` cluster arg:** Hartford/Jupiter pass cluster as a positional string. Empty string `""` is correct for AS400/ESX (no cluster qualifier in names). Confirm `_lun_batch(..., cluster, ...)` still accepts `""`.

- [ ] **Step 4: Run tests GREEN**

```powershell
python -m pytest tests/test_lun_builder_data.py tests/test_health_server_lun_builder.py -v
```

Expected: PASS. If AS400 expand names fail, verify shared+prefix+empty-cluster path yields `AVM1_AS400_N` (not `amv1_as400_…`).

- [ ] **Step 5: Commit**

```powershell
git add launchpad/lun_builder_data.py tests/test_lun_builder_data.py tests/test_health_server_lun_builder.py
git commit -m "Add Mount Vernon IL LUN Builder template."
```

---

### Task 2: Version bump and regression

**Files:**
- Modify: `launchpad/config.py`

**Interfaces:**
- Consumes: Task 1 template seed
- Produces: `APP_VERSION = "1.6.40"`

- [ ] **Step 1: Bump version**

```python
APP_VERSION = "1.6.40"
```

- [ ] **Step 2: Full suite**

```powershell
python -m pytest tests
```

Expected: all PASS.

- [ ] **Step 3: Commit**

```powershell
git add launchpad/config.py
git commit -m "Bump version to 1.6.40 for Mount Vernon template."
```

---

## Spec coverage checklist

| Requirement | Task |
|-------------|------|
| Branch from Pendergrass / four templates | Task 0 + 1 |
| `template-mount-vernon-il` identity + notes | Task 1 |
| Defaults card/profile/pool | Task 1 |
| 11 host rows, Active WWPNs, multi-row AS400/test | Task 1 |
| 7 LUN batches + expanded name samples | Task 1 |
| Prior templates unchanged; all four in API | Task 1 |
| Offline ports not seeded | Task 1 |
| Version `1.6.40` | Task 2 |
