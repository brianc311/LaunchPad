# Firmware Catalog Auto-Grow from Live Scans Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When Admin enables “Auto-add firmware from live scans,” System Connectivity Refresh live inserts unseen Current versions into each device_profile catalog by version-sort, saves once, and reports how many were added (v1.6.74).

**Architecture:** Extend `firmware_catalog.py` with auto-add setting load/save, version-key compare, sorted insert, and batch grow. Call grow inside `scan_system_connectivity_live` before enrich when enabled. Admin Firmware catalog tab gets the checkbox. Manual catalog editing unchanged.

**Tech Stack:** Python, CustomTkinter Admin, HealthServer live scan, pytest.

**Spec:** `docs/superpowers/specs/2026-07-29-firmware-catalog-auto-grow-design.md`

## Global Constraints

- **Worktree:** `.worktrees/firmware-catalog-auto-grow` on `feature/firmware-catalog-auto-grow` from `feature/contingency-groups` tip (include design commit `c87a873` or later)
- Auto-add setting default **off**; Refresh never mutates catalog when off
- Insert only non-empty Current missing from that profile; version-sort placement; no full re-sort of existing list beyond inserting the new string
- Batch save once per Refresh if N > 0; status `Catalog updated: N new version(s).`
- No vendor portal download
- Bump `APP_VERSION` to **1.6.74**
- Commit at each task’s commit step
- Run from: `cd C:\Users\BrianColley\LaunchPad\.worktrees\firmware-catalog-auto-grow`

---

## File map

| File | Responsibility |
|------|----------------|
| `launchpad/firmware_catalog.py` | Setting + version-sort insert + grow_catalog_from_currents |
| `launchpad/health_server.py` | Grow during live scan when enabled; expose catalog_updates in payload/status |
| `launchpad/system_connectivity_page.py` | Show catalog-update status when N > 0 (if payload carries it) |
| `launchpad/ui/admin_view.py` | Checkbox + hint; load/save setting |
| `launchpad/config.py` | `1.6.74` |
| Tests | Sort/insert/grow/setting/page/admin/version |

---

### Task 0: Confirm baseline

**Files:** none

- [ ] **Step 1: Create worktree**

```powershell
cd C:\Users\BrianColley\LaunchPad
git worktree add .worktrees/firmware-catalog-auto-grow -b feature/firmware-catalog-auto-grow feature/contingency-groups
cd .worktrees/firmware-catalog-auto-grow
python -c "from launchpad.config import APP_VERSION; print(APP_VERSION)"
Test-Path docs\superpowers\specs\2026-07-29-firmware-catalog-auto-grow-design.md
```

Expected: tip ≥ `1.6.73`, spec `True`.

- [ ] **Step 2: No feature commit**

---

### Task 1: Version-sort insert + auto-add setting + grow helper (TDD)

**Files:**
- Modify: `launchpad/firmware_catalog.py`
- Create: `tests/test_firmware_catalog_auto_grow.py`

**Interfaces:**
- Produces:
  - `FIRMWARE_AUTO_ADD_SETTING = "firmware_auto_add_from_scans"`
  - `load_firmware_auto_add(db) -> bool` — missing/empty/falsey → `False`; truthy `"1"|"true"|"yes"|"on"` → `True`
  - `save_firmware_auto_add(db, enabled: bool) -> bool` — store `"true"` / `"false"`; return normalized bool
  - `version_sort_key(version: str) -> tuple` — comparable key for semver-ish ordering
  - `insert_version_sorted(versions: list[str], new_version: str) -> tuple[list[str], bool]` — returns `(new_list, inserted)`; blank → no-op; duplicate → no-op `False`; else insert so list ascending by `version_sort_key`; equal keys → insert after last equal (deterministic)
  - `grow_catalog_from_currents(catalog: dict[str, list[str]], currents: list[tuple[str, str]]) -> tuple[dict[str, list[str]], int]` — each `(profile, current)`; skip blank profile/current; apply insert per profile; return `(updated_catalog, total_inserted_count)` without DB I/O

