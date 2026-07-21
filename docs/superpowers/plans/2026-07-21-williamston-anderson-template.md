# Williamston (Anderson) LUN Builder + Contingency Groups Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Williamston (Anderson) LUN Builder template (full site, Active WWPNs, FlashSystem 7200 / `G3_AND_Pool`) and a matching Contingency Groups seed (`v7kand-g3v1`, LaunchPad `_snap` rows).

**Architecture:** Independent seeds — extend `seed_lun_builder_templates()` with `template-williamston-anderson` (Windsor-style `_anderson_host(name, wwpn1, wwpn2)` + `_lun_batch`), and extend `seed_contingency_groups()` with `_williamston_anderson()` wrapped in `generate_snap_rows()`. Keep all prior templates/groups unchanged. Transcribe exact hosts/WWPNs/volumes/UIDs from Cursor project `assets/` screenshots (re-read images; do not trust truncated OCR). Bump `APP_VERSION` last.

**Tech Stack:** Python seed data in `launchpad/lun_builder_data.py` and `launchpad/contingency_groups_data.py`, pytest.

**Spec:** `docs/superpowers/specs/2026-07-21-williamston-anderson-template-design.md`

## Global Constraints

- **Base branch:** `feature/contingency-groups` tip (includes design commit; `APP_VERSION=1.6.41`; five LUN templates; three Contingency Groups). Do not re-implement prior sites.
- LUN template id: `template-williamston-anderson`; name `Williamston (Anderson) (Template)`; location `Williamston (Anderson)`; `is_template: True`
- LUN defaults: `default_storage_profile=flashsystem_7200`, `default_pool_or_cpg=G3_AND_Pool`, `default_card_hint=Williamston (Anderson)`
- Every LUN row: same profile/pool/card_hint
- Hosts: full Hosts_1–3 catalog including Offline; `type=Generic`; Active Port Definition WWPNs with multi-row packing; blank when Offline/missing
- Pool OCR: always `G3_AND_Pool` (never seed `GS_AND_Pool`)
- Contingency Groups id: `williamston-anderson`; name/location `Williamston (Anderson)`; `storage_hint=v7kand-g3v1`
- Contingency Groups: same unique hosts; source volumes + maps from inventory; wrap with `generate_snap_rows()`
- Do not seed IBM CG / `*_Snap*` / `*_snap` array targets as sources; do not modify prior seeds
- **Assets root:** `C:\Users\BrianColley\.cursor\projects\c-Users-BrianColley-LaunchPad\assets\` (Hosts_*, Volume_*, *Ports*, Pools*, CG_*)
- Bump `APP_VERSION` to `1.6.42` in the final task (reconcile with parallel PRs at merge)
- Commit at each task’s commit step

---

## File map

| File | Responsibility |
|------|----------------|
| `launchpad/lun_builder_data.py` | `_anderson_host`, Williamston (Anderson) LUN template |
| `launchpad/contingency_groups_data.py` | `_williamston_anderson`, seed list entry |
| `tests/test_lun_builder_data.py` | Anderson LUN contracts; bump `len==5` → `6` |
| `tests/test_health_server_lun_builder.py` | API template id set includes Anderson |
| `tests/test_contingency_groups_data.py` | Four-site seed contracts + Anderson details |
| `tests/test_health_server_contingency_groups.py` | API seed id set includes Anderson |
| `launchpad/config.py` | `1.6.42` |

## Naming strategy (LUN expand)

- Prefer `_lun_batch` patterns that expand to live-like names (`{host}_{purpose}_{N}`, shared prefix+purpose, etc.).
- For irregular live names (`ADC-Data01`, `pla-wanoemcr01_02_5GB1`, `Andesx-DS01`), use **count=1** batches where `expand_lun_batch` yields the exact live name (set `purpose` to the live name and choose `name_prefix`/`shared`/`host_names` so `_volume_name_base` does not rewrite it — verify with a unit assertion).
- Contingency Groups always use **exact** live volume names and capacities.

## Required unique host names

```python
ANDERSON_REQUIRED_HOSTS = frozenset({
    "AAN1", "AAN1C", "FC_AAN1",
    "BIB_ADC_VM01", "BIB_ADC_VM02",
    "pen_andesx_vm03", "pen_andesx_vm04",
    "pla-wanoemcr01", "pla-wanoemcr02",
    "pandvio01a", "pandvio01b", "pandvio02a", "pandvio02b",
    "pandvio03a", "pandvio03b", "pandvio04a", "pandvio04b",
    "pandvio05a", "pandvio05b", "pandvio06a", "pandvio06b",
    "pandvio07a", "pandvio07b", "pandvio08a", "pandvio08b",
    "pandvio09a", "pandvio09b", "pandvio10a", "pandvio10b",
    "pandap01", "pandap02",
    "pandbt1", "pandbt2", "pandbt3", "pandbt4", "pandbtdg1",
    "panddb01", "panddb02",
    "pandmfs1", "pandmfs2", "pandmfs3", "pandmfs4", "pandmfs10", "pandmfsdg1",
    "pandnim01",
    "pandps1", "pandps2", "pandps3", "pandps4", "pandpspdg1",
    "pandpspa1", "pandpspa2",
    "dandmfs1",
    "tandbt1", "tandbt20",
    "tandmfs1", "tandmfs2", "tandmfs20",
    "tandsps1", "tandsps2",
    "tandeps1", "tandeps2", "tandeps20", "tandeps21",
    "tconbt20", "tconmfs20", "tconsps20", "tconsps21",
    "TLA_WANMFS01", "TLA_WANMFS02",
})
```

If Hosts screenshots prove `tandeps*` is OCR for `tandsps*` (or the reverse), keep **only** the names that appear on the Hosts list **and** have Mapped Volumes evidence; update `ANDERSON_REQUIRED_HOSTS` in tests to match. Do not invent hosts.

---

### Task 0: Branch / worktree from contingency-groups

**Files:** none (git only)

**Interfaces:**
- Consumes: `feature/contingency-groups` at `1.6.41` with five LUN templates and three Contingency Groups
- Produces: working branch `feature/williamston-anderson`

- [ ] **Step 1: Create branch from contingency-groups tip**

```powershell
git fetch origin
git -C "C:\Users\BrianColley\LaunchPad" worktree add .worktrees/williamston-anderson -b feature/williamston-anderson feature/contingency-groups
cd C:\Users\BrianColley\LaunchPad\.worktrees\williamston-anderson
```

- [ ] **Step 2: Confirm baseline**

```powershell
python -c "from launchpad.lun_builder_data import seed_lun_builder_templates; from launchpad.contingency_groups_data import seed_contingency_groups; from launchpad.config import APP_VERSION; print(APP_VERSION); print([t['id'] for t in seed_lun_builder_templates()]); print([g['id'] for g in seed_contingency_groups()])"
```

Expected: `1.6.41`; five LUN ids including `template-windsor-wi`; Contingency Groups ids `hartford-ct`, `houston-tx`, `windsor`.

- [ ] **Step 3: No commit** (setup only)

---

### Task 1: LUN template identity + full host catalog (blank WWPNs)

**Files:**
- Modify: `launchpad/lun_builder_data.py`
- Test: `tests/test_lun_builder_data.py`
- Test: `tests/test_health_server_lun_builder.py`

**Interfaces:**
- Consumes: `_lun_batch`, `seed_lun_builder_templates`, `normalize_build`
- Produces: sixth template `template-williamston-anderson`; `_anderson_host(lpar_name: str, wwpn1: str = "", wwpn2: str = "") -> dict`; at least one host row per required unique name (blank WWPNs); temporary minimal LUN list allowed until Task 3 (must be non-empty — seed one placeholder batch that Task 3 replaces)

- [ ] **Step 1: Write failing tests**

In `tests/test_lun_builder_data.py`, change `assert len(templates) == 5` to `assert len(templates) == 6`.

In `tests/test_health_server_lun_builder.py`, add `"template-williamston-anderson"` to the expected `template_ids` set.

Append:

```python
ANDERSON_REQUIRED_HOSTS = frozenset({
    "AAN1", "AAN1C", "FC_AAN1",
    "BIB_ADC_VM01", "BIB_ADC_VM02",
    "pen_andesx_vm03", "pen_andesx_vm04",
    "pla-wanoemcr01", "pla-wanoemcr02",
    "pandvio01a", "pandvio01b", "pandvio02a", "pandvio02b",
    "pandvio03a", "pandvio03b", "pandvio04a", "pandvio04b",
    "pandvio05a", "pandvio05b", "pandvio06a", "pandvio06b",
    "pandvio07a", "pandvio07b", "pandvio08a", "pandvio08b",
    "pandvio09a", "pandvio09b", "pandvio10a", "pandvio10b",
    "pandap01", "pandap02",
    "pandbt1", "pandbt2", "pandbt3", "pandbt4", "pandbtdg1",
    "panddb01", "panddb02",
    "pandmfs1", "pandmfs2", "pandmfs3", "pandmfs4", "pandmfs10", "pandmfsdg1",
    "pandnim01",
    "pandps1", "pandps2", "pandps3", "pandps4", "pandpspdg1",
    "pandpspa1", "pandpspa2",
    "dandmfs1",
    "tandbt1", "tandbt20",
    "tandmfs1", "tandmfs2", "tandmfs20",
    "tandsps1", "tandsps2",
    "tandeps1", "tandeps2", "tandeps20", "tandeps21",
    "tconbt20", "tconmfs20", "tconsps20", "tconsps21",
    "TLA_WANMFS01", "TLA_WANMFS02",
})


