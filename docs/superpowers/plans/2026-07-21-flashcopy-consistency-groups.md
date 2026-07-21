# FlashCopy Consistency Groups Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a top-level LaunchPad browser page to list and manage IBM FlashCopy Consistency Groups on a selected SSH FlashSystem card, with Preview → confirm → Run for all mutations.

**Architecture:** New `fc_consistgrp_ops.py` parses `lsfcconsistgrp` / `lsfcmap` and builds CLI steps (reuse `SnapStep` + `run_snap_steps` + `cli_token` from `contingency_snap_create`). Health server serves `/fc-consistgrp` HTML and inventory/preview/run APIs over card SSH. Dashboard opens the page; page has its own card picker.

**Tech Stack:** Python 3, embedded HTML/JS (Contingency Groups styling), existing health-server SSH helpers, pytest.

**Spec:** `docs/superpowers/specs/2026-07-21-flashcopy-consistency-groups-design.md`

## Global Constraints

- New top-level page path: `/fc-consistgrp` (not inside Contingency Groups)
- Full edit: view, create CG, assign maps, remove maps, prepare+start CG, delete **empty** CG only
- Array selection: Dashboard shortcut **and** in-page card picker
- Mutations: Preview never writes; Run requires `confirm: true`
- CLI: `svcinfo lsfcconsistgrp` / `lsfcmap`; `svctask mkfcconsistgrp`, `chfcmap -consistgrp …`, `prestartfcconsistgrp`, `startfcconsistgrp`, `rmfcconsistgrp`
- Remove from CG: `svctask chfcmap -consistgrp null MAPNAME`
- Reuse `SnapStep`, `cli_token`, `run_snap_steps` from `launchpad.contingency_snap_create`
- Do not create FlashCopy maps/volumes here; do not change Contingency Group seeds
- Bump `APP_VERSION` one patch from Task 0 baseline in the final task
- Commit at each task’s commit step; imports at top of modules

---

## File map

| File | Responsibility |
|------|----------------|
| `launchpad/fc_consistgrp_ops.py` | Parse inventory; build preview/run steps; action validation |
| `launchpad/fc_consistgrp.py` | `FC_CONSISTGRP_PATH`, HTML/JS page |
| `launchpad/health_server.py` | Routes + inventory/preview/run methods + `open_fc_consistgrp` |
| `launchpad/ui/dashboard_view.py` | **FlashCopy CGs** button |
| Nav bars in existing report pages | Link to `/fc-consistgrp` |
| `launchpad/config.py` | Version bump |
| `tests/test_fc_consistgrp_ops.py` | Parser + step builder tests |
| `tests/test_health_server_fc_consistgrp.py` | API tests with mocks |

---

### Task 0: Branch / worktree

**Files:** none (git only)

**Interfaces:**
- Consumes: `feature/contingency-groups` tip (includes design commit)
- Produces: `feature/fc-consistgrp` worktree

- [ ] **Step 1: Create worktree**

```powershell
cd C:\Users\BrianColley\LaunchPad
git fetch origin
git worktree add .worktrees/fc-consistgrp -b feature/fc-consistgrp feature/contingency-groups
cd .worktrees/fc-consistgrp
```

- [ ] **Step 2: Record baseline version**

```powershell
python -c "from launchpad.config import APP_VERSION; print(APP_VERSION)"
```

Note printed version; final task bumps one patch (e.g. `1.6.41` → `1.6.42`).

- [ ] **Step 3: No commit**

---

### Task 1: Inventory parsers

**Files:**
- Create: `launchpad/fc_consistgrp_ops.py`
- Test: `tests/test_fc_consistgrp_ops.py`

**Interfaces:**
- Consumes: `launchpad.flashsystem_fc._get`, `_table_records`
- Produces:
  - `parse_lsfcconsistgrp(output: str) -> list[dict]` keys: `id`, `name`, `status`, `map_count` (string or int ok; normalize count to int when numeric)
  - `parse_lsfcmap_rows(output: str) -> list[dict]` keys: `id`, `name`, `source`, `target`, `status`, `progress`, `consistgrp`
  - `partition_maps(maps: list[dict]) -> tuple[list[dict], list[dict]]` → `(in_groups, stand_alone)` where stand-alone has empty/`0`/`no`/`none` consistgrp (case-insensitive); treat blank as stand-alone
  - `enrich_group_map_counts(groups: list[dict], maps: list[dict]) -> list[dict]` sets `map_count` from maps when missing/zero preferred from membership

