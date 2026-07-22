# Sync Live Snaps into Contingency Groups — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prefer live FlashCopy-target volumes (real names/UIDs) in Contingency Groups during Sync Inventory, and only generate `{source}_snap` when no matching live snap exists.

**Architecture:** `build_inventory_sync` attaches name-matched live snaps as `role=snap` before calling `generate_snap_rows`. `generate_snap_rows` skips inventing a placeholder when a source already has a linked snap and uses that snap’s name for maps. LUN Builder still excludes snap-like volumes. UI reports `live_snaps` beside `skipped_snaps`.

**Tech Stack:** Python, existing `inventory_sync` / Contingency Groups helpers, pytest, LUN Builder page JS string.

**Spec:** `docs/superpowers/specs/2026-07-22-sync-live-snaps-cg-design.md`

## Global Constraints

- Work in existing worktree: `C:\Users\BrianColley\LaunchPad\.worktrees\sync-live-snaps-cg` on branch `feature/sync-live-snaps-cg` (forked from `feature/ssh-inventory-sync`).
- Prefer live snap over generated `{source}_snap`; generate only when no linked live snap.
- Name matching only in v1 (same heuristic as `is_flashcopy_target_name`); no `lsfcmap`.
- Orphans (snap-like with no matching kept source): skip; still counted in `skipped_snaps`.
- One live snap per source: first inventory-order match wins; extra matches for the same source are not imported.
- LUN Builder output must continue to exclude all snap-like volumes.
- No new SSH commands; no `/fc-consistgrp` changes.
- Bump `APP_VERSION` from `1.6.43` to `1.6.48` (1.6.44–1.6.47 claimed by parallel branches).
- Commit at each task’s commit step.

---

## File map

| File | Responsibility |
|------|----------------|
| `launchpad/contingency_groups_data.py` | `generate_snap_rows`: honor existing linked snaps; map to live name |
| `launchpad/inventory_sync.py` | `flashcopy_source_candidate`; attach live snaps; `pulled.live_snaps` |
| `launchpad/lun_builder.py` | Status string includes `live_snaps` |
| `launchpad/config.py` | Version bump to `1.6.48` |
| `tests/test_contingency_groups_data.py` | generate_snap_rows live-link cases |
| `tests/test_inventory_sync.py` | live match / orphan / first-wins / LUN exclusion |
| `tests/test_lun_builder_page.py` | Status string mentions `live_snaps` (if page test pattern allows) |

---

### Task 0: Confirm worktree baseline

**Files:** none (git only; optional design-doc typo already fixed)

**Interfaces:**
- Consumes: branch `feature/sync-live-snaps-cg` with approved spec
- Produces: confirmed cwd + version baseline

- [ ] **Step 1: Confirm location and version**

```powershell
cd C:\Users\BrianColley\LaunchPad\.worktrees\sync-live-snaps-cg
git branch --show-current
python -c "from launchpad.config import APP_VERSION; print(APP_VERSION)"
```

Expected: `feature/sync-live-snaps-cg` and `1.6.43`.

- [ ] **Step 2: No commit** (unless the trailing `}` typo in the design doc is still uncommitted — then commit that alone with message `Fix trailing typo in live-snaps CG design spec.`)

---

### Task 1: `generate_snap_rows` respects linked live snaps

**Files:**
- Modify: `launchpad/contingency_groups_data.py` (`generate_snap_rows`)
- Test: `tests/test_contingency_groups_data.py`