def _anderson_template() -> dict:
    return next(
        t
        for t in seed_lun_builder_templates()
        if t["id"] == "template-williamston-anderson"
    )


def test_anderson_template_identity_and_defaults():
    and_ = _anderson_template()
    assert and_["name"] == "Williamston (Anderson) (Template)"
    assert and_["location"] == "Williamston (Anderson)"
    assert and_["is_template"] is True
    assert and_["default_storage_profile"] == "flashsystem_7200"
    assert and_["default_pool_or_cpg"] == "G3_AND_Pool"
    assert and_["default_card_hint"] == "Williamston (Anderson)"
    assert normalize_build(and_)["is_template"] is True
    assert "flashsystem_7200" in and_["notes"]
    assert "G3_AND_Pool" in and_["notes"]


def test_anderson_hosts_cover_required_catalog():
    and_ = _anderson_template()
    names = {h["lpar_name"] for h in and_["hosts"]}
    assert names == ANDERSON_REQUIRED_HOSTS
    assert all(h.get("type") == "Generic" for h in and_["hosts"])
    # Task 1 leaves WWPNs blank; Task 2 fills Active ports
    assert all(h.get("wwpn1") == "" and h.get("wwpn2") == "" for h in and_["hosts"])
```

- [ ] **Step 2: Run tests RED**

```powershell
python -m pytest tests/test_lun_builder_data.py::test_anderson_template_identity_and_defaults tests/test_lun_builder_data.py::test_hartford_template_identity -v
```

Expected: FAIL (missing template / length 5 vs 6).

- [ ] **Step 3: Implement host helper + template shell**

Add after `_windsor_host`:

```python
def _anderson_host(lpar_name: str, wwpn1: str = "", wwpn2: str = "") -> dict:
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

