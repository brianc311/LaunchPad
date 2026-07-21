# Woodland Hills CA LUN Builder + Contingency Groups Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Woodland Hills, CA LUN Builder template (blank WWPNs, full site) and a full-site Contingency Groups seed (`v5kwoo-g3c1`, LaunchPad `_snap` rows) on top of Windsor `1.6.41`.

**Architecture:** Independent seeds — extend `seed_lun_builder_templates()` with `template-woodland-hills-ca` (Jupiter-style blank WWPN host helper + `_lun_batch`), and extend `seed_contingency_groups()` with `_woodland_hills_ca()` wrapped in `generate_snap_rows()`. Keep all prior templates/groups unchanged. Bump version to `1.6.42` last.

**Tech Stack:** Python seed data in `launchpad/lun_builder_data.py` and `launchpad/contingency_groups_data.py`, pytest.

**Spec:** `docs/superpowers/specs/2026-07-20-woodland-hills-ca-design.md`

## Global Constraints

- **Base branch:** implement on top of `feature/contingency-groups` (already has Windsor + `APP_VERSION=1.6.41`). Do not re-implement prior sites.
- LUN template id: `template-woodland-hills-ca`; name `Woodland Hills, CA (Template)`; location `Woodland Hills, CA`; `is_template: True`
- LUN defaults: `default_storage_profile=flashsystem_5200`, `default_pool_or_cpg=WOO_Pool1`, `default_card_hint=Woodland Hills, CA`
- Every LUN row: same profile/pool/card_hint; all WWPNs blank
- Contingency Groups id: `woodland-hills-ca`; name/location `Woodland Hills, CA`; `storage_hint=v5kwoo-g3c1`
- Contingency Groups: full site (AS400 + ESX + VIO); blank `wwpns`; wrap with `generate_snap_rows()`
- Do not seed IBM CG / `*_SnapN` sources; do not fill WWPNs from screenshots; do not modify prior seeds
- Bump `APP_VERSION` to `1.6.42` in the final task
- Commit at each task’s commit step

---

## File map

| File | Responsibility |
|------|----------------|
| `launchpad/lun_builder_data.py` | `_woodland_hills_host`, Woodland Hills LUN template |
| `launchpad/contingency_groups_data.py` | `_woodland_hills_ca`, seed list entry |
| `tests/test_lun_builder_data.py` | Woodland Hills LUN contracts; bump `len==5` → `6` |
| `tests/test_health_server_lun_builder.py` | API template id set includes Woodland Hills |
| `tests/test_contingency_groups_data.py` | Four-site seed contracts + Woodland Hills details |
| `tests/test_health_server_contingency_groups.py` | API seed id set includes Woodland Hills |
| `launchpad/config.py` | `1.6.42` |

---

### Task 0: Branch / worktree from contingency-groups

**Files:** none (git only)

**Interfaces:**
- Consumes: `feature/contingency-groups` at `1.6.41` with five LUN templates and three Contingency Groups
- Produces: working branch `feature/woodland-hills-ca`

- [ ] **Step 1: Create branch from contingency-groups tip**

```powershell
git fetch origin
git worktree add .worktrees/woodland-hills-ca -b feature/woodland-hills-ca feature/contingency-groups
cd .worktrees/woodland-hills-ca
```

- [ ] **Step 2: Confirm baseline**

```powershell
python -c "from launchpad.lun_builder_data import seed_lun_builder_templates; from launchpad.contingency_groups_data import seed_contingency_groups; from launchpad.config import APP_VERSION; print(APP_VERSION); print([t['id'] for t in seed_lun_builder_templates()]); print([g['id'] for g in seed_contingency_groups()])"
```

Expected: `1.6.41`; five LUN template ids including `template-windsor-wi`; Contingency Groups ids `hartford-ct`, `houston-tx`, `windsor`.

- [ ] **Step 3: No commit** (setup only)

---

### Task 1: LUN Builder Woodland Hills template

