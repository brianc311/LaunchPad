# Dell Report Fidelity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Dell Report export populate IBM/HP Report with data + visible LED fills, add IBM/HP Forecast sheets, refresh monitored-on IBM/HPE capacity first, and error clearly when no rows result.

**Architecture:** Extend `dell_report_export.py` for facility grouping, direct util cell fills, and Forecast sheet builders. Tighten `export_dell_report_excel_bytes` to refresh only monitored-on IBM/HPE cards and raise a dedicated empty-result error mapped to HTTP 400. Keep `.xlsx` template builder (no `.xlsb`).

**Tech Stack:** Python 3, openpyxl, HealthServer API, pytest.

**Spec:** `docs/superpowers/specs/2026-08-04-dell-report-fidelity-design.md`

## Global Constraints

- **Branch:** continue on `feature/hpe-capacity-parse`.
- **Site set:** monitored-on IBM/HPE only (`dell_report_family` → `ibm`|`hp`).
- **Refresh:** on Dell Report click, refresh those cards before building.
- **Empty result:** raise / return clear error — do not open a blank success workbook.
- **LED bands:** green &lt;70%, amber 70–89%, red ≥90% (`utilization_led_fill`); apply **direct cell fills** and keep CF.
- **Forecast:** sheets `IBM Forecast` and `HP Forecast` only; flat current util into Date + 3/6/9/12 Month. No Forecast - Wkly required.
- **Bump** `APP_VERSION` to **1.6.111** in the final task.
- Commit at each task’s commit step.
- Run from: `C:\Users\BrianColley\LaunchPad`
- Place imports at module top (no new inline imports).

---

## File map

| File | Responsibility |
|------|----------------|
| `launchpad/dell_report_export.py` | Facility grouping, direct LED fills, Forecast sheets, Home list, empty-check helper |
| `launchpad/health_server.py` | Filter IBM/HPE + monitor-on before refresh; map empty error → 400 |
| `launchpad/dell_report_leds.py` | Reuse `utilization_led_fill` (no band change) |
| `tests/test_dell_report_export.py` | Workbook LED fills, facility blanking, Forecast sheets |
| `tests/test_dell_report_api.py` / `tests/test_dell_report_export_path.py` | Empty → 400; monitored IBM/HPE refresh filter |
| `launchpad/config.py` | `APP_VERSION = "1.6.111"` |
| `tests/test_system_connectivity_version.py` | Pin 1.6.111 |

---

### Task 1: Direct LED fills + facility grouping on Report sheets

**Files:**
- Modify: `launchpad/dell_report_export.py`
- Modify: `tests/test_dell_report_export.py`

**Interfaces:**

```python
def _apply_direct_utilization_fills(
    ws: Worksheet,
    start_row: int,
    end_row: int,
    util_columns: tuple[int, ...] = _UTIL_COLUMNS,
) -> None:
    """For each data row/col in util_columns, set PatternFill from utilization_led_fill(cell.value)."""

def _write_grouped_facility_rows(
    ws: Worksheet,
    rows: list[dict],
    *,
    data_start: int,
) -> None:
    """Sort by facility, array_name. Write Facility only on first row of each facility group; blank thereafter."""
```

- [ ] **Step 1: Write failing tests**

```python
from launchpad.dell_report_leds import utilization_led_fill, GREEN_FILL, AMBER_FILL, RED_FILL

def test_utilization_cells_have_direct_led_fills():
    wb = build_dell_report_workbook(
        ibm_rows=[
            _minimal_row(curr_util=0.5, prior_util=0.75),  # green / amber
            _minimal_row(array_name="Hot", curr_util=0.95, prior_util=0.95),  # red
        ],
        hp_rows=[],
    )
    ws = wb["IBM Report"]
    start = _data_start_row(ws)
    # prior util col 6, curr util col 9
    assert ws.cell(start, 6).fill.fgColor.rgb[-6:].upper() == AMBER_FILL
    assert ws.cell(start, 9).fill.fgColor.rgb[-6:].upper() == GREEN_FILL
    assert ws.cell(start + 1, 9).fill.fgColor.rgb[-6:].upper() == RED_FILL

def test_facility_shown_only_on_first_row_of_group():
    wb = build_dell_report_workbook(
        ibm_rows=[
            _minimal_row(facility="A-facility", array_name="B-array"),
            _minimal_row(facility="A-facility", array_name="A-array"),
            _minimal_row(facility="Z-facility", array_name="Z-array"),
        ],
        hp_rows=[],
    )
    ws = wb["IBM Report"]
    start = _data_start_row(ws)
    facilities = [ws.cell(row, 1).value for row in range(start, ws.max_row + 1)]
    arrays = [ws.cell(row, 2).value for row in range(start, ws.max_row + 1)]
    assert arrays == ["A-array", "B-array", "Z-array"]
    assert facilities == ["A-facility", None, "Z-facility"]  # or ""
```