Inside `seed_lun_builder_templates()`, before `return [`, build Anderson hosts (one row per required name, blank WWPNs) and a temporary single LUN batch (replaced in Task 3):

```python
    and_kwargs = {
        "storage_profile": "flashsystem_7200",
        "pool_or_cpg": "G3_AND_Pool",
        "card_hint": "Williamston (Anderson)",
    }
    and_host_names = sorted(ANDERSON_REQUIRED_HOSTS)  # or inline the frozenset members
    and_hosts = [_anderson_host(name) for name in and_host_names]
    and_luns: list[dict] = [
        _lun_batch(
            "placeholder", 1, "1GB", False, ["AAN1C"], "",
            name_prefix="AAN1C", **and_kwargs,
        ),
    ]
```

Append template dict to the returned list:

```python
        {
            "id": "template-williamston-anderson",
            "name": "Williamston (Anderson) (Template)",
            "location": "Williamston (Anderson)",
            "notes": (
                "Seeded from Anderson FlashSystem 7200 inventory (v7kand-g3v1). "
                "Active Port Definition WWPNs filled when known; Offline/missing blank. "
                "Defaults use card hint Williamston (Anderson), profile flashsystem_7200, "
                "pool G3_AND_Pool."
            ),
            "is_template": True,
            "default_storage_profile": "flashsystem_7200",
            "default_pool_or_cpg": "G3_AND_Pool",
            "default_card_hint": "Williamston (Anderson)",
            "hosts": and_hosts,
            "luns": and_luns,
        },
```

