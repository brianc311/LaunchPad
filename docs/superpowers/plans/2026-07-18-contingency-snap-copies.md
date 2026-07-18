# Contingency `_snap` Copies Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add planned `*_snap` volume/map rows to Contingency Groups, with Preview/Dry-run and confirmed Run Create that builds targets, FlashCopy maps, starts copies, and host-maps them on the IBM array via SSH.

**Architecture:** Extend contingency group data with `role` / `source_volume` and an idempotent `generate_snap_rows`. A new `contingency_snap_create` module builds CLI steps and optionally runs them over SSH using the HealthCard resolved from `storage_hint`. Health server exposes generate/preview/create POST APIs; the Contingency Groups page adds UI; Excel gains Role columns.

**Tech Stack:** Python 3, existing `run_ssh_command` / HealthCard credentials, embedded Contingency Groups HTML/JS, openpyxl export.

**Spec:** `docs/superpowers/specs/2026-07-18-contingency-snap-copies-design.md`

## Global Constraints

- Suffix exactly `_snap` (e.g. `HRDC_ESXI_DS01_snap`).
- Full create set: target volume + `mkfcmap` + `startfcmap` + host maps (same hosts/SCSI as source).
- Two-step safety: Preview never writes; Run Create requires `confirm: true`.
- Stop on first SSH error; no automatic rollback.
- Resolve array from `storage_hint` → HealthCard `name` (case-insensitive).
- Blocking if missing/unknown hint, or missing pool/size when create needed.
- Skip-if-exists for vdisk / fcmap / hostmap when inventory says present.
- Bump `APP_VERSION` to `1.6.20` in the final task.
- Do not commit unless the user asked for commits in this session.
- Imports at top of modules (lazy import only to avoid circular risk, matching existing health_server export pattern).

---

## File map

| File | Responsibility |
|------|----------------|
| `launchpad/contingency_groups_data.py` | `role`/`source_volume`, `generate_snap_rows`, seed snap pairs |
| `launchpad/contingency_snap_create.py` | Size parse, step builder, inventory parse, SSH runner |
| `launchpad/contingency_groups_export.py` | Role / Source Volume columns |
| `launchpad/contingency_groups.py` | Generate / Preview / Run Create UI |
| `launchpad/health_server.py` | Three POST routes + resolve card by hint |
| `launchpad/config.py` | `1.6.20` |
| `tests/test_contingency_snap_*.py` | Unit tests |

---

### Task 1: Data model — roles + generate_snap_rows + seed updates

**Files:**
- Modify: `launchpad/contingency_groups_data.py`
- Modify: `tests/test_contingency_groups_data.py`

**Interfaces:**
- Produces:
  - `SNAP_SUFFIX = "_snap"`
  - `snap_volume_name(source_name: str) -> str`
  - `generate_snap_rows(group: dict) -> dict` (returns normalized group with missing snap volumes/maps added; idempotent)
  - `_volume(..., role="source", source_volume="")` and `_maps_all_hosts(..., role="source")`
  - `normalize_group` preserves `role` (`source`|`snap`) and `source_volume`
  - Seeds for hartford/houston/windsor include snap volumes+maps after `generate_snap_rows` or inline

- [ ] **Step 1: Write failing tests**