Sample delimited header styles follow existing FlashSystem tables (`id:name:status:…`). Use `_table_records` like `parse_lsfcmap_names`.

- [ ] **Step 1: Write failing tests**

```python
from launchpad.fc_consistgrp_ops import (
    enrich_group_map_counts,
    parse_lsfcconsistgrp,
    parse_lsfcmap_rows,
    partition_maps,
)

CG_SAMPLE = """id:name:status:FC_mapping_count
0:AWD1_AS400_CG:idle_or_copied:6
1:empty_cg:empty:0
"""

MAP_SAMPLE = """id:name:source_vdisk_name:target_vdisk_name:status:progress:group_name
0:fcmap0:AWD1_AS400_1:AWD1_AS400_1_Snap1:copied:100:AWD1_AS400_CG
1:fcmap1:AWD1_AS400_2:AWD1_AS400_2_Snap2:copied:100:AWD1_AS400_CG
2:standalone1:VOL_A:VOL_A_snap:idle_or_copied:0:
"""


def test_parse_lsfcconsistgrp():
    groups = parse_lsfcconsistgrp(CG_SAMPLE)
    assert groups[0]["name"] == "AWD1_AS400_CG"
    assert groups[0]["status"] == "idle_or_copied"
    assert int(groups[0]["map_count"]) == 6


def test_parse_lsfcmap_rows_and_partition():
    maps = parse_lsfcmap_rows(MAP_SAMPLE)
    assert maps[0]["source"] == "AWD1_AS400_1"
    assert maps[0]["consistgrp"] == "AWD1_AS400_CG"
    in_g, alone = partition_maps(maps)
    assert {m["name"] for m in alone} == {"standalone1"}
    assert len(in_g) == 2


def test_enrich_group_map_counts():
    groups = parse_lsfcconsistgrp(CG_SAMPLE)
    maps = parse_lsfcmap_rows(MAP_SAMPLE)
    enriched = enrich_group_map_counts(groups, maps)
    awd = next(g for g in enriched if g["name"] == "AWD1_AS400_CG")
    assert awd["map_count"] == 2  # from membership in sample
```

Note: For `group_name` vs `consistgrp` column names, `_get(record, "group_name", "consistgrp", "FC_group_name", "fc_group_name")` in parser.

- [ ] **Step 2: Run RED**

```powershell
python -m pytest tests/test_fc_consistgrp_ops.py -v
```

Expected: FAIL (module missing).

- [ ] **Step 3: Implement parsers in `fc_consistgrp_ops.py`**

Implement the four functions. Keep file focused on ops (step builders come in Task 2).

- [ ] **Step 4: Run GREEN**

```powershell
python -m pytest tests/test_fc_consistgrp_ops.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add launchpad/fc_consistgrp_ops.py tests/test_fc_consistgrp_ops.py
git commit -m "Add FlashCopy consistency group inventory parsers."
```

---

### Task 2: Preview/run step builders

**Files:**
- Modify: `launchpad/fc_consistgrp_ops.py`
- Test: `tests/test_fc_consistgrp_ops.py`

**Interfaces:**
- Consumes: `SnapStep`, `cli_token` from `contingency_snap_create`; inventory lists from Task 1
- Produces:
  - `ACTIONS = frozenset({"create_group","assign_maps","remove_maps","start_group","delete_group"})`
  - `build_fc_consistgrp_steps(action: str, payload: dict, *, groups: list[dict], maps: list[dict]) -> tuple[list[SnapStep], list[str]]`

Rules:

| action | Steps | Warnings / blocks |
|--------|-------|-------------------|
| `create_group` | `mkfcconsistgrp -name NAME` | skip if name exists; error if name empty/unsafe |
| `assign_maps` | one `chfcmap -consistgrp CG MAP` per map | warn if map already in another CG; skip if already in target; error if CG/map missing |
| `remove_maps` | `chfcmap -consistgrp null MAP` | skip if already stand-alone; error if map missing |
| `start_group` | `prestartfcconsistgrp` then `startfcconsistgrp` | error if CG missing |
| `delete_group` | `rmfcconsistgrp NAME` | **refuse** (warning, no steps / ok=False path) if any map still in group; skip if CG already absent |

Return warnings list; callers treat non-empty blocking warnings as preview `ok: false` when no executable steps and errors present — define helper:

- `preview_ok(steps, warnings) -> bool`: `True` when there are no hard errors. Use convention: warnings starting with `ERROR:` are hard; others advisory. Or return `(steps, warnings, errors)` — **prefer** `(steps, warnings)` where delete-non-empty adds warning `ERROR: Consistency group NAME is not empty` and returns **empty steps**.

