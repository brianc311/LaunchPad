# Snapcopy Summary Outdated CG Filter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** On Snapcopy Summary, mark FlashCopy CGs whose flash time is older than the site schedule interval, filter with **Outdated (N)**, auto-check those rows, and export via the existing checked-rows Excel path.

**Architecture:** Pure helpers parse flash time and decide outdated vs `schedule.days`. Live CG summary payload gains `outdated` (and optional `expected_days` / `age_days`). Snapcopy Summary page adds an **Outdated (N)** toggle that filters, auto-checks, and mildly styles rows. No new export API.

**Tech Stack:** Python 3, CustomTkinter HealthServer HTML/JS page, pytest.

**Spec:** `docs/superpowers/specs/2026-08-04-snapcopy-outdated-cg-filter-design.md`

## Global Constraints

- **Branch:** continue on `feature/hpe-capacity-parse` (do not create a new worktree unless tip unavailable).
- **Placement:** Snapcopy Summary only — not System Connectivity.
- **Outdated when:** `age_days > expected_days` (strict).
- **Not outdated (v1):** held schedule, missing/`None` days, missing/unparseable flash time, age exactly equal to expected days.
- **Export:** reuse `POST /api/contingency-groups/fc-cg-summary/export-selected` with auto-checked outdated rows.
- Bump `APP_VERSION` to **1.6.108** in the final task (checkhealth idle-exit fix shipped as **1.6.107**; tip-stickiness as **1.6.106**).
- Commit at each task’s commit step.
- Run from: `C:\Users\BrianColley\LaunchPad`

---

## File map

| File | Responsibility |
|------|----------------|
| `launchpad/fc_consistgrp_ops.py` | Add `parse_flash_time` (datetime \| None) shared with display formatting |
| `launchpad/fc_cg_summary.py` (or small `launchpad/cg_outdated.py`) | `is_cg_outdated(...)` / annotate rows with `outdated` |
| `launchpad/health_server.py` | Include `outdated` (+ optional age fields) on live/summary rows |
| `launchpad/snapcopy_summary_page.py` | **Outdated (N)** toggle, filter, auto-check, row styling |
| `tests/test_cg_outdated.py` (new) | Unit tests for parse + outdated rules |
| `tests/test_snapcopy_summary_page.py` (or existing page test) | Marker asserts for toggle / outdated wiring |
| `launchpad/config.py` | `APP_VERSION = "1.6.107"` |

---

### Task 1: Parse flash time + outdated helper

**Files:**
- Modify: `launchpad/fc_consistgrp_ops.py`
- Create or modify: `launchpad/fc_cg_summary.py` (prefer keeping helper next to schedule context) **or** `launchpad/cg_outdated.py` if `fc_cg_summary.py` is already crowded
- Create: `tests/test_cg_outdated.py`

**Interfaces:**

```python
def parse_flash_time(raw: str, *, now: datetime | None = None) -> datetime | None:
    """Parse compact YYMMDDHHMMSS / YYYYMMDDHHMMSS or display form into aware/naive UTC-comparable datetime.
    Return None if missing/unparseable. Prefer reusing the digit-extraction logic from format_flash_time_display.
    """

def is_cg_outdated(
    *,
    flash_time: str | datetime | None,
    schedule: dict | None,
    now: datetime | None = None,
) -> bool:
    """True only when schedule is not held, days is an int, flash parses, and age_days > days."""
```

Optional helper for payload annotation:

```python
def cg_outdated_fields(
    *,
    flash_time: str,
    schedule: dict | None,
    now: datetime | None = None,
) -> dict:
    # {"outdated": bool, "expected_days": int | None, "age_days": float | None}
```

**Steps:**

- [ ] **Step 1: Write failing tests**

Create `tests/test_cg_outdated.py`:

