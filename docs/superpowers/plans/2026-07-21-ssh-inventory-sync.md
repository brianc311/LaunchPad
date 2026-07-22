# SSH Inventory Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Sync Inventory so a LUN Builder build and Contingency Groups site are replaced from live FlashSystem SSH (`lshost`, WWPNs, `lsvdisk`, `lshostvdiskmap`), matching the array without screenshots.

**Architecture:** Pure mappers in `launchpad/inventory_sync.py` turn parsed CLI tables into LUN hosts/luns + a CG group; `HealthServer.sync_inventory` runs a live SSH suite, replaces the build, upserts CG by card hint with `generate_snap_rows()`, and returns counts/warnings. LUN Builder UI gains a Sync Inventory button calling `POST /api/lun-builds/sync-inventory`.

**Tech Stack:** Existing Health Card SSH (`run_remote_ssh_command`), `flashsystem_fc` parsers, Contingency Groups upsert, pytest.

**Spec:** `docs/superpowers/specs/2026-07-21-ssh-inventory-sync-design.md`

## Global Constraints

- **Base branch:** `feature/contingency-groups` tip (includes sync design commit). Implement on a new branch/worktree.
- Surfaces: LUN Builder + Contingency Groups only (not `/fc-consistgrp`)
- Live SSH on button press; **replace** hosts/LUNs and CG hosts/volumes/maps
- Sources only + `generate_snap_rows()`; skip `*_snap` / `*_Snap*` (case-insensitive) as sources
- Upsert CG site by card hint (name/location); `storage_hint` = card name
- SVC / FlashSystem profiles only (`SVC_PROFILES`); fail closed on SSH/parse failure (no partial replace)
- Refuse empty replace when both hosts and volumes are empty (warn)
- Do not mutate built-in `template-*` persistence; Sync may update an in-memory/saved build only via existing upsert rules (template ids rejected on save as today)
- Keep `/api/lun-builds/pull-fc` working (host-only); primary UX is Sync Inventory
- Bump `APP_VERSION` to next patch on tip (use `1.6.43` if `1.6.42` already claimed by parallel PRs; otherwise `1.6.42`)
- Commit at each task’s commit step

---

## File map

| File | Responsibility |
|------|----------------|
| `launchpad/flashsystem_fc.py` | Add `parse_lsvdisk_volumes` (name, capacity, pool, uid, status) |
| `launchpad/inventory_sync.py` | Snap heuristics; map inventory → LUN hosts/luns + CG group; pack WWPNs |
| `launchpad/lun_builder_data.py` | Honor `exact_name` on expand/normalize if not already present |
| `launchpad/lun_builder.py` | Sync Inventory button + JS client |
| `launchpad/health_server.py` | `sync_inventory` + `POST /api/lun-builds/sync-inventory` |
| `launchpad/config.py` | Version bump |
| `tests/test_flashsystem_fc.py` or `tests/test_inventory_sync.py` | Parser + mapper fixtures |
| `tests/test_health_server_lun_builder.py` | API sync success/failure |
| `tests/test_lun_builder_page.py` | Button/endpoint wiring |

---

### Task 0: Branch / worktree

**Files:** none (git only)

**Interfaces:**
- Consumes: `feature/contingency-groups` with sync design doc
- Produces: `feature/ssh-inventory-sync` worktree

- [ ] **Step 1: Create worktree**

```powershell
git fetch origin
git -C "C:\Users\BrianColley\LaunchPad" worktree add .worktrees/ssh-inventory-sync -b feature/ssh-inventory-sync feature/contingency-groups
cd C:\Users\BrianColley\LaunchPad\.worktrees\ssh-inventory-sync
```

- [ ] **Step 2: Confirm baseline**

```powershell
python -c "from launchpad.config import APP_VERSION; print(APP_VERSION)"
```

Expected: tip version printed (e.g. `1.6.41`).

- [ ] **Step 3: No commit**

---

### Task 1: Parse volumes + snap-name heuristic

