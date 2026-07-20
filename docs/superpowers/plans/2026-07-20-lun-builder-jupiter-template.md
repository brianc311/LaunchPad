# Jupiter FL LUN Builder Template Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a built-in Jupiter, FL LUN Builder template (hosts + LUN plan, blank WWPNs, FlashSystem 5200 defaults) beside Hartford.

**Architecture:** Extend `seed_lun_builder_templates()` to return Hartford and Jupiter. Add a thin `_jupiter_host(name)` helper and Jupiter LUN batches using existing `_lun_batch`. Keep Hartford unchanged. Update tests that assumed a single template.

**Tech Stack:** Python seed data in `launchpad/lun_builder_data.py`, pytest.

**Spec:** `docs/superpowers/specs/2026-07-20-lun-builder-jupiter-template-design.md`

## Global Constraints

- Template id: `template-jupiter-fl`
- Name: `Jupiter, FL (Template)`; location: `Jupiter, FL`; `is_template: True`
- Defaults: `default_storage_profile=flashsystem_5200`, `default_pool_or_cpg=JUP_G3_Pool`, `default_card_hint=Jupiter, FL`
- Every LUN row: same profile/pool/card_hint, `name_prefix=pjup`
- All host `wwpn1`/`wwpn2` empty strings
- Hosts: eight `pjupvio*` + `pjupmhcdb2`, `pjupmhcdg2`, `pjupres01`
- LUN batches exactly as in the spec table (vio 2×100GB root; db root/data; res 5×100GB data)
- Do not modify Hartford seed content
- Bump `APP_VERSION` to `1.6.38` in the final task
- Commit at each task’s commit step

---

## File map

| File | Responsibility |
|------|----------------|
| `launchpad/lun_builder_data.py` | `_jupiter_host`, Jupiter seed entry in `seed_lun_builder_templates` |
| `tests/test_lun_builder_data.py` | Jupiter identity/hosts/LUN/WWPN contracts; update Hartford `len==1` |
| `tests/test_health_server_lun_builder.py` | API returns both templates (lookup by id, not only `[0]`) |
| `launchpad/config.py` | `1.6.38` |

---

### Task 1: Seed Jupiter template data + tests

**Files:**
- Modify: `launchpad/lun_builder_data.py`
- Test: `tests/test_lun_builder_data.py`
- Test: `tests/test_health_server_lun_builder.py`

**Interfaces:**
- Consumes: existing `_lun_batch`, `seed_lun_builder_templates`, `expand_lun_batch`, `normalize_build`
- Produces: second template dict `template-jupiter-fl`; `_jupiter_host(lpar_name: str) -> dict`

- [ ] **Step 1: Update Hartford length assumption and add failing Jupiter tests**

In `tests/test_lun_builder_data.py`, change:

```python
assert len(templates) == 1
```

to:

```python
assert len(templates) == 2
```

inside `test_hartford_template_identity`, and resolve Hartford by id:

```python
hartford = next(t for t in templates if t["id"] == "template-hartford-ct")
```

Also update `test_hartford_hosts_cover_six_lpars` and `test_hartford_lun_batches_and_blank_profile_pool` to select Hartford by id instead of `[0]`.

Add:

