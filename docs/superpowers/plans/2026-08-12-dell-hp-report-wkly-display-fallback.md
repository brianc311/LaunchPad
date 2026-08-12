# Dell HP Report Wkly Display Fallback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** HP Report - Wkly shows current-week capacity from row display metrics when no system snapshot exists (v**1.6.162**).

**Architecture:** `_build_report_wkly_sheet` already paints identity from `rows`. For each week column, prefer snapshot bytes; if missing and `week == iso_week_key(report_date)`, write `curr_usable_gib` / `curr_used_gib` / `curr_util` from the row.

**Tech Stack:** Python, openpyxl, pytest.

**Spec:** `docs/superpowers/specs/2026-08-12-dell-hp-report-wkly-display-fallback-design.md`

## Global Constraints

- APP_VERSION is currently `1.6.161`; bump to `1.6.162` in Task 2 only.
- Do not upsert raw/pool into the snapshot store.
- Prefer snapshot when present for a week; only fall back for the **current** report ISO week.
- Windows PowerShell commits; TDD; no `.superpowers/sdd*` or install zips in commits.

## File structure

| File | Responsibility |
|------|----------------|
| `launchpad/dell_report_export.py` | Wkly current-week display fallback |
| `tests/test_dell_report_export.py` | Test HP Wkly fills from row when store empty |
| `launchpad/config.py` | `APP_VERSION` → `1.6.162` |
| Version pin tests | Same three as prior bumps |

---

### Task 1: Wkly current-week display fallback

**Files:**
- Modify: `launchpad/dell_report_export.py`
- Modify: `tests/test_dell_report_export.py`

**Interfaces:**
- Consumes: `iso_week_key(report_date)`, row `curr_*` fields, existing snapshot cell write
- Produces: Wkly cells filled for current week when snap missing

- [ ] **Step 1: Write the failing test**

Append to `tests/test_dell_report_export.py`:

```python
def test_hp_report_wkly_uses_row_curr_when_no_snapshot():
    rows = [
        _minimal_row(
            card_id=5,
            facility="Data center -WAG2",
            array_name="HPE - VDIPRIMERA101 - WAG2",
            model="HPE Primera 600 4-way",
            curr_usable_gib=200.0,
            curr_used_gib=50.0,
            curr_util=0.25,
        )
    ]
    wb = build_dell_report_workbook(
        ibm_rows=[],
        hp_rows=rows,
        snapshot_store={},
        report_date=datetime(2026, 8, 12, tzinfo=timezone.utc),
    )
    ws = wb["HP Report - Wkly"]
    assert ws.cell(row=10, column=_FIRST_DATA_COL + 1).value == (
        "HPE - VDIPRIMERA101 - WAG2"
    )
    # First week metric columns start at _FIRST_DATA_COL + 3
    assert ws.cell(row=10, column=_FIRST_DATA_COL + 3).value == pytest.approx(200.0)
    assert ws.cell(row=10, column=_FIRST_DATA_COL + 4).value == pytest.approx(50.0)
    assert ws.cell(row=10, column=_FIRST_DATA_COL + 5).value == pytest.approx(0.25)
```

- [ ] **Step 2: Run test to verify it fails**

```powershell
python -m pytest tests/test_dell_report_export.py::test_hp_report_wkly_uses_row_curr_when_no_snapshot -v
```

Expected: FAIL (metric cells None).

- [ ] **Step 3: Implement fallback**

In `_build_report_wkly_sheet`, after computing `weeks`, set:

```python
    current_week = iso_week_key(report_date)
```

Replace the inner week loop body so that when `snap` is missing/invalid, if `week == current_week` and row has `curr_usable_gib is not None`, write row current metrics (usable/used with `"0.00"` format, util with `"0.0%"`). Otherwise `continue` as today.

Prefer snapshot when present (unchanged path).

- [ ] **Step 4: Run tests**

```powershell
python -m pytest tests/test_dell_report_export.py::test_hp_report_wkly_uses_row_curr_when_no_snapshot tests/test_dell_report_export.py::test_workbook_has_report_wkly_sheets_with_week_columns -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add launchpad/dell_report_export.py tests/test_dell_report_export.py
git commit -m "Fill HP Report Wkly current week from display row when no snapshot."
```

---

### Task 2: Bump APP_VERSION to 1.6.162

**Files:**
- Modify: `launchpad/config.py`
- Modify: `tests/test_system_connectivity_version.py`
- Modify: `tests/test_hadoop_sudo_wire.py`
- Modify: `tests/test_capacity_unit_js.py`

- [ ] **Step 1:** Set `APP_VERSION = "1.6.162"` and pin tests.

- [ ] **Step 2:**

```powershell
python -m pytest tests/test_system_connectivity_version.py tests/test_hadoop_sudo_wire.py tests/test_capacity_unit_js.py tests/test_dell_report_export.py::test_hp_report_wkly_uses_row_curr_when_no_snapshot -v
```

- [ ] **Step 3:** Commit `Bump version to 1.6.162 for HP Report Wkly display fallback.`