**Files:**
- Modify: `launchpad/flashsystem_fc.py`
- Create: `tests/test_inventory_sync.py` (start here; grow in later tasks)

**Interfaces:**
- Consumes: `_table_records`, `_get` in `flashsystem_fc.py`
- Produces: `parse_lsvdisk_volumes(output: str) -> list[dict]` with keys `name`, `capacity`, `pool`, `uid`, `status`; `is_flashcopy_target_name(name: str) -> bool`

- [ ] **Step 1: Write failing tests**

In `tests/test_inventory_sync.py`:

```python
from launchpad.flashsystem_fc import parse_lsvdisk_volumes
from launchpad.inventory_sync import is_flashcopy_target_name


LSVDISK_SAMPLE = """id:name:IO_group_id:IO_group_name:status:mdisk_grp_id:mdisk_grp_name:capacity:type:FC_id:FC_name:RC_id:RC_name:vdisk_UID:fc_map_count:copy_count:fast_write_state:se_copy_count:RC_change
0:ADC-Data01:0:io_grp0:online:0:G3_AND_Pool:1.00TB:striped:::::60050764008101A45800000000000B90:0:1:empty:0:no
1:vol_a_snap:0:io_grp0:online:0:G3_AND_Pool:100.00GB:striped:::::60050764008101A45800000000000B91:1:1:empty:0:no
2:host1_data:0:io_grp0:online:0:G3_AND_Pool:50.00GB:striped:::::60050764008101A45800000000000B92:0:1:empty:0:no
"""


def test_parse_lsvdisk_volumes_extracts_fields():
    rows = parse_lsvdisk_volumes(LSVDISK_SAMPLE)
    by_name = {r["name"]: r for r in rows}
    assert by_name["ADC-Data01"]["pool"] == "G3_AND_Pool"
    assert by_name["ADC-Data01"]["uid"].startswith("60050764")
    assert by_name["ADC-Data01"]["capacity"]
    assert by_name["ADC-Data01"]["status"] == "online"


def test_is_flashcopy_target_name():
    assert is_flashcopy_target_name("vol_a_snap") is True
    assert is_flashcopy_target_name("VOL_A_SNAP") is True
    assert is_flashcopy_target_name("foo_Snap1") is True
    assert is_flashcopy_target_name("ADC-Data01") is False
    assert is_flashcopy_target_name("host1_data") is False
```

- [ ] **Step 2: Run RED**

```powershell
python -m pytest tests/test_inventory_sync.py::test_parse_lsvdisk_volumes_extracts_fields tests/test_inventory_sync.py::test_is_flashcopy_target_name -v
```

Expected: FAIL (import / missing symbols).

- [ ] **Step 3: Implement**

In `flashsystem_fc.py` add:

```python
def parse_lsvdisk_volumes(output: str) -> list[dict[str, str]]:
    volumes: list[dict[str, str]] = []
    for record in _table_records(output):
        name = _get(record, "name", "vdisk_name", "volume_name")
        if not name:
            continue
        volumes.append(
            {
                "name": name,
                "capacity": _get(record, "capacity"),
                "pool": _get(record, "mdisk_grp_name", "pool", "mdisk_grp"),
                "uid": _get(record, "vdisk_UID", "UID", "uid"),
                "status": _get(record, "status", "state"),
            }
        )
    return volumes
```

Create `launchpad/inventory_sync.py` with:

```python
from __future__ import annotations

import re


def is_flashcopy_target_name(name: str) -> bool:
    text = str(name or "").strip()
    if not text:
        return False
    # Matches *_snap, *_snapN, *_Snap1, and ..._snap_...
    return bool(re.search(r"(?i)(^|_)snap\d*(_|$)", text))
```

Tune until the unit tests above pass (including `foo_Snap1` and `vol_a_snap`).

- [ ] **Step 4: Run GREEN**

```powershell
python -m pytest tests/test_inventory_sync.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add launchpad/flashsystem_fc.py launchpad/inventory_sync.py tests/test_inventory_sync.py
git commit -m "Add lsvdisk volume parse and snap-name heuristic."
```