- [ ] **Step 1: Append failing builder tests**

```python
from launchpad.contingency_snap_create import SnapStep
from launchpad.fc_consistgrp_ops import build_fc_consistgrp_steps, parse_lsfcconsistgrp, parse_lsfcmap_rows

def _inv():
    return parse_lsfcconsistgrp(CG_SAMPLE), parse_lsfcmap_rows(MAP_SAMPLE)


def test_create_group_skips_existing():
    groups, maps = _inv()
    steps, warnings = build_fc_consistgrp_steps(
        "create_group", {"name": "AWD1_AS400_CG"}, groups=groups, maps=maps
    )
    assert len(steps) == 1 and steps[0].skip
    assert "mkfcconsistgrp" in steps[0].cmd


def test_assign_and_remove_and_start():
    groups, maps = _inv()
    steps, _ = build_fc_consistgrp_steps(
        "assign_maps",
        {"group_name": "AWD1_AS400_CG", "map_names": ["standalone1"]},
        groups=groups,
        maps=maps,
    )
    assert any("chfcmap -consistgrp AWD1_AS400_CG standalone1" in s.cmd for s in steps)
    steps, _ = build_fc_consistgrp_steps(
        "remove_maps", {"map_names": ["fcmap0"]}, groups=groups, maps=maps
    )
    assert any("chfcmap -consistgrp null fcmap0" in s.cmd for s in steps)
    steps, _ = build_fc_consistgrp_steps(
        "start_group", {"group_name": "AWD1_AS400_CG"}, groups=groups, maps=maps
    )
    assert [s.kind for s in steps] == ["prestartfcconsistgrp", "startfcconsistgrp"]


def test_delete_non_empty_refused():
    groups, maps = _inv()
    steps, warnings = build_fc_consistgrp_steps(
        "delete_group", {"group_name": "AWD1_AS400_CG"}, groups=groups, maps=maps
    )
    assert steps == []
    assert any(w.startswith("ERROR:") for w in warnings)


def test_delete_empty_ok():
    groups, maps = _inv()
    steps, warnings = build_fc_consistgrp_steps(
        "delete_group", {"group_name": "empty_cg"}, groups=groups, maps=maps
    )
    assert len(steps) == 1 and "rmfcconsistgrp empty_cg" in steps[0].cmd
    assert not any(w.startswith("ERROR:") for w in warnings)
```

- [ ] **Step 2: Run RED**

```powershell
python -m pytest tests/test_fc_consistgrp_ops.py -v
```

- [ ] **Step 3: Implement `build_fc_consistgrp_steps`**

Use `cli_token` on all names. Kind strings match command verbs for log clarity.

- [ ] **Step 4: Run GREEN + commit**

```powershell
python -m pytest tests/test_fc_consistgrp_ops.py -v
git add launchpad/fc_consistgrp_ops.py tests/test_fc_consistgrp_ops.py
git commit -m "Add FlashCopy consistency group preview/run step builders."
```

---

### Task 3: Health server APIs + open helper

**Files:**
- Modify: `launchpad/health_server.py`
- Create: `launchpad/fc_consistgrp.py` (minimal HTML stub is OK if Task 4 fills UI — **prefer** ship path constant + placeholder page that says “Loading…” and card picker wired enough for API smoke)
- Test: `tests/test_health_server_fc_consistgrp.py`

**Interfaces:**
- `FC_CONSISTGRP_PATH = "/fc-consistgrp"`
- GET page returns HTML
- GET `/api/fc-consistgrp/cards` → list SSH cards `{id,name,host}` from registered health cards (unlocked)
- GET `/api/fc-consistgrp/inventory?card_id=` → run SSH inventory; return groups/maps/stand_alone/warnings
- POST `/api/fc-consistgrp/preview` body `{card_id, action, ...}` → steps payload like contingency snap
- POST `/api/fc-consistgrp/run` body `{card_id, action, confirm: true, ...}` → reject if confirm is not true; else run_snap_steps
- `HealthServer.open_fc_consistgrp(card_id: int | None = None) -> str` URL with optional `?card=`

Reuse `_snap_run_command(card)` / inventory collection pattern: collect with delimited + fallback for both `lsfcconsistgrp` and `lsfcmap`.

- [ ] **Step 1: Failing API tests** with fake settings backend and monkeypatched SSH runner on server methods (follow `tests/test_health_server_contingency_snap.py` style).