- [ ] **Step 1: Write failing tests**

```python
from launchpad.firmware_catalog import (
    grow_catalog_from_currents,
    insert_version_sorted,
    load_firmware_auto_add,
    save_firmware_auto_add,
    version_sort_key,
)


class _FakeDB:
    def __init__(self):
        self._s = {}

    def get_setting(self, key, default=""):
        return self._s.get(key, default)

    def set_setting(self, key, value):
        self._s[key] = value


def test_insert_version_sorted_middle_start_end():
    assert insert_version_sorted(["8.5.0", "8.6.1"], "8.6.0") == (
        ["8.5.0", "8.6.0", "8.6.1"],
        True,
    )
    assert insert_version_sorted(["8.6.0", "8.6.1"], "8.5.0") == (
        ["8.5.0", "8.6.0", "8.6.1"],
        True,
    )
    assert insert_version_sorted(["8.5.0", "8.6.0"], "8.6.1") == (
        ["8.5.0", "8.6.0", "8.6.1"],
        True,
    )


def test_insert_version_sorted_duplicate_and_blank():
    assert insert_version_sorted(["8.6.0"], "8.6.0") == (["8.6.0"], False)
    assert insert_version_sorted(["8.6.0"], "") == (["8.6.0"], False)
    assert insert_version_sorted(["8.6.0"], "  ") == (["8.6.0"], False)


def test_grow_catalog_from_currents_counts_inserts():
    catalog = {"flashsystem_7300": ["8.5.0", "8.6.1"]}
    updated, n = grow_catalog_from_currents(
        catalog,
        [
            ("flashsystem_7300", "8.6.0"),
            ("flashsystem_7300", "8.6.0"),  # dup in batch
            ("flashsystem_7300", "8.6.1"),  # already present
            ("", "9.0.0"),
            ("flashsystem_7300", ""),
        ],
    )
    assert n == 1
    assert updated["flashsystem_7300"] == ["8.5.0", "8.6.0", "8.6.1"]


def test_auto_add_setting_default_off_and_persist():
    db = _FakeDB()
    assert load_firmware_auto_add(db) is False
    assert save_firmware_auto_add(db, True) is True
    assert load_firmware_auto_add(db) is True
    assert save_firmware_auto_add(db, False) is False
    assert load_firmware_auto_add(db) is False
```

- [ ] **Step 2: Run — expect FAIL**

Run: `pytest tests/test_firmware_catalog_auto_grow.py -v`  
Expected: FAIL (symbols missing)

- [ ] **Step 3: Implement in `firmware_catalog.py`**

```python
FIRMWARE_AUTO_ADD_SETTING = "firmware_auto_add_from_scans"

def load_firmware_auto_add(db) -> bool:
    raw = str(db.get_setting(FIRMWARE_AUTO_ADD_SETTING, "") or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}

def save_firmware_auto_add(db, enabled: bool) -> bool:
    value = bool(enabled)
    db.set_setting(FIRMWARE_AUTO_ADD_SETTING, "true" if value else "false")
    return value

def version_sort_key(version: str) -> tuple:
    import re
    parts = re.split(r"(\d+)", str(version or "").strip())
    key = []
    for part in parts:
        if not part:
            continue
        if part.isdigit():
            key.append((0, int(part)))
        else:
            key.append((1, part.lower()))
    return tuple(key)

def insert_version_sorted(versions: list[str], new_version: str) -> tuple[list[str], bool]:
    new_v = str(new_version or "").strip()
    out = list(versions)
    if not new_v or new_v in out:
        return out, False
    new_key = version_sort_key(new_v)
    idx = 0
    while idx < len(out) and version_sort_key(out[idx]) <= new_key:
        idx += 1
    out.insert(idx, new_v)
    return out, True

def grow_catalog_from_currents(
    catalog: dict[str, list[str]],
    currents: list[tuple[str, str]],
) -> tuple[dict[str, list[str]], int]:
    updated = {k: list(v) for k, v in (catalog or {}).items()}
    inserted = 0
    for profile, current in currents:
        profile_key = str(profile or "").strip().lower()
        cur = str(current or "").strip()
        if not profile_key or not cur:
            continue
        existing = list(updated.get(profile_key) or [])
        new_list, did = insert_version_sorted(existing, cur)
        if did:
            updated[profile_key] = new_list
            inserted += 1
    return updated, inserted
```

