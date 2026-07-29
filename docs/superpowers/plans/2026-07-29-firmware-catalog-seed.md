# Firmware Catalog Recommended Seed Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a built-in IBM/HPE firmware catalog seed and an Admin **Load recommended catalog seed** button that version-sort–merges it into existing catalogs (v1.6.75), plus HPE Current normalization for match.

**Architecture:** Static `firmware_catalog_seed.py` builds per-profile lists from locked FlashSystem union + HPE `3.3.1.648 (MU5)`. `merge_seed_into_catalog` reuses `insert_version_sorted`. Admin button merges and saves. HPE live Current strips `+P…` before enrich/auto-grow.

**Tech Stack:** Python, CustomTkinter Admin, pytest.

**Spec:** `docs/superpowers/specs/2026-07-29-firmware-catalog-seed-design.md`

## Global Constraints

- **Worktree:** `.worktrees/firmware-catalog-seed` on `feature/firmware-catalog-seed` from `feature/contingency-groups` tip (include design `d02cb8f` or later)
- Shared per-profile catalogs; merge-insert only (never delete)
- FlashSystem union exact list from spec; HPE base `3.3.1.648 (MU5)` for all `HPE_SHELL_PROFILES`
- HPE live Current normalized same as seed before match/grow
- No IBM URL, License Key, DS8884 seed, or per-site catalogs
- Bump `APP_VERSION` to **1.6.75**
- Commit at each task’s commit step
- Run from: `cd C:\Users\BrianColley\LaunchPad\.worktrees\firmware-catalog-seed`

---

## File map

| File | Responsibility |
|------|----------------|
| `launchpad/firmware_catalog_seed.py` | Static seed; `recommended_firmware_seed()` |
| `launchpad/firmware_catalog.py` | `normalize_hpe_firmware_version`; `merge_seed_into_catalog` |
| `launchpad/system_connectivity.py` | Normalize HPE Current in parse/enrich path |
| `launchpad/ui/admin_view.py` | Seed button + status |
| `launchpad/config.py` | `1.6.75` |
| Tests | Seed, merge, HPE normalize, Admin, version |

---

### Task 0: Confirm baseline

**Files:** none

- [ ] **Step 1: Create worktree**

```powershell
cd C:\Users\BrianColley\LaunchPad
git worktree add .worktrees/firmware-catalog-seed -b feature/firmware-catalog-seed feature/contingency-groups
cd .worktrees/firmware-catalog-seed
python -c "from launchpad.config import APP_VERSION; print(APP_VERSION)"
Test-Path docs\superpowers\specs\2026-07-29-firmware-catalog-seed-design.md
```

Expected: tip ≥ `1.6.74`, spec `True`.

- [ ] **Step 2: No feature commit**

---

### Task 1: Seed module + merge + HPE normalize (TDD)

**Files:**
- Create: `launchpad/firmware_catalog_seed.py`
- Modify: `launchpad/firmware_catalog.py`
- Create: `tests/test_firmware_catalog_seed.py`

**Interfaces:**
- Produces:
  - `FLASHSYSTEM_SEED_VERSIONS: tuple[str, ...]` — exact ordered union from spec
  - `HPE_SEED_VERSION = "3.3.1.648 (MU5)"`
  - `recommended_firmware_seed() -> dict[str, list[str]]` — every `SVC_PROFILES` key → list(FLASHSYSTEM…); every `HPE_SHELL_PROFILES` key → `[HPE_SEED_VERSION]`; no DS8884
  - `normalize_hpe_firmware_version(raw: str) -> str` — strip after first `+`; trim; blank stays blank
  - `merge_seed_into_catalog(catalog: dict[str, list[str]], seed: dict[str, list[str]]) -> tuple[dict[str, list[str]], int]` — for each seed profile/version call `insert_version_sorted`; return updated catalog + insert count

- [ ] **Step 1: Write failing tests**