**Interfaces:**
- Consumes: existing `generate_snap_rows(group: dict) -> dict`, `snap_volume_name(source_name: str) -> str`
- Produces: same function signature; if any volume has `role=snap` and non-empty `source_volume` matching a source, do not invent `{source}_snap`; snap maps use that existing snap’s `name`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_contingency_groups_data.py`:

```python
def test_generate_snap_rows_keeps_linked_live_snap_name():
    group = {
        "id": "lab",
        "name": "Lab",
        "location": "Lab",
        "storage_hint": "",
        "notes": "",
        "updated_at": "",
        "hosts": [{"name": "h1", "status": "Online", "host_type": "Generic", "port_count": 2, "protocol": "SCSI", "wwpns": []}],
        "volumes": [
            {
                "name": "volA",
                "capacity": "1.00TB",
                "pool": "Pool1",
                "uid": "UID-SRC",
                "protocol": "SCSI",
                "role": "source",
                "source_volume": "",
            },
            {
                "name": "volA_Snap1",
                "capacity": "1.00TB",
                "pool": "Pool1",
                "uid": "UID-LIVE",
                "protocol": "SCSI",
                "role": "snap",
                "source_volume": "volA",
            },
        ],
        "maps": [
            {"volume": "volA", "host": "h1", "scsi_id": "0", "role": "source"},
        ],
    }
    out = generate_snap_rows(group)
    snaps = [v for v in out["volumes"] if v.get("role") == "snap"]
    assert len(snaps) == 1
    assert snaps[0]["name"] == "volA_Snap1"
    assert snaps[0]["uid"] == "UID-LIVE"
    assert "volA_snap" not in {v["name"] for v in out["volumes"]}
    snap_maps = [m for m in out["maps"] if m.get("role") == "snap"]
    assert snap_maps
    assert all(m["volume"] == "volA_Snap1" for m in snap_maps)


def test_generate_snap_rows_still_creates_placeholder_when_no_live_snap():
    group = {
        "id": "lab",
        "name": "Lab",
        "location": "Lab",
        "storage_hint": "",
        "notes": "",
        "updated_at": "",
        "hosts": [],
        "volumes": [
            {
                "name": "solo",
                "capacity": "50GB",
                "pool": "P",
                "uid": "U1",
                "protocol": "SCSI",
                "role": "source",
                "source_volume": "",
            }
        ],
        "maps": [{"volume": "solo", "host": "h1", "scsi_id": "1", "role": "source"}],
    }
    out = generate_snap_rows(group)
    assert any(v["name"] == "solo_snap" and v.get("role") == "snap" for v in out["volumes"])
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
python -m pytest tests/test_contingency_groups_data.py::test_generate_snap_rows_keeps_linked_live_snap_name tests/test_contingency_groups_data.py::test_generate_snap_rows_still_creates_placeholder_when_no_live_snap -v
```

Expected: `test_generate_snap_rows_keeps_linked_live_snap_name` FAIL (duplicate `volA_snap` and/or snap maps targeting `volA_snap`). Placeholder test may already PASS.

- [ ] **Step 3: Implement minimal `generate_snap_rows` fix**

Replace the body of `generate_snap_rows` in `launchpad/contingency_groups_data.py` so the per-source loop resolves `target` from an existing linked snap first:

```python
def generate_snap_rows(group: dict) -> dict:
    g = normalize_group(group) or {
        "id": "",
        "name": "",
        "location": "",
        "storage_hint": "",
        "notes": "",
        "updated_at": "",
        "hosts": [],
        "volumes": [],
        "maps": [],
    }
    volumes = list(g["volumes"])
    maps = list(g["maps"])
    by_name = {str(v.get("name") or ""): v for v in volumes}
    linked_snap_by_source: dict[str, str] = {}
    for vol in volumes:
        if str(vol.get("role") or "").lower() != "snap":
            continue
        source = str(vol.get("source_volume") or "").strip()
        snap_name = str(vol.get("name") or "").strip()
        if source and snap_name and source not in linked_snap_by_source:
            linked_snap_by_source[source] = snap_name
    for vol in list(volumes):
        role = str(vol.get("role") or "source").lower()
        name = str(vol.get("name") or "")
        if role == "snap" or name.endswith(SNAP_SUFFIX):
            continue
        if name in linked_snap_by_source:
            target = linked_snap_by_source[name]
        else:
            target = snap_volume_name(name)
            if target not in by_name:
                snap = {
                    "name": target,
                    "capacity": vol.get("capacity") or "",
                    "pool": vol.get("pool") or "",
                    "uid": "",
                    "protocol": vol.get("protocol") or "SCSI",
                    "role": "snap",
                    "source_volume": name,
                }
                volumes.append(snap)
                by_name[target] = snap
                linked_snap_by_source[name] = target
        source_maps = [
            m
            for m in maps
            if str(m.get("volume") or "") == name
            and str(m.get("role") or "source") != "snap"
        ]
        existing_snap_map_keys = {
            (str(m.get("volume")), str(m.get("host")), str(m.get("scsi_id")))
            for m in maps
            if str(m.get("role") or "") == "snap"
        }
        for m in source_maps:
            key = (target, str(m.get("host") or ""), str(m.get("scsi_id") or ""))
            if key in existing_snap_map_keys:
                continue
            maps.append(
                {
                    "volume": target,
                    "host": str(m.get("host") or ""),
                    "scsi_id": str(m.get("scsi_id") or ""),
                    "role": "snap",
                }
            )
            existing_snap_map_keys.add(key)
    g["volumes"] = volumes
    g["maps"] = maps
    return normalize_group(g) or g