Do **not** import the test frozenset into production code — duplicate the host name list in the seed.

- [ ] **Step 4: Run tests GREEN**

```powershell
python -m pytest tests/test_lun_builder_data.py tests/test_health_server_lun_builder.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add launchpad/lun_builder_data.py tests/test_lun_builder_data.py tests/test_health_server_lun_builder.py
git commit -m "Add Williamston Anderson LUN template host catalog."
```

---

### Task 2: Fill Active WWPNs (multi-row)

**Files:**
- Modify: `launchpad/lun_builder_data.py`
- Test: `tests/test_lun_builder_data.py`

**Interfaces:**
- Consumes: `_anderson_host`, Port Definitions screenshots under assets (`*_Ports*`, Host Port Definitions)
- Produces: host rows with Active WWPNs; multiple rows when >2 Active ports; Offline/missing remain blank

- [ ] **Step 1: Replace blank-WWPN assertion with packing contracts**

Remove the “all WWPNs blank” assertion from `test_anderson_hosts_cover_required_catalog`. Add:

```python
def test_anderson_wwpn_multi_row_packing():
    and_ = _anderson_template()
    hosts = and_["hosts"]
    # Every required name still present
    assert {h["lpar_name"] for h in hosts} == ANDERSON_REQUIRED_HOSTS
    # Offline / no-port hosts stay blank (at least these)
    for name in ("FC_AAN1", "BIB_ADC_VM02", "pandvio05a", "pandvio05b", "pandpspa1", "pandpspa2"):
        rows = [h for h in hosts if h["lpar_name"] == name]
        assert rows, name
        assert all(h.get("wwpn1") == "" and h.get("wwpn2") == "" for h in rows)
    # At least one host has a filled Active WWPN (transcribed)
    assert any(h.get("wwpn1") for h in hosts)
    # Multi-row: any host with >2 Active ports must appear more than once
    from collections import Counter
    counts = Counter(h["lpar_name"] for h in hosts)
    assert any(n > 1 for n in counts.values()) or any(
        h.get("wwpn1") and h.get("wwpn2") for h in hosts
    )
```

After transcription, tighten this test with concrete WWPN literals for at least two hosts that have Port Definitions screenshots (copy exact hex from images into the assert).

- [ ] **Step 2: Run RED** (fails until WWPNs filled)

```powershell
python -m pytest tests/test_lun_builder_data.py::test_anderson_wwpn_multi_row_packing -v
```

- [ ] **Step 3: Transcribe Port Definitions**

Re-read each Host → Port Definitions asset. For every Active initiator WWPN, pack into `wwpn1`/`wwpn2` pairs via additional `_anderson_host(name, wwpn1, wwpn2)` rows (Windsor pattern). Skip Offline ports and array canister FC ports.

Replace `and_hosts = [_anderson_host(name) for name in ...]` with an explicit list that includes multi-rows where needed.

- [ ] **Step 4: Run GREEN**

```powershell
python -m pytest tests/test_lun_builder_data.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add launchpad/lun_builder_data.py tests/test_lun_builder_data.py
git commit -m "Seed Anderson Active Port Definition WWPNs."
```

---

### Task 3: LUN batches — AS400, ESX, OEM, sample AIX

**Files:**
- Modify: `launchpad/lun_builder_data.py`
- Test: `tests/test_lun_builder_data.py`

**Interfaces:**
- Consumes: `_lun_batch`, `expand_lun_batch`, Mapped Volumes screenshots for AAN1/AAN1C/FC_AAN1, `pen_andesx_*`, `pla-wanoemcr*`, `pandap01`
- Produces: replace placeholder `and_luns` with real batches for these families; all rows use `and_kwargs`

- [ ] **Step 1: Add failing family tests**