```python
from launchpad.firmware_catalog import (
    merge_seed_into_catalog,
    normalize_hpe_firmware_version,
)
from launchpad.firmware_catalog_seed import (
    FLASHSYSTEM_SEED_VERSIONS,
    HPE_SEED_VERSION,
    recommended_firmware_seed,
)
from launchpad.storage_presets import HPE_SHELL_PROFILES, SVC_PROFILES


def test_flashsystem_seed_contains_spec_union():
    required = {
        "7.8.1.8", "7.8.1.16", "8.2.1.11", "8.4.0.20",
        "8.6.0.2", "8.6.0.7", "8.6.0.9", "8.6.0.11",
        "8.6.1.0", "8.6.2.1", "8.6.3.0", "8.7.0.3", "8.7.0.13",
    }
    assert required.issubset(set(FLASHSYSTEM_SEED_VERSIONS))
    assert list(FLASHSYSTEM_SEED_VERSIONS) == sorted(
        FLASHSYSTEM_SEED_VERSIONS,
        key=lambda v: __import__("launchpad.firmware_catalog", fromlist=["version_sort_key"]).version_sort_key(v),
    )


def test_recommended_seed_covers_svc_and_hpe_profiles():
    seed = recommended_firmware_seed()
    for profile in SVC_PROFILES:
        assert seed[profile] == list(FLASHSYSTEM_SEED_VERSIONS)
    for profile in HPE_SHELL_PROFILES:
        assert seed[profile] == [HPE_SEED_VERSION]
    assert "ibm_ds8884" not in seed


def test_normalize_hpe_firmware_version_strips_patches():
    assert (
        normalize_hpe_firmware_version(
            "3.3.1.648 (MU5)+P126,P132,P135,P140,P146,P150,P151,P155,P156"
        )
        == "3.3.1.648 (MU5)"
    )
    assert normalize_hpe_firmware_version("3.3.1.648 (MU5)") == "3.3.1.648 (MU5)"
    assert normalize_hpe_firmware_version("") == ""


def test_merge_seed_inserts_missing_only():
    catalog = {"flashsystem_7300": ["8.6.0.11", "9.9.9.9"]}
    seed = {"flashsystem_7300": ["8.6.0.11", "8.7.0.13"]}
    updated, n = merge_seed_into_catalog(catalog, seed)
    assert n == 1
    assert "8.7.0.13" in updated["flashsystem_7300"]
    assert "9.9.9.9" in updated["flashsystem_7300"]
    _, n2 = merge_seed_into_catalog(updated, seed)
    assert n2 == 0
```

(Prefer importing `version_sort_key` at top of test file instead of inline `__import__`.)

- [ ] **Step 2: Run — expect FAIL**

Run: `pytest tests/test_firmware_catalog_seed.py -v`

- [ ] **Step 3: Implement seed module + helpers**

`firmware_catalog_seed.py`:

```python
from launchpad.storage_presets import HPE_SHELL_PROFILES, SVC_PROFILES

FLASHSYSTEM_SEED_VERSIONS: tuple[str, ...] = (
    "7.8.1.8",
    "7.8.1.16",
    "8.2.1.11",
    "8.4.0.20",
    "8.6.0.2",
    "8.6.0.7",
    "8.6.0.9",
    "8.6.0.11",
    "8.6.1.0",
    "8.6.2.1",
    "8.6.3.0",
    "8.7.0.3",
    "8.7.0.13",
)
HPE_SEED_VERSION = "3.3.1.648 (MU5)"

def recommended_firmware_seed() -> dict[str, list[str]]:
    seed: dict[str, list[str]] = {}
    fs = list(FLASHSYSTEM_SEED_VERSIONS)
    for profile in SVC_PROFILES:
        seed[str(profile)] = list(fs)
    for profile in HPE_SHELL_PROFILES:
        seed[str(profile)] = [HPE_SEED_VERSION]
    return seed
```

In `firmware_catalog.py`:

```python
def normalize_hpe_firmware_version(raw: str) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""
    base, _sep, _rest = text.partition("+")
    return base.strip()

def merge_seed_into_catalog(
    catalog: dict[str, list[str]],
    seed: dict[str, list[str]],
) -> tuple[dict[str, list[str]], int]:
    updated = {k: list(v) for k, v in (catalog or {}).items()}
    inserted = 0
    for profile, versions in (seed or {}).items():
        key = str(profile or "").strip().lower()
        if not key:
            continue
        current = list(updated.get(key) or [])
        for version in versions or []:
            current, did = insert_version_sorted(current, version)
            if did:
                inserted += 1
        updated[key] = current
    return updated, inserted
```

- [ ] **Step 4: Run — expect PASS**

