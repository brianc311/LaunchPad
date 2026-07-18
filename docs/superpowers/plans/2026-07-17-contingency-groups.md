# Contingency Groups Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Contingency Groups library (seeded Houston / Hartford / Windsor) that operators can select, edit (WWPNs + UIDs), save, export, and use to filter the FC WWPN report.

**Architecture:** Pure Python module owns seeds, normalize/upsert, and FC filter matching. Health server persists JSON under `contingency_groups` (notes/overrides pattern). A new browser page edits groups; FC WWPN gains a group dropdown filter; Excel export mirrors schedule/FC export style.

**Tech Stack:** Python 3, openpyxl, local health HTTP server, embedded HTML/JS, SQLite settings via `db.get_setting` / `db.set_setting`.

**Spec:** `docs/superpowers/specs/2026-07-17-contingency-groups-design.md`

## Global Constraints

- Setting key exactly `contingency_groups` (JSON array).
- Seed on first empty DB: `hartford-ct`, `houston-tx`, `windsor` with hosts/volumes/maps from the spec (Windsor includes WWPNs + UIDs; Houston/Hartford WWPNs/UIDs empty lists/strings).
- WWPN and UID fields always editable; empty allowed.
- Save updates in place; Save as new creates new unique `id`.
- FC filter: case-insensitive host name and volume/vdisk name; also match host WWPNs when present.
- Reference library only — do not modify the storage array.
- Bump `APP_VERSION` to `1.6.19` in the final task.
- Prefer patterns from snapshot notes/overrides and FC/schedule pages.
- Do not commit unless the user asked for commits in this session; skip commit steps if unclear.
- Imports at top of modules (no inline imports unless existing file pattern requires lazy import for circular risk).

---

## File map

| File | Responsibility |
|------|----------------|
| `launchpad/contingency_groups_data.py` | Seeds, normalize, upsert/delete, filter match helpers |
| `tests/test_contingency_groups_data.py` | Unit tests for data helpers |
| `launchpad/contingency_groups_export.py` | Excel workbook builder |
| `tests/test_contingency_groups_export.py` | Export smoke tests |
| `launchpad/contingency_groups.py` | Page HTML/JS (`CONTINGENCY_GROUPS_PATH`, `CONTINGENCY_GROUPS_HTML`) |
| `launchpad/health_server.py` | GET/POST APIs, page route, export route, seed-on-empty |
| `launchpad/fc_wwpn_report.py` | Contingency group filter dropdown |
| `launchpad/ui/dashboard_view.py` | Button to open Contingency Groups |
| `launchpad/config.py` | `1.6.19` |

---

### Task 1: Data helpers + seeds + unit tests

**Files:**
- Create: `launchpad/contingency_groups_data.py`
- Create: `tests/test_contingency_groups_data.py`

**Interfaces:**
- Produces:
  - `CONTINGENCY_GROUPS_SETTING = "contingency_groups"`
  - `seed_contingency_groups() -> list[dict]`
  - `normalize_group(raw: Any) -> dict | None`
  - `normalize_groups(raw: Any) -> list[dict]`
  - `upsert_group(groups: list[dict], group: dict) -> list[dict]`
  - `delete_group(groups: list[dict], group_id: str) -> list[dict]`
  - `new_group_id(name: str, existing: list[dict]) -> str`
  - `group_matches_host(group: dict, host_name: str, wwpns_haystack: str = "") -> bool`
  - `group_matches_volume(group: dict, volume_name: str) -> bool`
  - `filter_fc_card(card: dict, group: dict | None) -> dict` (returns card-shaped dict with filtered `fc_hosts` / `fc_mappings` / optionally ports — or document that filtering is client-side only; prefer shared helpers used by both JS logic tests in Python)

- [ ] **Step 1: Write failing tests**

