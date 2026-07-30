# Snapshot Schedule Day-Complete Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let operators mark planned Snapshot Schedule calendar days complete (solid green) with `completed_dates` on overrides, pruned when the date leaves the planned set (v**1.6.83**).

**Architecture:** Extend override normalize with `completed_dates`; add `prune_completed_dates`; calendar toggle + CSS in `snapshot_schedule.py`; reuse existing overrides API.

**Tech Stack:** Python, pytest, existing Snapshot Schedule HTML/JS.

**Spec:** `docs/superpowers/specs/2026-07-30-snapshot-schedule-day-complete-design.md`

## Global Constraints

- **Worktree:** `.worktrees/snapshot-schedule-day-complete` on `feature/snapshot-schedule-day-complete` from tip **after Feature A merged** (or from `feature/contingency-groups` once A is on tip; APP_VERSION base `1.6.82`)
- Planned days only; solid green; toggle; prune vs current planned set
- No Excel color work in v1
- No array auto-detect
- Bump `APP_VERSION` to **1.6.83**
- Commit per task; run from worktree

---

## File map

| File | Responsibility |
|------|----------------|
| `launchpad/snapshot_schedule_overrides.py` | `completed_dates` normalize + `prune_completed_dates` |
| `launchpad/snapshot_schedule.py` | CSS, toggle, prune on render/save, legend |
| `launchpad/config.py` | `1.6.83` |
| Tests | Overrides unit, page markers, version |

---

### Task 0: Confirm baseline

```powershell
cd C:\Users\BrianColley\LaunchPad
git worktree add .worktrees/snapshot-schedule-day-complete -b feature/snapshot-schedule-day-complete feature/contingency-groups
cd .worktrees\snapshot-schedule-day-complete
python -c "from launchpad.config import APP_VERSION; print(APP_VERSION)"
Test-Path docs\superpowers\specs\2026-07-30-snapshot-schedule-day-complete-design.md
```

Expected: tip ≥ `1.6.82` if A already merged; else implement A first. Spec `True`.

---

### Task 1: completed_dates normalize + prune (TDD)

**Files:**
- Modify: `launchpad/snapshot_schedule_overrides.py`
- Modify: `tests/test_snapshot_schedule_overrides.py`

**Interfaces:**
- `normalize_override` includes `"completed_dates": list[str]` (unique sorted ISO dates)
- `prune_completed_dates(completed: list[str], planned: set[str] | list[str]) -> list[str]` — intersection, sorted

- [ ] **Step 1: Failing tests**

```python
def test_normalize_override_completed_dates():
    out = normalize_override(
        {
            "mode": "auto",
            "held": False,
            "completed_dates": ["2026-07-30", "bad", "2026-07-30", "2026-07-01"],
        }
    )
    assert out["completed_dates"] == ["2026-07-01", "2026-07-30"]


def test_prune_completed_dates_intersection():
    from launchpad.snapshot_schedule_overrides import prune_completed_dates

    assert prune_completed_dates(
        ["2026-07-01", "2026-07-30"],
        {"2026-07-30", "2026-08-06"},
    ) == ["2026-07-30"]
```

- [ ] **Step 2: Implement → PASS → Commit**

```powershell
python -m pytest tests/test_snapshot_schedule_overrides.py -q --tb=short
git add launchpad/snapshot_schedule_overrides.py tests/test_snapshot_schedule_overrides.py
git commit -m "Add completed_dates normalize and prune for Snapshot Schedule."
```

---

### Task 2: Calendar UI toggle + solid green (TDD)

**Files:**
- Modify: `launchpad/snapshot_schedule.py`
- Create or modify: `tests/test_snapshot_schedule_page.py` (create if missing; else extend)

**Behavior:**
- CSS class e.g. `.cal-cell.completed` with solid green background
- Planned cells clickable → toggle date in that card’s `completed_dates` → save overrides
- Overall calendar: if multiple sites share a day, define v1 as: toggle applies to **all visible sites that have that date planned**, or only per-site calendars get toggle — **prefer per-site card calendars for toggle; overall calendar shows green if any/all completed** — lock simpler: **toggle on per-site calendars**; overall calendar cells with that date show completed style when **all** sites that plan that day have it completed (or when any — prefer **any** for visibility). Even simpler v1: **both calendars toggle the focused/primary site** — Best lock: **click works on per-site calendars**; overall calendar is display-only for completed (green if any included site has that date completed).

**Locked for implementer:** Toggle on **per-site** calendars; overall calendar paints solid green for a date if **any** included site has that date in `completed_dates` and plans that day. Legend mentions completed.

- [ ] **Step 1: Page tests** assert `.cal-cell.completed` or `completed` class string, `completed_dates`, toggle function name, legend text “complete” / “done”

- [ ] **Step 2: Implement → PASS → Commit**

```powershell
python -m pytest tests/test_snapshot_schedule_overrides.py tests/test_snapshot_schedule_page.py -q --tb=short
git add launchpad/snapshot_schedule.py tests/test_snapshot_schedule_page.py
git commit -m "Add Snapshot Schedule mark-day-complete calendar UI."
```

---

### Task 3: Version 1.6.83

- [ ] Assert + set `APP_VERSION = "1.6.83"`
- [ ] Commit: `Bump LaunchPad to 1.6.83 for Snapshot Schedule day complete.`

---

### Task 4: Final verification

```powershell
python -m pytest tests/test_snapshot_schedule_overrides.py tests/test_snapshot_schedule_page.py tests/test_system_connectivity_version.py -q --tb=short
python -c "from launchpad.config import APP_VERSION; print(APP_VERSION)"
```

Expected: PASS, `1.6.83`.

---

## Spec coverage checklist

| Spec item | Task |
|-----------|------|
| completed_dates normalize + prune | 1 |
| Solid green + toggle UI | 2 |
| Version 1.6.83 | 3 |
| No Excel colors / no array detect | Global |
