# Contingency Snap Assign to FlashCopy CG Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** After Contingency Groups Run Create, optionally create-or-reuse an array FlashCopy CG and assign only this run’s new FlashCopy maps into it.

**Architecture:** Extend `build_snap_steps` / preview-create pipeline with optional CG steps. Persist `snap_assign_cg_name` / `snap_assign_cg_enabled` on the Contingency group; Preview/Run also accept request overrides so an unsaved name change still applies. Advisory CG messages must not block Run Create (fix UI `blocking` to use `data.ok` only).

**Tech Stack:** Python HealthServer, Contingency Groups HTML/JS, `SnapStep` runner, `fc_consistgrp_ops` parsers, pytest.

**Spec:** `docs/superpowers/specs/2026-07-25-contingency-snap-assign-cg-design.md`

## Global Constraints

- **Worktree:** `.worktrees/contingency-snap-assign-cg` on `feature/contingency-snap-assign-cg` from `feature/contingency-groups` (include design commit `7d47154` or merge tip)
- Optional assign only; checkbox off = unchanged snap create behavior
- Missing CG → `mkfcconsistgrp`; existing CG → advisory “already exists — will assign into it” (not blocking)
- Assign only maps with a **non-skipped** `mkfcmap` and/or `startfcmap` step in this preview
- Map already in target CG → skip assign; map in **other** CG → advisory warn + **skip** (do not steal)
- Empty CG name with checkbox on → blocking `ERROR:`
- No eligible maps → advisory only; snap create may still proceed
- Persist fields on group; API may override per request
- Bump `APP_VERSION` to **1.6.67**
- Commit at each task’s commit step
- Run from: `cd C:\Users\BrianColley\LaunchPad\.worktrees\contingency-snap-assign-cg`

---

## File map

| File | Responsibility |
|------|----------------|
| `launchpad/contingency_groups_data.py` | Normalize/persist `snap_assign_cg_name`, `snap_assign_cg_enabled` |
| `launchpad/contingency_snap_create.py` | `maps_touched_this_run`, `append_snap_cg_assign_steps` |
| `launchpad/health_server.py` | Collect FC CG inventory; pass assign options into preview/create |
| `launchpad/contingency_groups.py` | Checkbox + CG name UI; save/load; Preview/Run payload; advisory vs blocking |
| `launchpad/config.py` | `1.6.67` |
| Tests | Normalize, step builder, API, UI chrome |

---

### Task 0: Confirm baseline

**Files:** none

- [ ] **Step 1: Create worktree**

```powershell
cd C:\Users\BrianColley\LaunchPad
git fetch origin
git worktree add .worktrees/contingency-snap-assign-cg -b feature/contingency-snap-assign-cg feature/contingency-groups
cd .worktrees/contingency-snap-assign-cg
python -c "from launchpad.config import APP_VERSION; print(APP_VERSION)"
Test-Path docs\superpowers\specs\2026-07-25-contingency-snap-assign-cg-design.md
```

Expected: `1.6.66` (or tip), spec path `True`.

- [ ] **Step 2: No feature commit**

---

### Task 1: Persist assign fields on Contingency group (TDD)

**Files:**
- Modify: `launchpad/contingency_groups_data.py` (`normalize_group`)
- Modify: `tests/test_contingency_groups_data.py` (or create if missing — prefer existing normalize tests)

**Interfaces:**
- Produces: each normalized group includes:
  - `snap_assign_cg_name: str` (default `""`)
  - `snap_assign_cg_enabled: bool` (default `False`)

- [ ] **Step 1: Failing tests**

```python
from launchpad.contingency_groups_data import normalize_group

def test_normalize_group_defaults_snap_assign_fields():
    group = normalize_group({"id": "windsor", "name": "Windsor"})
    assert group["snap_assign_cg_name"] == ""
    assert group["snap_assign_cg_enabled"] is False

def test_normalize_group_keeps_snap_assign_fields():
    group = normalize_group({
        "id": "windsor",
        "name": "Windsor",
        "snap_assign_cg_name": "WIN_ESX_snap",
        "snap_assign_cg_enabled": True,
    })
    assert group["snap_assign_cg_name"] == "WIN_ESX_snap"
    assert group["snap_assign_cg_enabled"] is True
```

- [ ] **Step 2: Run tests — expect FAIL** (keys missing)

```powershell
python -m pytest tests/test_contingency_groups_data.py -k snap_assign -v
```

- [ ] **Step 3: Implement in `normalize_group` return dict**

```python
"snap_assign_cg_name": str(raw.get("snap_assign_cg_name") or "").strip(),
"snap_assign_cg_enabled": bool(raw.get("snap_assign_cg_enabled")),
```

- [ ] **Step 4: Tests PASS**

- [ ] **Step 5: Commit**