Update `test_rows_sorted_by_facility_then_array_name` to expect blanked facility on subsequent group rows (same assertion as above).

- [ ] **Step 2: Run — expect FAIL**

```bash
python -m pytest tests/test_dell_report_export.py -q -k "direct_led or facility_shown or rows_sorted"
```

- [ ] **Step 3: Implement**

In `_build_data_sheet` after writing values:
1. Call `_apply_direct_utilization_fills` then existing `_apply_utilization_formatting` (CF).
2. When writing Facility column, track `last_facility`; if same as previous row, write `None`/empty for Facility.

Import `utilization_led_fill` at module top from `launchpad.dell_report_leds`.

- [ ] **Step 4: Run — expect PASS**

```bash
python -m pytest tests/test_dell_report_export.py -q
```

- [ ] **Step 5: Commit**

```bash
git commit -m "Add Dell Report LED cell fills and facility grouping."
```

---

### Task 2: IBM Forecast + HP Forecast sheets

**Files:**
- Modify: `launchpad/dell_report_export.py`
- Modify: `tests/test_dell_report_export.py`

**Interfaces:**

```python
IBM_FORECAST_SHEET_NAME = "IBM Forecast"
HP_FORECAST_SHEET_NAME = "HP Forecast"

_FORECAST_UTIL_COLUMNS = (4, 5, 6, 7, 8)  # Date, 3M, 6M, 9M, 12M — 1-based after Facility/Array/Model

def _build_forecast_sheet(
    ws: Worksheet,
    rows: list[dict],
    *,
    report_date: datetime,
) -> None:
    """
    Header: Facility, Storage Array, Model Number, <date label or 'Date'>, 3 Month, 6 Month, 9 Month, 12 Month.
    One row per report row; util = curr_util (flat) in all util columns.
    Facility grouping + direct LED fills on util columns.
    """

def build_dell_report_workbook(...) -> Workbook:
    # After IBM/HP Report sheets, create IBM Forecast / HP Forecast from same row lists.
    # Update Home sheet list to include forecast names before stubs.
```

- [ ] **Step 1: Failing tests**

```python
def test_workbook_includes_ibm_and_hp_forecast_sheets():
    wb = build_dell_report_workbook(
        ibm_rows=[_minimal_row(curr_util=0.61)],
        hp_rows=[_minimal_row(array_name="3PAR001", curr_util=0.82)],
    )
    assert "IBM Forecast" in wb.sheetnames
    assert "HP Forecast" in wb.sheetnames
    ibm_f = wb["IBM Forecast"]
    # locate header row containing "3 Month"
    # data row: util columns all == 0.61
    # LED fill on a util cell matches GREEN_FILL for 0.61

def test_home_lists_forecast_sheets():
    wb = build_dell_report_workbook(ibm_rows=[_minimal_row()], hp_rows=[])
    home_text = " ".join(
        str(c.value) for row in wb[HOME_SHEET_NAME].iter_rows(max_row=20) for c in row if c.value
    )
    assert "IBM Forecast" in home_text
    assert "HP Forecast" in home_text
```

(`HOME_SHEET_NAME` already `"Home"` — import or use `"Home"`.)

- [ ] **Step 2–4:** Implement + pass `tests/test_dell_report_export.py`

- [ ] **Step 5: Commit**

```bash
git commit -m "Add IBM and HP Forecast sheets to Dell Report workbook."
```

---

### Task 3: Monitored IBM/HPE refresh filter + empty-export error