(Place `import re` at module top — no inline imports.)

- [ ] **Step 4: Run — expect PASS**

Run: `pytest tests/test_firmware_catalog_auto_grow.py tests/test_firmware_catalog.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add launchpad/firmware_catalog.py tests/test_firmware_catalog_auto_grow.py
git commit -m "Add firmware catalog version-sort grow helpers and auto-add setting."
```

---

### Task 2: Wire Refresh live grow + status

**Files:**
- Modify: `launchpad/health_server.py` (`scan_system_connectivity_live`, settings view for set_setting if needed)
- Modify: `launchpad/system_connectivity_page.py` (show `catalog_updates` in status when present)
- Create/extend: `tests/test_firmware_catalog_auto_grow_scan.py`

**Interfaces:**
- Consumes: Task 1 helpers; existing `_firmware_catalog_for_scan`, scan loops
- Produces: payload may include `"catalog_updates": N` (int); when auto-add on, catalog mutated+saved before enrich so behind counts use new entries

**Algorithm in `scan_system_connectivity_live`:**
1. Load catalog as today.
2. Load auto-add via same `_SettingsView` pattern (extend view with `set_setting` when getter/setter available — mirror how other settings persist from HealthServer; if only get_setting exists on callback, use app DB path already used by `_get_setting` / add `_set_setting` if present, or grow in-memory then save through a small adapter that calls both get and set on the registered settings hooks).
3. Run card scans collecting firmware Currents into `currents: list[tuple[profile, current]]` **or** two-phase: first scan into topic_rows, then if auto-add: grow from firmware rows’ `(profile, current)`, save, **re-enrich** firmware rows with updated catalog.
4. Preferred simpler path: **two-phase after all scans** — gather `(profile, current)` from `topic_rows["firmware"]` where current non-empty; if auto-add and currents: `updated, n = grow_catalog_from_currents(catalog, currents)`; if n>0: `save_firmware_catalog(db_view, updated)`; then re-map firmware rows through `enrich_firmware_row` with updated profile lists; set `payload["catalog_updates"] = n`.
5. Page JS: if `data.catalog_updates > 0`, append `Catalog updated: N new version(s).` to status text.

Inspect HealthServer for `_get_setting` / `_set_setting` (or equivalent). If no setter, register one the same way getter is registered from the app, or save via a DB handle already available — follow existing Capacity Email / settings patterns in this codebase.

- [ ] **Step 1: Failing test**

```python
from launchpad.firmware_catalog import (
    grow_catalog_from_currents,
    save_firmware_catalog,
    load_firmware_auto_add,
    save_firmware_auto_add,
)
from launchpad.system_connectivity_page import SYSTEM_CONNECTIVITY_HTML


def test_page_mentions_catalog_updated_status_handling():
    assert "catalog_updates" in SYSTEM_CONNECTIVITY_HTML or "Catalog updated:" in SYSTEM_CONNECTIVITY_HTML


def test_grow_then_behind_uses_new_entry():
    catalog = {"flashsystem_7300": ["8.5.0"]}
    updated, n = grow_catalog_from_currents(
        catalog, [("flashsystem_7300", "8.6.0")]
    )
    assert n == 1
    from launchpad.firmware_catalog import versions_behind
    assert versions_behind("8.5.0", updated["flashsystem_7300"]) == "1"
```

(Also add a HealthServer unit test if settings adapter is mockable — otherwise keep grow logic tested here and assert scan payload key in a focused fake if already patterned in `test_system_connectivity_firmware_api.py`.)