```python
from launchpad.contingency_groups_data import (
    generate_snap_rows,
    normalize_group,
    seed_contingency_groups,
    snap_volume_name,
)


def test_snap_volume_name():
    assert snap_volume_name("HRDC_ESXI_DS01") == "HRDC_ESXI_DS01_snap"
    assert snap_volume_name("HRDC_ESXI_DS01_snap") == "HRDC_ESXI_DS01_snap"


def test_generate_snap_rows_idempotent():
    group = normalize_group(
        {
            "id": "lab",
            "name": "Lab",
            "hosts": [{"name": "h1"}],
            "volumes": [{"name": "VOL1", "pool": "P0", "capacity": "4.00 TiB"}],
            "maps": [{"volume": "VOL1", "host": "h1", "scsi_id": "0"}],
        }
    )
    once = generate_snap_rows(group)
    twice = generate_snap_rows(once)
    snaps = [v for v in once["volumes"] if v.get("role") == "snap"]
    assert len(snaps) == 1
    assert snaps[0]["name"] == "VOL1_snap"
    assert snaps[0]["source_volume"] == "VOL1"
    assert snaps[0]["pool"] == "P0"
    assert len([v for v in twice["volumes"] if v.get("role") == "snap"]) == 1
    snap_maps = [m for m in once["maps"] if m.get("role") == "snap"]
    assert snap_maps == [
        {"volume": "VOL1_snap", "host": "h1", "scsi_id": "0", "role": "snap"}
    ]


def test_seeds_include_snap_rows():
    seeds = {g["id"]: g for g in seed_contingency_groups()}
    hartford = seeds["hartford-ct"]
    assert any(v["name"] == "HRDC_ESXI_DS01_snap" for v in hartford["volumes"])
    assert any(
        m.get("role") == "snap" and m["volume"] == "HRDC_ESXI_DS01_snap"
        for m in hartford["maps"]
    )
    houston = seeds["houston-tx"]
    assert any(v["name"].endswith("_snap") for v in houston["volumes"])
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `python -m pytest tests/test_contingency_groups_data.py -k snap -v`

- [ ] **Step 3: Implement**

```python
SNAP_SUFFIX = "_snap"