```powershell
git add launchpad/contingency_groups_data.py tests/test_contingency_groups_data.py
git commit -m "Persist Contingency snap assign CG name and enabled flag."
```

---

### Task 2: CG assign step builder (TDD)

**Files:**
- Modify: `launchpad/contingency_snap_create.py`
- Modify: `tests/test_contingency_snap_create.py`

**Interfaces:**
- Produces:
  - `maps_touched_this_run(steps: list[SnapStep]) -> list[str]` — unique fcmap names from non-skipped `mkfcmap` / `startfcmap` (parse map name from cmd: last token of `startfcmap X` or `-name X` of mkfcmap)
  - `append_snap_cg_assign_steps(steps, *, cg_name: str, enabled: bool, fc_groups: list[dict], fc_maps: list[dict]) -> tuple[list[SnapStep], list[str]]`
    - If `enabled` is False → return `(steps, [])` unchanged
    - If `enabled` and empty/unsafe name → return steps + blocking warning `ERROR: …`
    - Else append mkfcconsistgrp (skip if name in groups) + chfcmap for touched maps
    - Advisory (non-`ERROR:`) for: CG already exists; no maps to assign; map in other CG (skip that map); map already in target (skip step)

Reuse `cli_token` and standalone-consistgrp check from `fc_consistgrp_ops` (`_is_standalone_consistgrp` — import public helper or duplicate the small set `{"", "many", "none"}` casefold check already used there). Prefer importing a small public `is_standalone_consistgrp` if present; else add one-liner helper in `contingency_snap_create.py`.

- [ ] **Step 1: Failing tests** (add to `tests/test_contingency_snap_create.py`)

```python
from launchpad.contingency_snap_create import (
    SnapStep,
    append_snap_cg_assign_steps,
    maps_touched_this_run,
)

def test_maps_touched_this_run_only_nonskipped():
    steps = [
        SnapStep("mkfcmap", "create", "svctask mkfcmap -source A -target B -name fc_A_to_B", skip=False),
        SnapStep("startfcmap", "start", "svctask startfcmap fc_A_to_B", skip=False),
        SnapStep("mkfcmap", "create", "svctask mkfcmap -source C -target D -name fc_C_to_D", skip=True),
        SnapStep("startfcmap", "start", "svctask startfcmap fc_C_to_D", skip=True),
    ]
    assert maps_touched_this_run(steps) == ["fc_A_to_B"]

def test_append_cg_assign_off_is_noop():
    base = [SnapStep("mkvdisk", "create", "svctask mkvdisk -name X -mdiskgrp P -size 1 -unit gb")]
    out, warnings = append_snap_cg_assign_steps(
        base, cg_name="WIN_ESX_snap", enabled=False, fc_groups=[], fc_maps=[]
    )
    assert out == base
    assert warnings == []

def test_append_cg_assign_creates_group_and_assigns():
    base = [
        SnapStep("mkfcmap", "create", "svctask mkfcmap -source A -target B -name fc_A_to_B"),
        SnapStep("startfcmap", "start", "svctask startfcmap fc_A_to_B"),
    ]
    out, warnings = append_snap_cg_assign_steps(
        base,
        cg_name="WIN_ESX_snap",
        enabled=True,
        fc_groups=[],
        fc_maps=[{"name": "fc_A_to_B", "consistgrp": ""}],
    )
    kinds = [s.kind for s in out]
    assert "mkfcconsistgrp" in kinds
    assert kinds.count("chfcmap") == 1
    assert not any(w.startswith("ERROR:") for w in warnings)

def test_append_cg_assign_existing_group_advisory():
    base = [
        SnapStep("mkfcmap", "create", "svctask mkfcmap -source A -target B -name fc_A_to_B"),
        SnapStep("startfcmap", "start", "svctask startfcmap fc_A_to_B"),
    ]
    out, warnings = append_snap_cg_assign_steps(
        base,
        cg_name="WIN_ESX_snap",
        enabled=True,
        fc_groups=[{"name": "WIN_ESX_snap"}],
        fc_maps=[{"name": "fc_A_to_B", "consistgrp": ""}],
    )
    cg_steps = [s for s in out if s.kind == "mkfcconsistgrp"]
    assert len(cg_steps) == 1 and cg_steps[0].skip is True
    assert any("already exists" in w.lower() for w in warnings)
    assert not any(w.startswith("ERROR:") for w in warnings)

def test_append_cg_assign_skips_map_in_other_cg():
    base = [
        SnapStep("mkfcmap", "create", "svctask mkfcmap -source A -target B -name fc_A_to_B"),
        SnapStep("startfcmap", "start", "svctask startfcmap fc_A_to_B"),
    ]
    out, warnings = append_snap_cg_assign_steps(
        base,
        cg_name="WIN_ESX_snap",
        enabled=True,
        fc_groups=[{"name": "WIN_ESX_snap"}],
        fc_maps=[{"name": "fc_A_to_B", "consistgrp": "OTHER_CG"}],
    )
    assert not any(s.kind == "chfcmap" and not s.skip for s in out)
    assert any("OTHER_CG" in w for w in warnings)
```