---

### Task 2: Map inventory → LUN build + Contingency Group

**Files:**
- Modify: `launchpad/inventory_sync.py`
- Modify: `launchpad/lun_builder_data.py` (add `exact_name` support on expand/normalize if missing)
- Modify: `launchpad/lun_builder.py` JS expand if `exact_name` added
- Test: `tests/test_inventory_sync.py`

**Interfaces:**
- Consumes: `parse_fc_hosts`, `parse_host_lun_maps`, `parse_lsvdisk_volumes`, `analyze_fc_inventory` host WWPN enrichment pattern, `generate_snap_rows`, `_host`/`_volume` patterns from contingency_groups_data
- Produces:
  - `build_inventory_sync(*, hosts, volumes, maps, fabric_or_host_wwpns, card_name, storage_profile) -> dict` with keys `hosts`, `luns`, `defaults`, `group`, `pulled`, `warnings`
  - LUN hosts packed wwpn1/wwpn2 multi-row; LUN rows `count=1`, `exact_name=True`, `purpose`=live name
  - CG group with sources + maps + snaps via `generate_snap_rows`

- [ ] **Step 1: Write failing mapper tests**

Append fixtures (abbrev hosts/maps) and:

```python
def test_build_inventory_sync_replaces_shaped_lun_and_cg():
    from launchpad.inventory_sync import build_inventory_sync
    from launchpad.lun_builder_data import expand_lun_batch

    hosts = [
        {"host_name": "esx1", "status": "online", "port_count": "2", "wwpns": "AA;BB"},
        {"host_name": "esx2", "status": "online", "port_count": "2", "wwpns": "CC;DD"},
    ]
    volumes = [
        {"name": "ADC-Data01", "capacity": "1.00TB", "pool": "G3_AND_Pool", "uid": "6005AAA", "status": "online"},
        {"name": "vol_a_snap", "capacity": "100.00GB", "pool": "G3_AND_Pool", "uid": "6005BBB", "status": "online"},
        {"name": "solo_data", "capacity": "50.00GB", "pool": "G3_AND_Pool", "uid": "6005CCC", "status": "online"},
    ]
    maps = [
        {"host_name": "esx1", "vdisk_name": "ADC-Data01", "scsi_id": "0"},
        {"host_name": "esx2", "vdisk_name": "ADC-Data01", "scsi_id": "0"},
        {"host_name": "esx1", "vdisk_name": "solo_data", "scsi_id": "1"},
        {"host_name": "esx1", "vdisk_name": "vol_a_snap", "scsi_id": "2"},
    ]
    result = build_inventory_sync(
        hosts=hosts,
        volumes=volumes,
        maps=maps,
        card_name="Williamston (Anderson)",
        storage_profile="flashsystem_7200",
        storage_hint="v7kand-g3v1",
    )
    assert result["pulled"]["skipped_snaps"] == 1
    assert result["defaults"]["default_pool_or_cpg"] == "G3_AND_Pool"
    assert result["defaults"]["default_card_hint"] == "Williamston (Anderson)"
    names = [expand_lun_batch(lun)[0]["name"] for lun in result["luns"]]
    assert "ADC-Data01" in names
    assert "solo_data" in names
    assert "vol_a_snap" not in names
    adc = next(lun for lun in result["luns"] if expand_lun_batch(lun)[0]["name"] == "ADC-Data01")
    assert set(adc["host_names"]) == {"esx1", "esx2"}
    assert adc["shared"] is True

    group = result["group"]
    assert group["name"] == "Williamston (Anderson)"
    assert group["storage_hint"] == "v7kand-g3v1"
    sources = [v for v in group["volumes"] if v.get("role") != "snap"]
    snaps = [v for v in group["volumes"] if v.get("role") == "snap"]
    assert {v["name"] for v in sources} == {"ADC-Data01", "solo_data"}
    assert len(snaps) == 2
    adc_maps = [m for m in group["maps"] if m["volume"] == "ADC-Data01" and m.get("role") != "snap"]
    assert {m["host"] for m in adc_maps} == {"esx1", "esx2"}
    assert all(m["scsi_id"] == "0" for m in adc_maps)


def test_build_inventory_sync_packs_multi_wwpn_host_rows():
    from launchpad.inventory_sync import build_inventory_sync

    hosts = [
        {"host_name": "AAN1", "status": "online", "port_count": "8", "wwpns": "W1;W2;W3;W4"},
    ]
    result = build_inventory_sync(
        hosts=hosts,
        volumes=[],
        maps=[],
        card_name="Site",
        storage_profile="flashsystem_7200",
        storage_hint="hint",
        allow_empty=True,
    )
    rows = [h for h in result["hosts"] if h["lpar_name"] == "AAN1"]
    assert len(rows) == 2
    assert rows[0]["wwpn1"] == "W1" and rows[0]["wwpn2"] == "W2"
    assert rows[1]["wwpn1"] == "W3" and rows[1]["wwpn2"] == "W4"
```