Cover at minimum:

1. Run without confirm → ok False  
2. Delete non-empty via preview → warnings ERROR, no executable steps / ok False  
3. Preview create_group returns mkfcconsistgrp step  

- [ ] **Step 2: Implement routes + methods + minimal page HTML**

Wire GET HTML in the same place Contingency Groups HTML is served. Add nav link stubs later in Task 5.

- [ ] **Step 3: GREEN + commit**

```powershell
python -m pytest tests/test_fc_consistgrp_ops.py tests/test_health_server_fc_consistgrp.py -v
git add launchpad/fc_consistgrp.py launchpad/fc_consistgrp_ops.py launchpad/health_server.py tests/test_health_server_fc_consistgrp.py
git commit -m "Add FlashCopy consistency group health-server APIs."
```

---

### Task 4: Full browser UI

**Files:**
- Modify: `launchpad/fc_consistgrp.py` (replace stub with full UI)

**Interfaces:**
- Consumes Task 3 APIs
- Produces operator UI per spec: card picker, Refresh, CG table, member maps, stand-alone maps, actions, Preview/Run modal

Match Contingency Groups visual language (CSS variables, modal, step list, warnings).

JS behaviors:

1. On load: fetch cards; if `?card=` query present, select it  
2. On card change / Refresh: fetch inventory; render tables  
3. Selecting a CG filters member maps  
4. Actions collect form state → POST preview → show modal; enable Run only when preview ok (or when steps exist and no ERROR warnings — match Contingency snap: Run enabled when preview returned ok)  
5. Run posts `confirm: true` then shows log; Refresh inventory after success  

Actions UI:

- Create: name input + Create CG  
- Assign: multi-select stand-alone maps + Assign to selected CG  
- Remove: multi-select member maps + Remove from CG  
- Start: Start selected CG  
- Delete: Delete selected CG  

- [ ] **Step 1: Implement HTML/JS** in `fc_consistgrp.py`

- [ ] **Step 2: No mandatory pytest for UI** — keep API tests green

```powershell
python -m pytest tests/test_fc_consistgrp_ops.py tests/test_health_server_fc_consistgrp.py -v
```

- [ ] **Step 3: Commit**

```powershell
git add launchpad/fc_consistgrp.py
git commit -m "Add FlashCopy consistency groups browser UI."
```

---

### Task 5: Dashboard button + cross-page nav links

**Files:**
- Modify: `launchpad/ui/dashboard_view.py`
- Modify nav bars in: `launchpad/health_server.py` (main health HTML if it has nav), `launchpad/capacity_report.py`, `launchpad/contingency_groups.py`, `launchpad/snapshot_schedule.py`, `launchpad/fc_wwpn_report.py` — add `<a class="btn secondary" href="/fc-consistgrp">FlashCopy CGs</a>` beside existing links

**Interfaces:**
- `_open_fc_consistgrp` mirrors `_open_contingency_groups`: `ensure_health_dashboard_registered`, `get_health_server().open_fc_consistgrp()`, status text that this page **does** mutate arrays after confirm

- [ ] **Step 1: Add Dashboard button** near Contingency Groups button, label `FlashCopy CGs`

- [ ] **Step 2: Add nav links** on sibling pages

- [ ] **Step 3: Commit**

```powershell
git add launchpad/ui/dashboard_view.py launchpad/health_server.py launchpad/capacity_report.py launchpad/contingency_groups.py launchpad/snapshot_schedule.py launchpad/fc_wwpn_report.py
git commit -m "Wire FlashCopy CGs dashboard entry and nav links."
```

---

### Task 6: Version bump and regression

**Files:**
- Modify: `launchpad/config.py`

- [ ] **Step 1: Bump** `APP_VERSION` to Task 0 baseline + one patch

- [ ] **Step 2: Full suite**

```powershell
python -m pytest tests
```

Expected: all PASS.

- [ ] **Step 3: Commit**

```powershell
git add launchpad/config.py
git commit -m "Bump version for FlashCopy consistency groups."
```

---

## Spec coverage checklist

| Requirement | Task |
|-------------|------|
| Parsers for CG + map inventory | Task 1 |
| Create/assign/remove/start/delete steps + empty-only delete | Task 2 |
| APIs inventory/preview/run + confirm gate | Task 3 |
| Top-level page UI + card picker + Preview/Run | Task 4 |
| Dashboard shortcut + nav links | Task 5 |
| Version bump | Task 6 |
| No Contingency seed / no mkfcmap volume create | (non-goals) |