- [ ] **Step 2: Run — expect FAIL**

```powershell
python -m pytest tests/test_contingency_snap_create.py -k "maps_touched or append_cg" -v
```

- [ ] **Step 3: Implement helpers** in `contingency_snap_create.py`

Core logic sketch:

```python
def maps_touched_this_run(steps: list[SnapStep]) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for step in steps:
        if step.skip or step.kind not in {"mkfcmap", "startfcmap"}:
            continue
        name = _fcmap_name_from_cmd(step.cmd)
        if name and name not in seen:
            seen.add(name)
            names.append(name)
    return names

def append_snap_cg_assign_steps(...):
    if not enabled:
        return list(steps), []
    warnings: list[str] = []
    out = list(steps)
    try:
        name = cli_token(cg_name)
    except ValueError:
        warnings.append("ERROR: Assign to CG requires a valid CG name")
        return out, warnings
    group_names = {str(g.get("name") or "") for g in fc_groups}
    maps_by_name = {str(m.get("name") or ""): m for m in fc_maps}
    if name in group_names:
        warnings.append(f'CG "{name}" already exists — will assign maps into it.')
        out.append(SnapStep("mkfcconsistgrp", "create consistency group",
                            f"svctask mkfcconsistgrp -name {name}", skip=True,
                            reason="consistency group already exists"))
    else:
        out.append(SnapStep("mkfcconsistgrp", "create consistency group",
                            f"svctask mkfcconsistgrp -name {name}"))
    touched = maps_touched_this_run(steps)
    if not touched:
        warnings.append("No FlashCopy maps created or started this run to assign.")
        return out, warnings
    for map_name in touched:
        mapping = maps_by_name.get(map_name)
        current = str((mapping or {}).get("consistgrp") or "").strip()
        if current == name:
            out.append(SnapStep("chfcmap", f"assign map {map_name} …",
                                f"svctask chfcmap -consistgrp {name} {map_name}",
                                skip=True, reason=f"map already in {name}"))
            continue
        if current and current.casefold() not in {"", "many", "none"}:
            warnings.append(
                f"Skipping map {map_name}: already in consistency group {current}"
            )
            continue
        # New map may be absent from inventory until after mkfcmap; still plan assign
        out.append(SnapStep("chfcmap", f"assign map {map_name} to consistency group",
                            f"svctask chfcmap -consistgrp {name} {map_name}"))
    return out, warnings
```

- [ ] **Step 4: Tests PASS**

- [ ] **Step 5: Commit**

```powershell
git add launchpad/contingency_snap_create.py tests/test_contingency_snap_create.py
git commit -m "Add Contingency snap steps to create-or-reuse CG and assign maps."
```

---

### Task 3: Wire preview/create APIs

**Files:**
- Modify: `launchpad/health_server.py` (`preview_contingency_snaps`, `create_contingency_snaps`, snap POST handler)
- Modify: `tests/test_health_server_contingency_snap.py`

**Interfaces:**
- `preview_contingency_snaps(group_id, *, assign_cg_enabled: bool | None = None, assign_cg_name: str | None = None)`
  - Resolve enabled/name: request override if not None, else group fields
  - After `build_snap_steps`, if enabled: `collect_fc_consistgrp_inventory(run)` (or parse lsfcconsistgrp + lsfcmap), then `append_snap_cg_assign_steps`
  - `ok = not any(w.startswith("ERROR:") for w in all_warnings) and not blocking_snap_warnings`
  - **Important:** today’s snap warnings (missing pool, etc.) remain blocking. Treat any warning from `build_snap_steps` as blocking (unchanged). Treat assign advisories without `ERROR:` as non-blocking. Combined:

```python
snap_steps, snap_warnings = build_snap_steps(...)
steps, assign_warnings = append_snap_cg_assign_steps(
    snap_steps, cg_name=..., enabled=..., fc_groups=..., fc_maps=...
)
warnings = snap_warnings + assign_warnings
ok = (not snap_warnings) and (not any(w.startswith("ERROR:") for w in assign_warnings))
```

- POST `/api/contingency-groups/snap-preview` and `snap-create` accept optional `snap_assign_cg_enabled` / `snap_assign_cg_name` in JSON body and pass through.

- [ ] **Step 1: Failing API test** — preview with assign enabled adds mkfcconsistgrp when inventory empty of that CG; `ok` True when snap_warnings empty even if advisory present

- [ ] **Step 2: Implement wiring + inventory collect**

