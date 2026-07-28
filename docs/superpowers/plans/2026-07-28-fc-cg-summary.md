# FlashCopy CG Summary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show a shared FlashCopy CG summary (policy, FC map count, host map count, total size, snaps/week) on FlashCopy CGs and as a read-only Contingency section.

**Architecture:** New `fc_cg_summary` helper builds summary rows from CG/map/size inventory, `lshostvdiskmap`, and Snapshot Schedule interval for the card. HealthServer attaches `summaries` to FC inventory and exposes a Contingency summary API. Both HTML pages render the same fields (counts/totals only in v1).

**Tech Stack:** Python HealthServer, `fc_consistgrp_ops`, Contingency/FC HTML+JS, pytest.

**Spec:** `docs/superpowers/specs/2026-07-28-fc-cg-summary-design.md`

## Global Constraints

- **Worktree:** `.worktrees/fc-cg-summary` on `feature/fc-cg-summary` from `feature/contingency-groups` tip (includes design commit)
- Shared summary fields: `name`, `status`, `policy`, `fc_map_count`, `host_map_count`, `total_size`, `total_size_bytes`, `snaps_per_week`, `snaps_source` (`array`|`schedule`|`none`)
- Policy from extra `lsfcconsistgrp` columns when present; else empty / UI `—`
- Host maps = count of `lshostvdiskmap` rows whose volume is a **target** of this CG’s member maps
- Size = existing member **source** size sum
- Snaps/week: array field if present; else `7 / schedule_days` for the card; held/no data → label not a number
- v1 thin slice only (no Contingency host-map detail tables)
- Bump `APP_VERSION` to **1.6.69**
- Commit at each task’s commit step
- Run from: `cd C:\Users\BrianColley\LaunchPad\.worktrees\fc-cg-summary`

---

## File map

| File | Responsibility |
|------|----------------|
| `launchpad/fc_cg_summary.py` | Build summaries; policy text; host-map counts; snaps/week |
| `launchpad/fc_consistgrp_ops.py` | Parse optional policy columns on CGs; optionally collect host maps in inventory |
| `launchpad/health_server.py` | Enrich FC inventory with summaries; Contingency summary API |
| `launchpad/fc_consistgrp.py` | CG table columns Policy / Host maps / Size / Snaps/week |
| `launchpad/contingency_groups.py` | Read-only Array FlashCopy CG summary section |
| `launchpad/config.py` | `1.6.69` |
| Tests | Summary unit, FC inventory, Contingency API, page contracts |

---

### Task 0: Confirm baseline

**Files:** none

- [ ] **Step 1: Create worktree**

```powershell
cd C:\Users\BrianColley\LaunchPad
git fetch origin
git worktree add .worktrees/fc-cg-summary -b feature/fc-cg-summary feature/contingency-groups
cd .worktrees/fc-cg-summary
python -c "from launchpad.config import APP_VERSION; print(APP_VERSION)"
Test-Path docs\superpowers\specs\2026-07-28-fc-cg-summary-design.md
```

Expected: `1.6.68` (or tip), spec `True`.

- [ ] **Step 2: No feature commit**

---

### Task 1: Shared CG summary helpers (TDD)

**Files:**
- Create: `launchpad/fc_cg_summary.py`
- Create: `tests/test_fc_cg_summary.py`
- Modify: `launchpad/fc_consistgrp_ops.py` (`parse_lsfcconsistgrp` to capture policy-ish columns into `policy`)

**Interfaces:**
- Produces:
  - `format_cg_policy(record_fields: dict[str, str]) -> str` — join non-empty known keys (`copy_rate`, `autodelete`, `relationship`, `starting_status`, `policy`) with ` · `; unknown empty → `""`
  - `schedule_interval_days(used_pct: float, threshold: float = 80.0) -> int` — mirror Snapshot Schedule JS: `max(2, round(2 + (used_pct/threshold clamped 0..1) * 19))`
  - `snaps_per_week_from_days(days: int) -> float` — `round(7 / days, 2)` with `days >= 1`
  - `count_host_maps_for_targets(host_maps: list[dict], target_volumes: set[str]) -> int` — count rows whose `volume`/`vdisk`/`vdisk_name` is in targets
  - `build_cg_summaries(*, groups, maps, host_maps, schedule: dict | None) -> list[dict]`
    - `schedule` shape: `{"days": int|None, "held": bool, "label": str}` (label used when held/no data)
    - For each group: set `fc_map_count` from membership; `host_map_count` from targets; `total_size`/`total_size_bytes` via existing `sum_source_size_bytes` + `format_cg_total_size` helpers already in `fc_consistgrp_ops`; `policy` from group; snaps from `group.get("snaps_per_week")` if numeric else schedule

