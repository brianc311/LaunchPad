# Pendergrass GA LUN Builder Template Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a built-in Pendergrass, GA LUN Builder template (two ESX hosts, three shared LUN batches, blank WWPNs, FlashSystem 5200 defaults) beside Hartford and Jupiter.

**Architecture:** Extend `seed_lun_builder_templates()` to return Hartford, Jupiter, and Pendergrass. Add a thin `_pendergrass_host(name)` helper (same shape as `_jupiter_host`) and three shared LUN batches via existing `_lun_batch` kwargs. Keep Hartford and Jupiter unchanged. Update tests that assert template count / id set.

**Tech Stack:** Python seed data in `launchpad/lun_builder_data.py`, pytest.

**Spec:** `docs/superpowers/specs/2026-07-20-lun-builder-pendergrass-template-design.md`

## Global Constraints

- **Base branch:** implement on top of `feature/lun-jupiter-template` (already has Jupiter + `_lun_batch` profile/pool/card kwargs + `APP_VERSION=1.6.38`). Do not re-implement Jupiter.
- Template id: `template-pendergrass-ga`
- Name: `Pendergrass, GA (Template)`; location: `Pendergrass, GA`; `is_template: True`
- Defaults: `default_storage_profile=flashsystem_5200`, `default_pool_or_cpg=G3_PEN_Pool1`, `default_card_hint=Pendergrass, GA`
- Every LUN row: same profile/pool/card_hint, `name_prefix=PEN`, `shared=True`, `cluster=esx`, both host names
- All host `wwpn1`/`wwpn2` empty strings; `type=Generic`
- Hosts: `pen_penesx_vm05`, `pen_penesx_vm06`
- LUN batches: `ESX_VOL`×3 @ `2TB`; `ESX_VOL`×1 @ `4TB`; `ESX_VOL_COREDUMP`×1 @ `100GB`
- Do not store array canister FC ports as host WWPNs
- Do not modify Hartford or Jupiter seed content
- Bump `APP_VERSION` to `1.6.39` in the final task
- Commit at each task’s commit step

---

## File map

| File | Responsibility |
|------|----------------|
| `launchpad/lun_builder_data.py` | `_pendergrass_host`, Pendergrass seed entry in `seed_lun_builder_templates` |
| `tests/test_lun_builder_data.py` | Pendergrass identity/hosts/LUN/WWPN contracts; bump Hartford `len==2` → `3` |
| `tests/test_health_server_lun_builder.py` | API template id set includes Pendergrass |
| `launchpad/config.py` | `1.6.39` |

---

### Task 0: Branch / worktree from Jupiter

**Files:** none (git only)

**Interfaces:**
- Consumes: remote/local `feature/lun-jupiter-template` at `1.6.38`
- Produces: working branch `feature/lun-pendergrass-template` (or equivalent worktree)

- [ ] **Step 1: Create branch from Jupiter tip**

```powershell
git fetch origin
git checkout -b feature/lun-pendergrass-template feature/lun-jupiter-template
```

If using a worktree (preferred for isolation):

```powershell
git worktree add .worktrees/lun-pendergrass-template -b feature/lun-pendergrass-template feature/lun-jupiter-template
cd .worktrees/lun-pendergrass-template
```

- [ ] **Step 2: Confirm Jupiter is present**

```powershell
python -c "from launchpad.lun_builder_data import seed_lun_builder_templates; print([t['id'] for t in seed_lun_builder_templates()])"
```

Expected: `['template-hartford-ct', 'template-jupiter-fl']`

- [ ] **Step 3: No commit** (setup only)

---

### Task 1: Seed Pendergrass template data + tests

**Files:**
- Modify: `launchpad/lun_builder_data.py`
- Test: `tests/test_lun_builder_data.py`
- Test: `tests/test_health_server_lun_builder.py`

**Interfaces:**
- Consumes: existing `_lun_batch` (with `storage_profile` / `pool_or_cpg` / `card_hint` kwargs), `_jupiter_host` pattern, `seed_lun_builder_templates`, `expand_lun_batch`, `normalize_build`
- Produces: third template dict `template-pendergrass-ga`; `_pendergrass_host(lpar_name: str) -> dict`

- [ ] **Step 1: Update length / API set and add failing Pendergrass tests**

In `tests/test_lun_builder_data.py`, inside `test_hartford_template_identity`, change:

```python
assert len(templates) == 2
```