- [ ] **Step 2: Run RED**

```powershell
python -m pytest tests/test_inventory_sync.py -v
```

Expected: FAIL missing `build_inventory_sync` / exact names.

- [ ] **Step 3: Implement mapper + exact_name expand**

Implement `build_inventory_sync` in `inventory_sync.py`:

1. Filter volumes with `is_flashcopy_target_name`.
2. Dominant pool = most common `pool` among kept volumes (or `""`).
3. Pack each host’s WWPN list (split on `;` / comma) into Generic LUN host rows (2 per row).
4. For each kept volume: LUN dict with `purpose=name`, `count=1`, `exact_name=True`, `name_prefix=""`, `size` from capacity (pass through or normalize to existing size tokens), `pool_or_cpg`, `storage_profile`, `card_hint`, `host_names` from maps, `shared=len(hosts)>1`, `scsi_or_lun_id` if all map scsi ids for that volume agree else `""`.
5. Build CG hosts (`name`, `status`, `port_count` int, `wwpns` list), volumes (`_volume`-like dicts), maps; `id` via caller or slugify card_name; then `generate_snap_rows(group)`.
6. `allow_empty=False` by default: if no hosts and no kept volumes, set warning and raise `ValueError("Refusing empty inventory sync")` (or return error flag for API).

If `exact_name` is not yet supported on this branch, add to `expand_lun_batch` / `_volume_name_base`: when `exact_name` truthy, return `None` from `_volume_name_base` so name = purpose; mirror in `lun_builder.py` JS expand; preserve through `normalize_lun_row`.

- [ ] **Step 4: Run GREEN**

```powershell
python -m pytest tests/test_inventory_sync.py tests/test_lun_builder_data.py -v
```

Expected: PASS (no regressions on expand).

- [ ] **Step 5: Commit**

```powershell
git add launchpad/inventory_sync.py launchpad/lun_builder_data.py launchpad/lun_builder.py tests/test_inventory_sync.py
git commit -m "Map SSH inventory into LUN builds and Contingency Groups."
```

---

### Task 3: HealthServer.sync_inventory + API

**Files:**
- Modify: `launchpad/health_server.py`
- Test: `tests/test_health_server_lun_builder.py`
- Test: `tests/test_health_server_contingency_groups.py` (optional CG upsert assert)

**Interfaces:**
- Consumes: `build_inventory_sync`, `parse_*`, `run_remote_ssh_command`, `upsert_lun_build`, `upsert_contingency_group`, `new_group_id`, `SVC_PROFILES` / `is_svc_fc_profile`
- Produces: `HealthServer.sync_inventory(build_id, card_name) -> dict`; route `POST /api/lun-builds/sync-inventory`

- [ ] **Step 1: Write failing API tests**