- [ ] **Step 1: Failing tests**

```python
from launchpad.fc_cg_summary import (
    build_cg_summaries,
    count_host_maps_for_targets,
    schedule_interval_days,
    snaps_per_week_from_days,
)

def test_schedule_interval_and_snaps_week():
    assert schedule_interval_days(0, 80) == 2
    assert snaps_per_week_from_days(7) == 1.0
    assert snaps_per_week_from_days(14) == 0.5

def test_host_map_count_only_targets():
    host_maps = [
        {"volume": "vol_a_snap", "host": "h1"},
        {"volume": "other", "host": "h2"},
        {"volume": "vol_a_snap", "host": "h3"},
    ]
    assert count_host_maps_for_targets(host_maps, {"vol_a_snap"}) == 2

def test_build_cg_summaries_schedule_fallback():
    groups = [{"name": "CG1", "status": "empty", "policy": "", "map_count": 0}]
    maps = [
        {
            "name": "m1",
            "source": "src1",
            "target": "tgt1",
            "consistgrp": "CG1",
            "source_size": "10 GB",
            "source_size_bytes": 10 * (1024**3),
        }
    ]
    host_maps = [{"volume": "tgt1", "host": "h1"}]
    rows = build_cg_summaries(
        groups=groups,
        maps=maps,
        host_maps=host_maps,
        schedule={"days": 7, "held": False, "label": "WEEKLY"},
    )
    assert len(rows) == 1
    assert rows[0]["fc_map_count"] == 1
    assert rows[0]["host_map_count"] == 1
    assert rows[0]["snaps_per_week"] == 1.0
    assert rows[0]["snaps_source"] == "schedule"
```

- [ ] **Step 2: Run — expect FAIL**

```powershell
python -m pytest tests/test_fc_cg_summary.py -v
```

- [ ] **Step 3: Implement `fc_cg_summary.py` + extend `parse_lsfcconsistgrp`**

In `parse_lsfcconsistgrp`, after building the base dict, set:

```python
policy = format_cg_policy(record)  # or inline join of known keys from record
# store as "policy": policy
```

Keep `format_cg_policy` importable from `fc_cg_summary` to avoid circular imports — prefer parsing raw optional keys in `parse_lsfcconsistgrp` with a small local join, and also export `format_cg_policy` for tests.

- [ ] **Step 4: Tests PASS**

- [ ] **Step 5: Commit**

```powershell
git add launchpad/fc_cg_summary.py launchpad/fc_consistgrp_ops.py tests/test_fc_cg_summary.py
git commit -m "Add FlashCopy CG summary helpers for policy, host maps, and snaps/week."
```

---

### Task 2: Enrich FC inventory + Contingency summary API

**Files:**
- Modify: `launchpad/fc_consistgrp_ops.py` (`collect_fc_consistgrp_inventory` — also run `lshostvdiskmap` OR keep host maps collection in HealthServer only)
- Modify: `launchpad/health_server.py`
- Modify: `tests/test_health_server_fc_consistgrp.py` (or create `tests/test_fc_cg_summary_api.py`)

**Interfaces:**
- `HealthServer.fc_consistgrp_inventory` return also includes `"summaries": [...]` and may include `"host_maps"` internally.
- New: `HealthServer.contingency_fc_cg_summary(group_id: str) -> dict`  
  - Resolve group → card via storage_hint/name (`find_card_by_hint`)  
  - Unlock required for SSH (same as Sync) — if locked, clear error  
  - Collect inventory + host maps; build schedule dict from card capacity (`pool_capacity_from_commands` / monitor results: max or primary pool `used_pct`, threshold default 80; overrides/held from `get_snapshot_overrides` if present for card name)  
  - Return `{"ok": True, "card": {...}, "summaries": [...], "warnings": []}`

Prefer collecting host maps inside `fc_consistgrp_inventory` via extra SSH call:

```python
host_out = run_cmd("svcinfo lshostvdiskmap -delim :")
host_maps = parse_host_lun_maps(host_out)
summaries = build_cg_summaries(groups=groups, maps=maps, host_maps=host_maps, schedule=schedule)
```

Schedule attachment: helper `schedule_context_for_card(server, card) -> dict` in `fc_cg_summary.py` or health_server method.

- [ ] **Step 1: API tests** — inventory includes summaries keys; contingency summary resolves card / unknown group

- [ ] **Step 2: Implement**

POST or GET: `GET /api/contingency-groups/fc-cg-summary?group_id=` (GET is fine for read-only). Register in `_HealthHandler.do_GET`.

- [ ] **Step 3: Tests PASS**

```powershell
python -m pytest tests/test_fc_cg_summary.py tests/test_health_server_fc_consistgrp.py -q
```