```python
from launchpad.contingency_groups_data import (
    CONTINGENCY_GROUPS_SETTING,
    delete_group,
    group_matches_host,
    group_matches_volume,
    normalize_group,
    normalize_groups,
    seed_contingency_groups,
    upsert_group,
    new_group_id,
)


def test_setting_key():
    assert CONTINGENCY_GROUPS_SETTING == "contingency_groups"


def test_seeds_include_three_sites():
    seeds = seed_contingency_groups()
    ids = {g["id"] for g in seeds}
    assert ids == {"hartford-ct", "houston-tx", "windsor"}
    hartford = next(g for g in seeds if g["id"] == "hartford-ct")
    assert len(hartford["hosts"]) == 3
    assert len(hartford["volumes"]) == 3
    assert any(m["scsi_id"] == "0" for m in hartford["maps"])
    houston = next(g for g in seeds if g["id"] == "houston-tx")
    assert {h["name"] for h in houston["hosts"]} == {
        "pen-houesx-vm03",
        "pen-houesx-vm04",
    }
    assert len(houston["volumes"]) == 4
    windsor = next(g for g in seeds if g["id"] == "windsor")
    vm01 = next(h for h in windsor["hosts"] if h["name"] == "PEN_WINESX_VM01")
    assert "51402EC012CFD072" in vm01["wwpns"]
    vol1 = next(v for v in windsor["volumes"] if v["name"] == "WIN_ESX_DataStore_1")
    assert vol1["uid"].startswith("60050768128000A758")


def test_normalize_strips_and_keeps_empty_wwpn_uid():
    g = normalize_group(
        {
            "id": "x",
            "name": " X ",
            "hosts": [{"name": "h1", "wwpns": ["", " AA "]}],
            "volumes": [{"name": "v1", "uid": ""}],
            "maps": [{"volume": "v1", "host": "h1", "scsi_id": 0}],
        }
    )
    assert g is not None
    assert g["name"] == "X"
    assert g["hosts"][0]["wwpns"] == ["AA"]
    assert g["volumes"][0]["uid"] == ""
    assert g["maps"][0]["scsi_id"] == "0"


def test_upsert_and_delete():
    groups = normalize_groups(seed_contingency_groups())
    extra = normalize_group(
        {
            "id": "lab-1",
            "name": "Lab",
            "hosts": [],
            "volumes": [],
            "maps": [],
        }
    )
    groups = upsert_group(groups, extra)
    assert any(g["id"] == "lab-1" for g in groups)
    groups = delete_group(groups, "lab-1")
    assert all(g["id"] != "lab-1" for g in groups)


def test_match_helpers():
    seeds = {g["id"]: g for g in seed_contingency_groups()}
    assert group_matches_host(seeds["houston-tx"], "PEN-HOUESX-VM03")
    assert group_matches_volume(seeds["houston-tx"], "houston_esx1_datastore_2")
    assert group_matches_host(
        seeds["windsor"], "other", wwpns_haystack="51402EC012CFD072"
    )
    assert not group_matches_host(seeds["houston-tx"], "nope")


def test_new_group_id_unique():
    existing = seed_contingency_groups()
    gid = new_group_id("Houston, TX", existing)
    assert gid != "houston-tx"
    assert gid
```

- [ ] **Step 2: Run tests — expect FAIL** (missing module)

Run: `python -m pytest tests/test_contingency_groups_data.py -v`

- [ ] **Step 3: Implement `launchpad/contingency_groups_data.py`**

Include full seed payloads from the design spec. Windsor WWPNs:

```text
PEN_WINESX_VM01: 51402EC012CFD072, 51402EC012CFD073, 51402EC012CFD2BE, 51402EC012CFD2BF
PEN_WINESX_VM02: 51402EC012CFD090, 51402EC012CFD091, 51402EC012CFD2C4, 51402EC012CFD2C5
PEN_WINESX_VM03: 51402EC012C90280, 51402EC012C90281, 51402EC012C904A4, 51402EC012C904A5
```

Windsor UIDs:

```text
WIN_ESX_DataStore_1: 60050768128000A75800000000000000
WIN_ESX_DataStore_2: 60050768128000A75800000000000001
WIN_ESX_DataStore_3: 60050768128000A75800000000000002
```

`new_group_id`: slugify name; if collision append `-2`, `-3`, …

`group_matches_host`: lower-case equality on host names in group OR any WWPN substring match in `wwpns_haystack` (normalized, strip colons/spaces for compare).

- [ ] **Step 4: Run tests — expect PASS**

- [ ] **Step 5: Commit only if user asked**

---

### Task 2: Health server persistence + APIs + seed-on-empty

**Files:**
- Modify: `launchpad/health_server.py`
- Create: `tests/test_health_server_contingency_groups.py`

**Interfaces:**
- Consumes: Task 1 helpers + `CONTINGENCY_GROUPS_SETTING`
- Produces:
  - `HealthServer.contingency_groups_persist_available() -> bool`
  - `HealthServer.get_contingency_groups() -> list[dict]` (seed-write if empty when backend available)
  - `HealthServer.set_contingency_groups(groups) -> list[dict]`
  - `HealthServer.upsert_contingency_group(group) -> list[dict]`
  - `HealthServer.delete_contingency_group(group_id) -> list[dict]`
  - GET `/api/contingency-groups` → `{ groups, persisted }`
  - POST `/api/contingency-groups` body variants
  - GET `/contingency-groups` HTML stub OK to land in Task 4; this task may return 404 for HTML until Task 4 — prefer registering path with placeholder HTML `"ok"` only if needed for smoke; better wait for Task 4 page

- [ ] **Step 1: Write server tests** mirroring `tests/test_health_server_snapshot_overrides.py`:

```python
def test_get_seeds_when_empty(tmp_settings):
    # backend dict storage; get returns 3 seeds and persists them
    ...

def test_upsert_and_delete(tmp_settings):
    ...

def test_persisted_false_without_backend():
    s = HealthServer()
    assert s.contingency_groups_persist_available() is False
```

