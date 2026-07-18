# Contingency Source → Target Wizard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the table-first Contingency Groups UX with an easy Source → Target → Create & Map wizard while keeping Advanced edit and the existing `_snap` Preview/Run Create engine.

**Architecture:** Mostly a UI redesign in `contingency_groups.py`. Small pure helpers in `contingency_groups_data.py` filter source volumes, build source/target pairs, and validate step readiness. Existing generate/preview/create APIs remain unchanged. Wizard step is client-only state.

**Tech Stack:** Embedded HTML/CSS/JS in Contingency Groups page, existing contingency APIs, pytest page-contract tests.

**Spec:** `docs/superpowers/specs/2026-07-18-contingency-source-target-wizard-design.md`

## Global Constraints

- Three steps exactly: **1 Source · 2 Target · 3 Create & Map**.
- Advanced edit tables remain available (toggle).
- Reuse `generate-snaps`, `snap-preview`, `snap-create` — no new create engine.
- Wizard step is client-only (no DB field).
- Keep modal `[hidden]` CSS fix (`display:none !important`).
- Save-before-snap-ops remains.
- Bump `APP_VERSION` to `1.6.21` in the final task.
- Do not commit unless the user asked for commits in this session.
- Skip optional **Refresh from array** unless time remains after core wizard (stretch only).

---

## File map

| File | Responsibility |
|------|----------------|
| `launchpad/contingency_groups_data.py` | `source_volumes`, `snap_pairs`, `validate_wizard_step1/2` helpers |
| `tests/test_contingency_groups_data.py` | Tests for helpers |
| `launchpad/contingency_groups.py` | Wizard UI + Advanced toggle |
| `tests/test_contingency_groups_page.py` | Wizard contract strings |
| `launchpad/config.py` | `1.6.21` |

---

### Task 1: Pure helpers for wizard views + validation

**Files:**
- Modify: `launchpad/contingency_groups_data.py`
- Modify: `tests/test_contingency_groups_data.py`

**Interfaces:**
- `is_snap_volume(vol: dict) -> bool`
- `source_volumes(group: dict) -> list[dict]`  # role != snap and name not ending `_snap`
- `source_maps_for_volume(group: dict, volume_name: str) -> list[dict]`
- `snap_pairs(group: dict) -> list[dict]`  
  each: `{ "source": vol, "target": vol|None, "maps": [snap maps] }`
- `validate_wizard_step1(group: dict) -> list[str]`  # blocking messages
- `validate_wizard_step2(group: dict) -> list[str]`  # every source has target

Step1 rules (match snap create readiness for planning create):
- ≥1 source volume
- each source has non-empty name
- each source has non-empty pool and capacity (blocking — same as create needing size/pool)

- [ ] **Step 1: Write failing tests**

```python
from launchpad.contingency_groups_data import (
    seed_contingency_groups,
    snap_pairs,
    source_volumes,
    validate_wizard_step1,
    validate_wizard_step2,
)


def test_source_volumes_exclude_snaps():
    hartford = next(g for g in seed_contingency_groups() if g["id"] == "hartford-ct")
    sources = source_volumes(hartford)
    assert sources
    assert all(not str(v["name"]).endswith("_snap") for v in sources)
    assert all(str(v.get("role") or "source") != "snap" for v in sources)


def test_snap_pairs_link_source_to_target():
    hartford = next(g for g in seed_contingency_groups() if g["id"] == "hartford-ct")
    pairs = snap_pairs(hartford)
    assert pairs
    for pair in pairs:
        assert pair["target"] is not None
        assert pair["target"]["name"] == f"{pair['source']['name']}_snap"


def test_validate_step1_requires_pool_capacity():
    group = {
        "volumes": [{"name": "V1", "role": "source", "pool": "", "capacity": ""}],
        "maps": [],
    }
    warnings = validate_wizard_step1(group)
    assert warnings


def test_validate_step2_requires_targets():
    group = {
        "volumes": [{"name": "V1", "role": "source", "pool": "P0", "capacity": "4.00 TiB"}],
        "maps": [],
    }
    assert validate_wizard_step2(group)
```

- [ ] **Step 2: Implement helpers; pytest PASS**

- [ ] **Step 3: Commit only if user asked**

---

### Task 2: Wizard shell UI (steps, Back/Next, Advanced toggle)

**Files:**
- Modify: `launchpad/contingency_groups.py`
- Modify: `tests/test_contingency_groups_page.py`