def snap_volume_name(source_name: str) -> str:
    name = str(source_name or "").strip()
    if name.endswith(SNAP_SUFFIX):
        return name
    return f"{name}{SNAP_SUFFIX}"


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
    for vol in list(volumes):
        role = str(vol.get("role") or "source").lower()
        name = str(vol.get("name") or "")
        if role == "snap" or name.endswith(SNAP_SUFFIX):
            continue
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
        source_maps = [
            m for m in maps
            if str(m.get("volume") or "") == name and str(m.get("role") or "source") != "snap"
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

Update `_normalize_volume` / map normalize to keep `role` and `source_volume`.  
End each seed builder with `return generate_snap_rows({...})` OR call `generate_snap_rows` inside `seed_contingency_groups()`.

- [ ] **Step 4: Full data tests PASS**

Run: `python -m pytest tests/test_contingency_groups_data.py -q`

- [ ] **Step 5: Commit only if user asked**

---

### Task 2: Step builder + inventory helpers (preview, no SSH)

**Files:**
- Create: `launchpad/contingency_snap_create.py`
- Create: `tests/test_contingency_snap_create.py`

**Interfaces:**
- Produces:
  - `@dataclass SnapStep: kind, purpose, cmd, skip: bool = False, reason: str = ""`
  - `parse_capacity_to_gb(capacity: str) -> float | None`  # `"4.00 TiB"` → `4096.0` approx or exact 4*1024
  - `safe_fcmap_name(source: str, target: str) -> str`  # alphanumeric/underscore, max length safe
  - `build_snap_steps(group: dict, *, inventory: dict | None = None) -> tuple[list[SnapStep], list[str]]`
    - `inventory` optional: `{ "vdisks": set[str], "fcmaps": set[str], "hostmaps": set[tuple[host,scsi,vdisk]] }`
    - returns `(steps, blocking_warnings)`
  - `parse_lsvdisk_names(output: str) -> set[str]`
  - `parse_lsfcmap_names(output: str) -> set[str]`
  - `parse_lshostvdiskmap_keys(output: str) -> set[tuple[str,str,str]]`  # host, scsi, vdisk

CLI shapes (use bare `svctask` / `svcinfo` style consistent with FC presets):

```text
svctask mkvdisk -name VOL_snap -mdiskgrp POOL -size N -unit gb
svctask mkfcmap -source VOL -target VOL_snap -name fc_VOL_to_snap
svctask startfcmap fc_VOL_to_snap
svctask mkvdiskhostmap -host HOST -scsi ID VOL_snap
```

- [ ] **Step 1: Failing tests**

```python
from launchpad.contingency_snap_create import (
    build_snap_steps,
    parse_capacity_to_gb,
    safe_fcmap_name,
)


def test_parse_capacity_tib():
    assert parse_capacity_to_gb("4.00 TiB") == 4096.0


def test_build_steps_blocking_without_pool_size():
    group = {
        "id": "x",
        "name": "X",
        "storage_hint": "array1",
        "volumes": [
            {"name": "V1", "role": "source", "pool": "", "capacity": ""},
            {
                "name": "V1_snap",
                "role": "snap",
                "source_volume": "V1",
                "pool": "",
                "capacity": "",
            },
        ],
        "maps": [
            {"volume": "V1", "host": "h1", "scsi_id": "0", "role": "source"},
            {"volume": "V1_snap", "host": "h1", "scsi_id": "0", "role": "snap"},
        ],
    }
    steps, warnings = build_snap_steps(group, inventory={"vdisks": set(), "fcmaps": set(), "hostmaps": set()})
    assert any("pool" in w.lower() or "size" in w.lower() for w in warnings)


def test_build_steps_happy_path_and_skip():
    group = {
        "id": "x",
        "name": "X",
        "storage_hint": "array1",
        "volumes": [
            {"name": "V1", "role": "source", "pool": "P0", "capacity": "4.00 TiB"},
            {
                "name": "V1_snap",
                "role": "snap",
                "source_volume": "V1",
                "pool": "P0",
                "capacity": "4.00 TiB",
            },
        ],
        "maps": [
            {"volume": "V1_snap", "host": "h1", "scsi_id": "0", "role": "snap"},
        ],
    }
    steps, warnings = build_snap_steps(
        group,
        inventory={
            "vdisks": {"V1", "V1_snap"},
            "fcmaps": set(),
            "hostmaps": set(),
        },
    )
    assert not warnings
    assert any(s.skip and "mkvdisk" in s.cmd for s in steps)
    assert any("mkfcmap" in s.cmd and not s.skip for s in steps)
    assert any("startfcmap" in s.cmd for s in steps)
    assert any("mkvdiskhostmap" in s.cmd for s in steps)
    assert "fc_" in safe_fcmap_name("V1", "V1_snap")
```

- [ ] **Step 2: Implement `contingency_snap_create.py`** (preview-only functions first; runner stubs OK as `NotImplemented` until Task 3)

- [ ] **Step 3: pytest PASS** for Task 2 tests

---

### Task 3: SSH runner + HealthServer APIs

**Files:**
- Modify: `launchpad/contingency_snap_create.py` — `run_snap_create`, `collect_inventory`
- Modify: `launchpad/health_server.py`
- Create: `tests/test_health_server_contingency_snap.py`

**Interfaces:**
- `resolve_card_by_storage_hint(cards: list[HealthCard]|list[dict], hint: str) -> HealthCard|dict|None`
- `collect_inventory(run_cmd: Callable[[str], str]) -> dict`  
  runs `svcinfo lsvdisk -delim :`, `svcinfo lsfcmap -delim :`, `svcinfo lshostvdiskmap -delim :` (with bare fallbacks if empty)
- `run_snap_steps(steps: list[SnapStep], run_cmd: Callable[[str], str]) -> list[dict]`  
  skip steps with `skip=True`; on error raise or return `{ok: False, log}` — prefer return structure matching API
- HealthServer:
  - `find_card_by_hint(hint: str) -> HealthCard | None` (search `_cards` by name)
  - `generate_contingency_snaps(group_id) -> dict`
  - `preview_contingency_snaps(group_id) -> dict`
  - `create_contingency_snaps(group_id, *, confirm: bool) -> dict`

POST routes:

```text
POST /api/contingency-groups/generate-snaps   { group_id }
POST /api/contingency-groups/snap-preview     { group_id }
POST /api/contingency-groups/snap-create      { group_id, confirm: true }
```

Preview: resolve card; if missing → 400/warnings; optionally `collect_inventory` via `run_remote_ssh_command` using card credentials; `build_snap_steps`; never mutate.

Create: require `confirm is True`; if blocking warnings → 400; execute non-skip steps in order; stop on first failure; return `{ ok, log, warnings }`.

- [ ] **Step 1: Unit-test runner with fake `run_cmd`**

```python
def test_run_snap_steps_stops_on_error():
    calls = []
    def run_cmd(cmd: str) -> str:
        calls.append(cmd)
        if "startfcmap" in cmd:
            raise RuntimeError("boom")
        return "OK"
    steps = [
        SnapStep("mkvdisk", "create", "svctask mkvdisk ...", skip=True),
        SnapStep("mkfcmap", "map", "svctask mkfcmap ..."),
        SnapStep("startfcmap", "start", "svctask startfcmap ..."),
        SnapStep("hostmap", "map host", "svctask mkvdiskhostmap ..."),
    ]
    result = run_snap_steps(steps, run_cmd)
    assert result["ok"] is False
    assert len(calls) == 2  # mkfcmap + startfcmap
    assert "mkvdiskhostmap" not in "".join(calls)
```

- [ ] **Step 2: Implement runner + HealthServer methods/routes**

Wire `run_cmd` as:

```python
lambda cmd: run_remote_ssh_command(
    card.host, card.port, card.username, cmd,
    key_path=card.key_path, key_passphrase=card.key_passphrase,
    password=card.password, timeout=120,
)
```

Generate-snaps: load groups, find id, `generate_snap_rows`, upsert/save, return group.

- [ ] **Step 3: pytest** data + snap_create + health_server snap tests PASS

---

### Task 4: Excel Role columns

**Files:**
- Modify: `launchpad/contingency_groups_export.py`
- Modify: `tests/test_contingency_groups_export.py`

- [ ] **Step 1: Update headers**

```python
VOLUME_HEADERS = (..., "Role", "Source Volume")  # after Protocol or before
MAP_HEADERS = (..., "Role")
```

Populate from `vol.get("role") or "source"` and `vol.get("source_volume") or ""`.

- [ ] **Step 2: Test** Windsor/Hartford export includes a snap volume row with Role `snap`.

- [ ] **Step 3: pytest export PASS**

---

### Task 5: Contingency Groups UI + version bump

**Files:**
- Modify: `launchpad/contingency_groups.py`
- Modify: `launchpad/config.py` → `APP_VERSION = "1.6.20"`
- Modify: `tests/test_contingency_groups_page.py` — assert button/API strings
- Optional: mark snap design Status Implemented

**UI requirements:**
- Show `SNAP` badge on snap volume/map rows (`role === "snap"`).
- Buttons: **Generate _snap rows**, **Preview / Dry-run**, **Run Create**.
- Generate → POST generate-snaps → refresh editor from returned group → persist.
- Preview → modal listing `steps` (mark skipped), `warnings`, card name/host; set `window.__lastSnapPreviewOk = !blocking`.
- Run Create → disabled unless preview succeeded this session OR always enabled with confirm; `confirm("This will create volumes and start FlashCopy on <card>...")` then POST snap-create; show log modal.
- Footer note: create is operator-initiated.

- [ ] **Step 1: Implement UI + wire handlers**

- [ ] **Step 2: Bump version to 1.6.20**

- [ ] **Step 3: Regression**

```powershell
python -m pytest tests/test_contingency_groups_data.py tests/test_contingency_snap_create.py tests/test_health_server_contingency_snap.py tests/test_contingency_groups_export.py tests/test_contingency_groups_page.py -q
python -c "from launchpad.config import APP_VERSION; assert APP_VERSION=='1.6.20'"
```

- [ ] **Step 4: Manual checklist in report** (lab array only for Run Create)

---

## Spec coverage checklist

| Spec item | Task |
|-----------|------|
| `role` / `source_volume` / `_snap` naming | 1 |
| Generate _snap rows idempotent | 1, 5 |
| Seeds include snaps | 1 |
| Preview step list + skip-if-exists | 2, 3 |
| Run Create + confirm + stop on error | 3, 5 |
| Resolve storage_hint → card | 3 |
| Excel Role columns | 4 |
| UI badges + modals | 5 |
| Version 1.6.20 | 5 |

## Placeholder / consistency self-review

- Suffix `_snap`, API paths, and APP_VERSION consistent.
- Commit steps optional per session rules.
- CLI uses `svctask`/`svcinfo` to match existing FC command style.