to:

```python
assert len(templates) == 3
```

Add:

```python
def _pendergrass_template() -> dict:
    return next(
        t for t in seed_lun_builder_templates() if t["id"] == "template-pendergrass-ga"
    )


def test_pendergrass_template_identity_and_defaults():
    pen = _pendergrass_template()
    assert pen["name"] == "Pendergrass, GA (Template)"
    assert pen["location"] == "Pendergrass, GA"
    assert pen["is_template"] is True
    assert pen["default_storage_profile"] == "flashsystem_5200"
    assert pen["default_pool_or_cpg"] == "G3_PEN_Pool1"
    assert pen["default_card_hint"] == "Pendergrass, GA"
    assert normalize_build(pen)["is_template"] is True


def test_pendergrass_hosts_blank_wwpns():
    pen = _pendergrass_template()
    names = {h["lpar_name"] for h in pen["hosts"]}
    assert names == {"pen_penesx_vm05", "pen_penesx_vm06"}
    assert len(pen["hosts"]) == 2
    assert all(h.get("wwpn1") == "" and h.get("wwpn2") == "" for h in pen["hosts"])
    assert all(h.get("type") == "Generic" for h in pen["hosts"])


def test_pendergrass_lun_batches_shared_and_names():
    pen = _pendergrass_template()
    luns = pen["luns"]
    both = ["pen_penesx_vm05", "pen_penesx_vm06"]
    assert len(luns) == 3
    assert all(lun.get("name_prefix") == "PEN" for lun in luns)
    assert all(lun.get("storage_profile") == "flashsystem_5200" for lun in luns)
    assert all(lun.get("pool_or_cpg") == "G3_PEN_Pool1" for lun in luns)
    assert all(lun.get("card_hint") == "Pendergrass, GA" for lun in luns)
    assert all(lun.get("shared") is True for lun in luns)
    assert all(lun.get("cluster") == "esx" for lun in luns)
    assert all(lun.get("host_names") == both for lun in luns)

    vol_2tb = next(
        lun for lun in luns if lun["purpose"] == "ESX_VOL" and lun["size"] == "2TB"
    )
    assert vol_2tb["count"] == 3
    vol_4tb = next(
        lun for lun in luns if lun["purpose"] == "ESX_VOL" and lun["size"] == "4TB"
    )
    assert vol_4tb["count"] == 1
    coredump = next(lun for lun in luns if lun["purpose"] == "ESX_VOL_COREDUMP")
    assert coredump["count"] == 1 and coredump["size"] == "100GB"

    expanded = [
        name for lun in luns for name in (r["name"] for r in expand_lun_batch(lun))
    ]
    assert len(expanded) == 5
    assert len(expanded) == len(set(expanded))
    assert "PENesx_ESX_VOL_1" in expanded
    assert "PENesx_ESX_VOL_2" in expanded
    assert "PENesx_ESX_VOL_3" in expanded
    assert "PENesx_ESX_VOL" in expanded  # single 4TB batch (count==1 uses base only)
    assert "PENesx_ESX_VOL_COREDUMP" in expanded
```

**Naming note:** shared + `cluster=esx` + `name_prefix=PEN` → `_volume_name_base` yields `PENesx_<purpose>`. Count `1` omits the `_N` suffix; count `3` yields `_1`…`_3`. The 4TB and 3×2TB batches both use purpose `ESX_VOL`, so expanded names collide on the stem — the 4TB single name is `PENesx_ESX_VOL` while the 2TB set is `PENesx_ESX_VOL_1`…`_3`. That is intentional and unique.

In `tests/test_health_server_lun_builder.py`, update `test_api_get_lun_builds_includes_site_templates`:

```python
def test_api_get_lun_builds_includes_site_templates(monkeypatch):
    settings, getter, setter = _settings_backend()
    server = HealthServer()
    server.set_settings_backend(getter, setter)

    status, payload = _call_lun_builds_api(monkeypatch, server, "GET")

    assert status == 200
    template_ids = {t["id"] for t in payload["templates"]}
    assert template_ids == {
        "template-hartford-ct",
        "template-jupiter-fl",
        "template-pendergrass-ga",
    }
    assert all(
        build["id"] not in template_ids for build in payload["builds"]
    )
    assert LUN_BUILDS_SETTING not in settings
```

- [ ] **Step 2: Run tests to verify RED**