```python
from datetime import datetime, timezone

from launchpad.fc_consistgrp_ops import parse_flash_time
from launchpad.fc_cg_summary import is_cg_outdated  # or cg_outdated module


def test_parse_flash_time_compact_yymmdd():
    dt = parse_flash_time("260502060129")
    assert dt is not None
    assert dt.year == 2026 and dt.month == 5 and dt.day == 2


def test_outdated_when_age_exceeds_schedule_days():
    now = datetime(2026, 8, 4, 12, 0, 0, tzinfo=timezone.utc)
    # flash 10 days ago, weekly schedule
    flash = "260725120000"  # 2026-07-25
    assert is_cg_outdated(
        flash_time=flash,
        schedule={"days": 7, "held": False},
        now=now,
    )


def test_not_outdated_within_interval():
    now = datetime(2026, 8, 4, 12, 0, 0, tzinfo=timezone.utc)
    flash = "260802120000"  # 2 days ago
    assert not is_cg_outdated(
        flash_time=flash,
        schedule={"days": 7, "held": False},
        now=now,
    )


def test_not_outdated_held_or_missing():
    now = datetime(2026, 8, 4, 12, 0, 0, tzinfo=timezone.utc)
    flash = "260701120000"
    assert not is_cg_outdated(flash_time=flash, schedule={"days": None, "held": True}, now=now)
    assert not is_cg_outdated(flash_time="", schedule={"days": 7, "held": False}, now=now)
    assert not is_cg_outdated(flash_time=flash, schedule=None, now=now)


def test_not_outdated_when_age_equals_expected_days():
    now = datetime(2026, 8, 4, 12, 0, 0, tzinfo=timezone.utc)
    flash = "260728120000"  # exactly 7 days earlier
    assert not is_cg_outdated(
        flash_time=flash,
        schedule={"days": 7, "held": False},
        now=now,
    )
```

Fix the sloppy middle assert to three clear cases: held → False; empty flash → False; schedule None → False. Also assert age **equal** to expected days is not outdated.

- [ ] **Step 2: Run tests — expect FAIL**

```bash
python -m pytest tests/test_cg_outdated.py -q
```

- [ ] **Step 3: Implement parse + is_cg_outdated**

Refactor `format_flash_time_display` to call `parse_flash_time` when possible (keep display output identical). Implement age as `(now - flash).total_seconds() / 86400.0` with a consistent timezone policy (prefer UTC; if flash is naive, compare as naive UTC).

- [ ] **Step 4: Run tests — expect PASS**

```bash
python -m pytest tests/test_cg_outdated.py -q
```

- [ ] **Step 5: Commit**

```bash
git add launchpad/fc_consistgrp_ops.py launchpad/fc_cg_summary.py launchpad/cg_outdated.py tests/test_cg_outdated.py
git commit -m "$(cat <<'EOF'
Add CG outdated detection from flash age vs schedule days.

EOF
)"
```

---

### Task 2: Annotate live CG summary rows

**Files:**
- Modify: `launchpad/fc_cg_summary.py` — optionally set `outdated` inside `build_cg_summaries` when schedule is known
- Modify: `launchpad/health_server.py` — ensure live rows include `outdated` (and optional `expected_days` / `age_days`)

**Preferred approach:** Compute in `build_cg_summaries` so all callers stay consistent:

```python
fields = cg_outdated_fields(flash_time=..., schedule=schedule)
row["outdated"] = fields["outdated"]
# optional: row["expected_days"] = fields["expected_days"]
```

Live assembly around `rows.append({...})` in `health_server` should pass through `outdated` from `summary`.

**Steps:**

- [ ] **Step 1: Write / extend failing test**

If there is an existing `tests/test_fc_cg_summary*.py`, add a case that `build_cg_summaries` sets `outdated=True` for an old flash + weekly schedule. Otherwise add to `tests/test_cg_outdated.py`.

- [ ] **Step 2: Run — expect FAIL** (missing key or False)

- [ ] **Step 3: Wire annotation into `build_cg_summaries` + live row dict**

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit**