```

- [ ] **Step 4: Run tests to verify they pass**

```powershell
python -m pytest tests/test_contingency_groups_data.py -v
```

Expected: PASS (including new tests and existing seed/normalize tests).

- [ ] **Step 5: Commit**

```powershell
git add launchpad/contingency_groups_data.py tests/test_contingency_groups_data.py
git commit -m "Prefer linked live snaps over generated _snap rows."
```

---

### Task 2: Attach live snaps in `build_inventory_sync`

**Files:**
- Modify: `launchpad/inventory_sync.py`
- Test: `tests/test_inventory_sync.py`

**Interfaces:**
- Consumes: `is_flashcopy_target_name`, `generate_snap_rows` (Task 1 behavior)
- Produces:
  - `flashcopy_source_candidate(name: str) -> str | None`
  - `build_inventory_sync(...)-> dict` with `pulled["live_snaps"]: int` and CG volumes including matched live snaps

Name-strip rule for `flashcopy_source_candidate`:

```python
def flashcopy_source_candidate(name: str) -> str | None:
    text = str(name or "").strip()
    if not is_flashcopy_target_name(text):
        return None
    candidate = re.sub(r"(?i)_snap\d*(?=_|$)", "", text)
    candidate = re.sub(r"(?i)^snap\d*_?", "", candidate)
    candidate = candidate.strip("_")
    return candidate or None
```

Live-attach algorithm (after `cg_volumes` / `source_maps` are built, **before** `generate_snap_rows`):

1. `claimed_sources: set[str] = set()`
2. `live_snaps = 0`
3. For each volume in original `volumes` list (inventory order) where `is_flashcopy_target_name(name)`:
   - `candidate = flashcopy_source_candidate(name)`
   - If `candidate` not in `kept_names`: continue (orphan)
   - If `candidate` in `claimed_sources`: continue (first wins)
   - Append CG volume: live name/capacity/pool/uid, `role=snap`, `source_volume=candidate`
   - `claimed_sources.add(candidate)`; `live_snaps += 1`
4. Pass enriched volumes into `generate_snap_rows`
5. Set `pulled["live_snaps"] = live_snaps` (keep `skipped_snaps` as total snap-like count)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_inventory_sync.py`:

```python
def test_flashcopy_source_candidate():
    from launchpad.inventory_sync import flashcopy_source_candidate

    assert flashcopy_source_candidate("volA_Snap1") == "volA"
    assert flashcopy_source_candidate("vol_a_snap") == "vol_a"
    assert flashcopy_source_candidate("ADC-Data01") is None


def test_build_inventory_sync_prefers_live_snap_in_cg():
    from launchpad.inventory_sync import build_inventory_sync
    from launchpad.lun_builder_data import expand_lun_batch

    result = build_inventory_sync(
        hosts=[{"host_name": "esx1", "status": "online", "port_count": "2", "wwpns": "AA;BB"}],
        volumes=[
            {"name": "volA", "capacity": "1.00TB", "pool": "Pool1", "uid": "UID-SRC", "status": "online"},
            {"name": "volA_Snap1", "capacity": "1.00TB", "pool": "Pool1", "uid": "UID-LIVE", "status": "online"},
            {"name": "orphan_snap", "capacity": "10GB", "pool": "Pool1", "uid": "UID-ORPH", "status": "online"},
            {"name": "volA_Snap2", "capacity": "1.00TB", "pool": "Pool1", "uid": "UID-2ND", "status": "online"},
        ],
        maps=[
            {"host_name": "esx1", "vdisk_name": "volA", "scsi_id": "0"},
            {"host_name": "esx1", "vdisk_name": "volA_Snap1", "scsi_id": "9"},
        ],
        card_name="Site",
        storage_profile="flashsystem_7200",
        storage_hint="hint",
    )
    assert result["pulled"]["skipped_snaps"] == 3
    assert result["pulled"]["live_snaps"] == 1
    lun_names = [expand_lun_batch(lun)[0]["name"] for lun in result["luns"]]
    assert lun_names == ["volA"]
    snaps = [v for v in result["group"]["volumes"] if v.get("role") == "snap"]
    assert len(snaps) == 1
    assert snaps[0]["name"] == "volA_Snap1"
    assert snaps[0]["uid"] == "UID-LIVE"
    assert snaps[0]["source_volume"] == "volA"
    assert "orphan_snap" not in {v["name"] for v in result["group"]["volumes"]}
    assert "volA_Snap2" not in {v["name"] for v in result["group"]["volumes"]}
    assert "volA_snap" not in {v["name"] for v in result["group"]["volumes"]}
    snap_maps = [m for m in result["group"]["maps"] if m.get("role") == "snap"]
    assert snap_maps and all(m["volume"] == "volA_Snap1" for m in snap_maps)


def test_build_inventory_sync_generates_snap_when_no_live_match():
    from launchpad.inventory_sync import build_inventory_sync

    result = build_inventory_sync(
        hosts=[{"host_name": "esx1", "status": "online", "port_count": "2", "wwpns": "AA;BB"}],
        volumes=[
            {"name": "solo", "capacity": "50GB", "pool": "P", "uid": "U1", "status": "online"},
        ],
        maps=[{"host_name": "esx1", "vdisk_name": "solo", "scsi_id": "1"}],
        card_name="Site",
        storage_profile="flashsystem_7200",
        storage_hint="hint",
    )
    assert result["pulled"]["live_snaps"] == 0
    snaps = [v for v in result["group"]["volumes"] if v.get("role") == "snap"]
    assert len(snaps) == 1
    assert snaps[0]["name"] == "solo_snap"
```

Also update `test_build_inventory_sync_replaces_shaped_lun_and_cg` to assert `result["pulled"]["live_snaps"] == 0` (existing `vol_a_snap` is an orphan with no `vol_a` source).

- [ ] **Step 2: Run tests to verify they fail**

```powershell
python -m pytest tests/test_inventory_sync.py::test_flashcopy_source_candidate tests/test_inventory_sync.py::test_build_inventory_sync_prefers_live_snap_in_cg tests/test_inventory_sync.py::test_build_inventory_sync_generates_snap_when_no_live_match -v
```

Expected: FAIL (import / missing `live_snaps` / still generating `volA_snap` instead of live).

- [ ] **Step 3: Implement helpers + attach live snaps**

In `launchpad/inventory_sync.py`:

1. Add `flashcopy_source_candidate` next to `is_flashcopy_target_name`.
2. After the loop that builds `cg_volumes` (and before `generate_snap_rows(...)`), insert live-snap attachment using the algorithm above.
3. Include live snap volumes in the dict passed to `generate_snap_rows` (`"volumes": cg_volumes` already — append to `cg_volumes`).
4. Add `"live_snaps": live_snaps` to the `pulled` dict.

Do not change LUN `kept_volumes` filtering.

- [ ] **Step 4: Run inventory sync tests**

```powershell
python -m pytest tests/test_inventory_sync.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add launchpad/inventory_sync.py tests/test_inventory_sync.py
git commit -m "Attach matched live snap volumes into Contingency Groups on sync."
```

---

### Task 3: UI status + version bump

**Files:**
- Modify: `launchpad/lun_builder.py` (status string ~line 867)
- Modify: `launchpad/config.py` (`APP_VERSION`)
- Test: `tests/test_lun_builder_page.py` (add assertion if the page HTML/JS is scanned for Sync Inventory copy)

**Interfaces:**
- Consumes: `pulled.live_snaps` from Sync Inventory API response (already passed through unchanged)
- Produces: status text including `live_snaps=${p.live_snaps||0}`; `APP_VERSION == "1.6.48"`

- [ ] **Step 1: Write / extend failing page check**

If `tests/test_lun_builder_page.py` already asserts on Sync Inventory strings, add:

```python
assert "live_snaps=" in html  # or whatever variable holds lun_builder page source
```

If there is no Sync Inventory string assertion today, add a focused test that loads `lun_builder` page HTML/JS and asserts both `skipped_snaps=` and `live_snaps=` appear in the Sync success template.

- [ ] **Step 2: Run RED**

```powershell
python -m pytest tests/test_lun_builder_page.py -v -k "sync or live_snap" 
```

Expected: FAIL until string updated (adjust `-k` to the new test name).

- [ ] **Step 3: Update status string and version**

In `launchpad/lun_builder.py`, change the Sync success message to:

```javascript
`Synced hosts=${p.hosts||0} volumes=${p.volumes||0} maps=${p.maps||0} skipped_snaps=${p.skipped_snaps||0} live_snaps=${p.live_snaps||0}. CG upserted. No create was run.`,
```

In `launchpad/config.py`:

```python
APP_VERSION = "1.6.48"
```

- [ ] **Step 4: Run page + related tests**

```powershell
python -m pytest tests/test_lun_builder_page.py tests/test_inventory_sync.py tests/test_contingency_groups_data.py -v
python -c "from launchpad.config import APP_VERSION; assert APP_VERSION == '1.6.48'"
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add launchpad/lun_builder.py launchpad/config.py tests/test_lun_builder_page.py
git commit -m "Show live_snaps in Sync Inventory status and bump to 1.6.48."
```

---

### Task 4: Full verification

**Files:** none (run only)

**Interfaces:**
- Consumes: Tasks 1–3
- Produces: green targeted suite

- [ ] **Step 1: Run targeted regression suite**

```powershell
cd C:\Users\BrianColley\LaunchPad\.worktrees\sync-live-snaps-cg
python -m pytest tests/test_inventory_sync.py tests/test_contingency_groups_data.py tests/test_lun_builder_page.py tests/test_health_server_lun_builder.py -v
```

Expected: PASS.

- [ ] **Step 2: No code commit** unless a test revealed a bug — then fix in a new commit, do not amend.

---

## Spec coverage checklist (self-review)

| Spec requirement | Task |
|------------------|------|
| Prefer live snap name/UID/pool in CG | Task 2 |
| Generate `{source}_snap` only when no live match | Tasks 1–2 |
| LUN Builder still skips snap-like volumes | Task 2 tests |
| Orphans skipped | Task 2 |
| First match wins for multi-snap source | Task 2 |
| `generate_snap_rows` no duplicate / maps use live name | Task 1 |
| `pulled.live_snaps` + UI status | Tasks 2–3 |
| No `lsfcmap` / no new SSH | (non-goal; no task) |
| Version bump | Task 3 |