- [ ] **Step 2: Implement HealthServer methods + GET/POST** next to snapshot-overrides handlers. GET `persisted` uses backend availability (same as overrides fix).

POST:

```python
# { "groups": [...] } replace
# { "group": {...} } upsert
# { "delete_id": "..." } delete
```

503 when locked on write.

- [ ] **Step 3: Run** `python -m pytest tests/test_health_server_contingency_groups.py tests/test_contingency_groups_data.py -q` — expect PASS

- [ ] **Step 4: Commit only if user asked**

---

### Task 3: Excel export

**Files:**
- Create: `launchpad/contingency_groups_export.py`
- Create: `tests/test_contingency_groups_export.py`
- Modify: `launchpad/health_server.py` — GET `/api/contingency-groups-export?id=`

**Interfaces:**
- `build_contingency_groups_workbook(groups: list[dict]) -> Workbook`
- `workbook_to_bytes(wb) -> bytes`

Sheets: Summary, Hosts, Volumes, Maps.

- [ ] **Step 1: Failing test** — workbook has 4 sheets; Windsor host row contains a known WWPN; volume row contains UID.

- [ ] **Step 2: Implement export + wire GET** with content-type xlsx and filename `Contingency_Groups_{stamp}.xlsx` or `Contingency_{id}_{stamp}.xlsx`.

- [ ] **Step 3: pytest PASS**

---

### Task 4: Contingency Groups page UI

**Files:**
- Create: `launchpad/contingency_groups.py` (HTML/JS string + `CONTINGENCY_GROUPS_PATH = "/contingency-groups"`)
- Modify: `launchpad/health_server.py` — serve HTML; import path/html
- Modify: `launchpad/ui/dashboard_view.py` — button + `open_contingency_groups` helper on HealthServer

**UI requirements (from spec):**
- Group dropdown + New group
- Editable summary / hosts (WWPN list) / volumes (UID) / maps
- Save, Save as new, Delete, Export Excel, Open in FC WWPN (`/fc-wwpn?group=<id>`)
- localStorage cache key `launchpad.contingencyGroups` + debounced/API load like notes
- Planning-only footer text

- [ ] **Step 1: Implement page** following `snapshot_schedule.py` / `fc_wwpn_report.py` dark theme patterns (match existing CSS variables).

- [ ] **Step 2: Wire dashboard button** labeled `Contingency Groups` near FC WWPN.

- [ ] **Step 3: Add** `HealthServer.contingency_groups_url` + `open_contingency_groups()` always `webbrowser.open` (same reopen fix as other reports).

- [ ] **Step 4: Verify** `python -c "from launchpad.contingency_groups import CONTINGENCY_GROUPS_HTML; assert 'houston-tx' not in CONTINGENCY_GROUPS_HTML or True"` — seeds come from API not hardcoded in HTML. Assert API paths and button labels exist in HTML.

- [ ] **Step 5: node --check** extracted script if Node available.

---

### Task 5: FC WWPN filter + version bump

**Files:**
- Modify: `launchpad/fc_wwpn_report.py`
- Modify: `launchpad/config.py` → `APP_VERSION = "1.6.19"`
- Modify: design spec status → Implemented (optional)

**FC page:**
- Load groups from `/api/contingency-groups`
- Dropdown Contingency group
- Read `?group=` query param to preselect
- Client filter using same rules as Python helpers (duplicate small JS matchers; keep behavior aligned with tests)
- Link “Edit groups” → `/contingency-groups`
- Stretch if quick: “Save selection as group” — optional; skip if timeboxed (note in report)

- [ ] **Step 1: Implement filter UI + JS**

- [ ] **Step 2: Bump version to 1.6.19**

- [ ] **Step 3: Run full related pytest:**

```powershell
python -m pytest tests/test_contingency_groups_data.py tests/test_contingency_groups_export.py tests/test_health_server_contingency_groups.py -q
python -c "from launchpad.config import APP_VERSION; assert APP_VERSION=='1.6.19'"
```

- [ ] **Step 4: Manual checklist** (document in report): unlock → Contingency Groups → edit WWPN → Save → FC filter Houston → Export Excel

---

## Spec coverage checklist

| Spec item | Task |
|-----------|------|
| Seeds Houston/Hartford/Windsor | 1, 2 |
| Editable WWPN/UID | 4 |
| Persist + seed-on-empty | 2 |
| Save / Save as new / Delete | 2, 4 |
| Contingency Groups page + dashboard | 4 |
| FC filter + query param | 5 |
| Excel export | 3 |
| Version bump | 5 |

## Placeholder / consistency self-review

- Setting key, seed ids, and APP_VERSION consistent across tasks.
- No TBD steps; commit optional per session rules.
- Capture-from-FC marked optional stretch in Task 5.