```python
def test_anderson_core_lun_families():
    and_ = _anderson_template()
    luns = and_["luns"]
    assert all(lun.get("storage_profile") == "flashsystem_7200" for lun in luns)
    assert all(lun.get("pool_or_cpg") == "G3_AND_Pool" for lun in luns)
    assert all(lun.get("card_hint") == "Williamston (Anderson)" for lun in luns)
    assert not any(lun.get("purpose") == "placeholder" for lun in luns)

    expanded = [
        r["name"] for lun in luns for r in expand_lun_batch(lun)
    ]
    assert len(expanded) == len(set(expanded))
    assert not any("Snap" in n or n.lower().endswith("_snap") for n in expanded)

    # ESX shared datastores (exact live names)
    for name in (
        "ADC-Data01", "ADC-Data02", "ADC-Data03",
        "Andesx-DS01", "Andesx-DS02", "Andesx-DS03",
        "RHEL-Networker01",
    ):
        assert name in expanded
        batch = next(lun for lun in luns if expand_lun_batch(lun)[0]["name"] == name)
        assert set(batch["host_names"]) == {"pen_andesx_vm03", "pen_andesx_vm04"}
        assert batch["shared"] is True

    # pandap01 from Volume screenshot: 4x70GiB + 1x50GiB
    pandap_names = [n for n in expanded if n.startswith("pandap01_")]
    assert len(pandap_names) >= 5
```

Add size assertions matching screenshots after transcription (e.g. `ADC-Data01` → `1023GB` or `1TB` per existing size grammar in `_lun_batch` / UI — match the size strings other templates use: `100GB`, `4TB`, etc.).

- [ ] **Step 2: Run RED**

```powershell
python -m pytest tests/test_lun_builder_data.py::test_anderson_core_lun_families -v
```

- [ ] **Step 3: Implement core batches**

Remove the placeholder batch. Re-read Volume / mapping screenshots and encode:

| Family | Guidance |
|--------|----------|
| AAN1C | 4 volumes ~125 GiB — prefer expandable or exact names from AAN1C mapping screenshots |
| AAN1 | ~28× ~120 GiB |
| FC_AAN1 | ~28× ~120 GiB (include despite Offline host) |
| ESX | Exact names `ADC-Data01`…`03`, `Andesx-DS01`…`03`, `RHEL-Networker01` with capacities from screenshots; shared to both `pen_andesx_vm03` and `pen_andesx_vm04` |
| OEM | All `pla-wanoemcr01_02_*` size series shared to both OEM hosts (61 volumes on pla-wanoemcr02 screenshot) |
| pandap01 | `pandap01_0`…`3` @ 70 GiB + `pandap01_4` @ 50 GiB |

Example irregular-name batch (verify expand before committing):

```python
    esx_hosts = ["pen_andesx_vm03", "pen_andesx_vm04"]
    and_luns.append(
        _lun_batch(
            "ADC-Data01", 1, "1023GB", True, esx_hosts, "",
            name_prefix="", **and_kwargs,
        )
    )
```

If `expand_lun_batch` rewrites the name, adjust `name_prefix`/`shared` until the expanded name equals `ADC-Data01`, or split into purpose-only naming that matches.

- [ ] **Step 4: Run GREEN**

```powershell
python -m pytest tests/test_lun_builder_data.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add launchpad/lun_builder_data.py tests/test_lun_builder_data.py
git commit -m "Add Anderson AS400 ESX OEM core LUN batches."
```

---

### Task 4: LUN batches — remaining pand* / tand* / VIO / TLA

**Files:**
- Modify: `launchpad/lun_builder_data.py`
- Test: `tests/test_lun_builder_data.py`

**Interfaces:**
- Consumes: remaining `Volume_*` screenshots for hosts in `ANDERSON_REQUIRED_HOSTS` not finished in Task 3
- Produces: full-inventory LUN batches (no FlashCopy targets)

- [ ] **Step 1: Add coverage test**