**Files:**
- Modify: `launchpad/lun_builder_data.py`
- Test: `tests/test_lun_builder_data.py`
- Test: `tests/test_health_server_lun_builder.py`

**Interfaces:**
- Consumes: `_lun_batch`, `seed_lun_builder_templates`, `expand_lun_batch`, `normalize_build`
- Produces: sixth template dict `template-woodland-hills-ca`; `_woodland_hills_host(lpar_name: str) -> dict` (blank WWPNs)

- [ ] **Step 1: Update length / API set and add failing Woodland Hills LUN tests**

In `tests/test_lun_builder_data.py`, inside `test_hartford_template_identity`, change:

```python
assert len(templates) == 5
```

to:

```python
assert len(templates) == 6
```

Append:

```python
def _woodland_hills_template() -> dict:
    return next(
        t
        for t in seed_lun_builder_templates()
        if t["id"] == "template-woodland-hills-ca"
    )


def test_woodland_hills_template_identity_and_defaults():
    woo = _woodland_hills_template()
    assert woo["name"] == "Woodland Hills, CA (Template)"
    assert woo["location"] == "Woodland Hills, CA"
    assert woo["is_template"] is True
    assert woo["default_storage_profile"] == "flashsystem_5200"
    assert woo["default_pool_or_cpg"] == "WOO_Pool1"
    assert woo["default_card_hint"] == "Woodland Hills, CA"
    assert normalize_build(woo)["is_template"] is True
    assert "WWPNs are blank" in woo["notes"]


def test_woodland_hills_hosts_blank_wwpns():
    woo = _woodland_hills_template()
    hosts = woo["hosts"]
    assert len(hosts) == 12
    names = [h["lpar_name"] for h in hosts]
    assert names.count("AWD1_New_as400") == 4
    assert set(names) == {
        "AWD1_New_as400",
        "PEN-WODESX-VM01",
        "PEN-WODESX-VM02",
        "PEN-WODESX-VM03",
        "PEN-WODESX-VM04",
        "pwoovio01a",
        "pwoovio01b",
        "pwoovio02a",
        "pwoovio02b",
    }
    assert all(h.get("wwpn1") == "" and h.get("wwpn2") == "" for h in hosts)
    assert all(h.get("type") == "Generic" for h in hosts)


def test_woodland_hills_lun_batches_and_names():
    woo = _woodland_hills_template()
    luns = woo["luns"]
    # 1 AS400 + 1 ESX + 4 VIO root = 6
    assert len(luns) == 6
    assert all(lun.get("storage_profile") == "flashsystem_5200" for lun in luns)
    assert all(lun.get("pool_or_cpg") == "WOO_Pool1" for lun in luns)
    assert all(lun.get("card_hint") == "Woodland Hills, CA" for lun in luns)

    as400 = next(lun for lun in luns if lun["purpose"] == "AS400")
    assert as400["count"] == 6
    assert as400["size"] == "500GB"
    assert as400["shared"] is True
    assert as400["host_names"] == ["AWD1_New_as400"]
    assert as400["name_prefix"] == "AWD1"
    assert as400["cluster"] == ""

    esx = next(lun for lun in luns if lun["purpose"] == "ESX_DataStore")
    assert esx["count"] == 4
    assert esx["size"] == "4TB"
    assert esx["shared"] is True
    assert esx["host_names"] == [
        "PEN-WODESX-VM01",
        "PEN-WODESX-VM02",
        "PEN-WODESX-VM03",
        "PEN-WODESX-VM04",
    ]
    assert esx["name_prefix"] == "WOO"

    vio_roots = [
        lun
        for lun in luns
        if lun["purpose"] == "root" and lun["host_names"][0].startswith("pwoovio")
    ]
    assert len(vio_roots) == 4
    assert all(lun["count"] == 2 and lun["size"] == "100GB" for lun in vio_roots)
    assert all(lun["shared"] is False for lun in vio_roots)
    assert all(lun["name_prefix"] == "pwoo" for lun in vio_roots)
    assert all(lun["cluster"] == "vio" for lun in vio_roots)

    expanded = [
        name for lun in luns for name in (r["name"] for r in expand_lun_batch(lun))
    ]
    assert len(expanded) == 18
    assert len(expanded) == len(set(expanded))
    assert "AWD1_AS400_1" in expanded
    assert "AWD1_AS400_6" in expanded
    assert "WOO_ESX_DataStore_1" in expanded
    assert "WOO_ESX_DataStore_4" in expanded
    assert "pwoovio01a_root_1" in expanded
    assert "pwoovio02b_root_2" in expanded
    assert not any("Snap" in name for name in expanded)
```