```python
from launchpad.fc_consistgrp_ops import collect_fc_consistgrp_inventory
# in preview after build_snap_steps:
enabled = assign_cg_enabled if assign_cg_enabled is not None else bool(group.get("snap_assign_cg_enabled"))
cg_name = assign_cg_name if assign_cg_name is not None else str(group.get("snap_assign_cg_name") or "")
fc_groups, fc_maps = [], []
if enabled:
    try:
        fc_groups, fc_maps = collect_fc_consistgrp_inventory(self._snap_run_command(card))
    except Exception as exc:
        return {..., "ok": False, "warnings": [f"ERROR: Unable to collect FlashCopy CG inventory: {exc}"], ...}
steps, assign_warnings = append_snap_cg_assign_steps(...)
```

- [ ] **Step 3: Tests PASS**

```powershell
python -m pytest tests/test_health_server_contingency_snap.py tests/test_contingency_snap_create.py -q
```

- [ ] **Step 4: Commit**

```powershell
git commit -m "Wire Contingency snap preview/create to optional FlashCopy CG assign."
```

---

### Task 4: Contingency Groups UI

**Files:**
- Modify: `launchpad/contingency_groups.py`
- Create or modify: `tests/test_contingency_groups_page.py` (string asserts on HTML/JS)

**UI:**
- In step 3 Create & Map, above Preview / Run Create:

```html
<label class="hint">
  <input type="checkbox" id="snap-assign-cg-enabled">
  Assign new FlashCopy maps to CG
</label>
<label>CG name <input id="snap-assign-cg-name" type="text" placeholder="e.g. WIN_ESX_snap" disabled></label>
<p class="hint">Optional. Creates the CG if missing, or assigns into it if it already exists. Fine-grained add/remove remains on <a href="/fc-consistgrp">FlashCopy CGs</a>.</p>
```

- `emptyGroup()` includes `snap_assign_cg_name: ""`, `snap_assign_cg_enabled: false`
- On render/select: set checkbox + input from group; enable name input when checked
- On Save / persist before snap ops: write fields into group object
- `previewSnaps` / `runSnapCreate` POST body includes:

```javascript
{
  group_id: currentId,
  snap_assign_cg_enabled: document.getElementById("snap-assign-cg-enabled").checked,
  snap_assign_cg_name: document.getElementById("snap-assign-cg-name").value.trim(),
  confirm: true // create only
}
```

- **Fix blocking logic** (required for advisory warnings):

```javascript
const blocking = !data.ok;  // was: !data.ok || warnings.length > 0
```

Still show all warnings in the modal via existing `snapWarnings(warnings)`.

- [ ] **Step 1: Failing tests** asserting checkbox id, CG name id, FlashCopy CGs hint, and `blocking = !data.ok` present in HTML source

- [ ] **Step 2: Implement UI**

- [ ] **Step 3: Tests PASS**

- [ ] **Step 4: Commit**

```powershell
git commit -m "Add Contingency UI for optional FlashCopy CG assign after snap create."
```

---

### Task 5: Version bump 1.6.67

**Files:**
- Modify: `launchpad/config.py`

- [ ] **Step 1:** `APP_VERSION = "1.6.67"`

- [ ] **Step 2: Related suites**

```powershell
python -m pytest tests/test_contingency_snap_create.py tests/test_health_server_contingency_snap.py tests/test_contingency_groups_data.py -q
# plus page test file from Task 4
```

- [ ] **Step 3: Commit**

```powershell
git commit -m "Bump version to 1.6.67 for Contingency snap assign to FlashCopy CG."
```

---

### Task 6: Final review + PR

- [ ] Full related suite green
- [ ] Spec checklist (checkbox off unchanged; create-or-reuse; this-run maps only; persist fields; 1.6.67)
- [ ] PR into `feature/contingency-groups`

```powershell
git push -u origin HEAD
gh pr create --base feature/contingency-groups --title "Contingency snap assign to FlashCopy CG (v1.6.67)" --body "## Summary
- Optional Assign-to-CG on Contingency Create & Map
- Create CG if missing; reuse with Preview advisory if exists
- Assign only maps created/started this Run Create
- Persist CG name + enabled on Contingency group
- Version 1.6.67

## Test plan
- [ ] pytest related suites
- [ ] Preview with checkbox off — unchanged
- [ ] Preview with new CG name — mkfcconsistgrp + chfcmap in steps
- [ ] Preview with existing CG — advisory + skip create + assign
- [ ] Save group, reload — name/checkbox restored
"
```

---

## Spec coverage (self-review)

| Spec item | Task |
|-----------|------|
| Optional checkbox + CG name | 4 |
| Persist name + enabled | 1, 4 |
| Create if missing / reuse advisory | 2, 3 |
| Only this-run maps | 2 |
| Skip other-CG maps | 2 |
| Advisory must not block Run | 3, 4 |
| Unchanged when off | 2, 3 |
| Version 1.6.67 | 5 |
| PR | 6 |