**UI structure:**
1. Hero keeps picker + Save / Save as new / Delete / Export / FC WWPN / Health link.
2. Add progress bar: `1 Source · 2 Target · 3 Create & Map` with active state.
3. Add **Back** / **Next** buttons.
4. Wrap existing Hosts/Volumes/Maps sections in `#advanced-panel` (hidden by default).
5. Add toggle button **Advanced edit** / **Hide advanced**.
6. Add `#wizard-panel` with three step panels (`#wizard-step-1`, `#wizard-step-2`, `#wizard-step-3`).
7. `let wizardStep = 1;` client-only; reset to 1 on group change.

**Behavior:**
- `render()` updates wizard panels + advanced tables.
- Next: run validation for current step; if warnings, show in `#wizard-errors` and stay; else `wizardStep++`.
- Back: `wizardStep = max(1, wizardStep-1)`.
- Summary fields (name/location/storage hint/notes) stay visible above wizard (needed in Step 1).

- [ ] **Step 1: Implement shell + contract tests** asserting strings:
  - `1 Source`
  - `2 Target`
  - `3 Create & Map`
  - `wizard-step-1`
  - `advanced-panel`
  - `Advanced edit`
  - `wizardStep`

- [ ] **Step 2: node --check** extracted script if available

- [ ] **Step 3: Commit only if user asked**

---

### Task 3: Step 1 Source + Step 2 Target panels

**Files:**
- Modify: `launchpad/contingency_groups.py`

**Step 1 content:**
- Storage hint field already in summary (emphasize in step copy).
- Editable table of **source volumes only** (name, pool, capacity) — edits write back into `group.volumes` by name/index.
- Read-only or simple list of source maps (volume, host, scsi) for those sources.
- “Add source volume” button appends a source-role volume.
- On Next from Step 1: `validate_wizard_step1` (port logic to JS mirroring Python rules — duplicate small validators in JS to avoid round-trip).

**Step 2 content:**
- On entering Step 2 (Next from 1): call existing `generateSnapRows()` / generate-snaps API so targets exist (reuse current generate handler).
- Side-by-side table: Source | Target | Pool | Capacity (edit target name/pool/capacity; keep `source_volume` link).
- On Next: every source has a target (`validate_wizard_step2` in JS).

- [ ] **Step 1: Implement Step 1–2 render + edit bindings**

- [ ] **Step 2: Page tests** assert source-only wording / pair table headers (`Source`, `Target`)

- [ ] **Step 3: Manual mental check** — Hartford seed shows 3 sources then 3 pairs after generate

---

### Task 4: Step 3 Create & Map + relocate snap buttons

**Files:**
- Modify: `launchpad/contingency_groups.py`
- Modify: `launchpad/config.py` → `1.6.21`
- Optional: mark wizard design Status Implemented

**Step 3 content:**
- Plain-language checklist (4 bullets from spec).
- Pair summary: Source → Target → Hosts/SCSI → note that Preview will mark create vs skip.
- Move **Preview / Dry-run** and **Run Create** into Step 3 (remove from hero or leave duplicates — prefer **only in Step 3** to reduce clutter; keep **Generate _snap rows** available in Step 2 as secondary).
- Reuse existing `previewSnaps` / `runSnapCreate` / modal.
- If `storage_hint` empty: show warning in Step 3; Preview/Run stay blocked by existing API.

**Version:** `APP_VERSION = "1.6.21"`

- [ ] **Step 1: Implement Step 3 + relocate hero snap buttons into wizard**

- [ ] **Step 2: Regression**

```powershell
python -m pytest tests/test_contingency_groups_data.py tests/test_contingency_groups_page.py tests/test_contingency_snap_create.py tests/test_health_server_contingency_snap.py -q
python -c "from launchpad.config import APP_VERSION; assert APP_VERSION=='1.6.21'"
```

- [ ] **Step 3: Commit only if user asked**

---

## Spec coverage checklist

| Spec item | Task |
|-----------|------|
| Progress 1/2/3 + Back/Next | 2 |
| Advanced edit toggle | 2 |
| Step 1 source volumes + maps + validation | 1, 3 |
| Step 2 pairs + generate snaps | 3 |
| Step 3 checklist + Preview/Run | 4 |
| Reuse existing snap APIs | 3, 4 |
| Modal hidden CSS preserved | 2 (do not regress) |
| Version 1.6.21 | 4 |
| Refresh from array | Stretch — skip unless free time |

## Placeholder / consistency self-review

- No new create CLI; wizard is UX over existing engine.
- Commit steps optional per session rules.
- Stretch refresh-sources explicitly deferred.