```python
def _jupiter_template() -> dict:
    return next(
        t for t in seed_lun_builder_templates() if t["id"] == "template-jupiter-fl"
    )


def test_jupiter_template_identity_and_defaults():
    jup = _jupiter_template()
    assert jup["name"] == "Jupiter, FL (Template)"
    assert jup["location"] == "Jupiter, FL"
    assert jup["is_template"] is True
    assert jup["default_storage_profile"] == "flashsystem_5200"
    assert jup["default_pool_or_cpg"] == "JUP_G3_Pool"
    assert jup["default_card_hint"] == "Jupiter, FL"
    assert normalize_build(jup)["is_template"] is True


def test_jupiter_hosts_blank_wwpns():
    jup = _jupiter_template()
    names = {h["lpar_name"] for h in jup["hosts"]}
    assert names == {
        "pjupvio01a",
        "pjupvio01b",
        "pjupvio02a",
        "pjupvio02b",
        "pjupvio03a",
        "pjupvio03b",
        "pjupvio04a",
        "pjupvio04b",
        "pjupmhcdb2",
        "pjupmhcdg2",
        "pjupres01",
    }
    assert len(jup["hosts"]) == 11
    assert all(h.get("wwpn1") == "" and h.get("wwpn2") == "" for h in jup["hosts"])
    assert all(h.get("type") == "Generic" for h in jup["hosts"])


def test_jupiter_lun_batches_profile_and_names():
    jup = _jupiter_template()
    luns = jup["luns"]
    # 8 vio root + 2 db root + 2 db data + 1 res data = 13
    assert len(luns) == 13
    assert all(lun.get("name_prefix") == "pjup" for lun in luns)
    assert all(lun.get("storage_profile") == "flashsystem_5200" for lun in luns)
    assert all(lun.get("pool_or_cpg") == "JUP_G3_Pool" for lun in luns)
    assert all(lun.get("card_hint") == "Jupiter, FL" for lun in luns)

    vio_roots = [
        lun
        for lun in luns
        if lun["purpose"] == "root" and lun["host_names"][0].startswith("pjupvio")
    ]
    assert len(vio_roots) == 8
    assert all(lun["count"] == 2 and lun["size"] == "100GB" for lun in vio_roots)

    db2_root = next(
        lun
        for lun in luns
        if lun["purpose"] == "root" and lun["host_names"] == ["pjupmhcdb2"]
    )
    assert db2_root["count"] == 3 and db2_root["size"] == "50GB"
    db2_data = next(
        lun
        for lun in luns
        if lun["purpose"] == "data" and lun["host_names"] == ["pjupmhcdb2"]
    )
    assert db2_data["count"] == 9 and db2_data["size"] == "100GB"

    res = next(lun for lun in luns if lun["host_names"] == ["pjupres01"])
    assert res["purpose"] == "data" and res["count"] == 5 and res["size"] == "100GB"

    expanded = [
        name for lun in luns for name in (r["name"] for r in expand_lun_batch(lun))
    ]
    assert len(expanded) == len(set(expanded))
    assert "pjupvio01a_root_1" in expanded
    assert "pjupmhcdb2_root_1" in expanded
    assert "pjupmhcdb2_data_1" in expanded
    assert "pjupres01_data_1" in expanded
```

In `tests/test_health_server_lun_builder.py`, update `test_api_get_lun_builds_includes_hartford_template` to assert both template ids are present (rename function if desired):

```python
def test_api_get_lun_builds_includes_site_templates(monkeypatch):
    settings, getter, setter = _settings_backend()
    server = HealthServer()
    server.set_settings_backend(getter, setter)

    status, payload = _call_lun_builds_api(monkeypatch, server, "GET")

    assert status == 200
    template_ids = {t["id"] for t in payload["templates"]}
    assert template_ids == {"template-hartford-ct", "template-jupiter-fl"}
    assert all(
        build["id"] not in template_ids for build in payload["builds"]
    )
    assert LUN_BUILDS_SETTING not in settings
```

- [ ] **Step 2: Run tests to verify RED**

```powershell
python -m pytest tests/test_lun_builder_data.py -k "hartford or jupiter" tests/test_health_server_lun_builder.py::test_api_get_lun_builds_includes_site_templates -v
```

Expected: FAIL — Jupiter missing / length still 1 / old test name.

If the old test name still exists, run that name instead until renamed.

- [ ] **Step 3: Extend `_lun_batch` only if needed for card_hint**

Current `_lun_batch` does not set `card_hint`. Either:

**Option A (preferred):** add optional `card_hint: str = ""`, `storage_profile: str = ""`, `pool_or_cpg: str = ""` kwargs to `_lun_batch` and pass them through for Jupiter only (Hartford keeps defaults empty), **or**

**Option B:** after building each Jupiter lun dict, set the three fields.

Use Option A:

```python
def _lun_batch(
    purpose: str,
    count: int,
    size: str,
    shared: bool,
    host_names: list[str],
    cluster: str,
    *,
    name_prefix: str = "pcon",
    storage_profile: str = "",
    pool_or_cpg: str = "",
    card_hint: str = "",
) -> dict:
    return {
        "purpose": purpose,
        "count": count,
        "size": size,
        "shared": shared,
        "storage_profile": storage_profile,
        "pool_or_cpg": pool_or_cpg,
        "host_names": host_names,
        "scsi_or_lun_id": "",
        "card_hint": card_hint,
        "cluster": cluster,
        "name_prefix": name_prefix,
    }
```