- [ ] **Step 4: Commit**

```powershell
git commit -m "Attach CG summaries to FlashCopy inventory and Contingency summary API."
```

---

### Task 3: FlashCopy CGs UI columns

**Files:**
- Modify: `launchpad/fc_consistgrp.py`
- Modify: `tests/test_fc_consistgrp_page.py` (or existing page test)

**UI:**
- Groups table header: `Name | Status | Maps | Host maps | Size | Policy | Snaps/week`
- Render from `inventory.summaries` when present; else fall back to `inventory.groups` with blanks for new fields
- Selection still by CG name (radio on summary/group name)
- Member maps panel unchanged
- Optional hint: `Snaps/week from Snapshot Schedule` when any row has `snaps_source === "schedule"`

- [ ] **Step 1: Failing page contract tests** for new headers / field names in HTML+JS

- [ ] **Step 2: Implement renderGroups to use summaries**

```javascript
const rows = (inventory.summaries && inventory.summaries.length)
  ? inventory.summaries
  : (inventory.groups || []);
// columns: name, status, fc_map_count||map_count, host_map_count, total_size, policy, snaps_per_week
```

- [ ] **Step 3: Tests PASS**

- [ ] **Step 4: Commit**

```powershell
git commit -m "Show CG policy, host maps, size, and snaps/week on FlashCopy CGs."
```

---

### Task 4: Contingency Groups summary section

**Files:**
- Modify: `launchpad/contingency_groups.py`
- Modify: `tests/test_contingency_groups_page.py`

**UI:**
- After group metadata (Name/Location/Storage hint/Notes), add:

```html
<section class="section" id="fc-cg-summary-section">
  <div class="section-head">
    <h2>Array FlashCopy CG summary</h2>
    <button type="button" id="fc-cg-summary-refresh" class="secondary">Refresh CG summary</button>
  </div>
  <p class="hint">Live FlashCopy Consistency Groups on the linked array (read-only). Manage membership on <a href="/fc-consistgrp">FlashCopy CGs</a>.</p>
  <div class="table-wrap">
    <table>
      <thead><tr>
        <th>Name</th><th>Status</th><th>Maps</th><th>Host maps</th><th>Size</th><th>Policy</th><th>Snaps/week</th>
      </tr></thead>
      <tbody id="fc-cg-summary-body">
        <tr><td colspan="7" class="empty">Click Refresh CG summary (Unlock required).</td></tr>
      </tbody>
    </table>
  </div>
  <p class="hint" id="fc-cg-summary-status"></p>
</section>
```

- JS: on Refresh (and after successful Sync), `GET /api/contingency-groups/fc-cg-summary?group_id=` and render rows.
- Do not require Source volumes to be non-empty.

- [ ] **Step 1: Page contract tests**

- [ ] **Step 2: Implement**

- [ ] **Step 3: Tests PASS**

- [ ] **Step 4: Commit**

```powershell
git commit -m "Add Contingency read-only Array FlashCopy CG summary section."
```

---

### Task 5: Version bump 1.6.69

**Files:**
- Modify: `launchpad/config.py`

- [ ] **Step 1:** `APP_VERSION = "1.6.69"`

- [ ] **Step 2: Related suites**

```powershell
python -m pytest tests/test_fc_cg_summary.py tests/test_health_server_fc_consistgrp.py tests/test_fc_consistgrp_page.py tests/test_contingency_groups_page.py -q
```

- [ ] **Step 3: Commit**

```powershell
git commit -m "Bump version to 1.6.69 for FlashCopy CG summary."
```

---

### Task 6: Final review + PR

- [ ] Spec checklist green
- [ ] PR into `feature/contingency-groups`

```powershell
git push -u origin HEAD
gh pr create --base feature/contingency-groups --title "FlashCopy CG summary on FC CGs + Contingency (v1.6.69)" --body "## Summary
- Shared CG summary: policy, FC maps, host maps, size, snaps/week
- FlashCopy CGs table columns
- Contingency read-only Array FlashCopy CG summary
- Version 1.6.69

## Test plan
- [ ] pytest related suites
- [ ] FlashCopy CGs Refresh shows new columns
- [ ] Contingency stub site: Refresh CG summary without Source volumes
- [ ] Snaps/week matches Snapshot Schedule when no array field
"
```

---

## Spec coverage (self-review)

| Spec item | Task |
|-----------|------|
| Shared summary fields | 1 |
| Policy parse | 1 |
| Host map counts | 1–2 |
| Size totals | 1–2 (reuse existing) |
| Snaps/week array\|schedule | 1–2 |
| FlashCopy CGs columns | 3 |
| Contingency read-only section | 4 |
| Version 1.6.69 | 5 |
| PR | 6 |