```powershell
python -m pytest tests/test_lun_builder_data.py -k "hartford or jupiter or pendergrass" tests/test_health_server_lun_builder.py::test_api_get_lun_builds_includes_site_templates -v
```

Expected: FAIL — Pendergrass missing / `len(templates)` still 2 / API set missing id.

- [ ] **Step 3: Add `_pendergrass_host` and append Pendergrass seed**

Place `_pendergrass_host` immediately after `_jupiter_host` (same body; separate name for clarity):

```python
def _pendergrass_host(lpar_name: str) -> dict:
    return {
        "lpar_name": lpar_name,
        "slot": "",
        "state": "",
        "required": False,
        "type": "Generic",
        "remote_lpar": "",
        "remote_slot": "",
        "wwpn1": "",
        "wwpn2": "",
        "physical_fc_slot": "",
        "managed_system_name": "",
        "managed_system_serial": "",
        "notes": "",
    }
```

In `seed_lun_builder_templates()`, after the Jupiter block is built and before `return [...]`, build Pendergrass and include it as the third list element:

```python
    pen_hosts = [
        _pendergrass_host(name)
        for name in ("pen_penesx_vm05", "pen_penesx_vm06")
    ]
    pen_kwargs = {
        "name_prefix": "PEN",
        "storage_profile": "flashsystem_5200",
        "pool_or_cpg": "G3_PEN_Pool1",
        "card_hint": "Pendergrass, GA",
    }
    pen_both = ["pen_penesx_vm05", "pen_penesx_vm06"]
    pen_luns = [
        _lun_batch("ESX_VOL", 3, "2TB", True, pen_both, "esx", **pen_kwargs),
        _lun_batch("ESX_VOL", 1, "4TB", True, pen_both, "esx", **pen_kwargs),
        _lun_batch("ESX_VOL_COREDUMP", 1, "100GB", True, pen_both, "esx", **pen_kwargs),
    ]
```

Return structure:

```python
    return [
        { ... existing hartford dict unchanged ... },
        { ... existing jupiter dict unchanged ... },
        {
            "id": "template-pendergrass-ga",
            "name": "Pendergrass, GA (Template)",
            "location": "Pendergrass, GA",
            "notes": (
                "Seeded from Pendergrass FlashSystem 5200 inventory. "
                "WWPNs are blank — set Port Definitions / Pull from FC WWPN before create. "
                "Defaults use card hint Pendergrass, GA, profile flashsystem_5200, pool G3_PEN_Pool1."
            ),
            "is_template": True,
            "default_storage_profile": "flashsystem_5200",
            "default_pool_or_cpg": "G3_PEN_Pool1",
            "default_card_hint": "Pendergrass, GA",
            "hosts": pen_hosts,
            "luns": pen_luns,
        },
    ]
```

Do **not** change `_lun_batch` signature further unless Jupiter’s kwargs are missing on the base branch (they should already exist).

- [ ] **Step 4: Run tests GREEN**

```powershell
python -m pytest tests/test_lun_builder_data.py tests/test_health_server_lun_builder.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add launchpad/lun_builder_data.py tests/test_lun_builder_data.py tests/test_health_server_lun_builder.py
git commit -m "Add Pendergrass GA LUN Builder template."
```

---

### Task 2: Version bump and regression

**Files:**
- Modify: `launchpad/config.py`

**Interfaces:**
- Consumes: Task 1 template seed
- Produces: `APP_VERSION = "1.6.39"`

- [ ] **Step 1: Bump version**

In `launchpad/config.py`:

```python
APP_VERSION = "1.6.39"
```

- [ ] **Step 2: Full suite**

```powershell
python -m pytest tests
```

Expected: all PASS.

- [ ] **Step 3: Commit**

```powershell
git add launchpad/config.py
git commit -m "Bump version to 1.6.39 for Pendergrass template."
```

---

## Spec coverage checklist

| Requirement | Task |
|-------------|------|
| Branch from Jupiter / three templates | Task 0 + 1 |
| `template-pendergrass-ga` identity + notes | Task 1 |
| Defaults card/profile/pool | Task 1 |
| 2 hosts, blank WWPNs, Generic | Task 1 |
| 3 shared LUN batches + sizes + expanded names | Task 1 |
| Hartford/Jupiter unchanged; all three in API | Task 1 |
| No array canister WWPNs as host ports | Task 1 (blank WWPNs only) |
| Version `1.6.39` | Task 2 |