```bash
git commit -m "$(cat <<'EOF'
Expose outdated flag on FlashCopy CG summary rows.

EOF
)"
```

---

### Task 3: Snapcopy Summary Outdated (N) UI

**Files:**
- Modify: `launchpad/snapcopy_summary_page.py`
- Modify: `tests/test_snapcopy_summary_page.py` (create if missing; else extend)

**UI behavior (locked):**

1. Hero control: button/toggle `Outdated (N)` where N = count of `row.outdated === true` in the current result set (after site filter from Refresh).
2. Default off: show all rows; optional mild highlight for outdated rows (e.g. `tr.outdated` amber left border or background).
3. Toggle on: `renderRows` filters to outdated only; auto-check all visible row checkboxes; empty state “No outdated CGs.” when N=0.
4. Toggle off: restore full list; clear or leave checks (prefer: restore previous selection only if simple — otherwise clear checks to avoid surprise).
5. Export Excel unchanged: uses `selectedRowKeys()` → existing export-selected API.

**JS sketch:**

```javascript
let outdatedOnly = false;
// after load:
const outdatedCount = snapcopyRows.filter((r) => r.outdated).length;
outdatedBtn.textContent = `Outdated (${outdatedCount})`;
outdatedBtn.setAttribute("aria-pressed", outdatedOnly ? "true" : "false");

function visibleRows() {
  if (!outdatedOnly) return snapcopyRows;
  return snapcopyRows.filter((r) => r.outdated);
}

function renderRows(rows) {
  // ... existing map ...
  // add class outdated when row.outdated
  // if outdatedOnly, after render: check all .snapcopy-row-cb
}
```

**Steps:**

- [ ] **Step 1: Failing page marker tests**

```python
assert "Outdated (" in SNAPCOPY_SUMMARY_HTML
assert "outdatedOnly" in SNAPCOPY_SUMMARY_HTML or "outdated-only" in SNAPCOPY_SUMMARY_HTML
assert "row.outdated" in SNAPCOPY_SUMMARY_HTML
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement toggle + filter + auto-check + CSS**

- [ ] **Step 4: Run page + outdated unit tests — expect PASS**

```bash
python -m pytest tests/test_cg_outdated.py tests/test_snapcopy_summary_page.py -q
```

- [ ] **Step 5: Commit**

```bash
git commit -m "$(cat <<'EOF'
Add Outdated (N) filter toggle on Snapcopy Summary.

EOF
)"
```

---

### Task 4: Version bump + verification

**Files:**
- Modify: `launchpad/config.py` → `APP_VERSION = "1.6.107"`
- Modify: `tests/test_system_connectivity_version.py` → assert `1.6.107`

**Steps:**

- [ ] **Step 1: Bump version + pin test**

- [ ] **Step 2: Run focused suite**

```bash
python -m pytest tests/test_cg_outdated.py tests/test_snapcopy_summary_page.py tests/test_system_connectivity_version.py -q
```

- [ ] **Step 3: Manual smoke (operator)**

1. Unlock LaunchPad, Monitor on for at least one IBM site with CGs.
2. Open Snapcopy Summary → Refresh.
3. Confirm **Outdated (N)** count matches rows with flash older than schedule.
4. Toggle on → only outdated rows; checkboxes checked.
5. Export Excel → only those CGs.
6. Toggle off → full table returns.

- [ ] **Step 4: Commit**

```bash
git commit -m "$(cat <<'EOF'
Bump app version to 1.6.107 for Snapcopy outdated CG filter.

EOF
)"
```

---

## Done when

- [ ] Outdated detection unit tests cover held / missing flash / within interval / over interval / equal interval.
- [ ] Live summary rows include `outdated`.
- [ ] Snapcopy Summary shows **Outdated (N)**, filters, auto-checks, exports via existing path.
- [ ] System Connectivity unchanged.
- [ ] `APP_VERSION` is **1.6.107**.