```python
def test_sync_inventory_replaces_build_and_upserts_cg(monkeypatch):
    # Arrange server with settings backend, one saved build, one SVC HealthCard
    # Monkeypatch run_remote_ssh_command to return fixture outputs for lshost/lsvdisk/lshostvdiskmap/lsfabric
    # Call server.sync_inventory(build_id, card_name=card.name)
    # Assert build hosts/luns replaced; CG group present with storage_hint=card.name; snaps generated
    ...


def test_sync_inventory_ssh_failure_leaves_build_unchanged(monkeypatch):
    # Seed build with known host; make SSH raise; expect exception; build unchanged
    ...


def test_health_handler_declares_sync_inventory_route():
    source = Path("launchpad/health_server.py").read_text(encoding="utf-8")
    assert "/api/lun-builds/sync-inventory" in source
```

Mirror existing `test_pull_fc_hosts_*` patterns for settings backend and card injection.

- [ ] **Step 2: Run RED**

```powershell
python -m pytest tests/test_health_server_lun_builder.py -k sync_inventory -v
```

Expected: FAIL.

- [ ] **Step 3: Implement `sync_inventory`**

```python
def sync_inventory(self, build_id: str, *, card_name: str) -> dict:
    build = self._find_lun_build(build_id)
    card = self.find_card_by_hint(card_name) or self._find_card_by_name(card_name)
    if card is None:
        raise ValueError(f'Card "{card_name}" was not found.')
    if not is_svc_fc_profile(card.device_profile):  # or profile in SVC_PROFILES
        raise ValueError("Sync Inventory requires a FlashSystem / SVC card profile.")
    run = self._lun_run_command(card)
    # Fail closed: each required command must succeed
    hosts_out = run("svcinfo lshost -delim :")
    maps_out = run("svcinfo lshostvdiskmap -delim :")
    vols_out = run("svcinfo lsvdisk -delim :")
    fabric_out = ""
    try:
        fabric_out = run("svcinfo lsfabric -delim :")
    except Exception:
        fabric_out = ""  # optional enrichment only if spec requires fail-closed — prefer required in v1
    # Prefer requiring lshost, lsvdisk, lshostvdiskmap; fabric optional for WWPN fill
    hosts = parse_fc_hosts(hosts_out)
    # Enrich hosts with WWPNs from fabric (reuse analyze_fc_inventory logic or call it on synthetic command_results)
    volumes = parse_lsvdisk_volumes(vols_out)
    maps = parse_host_lun_maps(maps_out)
    result = build_inventory_sync(
        hosts=enriched_hosts,
        volumes=volumes,
        maps=maps,
        card_name=str(card.name),  # or display hint used as card_hint
        storage_profile=card.device_profile or "flashsystem_7200",
        storage_hint=str(card.name),
    )
    # Upsert CG: if group with same name exists, reuse id; else new_group_id
    groups = self.get_contingency_groups()
    existing = next((g for g in groups if g.get("name") == result["group"]["name"]), None)
    group = result["group"]
    group["id"] = existing["id"] if existing else new_group_id(group["name"], groups)
    group["location"] = group.get("location") or group["name"]
    groups = self.upsert_contingency_group(group)

    build = dict(build)
    build["hosts"] = result["hosts"]
    build["luns"] = result["luns"]
    build["default_storage_profile"] = result["defaults"]["default_storage_profile"]
    build["default_pool_or_cpg"] = result["defaults"]["default_pool_or_cpg"]
    build["default_card_hint"] = result["defaults"]["default_card_hint"]
    builds = self.upsert_lun_build(build)
    saved = next(b for b in builds if b["id"] == build["id"])
    return {
        "build": saved,
        "builds": builds,
        "group": next(g for g in groups if g["id"] == group["id"]),
        "groups": groups,
        "pulled": result["pulled"],
        "warnings": result["warnings"],
    }
```

Wire handler next to pull-fc:

```python
if path == "/api/lun-builds/sync-inventory":
    # parse JSON build_id + card_name (required)
    result = server.sync_inventory(build_id, card_name=card_name)
```

- [ ] **Step 4: Run GREEN**