- [ ] **Step 2: Run — expect FAIL**

Run: `pytest tests/test_firmware_catalog_auto_grow_scan.py -v`  
Expected: FAIL on page assert until JS/status wired

- [ ] **Step 3: Implement scan grow + page status**

- [ ] **Step 4: Run related tests — PASS**

```powershell
pytest tests/test_firmware_catalog_auto_grow.py tests/test_firmware_catalog_auto_grow_scan.py tests/test_system_connectivity_firmware_api.py tests/test_system_connectivity_page.py -q
```

- [ ] **Step 5: Commit**

```powershell
git add launchpad/health_server.py launchpad/system_connectivity_page.py tests/test_firmware_catalog_auto_grow_scan.py
git commit -m "Auto-grow firmware catalog on System Connectivity refresh when enabled."
```

---

### Task 3: Admin checkbox UI

**Files:**
- Modify: `launchpad/ui/admin_view.py` (`_build_firmware_catalog_panel`)
- Create/extend: `tests/test_firmware_catalog_admin.py`

**Interfaces:**
- Consumes: `load_firmware_auto_add`, `save_firmware_auto_add`
- Produces: `CTkCheckBox` labeled **Auto-add firmware from live scans**; hint text from spec; load on panel build; save when toggled **or** when user clicks a dedicated apply — prefer toggle saves immediately (simplest) **or** save with catalog Save button. Spec: persisted setting — **save immediately on toggle** for clarity.

- [ ] **Step 1: Failing source test**

```python
from pathlib import Path


def test_admin_firmware_auto_add_checkbox():
    source = (
        Path(__file__).parents[1] / "launchpad" / "ui" / "admin_view.py"
    ).read_text(encoding="utf-8")
    assert "Auto-add firmware from live scans" in source
    assert "save_firmware_auto_add" in source
    assert "load_firmware_auto_add" in source
    assert "When on, Refresh live inserts unseen Current" in source
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Add checkbox + hint under the existing Firmware Catalog description (before Profile row); wire command to save setting and status label**

- [ ] **Step 4: Run admin + auto-grow tests — PASS**

- [ ] **Step 5: Commit**

```powershell
git add launchpad/ui/admin_view.py tests/test_firmware_catalog_admin.py
git commit -m "Add Admin checkbox for firmware auto-add from live scans."
```

---

### Task 4: Version bump 1.6.74

**Files:**
- Modify: `launchpad/config.py`
- Modify: `tests/test_system_connectivity_version.py`

- [ ] **Step 1: Failing version test → `assert APP_VERSION == "1.6.74"`**

- [ ] **Step 2: Set `APP_VERSION = "1.6.74"`**

- [ ] **Step 3: Run focused suite**

```powershell
pytest tests/test_firmware_catalog.py tests/test_firmware_catalog_auto_grow.py tests/test_firmware_catalog_auto_grow_scan.py tests/test_firmware_catalog_admin.py tests/test_system_connectivity_firmware.py tests/test_system_connectivity_firmware_api.py tests/test_system_connectivity_page.py tests/test_system_connectivity_version.py -q
```

Expected: all PASS

- [ ] **Step 4: Commit**

```powershell
git add launchpad/config.py tests/test_system_connectivity_version.py
git commit -m "Bump LaunchPad to 1.6.74 for firmware catalog auto-grow."
```

---

## Spec coverage checklist

| Spec item | Task |
|-----------|------|
| Auto-add setting default off | 1, 3 |
| Version-sort insert | 1 |
| Grow on Refresh when on | 2 |
| No mutate when off | 1, 2 |
| Status `Catalog updated: N…` | 2 |
| Admin checkbox + hint | 3 |
| Manual catalog unchanged | 3 (no removal of existing controls) |
| Version 1.6.74 | 4 |

---

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-29-firmware-catalog-auto-grow.md`. Two execution options:

**1. Subagent-Driven (recommended)** — fresh subagent per task, review between tasks  
**2. Inline Execution** — execute in this session with checkpoints  

Which approach?