```python
def test_anderson_lun_inventory_covers_mapped_hosts():
    and_ = _anderson_template()
    luns = and_["luns"]
    hosts_with_luns = {h for lun in luns for h in lun.get("host_names") or []}
    # Offline hosts may still appear on batches when mapped (FC_AAN1, BIB_ADC_VM01)
    for required in (
        "AAN1", "AAN1C", "FC_AAN1",
        "pen_andesx_vm03", "pla-wanoemcr01",
        "pandap01", "pandvio08b",
        "tandbt1", "tandbt20", "tandmfs1", "tandmfs20",
        "tandsps1", "TLA_WANMFS01",
    ):
        assert required in hosts_with_luns or required in {
            h["lpar_name"] for h in and_["hosts"]
        }
    # Full inventory: expect a large expanded set (site has hundreds of volumes)
    expanded = [r["name"] for lun in luns for r in expand_lun_batch(lun)]
    assert len(expanded) >= 200
    assert len(expanded) == len(set(expanded))
    assert all(lun.get("pool_or_cpg") == "G3_AND_Pool" for lun in luns)
```

Tune the `>= 200` floor downward only if full screenshot inventory is genuinely smaller after excluding snaps — document the final count in the commit message.

- [ ] **Step 2: Run RED**

```powershell
python -m pytest tests/test_lun_builder_data.py::test_anderson_lun_inventory_covers_mapped_hosts -v
```

- [ ] **Step 3: Transcribe remaining volumes**

For each remaining host with Mapped Volumes screenshots, add `_lun_batch` groups by size/name pattern. Include clone **source** volumes that are ordinary pool volumes (`tandbt_clone_root*`, etc.). Exclude FlashCopy target-only names (`*_Snap*`, CG snap destinations).

Reconcile `tandeps*` vs `tandsps*` against Hosts + Mapped Volumes before seeding.

- [ ] **Step 4: Run GREEN**

```powershell
python -m pytest tests/test_lun_builder_data.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add launchpad/lun_builder_data.py tests/test_lun_builder_data.py
git commit -m "Complete Anderson full-inventory LUN batches."
```

---

### Task 5: Contingency Groups Williamston (Anderson) seed

**Files:**
- Modify: `launchpad/contingency_groups_data.py`
- Test: `tests/test_contingency_groups_data.py`
- Test: `tests/test_health_server_contingency_groups.py`

**Interfaces:**
- Consumes: `_host`, `_volume`, `_maps_all_hosts`, `generate_snap_rows`, `seed_contingency_groups`; LUN template inventory as the volume/host source of truth
- Produces: fourth seeded group `williamston-anderson` with `_snap` rows

- [ ] **Step 1: Update site-count assertions and add failing Anderson CG tests**

In `tests/test_contingency_groups_data.py`, rename/update `test_seeds_include_three_sites` to four sites:

```python
def test_seeds_include_four_sites():
    seeds = seed_contingency_groups()
    ids = {g["id"] for g in seeds}
    assert ids == {"hartford-ct", "houston-tx", "windsor", "williamston-anderson"}
    # keep existing hartford/houston/windsor assertions unchanged below...
```

(Preserve the existing hartford/houston/windsor body from the current three-site test.)

Append:

```python
def test_williamston_anderson_contingency_group():
    and_ = next(g for g in seed_contingency_groups() if g["id"] == "williamston-anderson")
    assert and_["name"] == "Williamston (Anderson)"
    assert and_["location"] == "Williamston (Anderson)"
    assert and_["storage_hint"] == "v7kand-g3v1"
    host_names = {h["name"] for h in and_["hosts"]}
    assert host_names == ANDERSON_REQUIRED_HOSTS  # import/share frozenset from lun tests or duplicate
    sources = [v for v in and_["volumes"] if v.get("role") != "snap"]
    snaps = [v for v in and_["volumes"] if v.get("role") == "snap"]
    assert len(sources) >= 200
    assert len(snaps) == len(sources)
    assert all(v.get("pool") == "G3_AND_Pool" for v in sources)
    assert all(s["name"].endswith("_snap") for s in snaps)
    # Sample known UID from ESX screenshot
    adc = next(v for v in sources if v["name"] == "ADC-Data01")
    assert adc["uid"].startswith("60050764008101A458")
    assert adc["capacity"]  # non-empty, e.g. "1,023.00 GiB" or normalized form used by _volume
    # Shared ESX maps
    adc_maps = [m for m in and_["maps"] if m["volume"] == "ADC-Data01" and m.get("role") != "snap"]
    assert {m["host"] for m in adc_maps} == {"pen_andesx_vm03", "pen_andesx_vm04"}
```

In `tests/test_health_server_contingency_groups.py`, extend the expected seed id set to include `"williamston-anderson"`.