Hartford call sites stay unchanged (empty profile/pool/card).

- [ ] **Step 4: Add `_jupiter_host` and Jupiter seed**

```python
def _jupiter_host(lpar_name: str) -> dict:
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

In `seed_lun_builder_templates()`, keep the existing Hartford dict as the first list element. Append Jupiter:

```python
    jup_hosts = [
        _jupiter_host(name)
        for name in (
            "pjupvio01a",
            "pjupvio01b",
            "pjupvio02a",
            "pjupvio02b",
            "pjupvio03a",
            "pjupvio03b",
            "pjupvio04a",
            "pjupvio04b",
            "pjupmhcdb2",
            "pjupmhcdg2",
            "pjupres01",
        )
    ]
    jup_kwargs = {
        "name_prefix": "pjup",
        "storage_profile": "flashsystem_5200",
        "pool_or_cpg": "JUP_G3_Pool",
        "card_hint": "Jupiter, FL",
    }
    jup_luns: list[dict] = []
    for vio in (
        "pjupvio01a",
        "pjupvio01b",
        "pjupvio02a",
        "pjupvio02b",
        "pjupvio03a",
        "pjupvio03b",
        "pjupvio04a",
        "pjupvio04b",
    ):
        jup_luns.append(_lun_batch("root", 2, "100GB", False, [vio], "vio", **jup_kwargs))
    for db_host in ("pjupmhcdb2", "pjupmhcdg2"):
        jup_luns.append(_lun_batch("root", 3, "50GB", False, [db_host], "db", **jup_kwargs))
        jup_luns.append(_lun_batch("data", 9, "100GB", False, [db_host], "db", **jup_kwargs))
    jup_luns.append(_lun_batch("data", 5, "100GB", False, ["pjupres01"], "res", **jup_kwargs))

    return [
        { ... existing hartford dict ... },
        {
            "id": "template-jupiter-fl",
            "name": "Jupiter, FL (Template)",
            "location": "Jupiter, FL",
            "notes": (
                "Seeded from Jupiter FlashSystem 5200 inventory. "
                "WWPNs are blank — set Port Definitions / Pull from FC WWPN before create. "
                "Defaults use card hint Jupiter, FL, profile flashsystem_5200, pool JUP_G3_Pool."
            ),
            "is_template": True,
            "default_storage_profile": "flashsystem_5200",
            "default_pool_or_cpg": "JUP_G3_Pool",
            "default_card_hint": "Jupiter, FL",
            "hosts": jup_hosts,
            "luns": jup_luns,
        },
    ]
```

Change the function from `return [{ hartford }]` to building Hartford as before then returning `[hartford, jupiter]`.

- [ ] **Step 5: Run tests GREEN**

```powershell
python -m pytest tests/test_lun_builder_data.py tests/test_health_server_lun_builder.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add launchpad/lun_builder_data.py tests/test_lun_builder_data.py tests/test_health_server_lun_builder.py
git commit -m "Add Jupiter FL LUN Builder template."
```

---

### Task 2: Version bump and regression

**Files:**
- Modify: `launchpad/config.py`

**Interfaces:**
- Consumes: Task 1 template seed
- Produces: `APP_VERSION = "1.6.38"`

- [ ] **Step 1: Bump version**

```python
APP_VERSION = "1.6.38"
```

- [ ] **Step 2: Full suite**

```powershell
python -m pytest tests
```

Expected: all PASS.

- [ ] **Step 3: Commit**

```powershell
git add launchpad/config.py
git commit -m "Bump version to 1.6.38 for Jupiter template."
```

---

## Spec coverage checklist

| Requirement | Task |
|-------------|------|
| `template-jupiter-fl` identity + notes | Task 1 |
| Defaults card/profile/pool | Task 1 |
| 11 hosts, blank WWPNs, Generic | Task 1 |
| 13 LUN batches + naming samples | Task 1 |
| Hartford unchanged; both in API templates | Task 1 |
| Version `1.6.38` | Task 2 |
