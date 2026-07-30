# CG Summary Flash Time + Progress Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Flash time and Progress (min map %) columns to Contingency Array FlashCopy CG summary table + Excel (v**1.6.82**).

**Architecture:** Extend `build_cg_summaries` with `flash_time` and `progress_pct`; update Contingency page render and `fc_cg_summary_export` headers/fields. No new SSH.

**Tech Stack:** Python, pytest, openpyxl (existing export).

**Spec:** `docs/superpowers/specs/2026-07-30-fc-cg-summary-flash-progress-design.md`

## Global Constraints

- **Worktree:** `.worktrees/fc-cg-summary-flash-progress` on `feature/fc-cg-summary-flash-progress` from `feature/contingency-groups` tip (≥ `1.6.81` + both design commits)
- Contingency summary table + Excel only (no Manage/Status UI column work)
- Progress = min of parseable member map progress while status is copying; else None / display `—`
- No end-date column
- Bump `APP_VERSION` to **1.6.82**
- Commit per task; run from worktree

---

## File map

| File | Responsibility |
|------|----------------|
| `launchpad/fc_cg_summary.py` | `flash_time`, `progress_pct` helpers + `build_cg_summaries` |
| `launchpad/contingency_groups.py` | Headers + render |
| `launchpad/fc_cg_summary_export.py` | Headers/fields |
| `launchpad/config.py` | `1.6.82` |
| Tests | Builder, page, export, version |

---

### Task 0: Confirm baseline

```powershell
cd C:\Users\BrianColley\LaunchPad
git worktree add .worktrees/fc-cg-summary-flash-progress -b feature/fc-cg-summary-flash-progress feature/contingency-groups
cd .worktrees\fc-cg-summary-flash-progress
python -c "from launchpad.config import APP_VERSION; print(APP_VERSION)"
Test-Path docs\superpowers\specs\2026-07-30-fc-cg-summary-flash-progress-design.md
```

Expected: ≥ `1.6.81`, spec `True`. No feature commit.

---

### Task 1: Summary builder flash_time + progress (TDD)

**Files:**
- Modify: `launchpad/fc_cg_summary.py`
- Modify: `tests/test_fc_cg_summary.py`

**Interfaces:**
- Produces helper e.g. `min_map_progress_pct(maps: list[dict], *, status: str) -> float | int | None`
- `build_cg_summaries` rows include:
  - `flash_time`: `str(group.get("flash_time") or "")`
  - `progress_pct`: number or `None`

- [ ] **Step 1: Failing tests**

```python
def test_build_cg_summaries_flash_time_and_min_progress_while_copying():
    groups = [
        {
            "name": "CG1",
            "status": "copying",
            "policy": "",
            "flash_time": "2026-07-30 10:00:00",
        }
    ]
    maps = [
        {"name": "m1", "consistgrp": "CG1", "progress": "80%", "source": "s", "target": "t"},
        {"name": "m2", "consistgrp": "CG1", "progress": "40", "source": "s2", "target": "t2"},
        {"name": "m3", "consistgrp": "other", "progress": "10", "source": "s3", "target": "t3"},
    ]
    rows = build_cg_summaries(groups=groups, maps=maps, host_maps=[], schedule=None)
    assert rows[0]["flash_time"] == "2026-07-30 10:00:00"
    assert rows[0]["progress_pct"] == 40


def test_build_cg_summaries_progress_none_when_not_copying():
    groups = [{"name": "CG1", "status": "idle_or_copied", "flash_time": "x"}]
    maps = [{"name": "m1", "consistgrp": "CG1", "progress": "90", "source": "s", "target": "t"}]
    rows = build_cg_summaries(groups=groups, maps=maps, host_maps=[], schedule=None)
    assert rows[0]["progress_pct"] is None
```

- [ ] **Step 2: Implement → PASS**

```powershell
python -m pytest tests/test_fc_cg_summary.py -q --tb=short
```

- [ ] **Step 3: Commit**

```powershell
git add launchpad/fc_cg_summary.py tests/test_fc_cg_summary.py
git commit -m "Add Flash time and min Progress to CG summary builder."
```

---

### Task 2: Contingency page + Excel columns (TDD)

**Files:**
- Modify: `launchpad/contingency_groups.py`
- Modify: `launchpad/fc_cg_summary_export.py`
- Modify: `tests/test_contingency_groups_page.py`
- Modify: `tests/test_fc_cg_summary_export.py`

**Column order:** Name, Status, Flash time, Progress, Maps, Host maps, Size, Policy, Snaps/week

- Display: `flash_time || "—"`, `progress_pct != null ? progress_pct + "%" : "—"`
- Export fields: insert `"flash_time"`, `"progress_pct"` after status (export may store raw number; display in cell as number or preformatted string — prefer write `f"{n}%"` in export by formatting in `_rows` or store display string in a `progress` field). **Lock:** SUMMARY_FIELDS use `flash_time` and `progress_display` where builder also sets `progress_display` as `f"{pct}%"` or `""`, **or** export formats `progress_pct` when writing. Prefer export formats number → `N%` string in cell.

- [ ] **Step 1: Page + export tests** assert headers Flash time / Progress; colspan 9; export SUMMARY_HEADERS include both after Status

- [ ] **Step 2: Implement → PASS → Commit**

```powershell
python -m pytest tests/test_contingency_groups_page.py tests/test_fc_cg_summary_export.py -q --tb=short
git add launchpad/contingency_groups.py launchpad/fc_cg_summary_export.py tests/test_contingency_groups_page.py tests/test_fc_cg_summary_export.py
git commit -m "Show Flash time and Progress on CG summary table and Excel."
```

---

### Task 3: Version 1.6.82

- [ ] Assert + set `APP_VERSION = "1.6.82"`
- [ ] Commit: `Bump LaunchPad to 1.6.82 for CG summary Flash time and Progress.`

---

### Task 4: Final verification

```powershell
python -m pytest tests/test_fc_cg_summary.py tests/test_fc_cg_summary_export.py tests/test_contingency_groups_page.py tests/test_system_connectivity_version.py -q --tb=short
python -c "from launchpad.config import APP_VERSION; print(APP_VERSION)"
```

Expected: PASS, `1.6.82`.

---

## Spec coverage checklist

| Spec item | Task |
|-----------|------|
| flash_time + min progress in builder | 1 |
| Contingency table + Excel columns | 2 |
| Version 1.6.82 | 3 |
| No Manage/Status / no end date | Global |