- [ ] **Step 2: Run RED**

```powershell
python -m pytest tests/test_contingency_groups_data.py::test_williamston_anderson_contingency_group tests/test_contingency_groups_data.py::test_seeds_include_four_sites -v
```

Expected: FAIL (missing seed).

- [ ] **Step 3: Implement `_williamston_anderson()`**

Mirror Woodland Hills / Windsor seed shape:

```python
def _williamston_anderson() -> dict[str, Any]:
    # hosts: one _host per unique name; port_count from Active WWPN count (2 or 8 typical);
    # wwpns list flattened from the same Port Definitions used in LUN multi-row packing;
    # status Online by default; Offline hosts may use status="Offline" if the model supports it —
    # otherwise leave Online and rely on blank wwpns (match existing seed conventions).
    hosts = [
        _host("AAN1", port_count=8, wwpns=[...]),
        # ... all ANDERSON_REQUIRED_HOSTS ...
    ]
    volumes = [
        _volume("ADC-Data01", pool="G3_AND_Pool", capacity="1023.00 GiB",
                uid="60050764008101A45800000000000B90"),
        # ... every source volume from LUN inventory / screenshots ...
    ]
    maps: list[dict[str, str]] = []
    # Mirror live mappings; shared volumes use _maps_all_hosts
    maps.extend(_maps_all_hosts("ADC-Data01", ["pen_andesx_vm03", "pen_andesx_vm04"], "0"))
    # ...
    return {
        "id": "williamston-anderson",
        "name": "Williamston (Anderson)",
        "location": "Williamston (Anderson)",
        "storage_hint": "v7kand-g3v1",
        "notes": "",
        "updated_at": _SEED_UPDATED_AT,
        "hosts": hosts,
        "volumes": volumes,
        "maps": maps,
    }
```

In `seed_contingency_groups()`, append `generate_snap_rows(_williamston_anderson())`.

UID/capacity: seed when readable from screenshots; otherwise `uid=""` and still set capacity/pool.

- [ ] **Step 4: Run GREEN**

```powershell
python -m pytest tests/test_contingency_groups_data.py tests/test_health_server_contingency_groups.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add launchpad/contingency_groups_data.py tests/test_contingency_groups_data.py tests/test_health_server_contingency_groups.py
git commit -m "Add Williamston Anderson Contingency Groups seed."
```

---

### Task 6: Version bump + smoke

**Files:**
- Modify: `launchpad/config.py`
- Test: any test that pins `APP_VERSION` (update if present)

**Interfaces:**
- Consumes: complete seeds from Tasks 1–5
- Produces: `APP_VERSION == "1.6.42"`

- [ ] **Step 1: Bump version**

In `launchpad/config.py`:

```python
APP_VERSION = "1.6.42"
```

- [ ] **Step 2: Smoke tests**

```powershell
python -m pytest tests/test_lun_builder_data.py tests/test_health_server_lun_builder.py tests/test_contingency_groups_data.py tests/test_health_server_contingency_groups.py -v
python -c "from launchpad.config import APP_VERSION; from launchpad.lun_builder_data import seed_lun_builder_templates; from launchpad.contingency_groups_data import seed_contingency_groups; assert APP_VERSION=='1.6.42'; assert any(t['id']=='template-williamston-anderson' for t in seed_lun_builder_templates()); assert any(g['id']=='williamston-anderson' for g in seed_contingency_groups()); print('ok')"
```

Expected: PASS / `ok`.

- [ ] **Step 3: Commit**

```powershell
git add launchpad/config.py
git commit -m "Bump version to 1.6.42 for Williamston Anderson template."
```

---

## Spec coverage checklist

| Spec requirement | Task |
|------------------|------|
| LUN template id/name/location/defaults `7200` / `G3_AND_Pool` / card hint | 1 |
| Full host catalog including Offline | 1 |
| Active WWPN multi-row packing | 2 |
| Full LUN inventory; no snap sources | 3, 4 |
| Shared ESX/OEM mapping | 3 |
| Contingency Groups id / `v7kand-g3v1` / snaps | 5 |
| API template + seed id visibility | 1, 5 |
| Version bump | 6 |
| No prior-site edits / no IBM CG seed | all (constraints) |