In `tests/test_health_server_lun_builder.py`, extend the expected template id set to include `"template-woodland-hills-ca"`.

- [ ] **Step 2: Run tests RED**

```powershell
python -m pytest tests/test_lun_builder_data.py::test_woodland_hills_template_identity_and_defaults tests/test_lun_builder_data.py::test_hartford_template_identity -v
```

Expected: FAIL (missing template id / length 5 vs 6).

- [ ] **Step 3: Implement seed**

In `launchpad/lun_builder_data.py`, add helper after the Windsor host helper (near other `_*_host` helpers):

```python
def _woodland_hills_host(lpar_name: str) -> dict:
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

Inside `seed_lun_builder_templates()`, after the Windsor `win_luns` block and before `return [`, build Woodland Hills hosts/luns:

```python
    woo_hosts = [
        _woodland_hills_host("AWD1_New_as400"),
        _woodland_hills_host("AWD1_New_as400"),
        _woodland_hills_host("AWD1_New_as400"),
        _woodland_hills_host("AWD1_New_as400"),
        _woodland_hills_host("PEN-WODESX-VM01"),
        _woodland_hills_host("PEN-WODESX-VM02"),
        _woodland_hills_host("PEN-WODESX-VM03"),
        _woodland_hills_host("PEN-WODESX-VM04"),
        _woodland_hills_host("pwoovio01a"),
        _woodland_hills_host("pwoovio01b"),
        _woodland_hills_host("pwoovio02a"),
        _woodland_hills_host("pwoovio02b"),
    ]
    woo_kwargs = {
        "storage_profile": "flashsystem_5200",
        "pool_or_cpg": "WOO_Pool1",
        "card_hint": "Woodland Hills, CA",
    }
    woo_esx = [
        "PEN-WODESX-VM01",
        "PEN-WODESX-VM02",
        "PEN-WODESX-VM03",
        "PEN-WODESX-VM04",
    ]
    woo_luns: list[dict] = [
        _lun_batch(
            "AS400", 6, "500GB", True, ["AWD1_New_as400"], "",
            name_prefix="AWD1", **woo_kwargs,
        ),
        _lun_batch(
            "ESX_DataStore", 4, "4TB", True, woo_esx, "",
            name_prefix="WOO", **woo_kwargs,
        ),
    ]
    for vio in ("pwoovio01a", "pwoovio01b", "pwoovio02a", "pwoovio02b"):
        woo_luns.append(
            _lun_batch(
                "root", 2, "100GB", False, [vio], "vio",
                name_prefix="pwoo", **woo_kwargs,
            )
        )
```

Append to the returned list (after Windsor):

```python
        {
            "id": "template-woodland-hills-ca",
            "name": "Woodland Hills, CA (Template)",
            "location": "Woodland Hills, CA",
            "notes": (
                "Seeded from Woodland Hills FlashSystem 5200 inventory. "
                "WWPNs are blank — set Port Definitions / Pull from FC WWPN before create. "
                "Defaults use card hint Woodland Hills, CA, profile flashsystem_5200, "
                "pool WOO_Pool1."
            ),
            "is_template": True,
            "default_storage_profile": "flashsystem_5200",
            "default_pool_or_cpg": "WOO_Pool1",
            "default_card_hint": "Woodland Hills, CA",
            "hosts": woo_hosts,
            "luns": woo_luns,
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
git commit -m "Add Woodland Hills CA LUN Builder template."
```

---

### Task 2: Contingency Groups Woodland Hills seed

**Files:**
- Modify: `launchpad/contingency_groups_data.py`
- Test: `tests/test_contingency_groups_data.py`
- Test: `tests/test_health_server_contingency_groups.py`

**Interfaces:**
- Consumes: `_host`, `_volume`, `_maps_all_hosts`, `generate_snap_rows`, `seed_contingency_groups`
- Produces: fourth seeded group `woodland-hills-ca` (with `_snap` rows)

- [ ] **Step 1: Update three-site assertions and add failing Woodland Hills CG tests**

In `tests/test_contingency_groups_data.py`, rename/update `test_seeds_include_three_sites`:

```python
def test_seeds_include_four_sites():
    seeds = seed_contingency_groups()
    ids = {g["id"] for g in seeds}
    assert ids == {"hartford-ct", "houston-tx", "windsor", "woodland-hills-ca"}
    hartford = next(g for g in seeds if g["id"] == "hartford-ct")
    assert len(hartford["hosts"]) == 3
    hartford_sources = [v for v in hartford["volumes"] if v.get("role") != "snap"]
    assert len(hartford_sources) == 3
    assert len(hartford["volumes"]) == 6
    assert any(m["scsi_id"] == "0" for m in hartford["maps"])
    houston = next(g for g in seeds if g["id"] == "houston-tx")
    assert {h["name"] for h in houston["hosts"]} == {
        "pen-houesx-vm03",
        "pen-houesx-vm04",
    }
    assert len(houston["volumes"]) == 8
    houston_sources = [v for v in houston["volumes"] if v.get("role") != "snap"]
    assert len(houston_sources) == 4
    assert all(volume["capacity"] == "" for volume in houston["volumes"])
    assert all(volume["pool"] == "" for volume in houston["volumes"])
    windsor = next(g for g in seeds if g["id"] == "windsor")
    vm01 = next(h for h in windsor["hosts"] if h["name"] == "PEN_WINESX_VM01")
    assert "51402EC012CFD072" in vm01["wwpns"]
    vol1 = next(v for v in windsor["volumes"] if v["name"] == "WIN_ESX_DataStore_1")
    assert vol1["uid"].startswith("60050768128000A758")
```

Add:

```python
def test_woodland_hills_seed_inventory():
    woo = next(g for g in seed_contingency_groups() if g["id"] == "woodland-hills-ca")
    assert woo["name"] == "Woodland Hills, CA"
    assert woo["location"] == "Woodland Hills, CA"
    assert woo["storage_hint"] == "v5kwoo-g3c1"
    assert {h["name"] for h in woo["hosts"]} == {
        "AWD1_New_as400",
        "PEN-WODESX-VM01",
        "PEN-WODESX-VM02",
        "PEN-WODESX-VM03",
        "PEN-WODESX-VM04",
        "pwoovio01a",
        "pwoovio01b",
        "pwoovio02a",
        "pwoovio02b",
    }
    as400 = next(h for h in woo["hosts"] if h["name"] == "AWD1_New_as400")
    assert as400["port_count"] == 8
    assert as400["wwpns"] == []
    assert all(h["wwpns"] == [] for h in woo["hosts"])

    sources = [v for v in woo["volumes"] if v.get("role") != "snap"]
    assert len(sources) == 18
    assert len(woo["volumes"]) == 36
    assert all(v["pool"] == "WOO_Pool1" for v in sources)

    ds1 = next(v for v in sources if v["name"] == "WOO_ESX_DataStore_1")
    assert ds1["uid"] == "60050768128100A7D000000000000000"
    assert ds1["capacity"] == "4.00 TiB"
    ds4 = next(v for v in sources if v["name"] == "WOO_ESX_DataStore_4")
    assert ds4["uid"] == "60050768128100A7D000000000000017"
    root1 = next(v for v in sources if v["name"] == "pwoovio02b_root_1")
    assert root1["uid"] == "60050768128100A7D00000000000000F"
    assert root1["capacity"] == "100.00 GiB"
    as400_vol = next(v for v in sources if v["name"] == "AWD1_AS400_1")
    assert as400_vol["uid"] == ""
    assert as400_vol["capacity"] == "500.00 GiB"
    assert not any(v["name"].endswith("Snap1") for v in sources)
    assert any(v["name"] == "AWD1_AS400_1_snap" for v in woo["volumes"])

    source_maps = [m for m in woo["maps"] if m.get("role") != "snap"]
    assert len(source_maps) == 30
    assert {
        (m["volume"], m["host"], m["scsi_id"])
        for m in source_maps
        if m["volume"] == "WOO_ESX_DataStore_1"
    } == {
        ("WOO_ESX_DataStore_1", "PEN-WODESX-VM01", "0"),
        ("WOO_ESX_DataStore_1", "PEN-WODESX-VM02", "0"),
        ("WOO_ESX_DataStore_1", "PEN-WODESX-VM03", "0"),
        ("WOO_ESX_DataStore_1", "PEN-WODESX-VM04", "0"),
    }
    assert {
        (m["volume"], m["host"], m["scsi_id"])
        for m in source_maps
        if m["volume"].startswith("AWD1_AS400_")
    } == {
        (f"AWD1_AS400_{i}", "AWD1_New_as400", str(i - 1)) for i in range(1, 7)
    }
    assert {
        (m["volume"], m["host"], m["scsi_id"])
        for m in source_maps
        if m["volume"].startswith("pwoovio02b_root_")
    } == {
        ("pwoovio02b_root_1", "pwoovio02b", "0"),
        ("pwoovio02b_root_2", "pwoovio02b", "1"),
    }
```

In `tests/test_health_server_contingency_groups.py`, extend the expected id set:

```python
    assert {group["id"] for group in groups} == {
        "hartford-ct",
        "houston-tx",
        "windsor",
        "woodland-hills-ca",
    }
```

Also update `test_seeds_include_snap_rows` if it should mention Woodland Hills (optional — existing Hartford/Houston checks remain valid).

- [ ] **Step 2: Run tests RED**

```powershell
python -m pytest tests/test_contingency_groups_data.py::test_seeds_include_four_sites tests/test_contingency_groups_data.py::test_woodland_hills_seed_inventory -v
```

Expected: FAIL (missing `woodland-hills-ca` / renamed test not found until file saved).

- [ ] **Step 3: Implement `_woodland_hills_ca` and seed entry**

In `launchpad/contingency_groups_data.py`, add before `seed_contingency_groups`:

```python
def _woodland_hills_ca() -> dict[str, Any]:
    esx_hosts = [
        "PEN-WODESX-VM01",
        "PEN-WODESX-VM02",
        "PEN-WODESX-VM03",
        "PEN-WODESX-VM04",
    ]
    vio_hosts = ["pwoovio01a", "pwoovio01b", "pwoovio02a", "pwoovio02b"]
    hosts = [
        _host("AWD1_New_as400", port_count=8, wwpns=[]),
        *[_host(name, port_count=2, wwpns=[]) for name in esx_hosts],
        *[_host(name, port_count=2, wwpns=[]) for name in vio_hosts],
    ]
    esx_uids = {
        1: "60050768128100A7D000000000000000",
        2: "60050768128100A7D000000000000001",
        3: "60050768128100A7D000000000000002",
        4: "60050768128100A7D000000000000017",
    }
    volumes: list[dict[str, Any]] = [
        _volume(f"AWD1_AS400_{i}", pool="WOO_Pool1", capacity="500.00 GiB")
        for i in range(1, 7)
    ]
    volumes.extend(
        _volume(
            f"WOO_ESX_DataStore_{i}",
            pool="WOO_Pool1",
            capacity="4.00 TiB",
            uid=esx_uids[i],
        )
        for i in range(1, 5)
    )
    for vio in vio_hosts:
        for n in (1, 2):
            uid = ""
            if vio == "pwoovio02b" and n == 1:
                uid = "60050768128100A7D00000000000000F"
            elif vio == "pwoovio02b" and n == 2:
                uid = "60050768128100A7D000000000000010"
            volumes.append(
                _volume(
                    f"{vio}_root_{n}",
                    pool="WOO_Pool1",
                    capacity="100.00 GiB",
                    uid=uid,
                )
            )
    maps: list[dict[str, str]] = []
    for i in range(1, 7):
        maps.extend(
            _maps_all_hosts(f"AWD1_AS400_{i}", ["AWD1_New_as400"], str(i - 1))
        )
    for i in range(1, 5):
        maps.extend(
            _maps_all_hosts(f"WOO_ESX_DataStore_{i}", esx_hosts, str(i - 1))
        )
    for vio in vio_hosts:
        for n in (1, 2):
            maps.extend(
                _maps_all_hosts(f"{vio}_root_{n}", [vio], str(n - 1))
            )
    return {
        "id": "woodland-hills-ca",
        "name": "Woodland Hills, CA",
        "location": "Woodland Hills, CA",
        "storage_hint": "v5kwoo-g3c1",
        "notes": "",
        "updated_at": _SEED_UPDATED_AT,
        "hosts": hosts,
        "volumes": volumes,
        "maps": maps,
    }
```

Update `seed_contingency_groups`:

```python
def seed_contingency_groups() -> list[dict]:
    return [
        generate_snap_rows(_hartford_ct()),
        generate_snap_rows(_houston_tx()),
        generate_snap_rows(_windsor()),
        generate_snap_rows(_woodland_hills_ca()),
    ]
```

- [ ] **Step 4: Run tests GREEN**

```powershell
python -m pytest tests/test_contingency_groups_data.py tests/test_health_server_contingency_groups.py tests/test_contingency_groups_export.py -v
```

Expected: PASS (export tests iterate all seeds and should remain valid).

- [ ] **Step 5: Commit**

```powershell
git add launchpad/contingency_groups_data.py tests/test_contingency_groups_data.py tests/test_health_server_contingency_groups.py
git commit -m "Add Woodland Hills CA Contingency Groups seed."
```

---

### Task 3: Version bump and regression

**Files:**
- Modify: `launchpad/config.py`

**Interfaces:**
- Consumes: Task 1 + Task 2 seeds
- Produces: `APP_VERSION = "1.6.42"`

- [ ] **Step 1: Bump version**

```python
APP_VERSION = "1.6.42"
```

- [ ] **Step 2: Full suite**

```powershell
python -m pytest tests
```

Expected: all PASS.

- [ ] **Step 3: Commit**

```powershell
git add launchpad/config.py
git commit -m "Bump version to 1.6.42 for Woodland Hills CA."
```

---

## Spec coverage checklist

| Requirement | Task |
|-------------|------|
| Branch from contingency-groups @ 1.6.41 | Task 0 |
| LUN `template-woodland-hills-ca` identity + notes + defaults | Task 1 |
| 12 blank-WWPN host rows (4× AS400) | Task 1 |
| 6 LUN batches; expand to `AWD1_AS400_*`, `WOO_ESX_*`, `pwoovio*_root_*` | Task 1 |
| No `*_SnapN` LUN batches; six templates in API | Task 1 |
| CG `woodland-hills-ca` full site + `v5kwoo-g3c1` | Task 2 |
| Blank CG WWPNs; known ESX/VIO UIDs; 18 sources + `_snap` | Task 2 |
| Maps AS400 / shared ESX / VIO roots | Task 2 |
| Version `1.6.42` | Task 3 |