Run: `pytest tests/test_firmware_catalog_seed.py tests/test_firmware_catalog.py tests/test_firmware_catalog_auto_grow.py -q`

- [ ] **Step 5: Commit**

```powershell
git add launchpad/firmware_catalog_seed.py launchpad/firmware_catalog.py tests/test_firmware_catalog_seed.py
git commit -m "Add recommended firmware catalog seed and merge helpers."
```

---

### Task 2: Apply HPE normalize on live Current

**Files:**
- Modify: `launchpad/system_connectivity.py` (`parse_hpe_showversion_firmware` and/or `enrich_firmware_row` callers — normalize HPE current when profile is HPE)
- Modify: `tests/test_system_connectivity_firmware.py`

**Interfaces:**
- Consumes: `normalize_hpe_firmware_version`
- Prefer: after HPE parser returns `current`, normalize it before return (or in enrich when vendor/profile is HPE). Simplest: normalize inside `parse_hpe_showversion_firmware` on the captured version string.

- [ ] **Step 1: Failing test**

```python
from launchpad.system_connectivity import parse_hpe_showversion_firmware

def test_hpe_showversion_normalizes_patch_suffix():
    output = "Version: 3.3.1.648 (MU5)+P126,P132\n"
    configured, status, details, current = parse_hpe_showversion_firmware(output)
    assert configured == "yes"
    assert current == "3.3.1.648 (MU5)"
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Normalize in parser**

- [ ] **Step 4: Run firmware parser tests — PASS**

- [ ] **Step 5: Commit**

```powershell
git add launchpad/system_connectivity.py tests/test_system_connectivity_firmware.py
git commit -m "Normalize HPE firmware Current by stripping +P patch lists."
```

---

### Task 3: Admin Load recommended catalog seed button

**Files:**
- Modify: `launchpad/ui/admin_view.py`
- Modify: `tests/test_firmware_catalog_admin.py`

**Interfaces:**
- Button text: **Load recommended catalog seed**
- Hint: *Merges built-in IBM/HPE release lists into each profile; does not remove your entries.*
- On click: load DB catalog → `merge_seed_into_catalog(..., recommended_firmware_seed())` → save if N>0 → refresh in-memory map + UI list → status `Seed merged: N new version(s).` or `Seed already up to date.`

- [ ] **Step 1: Failing source asserts**

```python
def test_admin_has_load_recommended_catalog_seed():
    source = (Path(__file__).parents[1] / "launchpad" / "ui" / "admin_view.py").read_text(encoding="utf-8")
    assert "Load recommended catalog seed" in source
    assert "Merges built-in IBM/HPE release lists into each profile" in source
    assert "recommended_firmware_seed" in source
    assert "merge_seed_into_catalog" in source
```

- [ ] **Step 2–4: Implement + tests PASS**

- [ ] **Step 5: Commit**

```powershell
git add launchpad/ui/admin_view.py tests/test_firmware_catalog_admin.py
git commit -m "Add Admin button to load recommended firmware catalog seed."
```

---

### Task 4: Version bump 1.6.75

**Files:**
- Modify: `launchpad/config.py`
- Modify: `tests/test_system_connectivity_version.py`

- [ ] **Step 1–3:** Failing version test → set `APP_VERSION = "1.6.75"` → focused suite PASS

```powershell
pytest tests/test_firmware_catalog_seed.py tests/test_firmware_catalog.py tests/test_firmware_catalog_auto_grow.py tests/test_firmware_catalog_admin.py tests/test_system_connectivity_firmware.py tests/test_system_connectivity_version.py -q
```

- [ ] **Step 4: Commit**

```powershell
git add launchpad/config.py tests/test_system_connectivity_version.py
git commit -m "Bump LaunchPad to 1.6.75 for firmware catalog recommended seed."
```

---

## Spec coverage checklist

| Spec item | Task |
|-----------|------|
| FlashSystem union seed | 1 |
| HPE `3.3.1.648 (MU5)` | 1 |
| Merge insert-only | 1, 3 |
| HPE live normalize | 2 |
| Admin button + status | 3 |
| Version 1.6.75 | 4 |
| No IBM URL / License / DS seed | Global |

---

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-29-firmware-catalog-seed.md`. Two execution options:

**1. Subagent-Driven (recommended)** — fresh subagent per task, review between tasks  
**2. Inline Execution** — execute in this session with checkpoints  

Which approach?