```powershell
python -m pytest tests/test_health_server_lun_builder.py tests/test_inventory_sync.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add launchpad/health_server.py tests/test_health_server_lun_builder.py
git commit -m "Add Sync Inventory API for LUN builds and Contingency Groups."
```

---

### Task 4: LUN Builder UI — Sync Inventory button

**Files:**
- Modify: `launchpad/lun_builder.py`
- Test: `tests/test_lun_builder_page.py`

**Interfaces:**
- Consumes: `POST /api/lun-builds/sync-inventory`
- Produces: button + JS `syncInventory()`; status shows pulled counts

- [ ] **Step 1: Failing page test**

In `tests/test_lun_builder_page.py`, assert HTML/JS contains `Sync Inventory` and `/api/lun-builds/sync-inventory` (same style as pull-fc assertions).

- [ ] **Step 2: Run RED**

```powershell
python -m pytest tests/test_lun_builder_page.py -k sync -v
```

- [ ] **Step 3: UI**

- Add button `id="sync-inventory-btn"` labeled **Sync Inventory** near Pull from FC WWPN (keep Pull).
- JS:

```javascript
async function syncInventory() {
  if (!currentId) { statusEl.textContent = "Save the build before syncing inventory."; return; }
  if (!persisted) { statusEl.textContent = "Unlock LaunchPad before syncing inventory."; return; }
  const cardName = window.prompt("Storage card name (required):", current()?.default_card_hint || "");
  if (cardName === null) return;
  if (!cardName.trim()) { statusEl.textContent = "Card name is required for Sync Inventory."; return; }
  statusEl.textContent = "Syncing inventory via SSH...";
  try {
    const response = await fetch("/api/lun-builds/sync-inventory", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({ build_id: currentId, card_name: cardName.trim() }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
    builds = data.builds; saveLocal(); invalidatePreview(); render();
    const p = data.pulled || {};
    importMessage(
      `Synced hosts=${p.hosts||0} volumes=${p.volumes||0} maps=${p.maps||0} skipped_snaps=${p.skipped_snaps||0}. CG upserted. No create was run.`,
      data.warnings
    );
  } catch (error) {
    statusEl.textContent = `Sync Inventory failed: ${error.message || error}`;
  }
}
```

Wire click listener.

- [ ] **Step 4: Run GREEN**

```powershell
python -m pytest tests/test_lun_builder_page.py tests/test_health_server_lun_builder.py -v
```

- [ ] **Step 5: Commit**

```powershell
git add launchpad/lun_builder.py tests/test_lun_builder_page.py
git commit -m "Add Sync Inventory button to LUN Builder."
```

---

### Task 5: Version bump + smoke

**Files:**
- Modify: `launchpad/config.py`

- [ ] **Step 1: Bump version**

Set `APP_VERSION` to the next patch after tip (`1.6.42` or `1.6.43` per Global Constraints).

- [ ] **Step 2: Smoke**

```powershell
python -m pytest tests/test_inventory_sync.py tests/test_health_server_lun_builder.py tests/test_lun_builder_page.py tests/test_lun_builder_data.py -v
python -c "from launchpad.config import APP_VERSION; print(APP_VERSION)"
```

Expected: PASS; version printed.

- [ ] **Step 3: Commit**

```powershell
git add launchpad/config.py
git commit -m "Bump version for SSH inventory sync."
```

---

## Spec coverage checklist

| Spec requirement | Task |
|------------------|------|
| Live SSH lshost / lsvdisk / lshostvdiskmap | 3 |
| Replace LUN hosts/luns | 2, 3 |
| Exact volume names | 2 |
| Skip snap-like sources + generate_snap_rows | 1, 2 |
| Upsert CG by card hint / storage_hint | 2, 3 |
| Fail closed / refuse empty | 2, 3 |
| Sync Inventory UI | 4 |
| Keep pull-fc | 4 (unchanged) |
| Version bump | 5 |
| No fc-consistgrp / no seed catalog overwrite | constraints |