**Files:**
- Modify: `launchpad/dell_report_export.py` (optional helper)
- Modify: `launchpad/health_server.py` (`export_dell_report_excel_bytes` + `/api/dell-report-export`)
- Create or extend: `tests/test_dell_report_api.py` / `tests/test_dell_report_collect.py`

**Interfaces:**

```python
# launchpad/dell_report_export.py
class DellReportEmptyError(ValueError):
    """Raised when no IBM/HP capacity rows after collection."""

def ensure_dell_report_has_rows(ibm_rows: list, hp_rows: list) -> None:
    if not ibm_rows and not hp_rows:
        raise DellReportEmptyError(
            "No Dell Report capacity data for monitored IBM/HPE sites after refresh."
        )

# health_server.export_dell_report_excel_bytes:
# 1. include_monitor_off forced False for fidelity (ignore include_off query) OR
#    document: always monitored-on only per spec — force include_monitor_off=False.
# 2. After building included list, filter to cards where dell_report_family(profile) in {ibm, hp}
#    BEFORE refresh_card loops (skip non-IBM/HPE SSH).
# 3. After collect_dell_report_rows, call ensure_dell_report_has_rows.
# 4. API: catch DellReportEmptyError → 400 JSON {"error": str(exc)}
```

- [ ] **Step 1: Failing tests**

```python
def test_export_raises_when_no_ibm_hp_rows(monkeypatch, tmp_path):
    # HealthServer with only a Linux/non-IBM card OR ibm card with no capacity
    # monkeypatch refresh_card to no-op returning empty capacity
    # expect DellReportEmptyError from export_dell_report_excel_bytes

def test_api_returns_400_when_dell_report_empty(monkeypatch):
    # Wire export to raise DellReportEmptyError
    # GET /api/dell-report-export?open=0 → status 400, error message in JSON

def test_export_skips_refresh_for_non_ibm_hp(monkeypatch):
    # Register ibm (monitor on) + linux (monitor on)
    # spy refresh_card; export; assert linux card_id never refreshed
```

- [ ] **Step 2–4:** Implement + pass focused tests

Force `include_monitor_off=False` inside `export_dell_report_excel_bytes` (spec: monitored-on only). Keep the parameter for call-site compatibility but ignore True.

- [ ] **Step 5: Commit**

```bash
git commit -m "Refresh monitored IBM/HPE only and error on empty Dell Report."
```

---

### Task 4: Version bump + verification

**Files:**
- Modify: `launchpad/config.py` → `APP_VERSION = "1.6.111"`
- Modify: `tests/test_system_connectivity_version.py`

- [ ] **Step 1: Bump + pin** `test_app_version_16111`

- [ ] **Step 2: Focused pytest**

```bash
python -m pytest tests/test_dell_report_export.py tests/test_dell_report_api.py tests/test_dell_report_collect.py tests/test_dell_report_helpers.py tests/test_system_connectivity_version.py -q
```

- [ ] **Step 3: Manual smoke (operator)**

1. Monitor on for ≥1 IBM FlashSystem and ≥1 HPE 3PAR/Primera with working SSH.
2. Dell Report → workbook opens with data rows on IBM/HP Report, colored util cells.
3. Confirm IBM Forecast / HP Forecast tabs with same arrays and util in 3–12 Month columns.
4. All monitors off (or no IBM/HPE) → clear error, no blank file.

- [ ] **Step 4: Commit**

```bash
git commit -m "Bump app version to 1.6.111 for Dell Report fidelity."
```

---

## Done when

- [ ] Monitored IBM/HPE capacity refresh precedes workbook build.
- [ ] IBM/HP Report show data, facility grouping, direct LED fills (+ CF).
- [ ] IBM Forecast / HP Forecast populated with flat util.
- [ ] Empty result → 400 / clear UI error.
- [ ] `APP_VERSION` is **1.6.111** and focused tests pass.

## Spec coverage check

| Spec requirement | Task |
|------------------|------|
| Refresh monitored-on IBM/HPE | 3 |
| Populate Report + LED fills | 1 |
| Facility grouping | 1 |
| IBM/HP Forecast flat util | 2 |
| Empty → error | 3 |
| No Forecast - Wkly required | 2 (omit) |
| Version 1.6.111 | 4 |
| Health Excel deferred | out of scope |
