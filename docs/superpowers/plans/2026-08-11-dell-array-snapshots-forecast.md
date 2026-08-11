# Dell Array Snapshots and Forecast Projection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dell weekly snapshots always store array/system usable/used with `layer: "system"`, Weekly Growth only compares two system weeks, and IBM/HP Forecast projects 3/6/9/12 Month at 13/26/39/52 weeks (v**1.6.152**).

**Architecture:** New `select_dell_array_snapshot_summary` returns non-rollup `capacity_summary` only (never pools/raw). `upsert_week_snapshot` stamps `layer`. `_row_from_snapshots` blanks growth unless both weeks are `layer == "system"`. `_project_util` returns None when growth is None and caps at 100%. IBM/HP Forecast Date stays current util; month columns call `_project_util`. Forecast-Wkly keeps +1/+4/+8/+12 and inherits the same `_project_util`.

**Tech Stack:** Python, openpyxl, pytest.

**Spec:** `docs/superpowers/specs/2026-08-11-dell-array-snapshots-forecast-design.md`

## Global Constraints

- APP_VERSION is currently `1.6.151`; bump to `1.6.152` in the Forecast/version task (Task 3). Do not bump earlier.
- Snapshot source is always array/system: `_usable(capacity_summary, allow_pool_rollup=False)`. Never pools, never raw, independent of `include_pools`.
- Missing or `total_bytes <= 0` array summary → do not upsert that card/week. Existing include-without-capacity blank rows stay blank.
- New snapshot records include `layer: "system"`. Old untagged records stay on disk unchanged.
- Weekly Growth is blank (`None`) unless **both** prior and current have `layer == "system"` and `prior_used > 0`. Untagged prior → blank, not `0%`.
- Same used both system weeks → growth `0.0` (correct; Forecast months stay flat).
- IBM/HP Forecast: Date = `curr_util`; 3/6/9/12 Month = `_project_util` at **13 / 26 / 39 / 52** weeks.
- `_project_util`: `curr_util is None` → None; `weekly_growth is None` → None (do not copy util into month / +N week cells); else `max(0.0, min(1.0, curr_util * (1 + growth) ** weeks))`.
- Forecast-Wkly horizons stay +1/+4/+8/+12. Do not change Capacity Report page totals, CPG/raw toggles, or LED thresholds.
- Do not rewrite or convert old untagged snapshots.
- Keep `select_dell_capacity_summary` unchanged (CPG/raw display selector). Snapshot collect/upsert stop calling it.
- Keep `collect_dell_report_rows(..., include_pools=...)` and `maybe_upsert_dell_snapshot_for_card(..., include_pools=...)` signatures for callers; ignore `include_pools` for bytes written to the snapshot store.
- Windows PowerShell commits (`git commit -m "..."`); commit at each task’s commit step.
- Prefer TDD: failing test → implement → pass → commit.
- Do not commit `.superpowers/sdd*` scratch or install zips.

## File structure

| File | Responsibility |
|------|----------------|
| `launchpad/dell_report_capacity.py` | Add `select_dell_array_snapshot_summary`; leave `select_dell_capacity_summary` as-is |
| `launchpad/dell_report_snapshots.py` | `SNAPSHOT_LAYER_SYSTEM`, persist `layer` on upsert, `snapshots_allow_weekly_growth` |
| `launchpad/dell_report_export.py` | Collect/upsert use array selector; gate growth; `_project_util` None+cap; Forecast months; Date col width |
| `tests/test_dell_report_capacity.py` | Array-only selector tests |
| `tests/test_dell_report_snapshots.py` | Layer stamp + growth-gate helper |
| `tests/test_dell_report_collect.py` | Collect uses array bytes; no snapshot when only raw; untagged prior blanks growth |
| `tests/test_dell_report_export.py` | Forecast 13/26/39/52, cap, None growth blanks months, Wkly None growth |
| `launchpad/config.py` | `APP_VERSION` → `1.6.152` |
| `tests/test_system_connectivity_version.py` | Version pin → `1.6.152` |
| `tests/test_hadoop_sudo_wire.py` | Version pin → `1.6.152` |
| `tests/test_capacity_unit_js.py` | Version pin → `1.6.152` |

---

### Task 1: Array selector + snapshot `layer`

**Files:**
- Modify: `launchpad/dell_report_capacity.py`
- Modify: `launchpad/dell_report_snapshots.py`
- Modify: `tests/test_dell_report_capacity.py`
- Modify: `tests/test_dell_report_snapshots.py`

**Interfaces:**
- Produces:
  - `select_dell_array_snapshot_summary(*, capacity_summary: dict | None) -> dict | None`
  - `SNAPSHOT_LAYER_SYSTEM = "system"`
  - `upsert_week_snapshot(..., layer: str = SNAPSHOT_LAYER_SYSTEM)` writes `"layer"` on the week dict
  - `snapshots_allow_weekly_growth(prior: dict | None, current: dict | None) -> bool`
- Consumes: existing `_usable(..., allow_pool_rollup=False)`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_dell_report_capacity.py`:

```python
from launchpad.dell_report_capacity import (
    select_dell_array_snapshot_summary,
    select_dell_capacity_summary,
)

POOLS = [{"name": "cpg1", "total_bytes": 50, "used_bytes": 40}]


def test_array_snapshot_uses_non_rollup_system_not_raw():
    chosen = select_dell_array_snapshot_summary(capacity_summary=SYSTEM)
    assert chosen is SYSTEM


def test_array_snapshot_rejects_all_cpgs():
    all_cpgs = {
        "name": "All CPGs",
        "total_bytes": 100,
        "used_bytes": 99,
        "used_pct": 99.0,
    }
    assert select_dell_array_snapshot_summary(capacity_summary=all_cpgs) is None


def test_array_snapshot_none_when_missing():
    assert select_dell_array_snapshot_summary(capacity_summary=None) is None
```

Keep existing `select_dell_capacity_summary` tests unchanged.

Append to `tests/test_dell_report_snapshots.py` (import the new names):

```python
from launchpad.dell_report_snapshots import (
    SNAPSHOT_LAYER_SYSTEM,
    snapshots_allow_weekly_growth,
    upsert_week_snapshot,
)


def test_upsert_stamps_layer_system():
    store = upsert_week_snapshot(
        {},
        card_id=7,
        week="2026-W32",
        usable_bytes=200,
        used_bytes=100,
        model="FS9500",
        facility="Data center -WAG1",
        family="ibm",
        array_name="site-a",
        captured_at="2026-08-04T12:00:00+00:00",
    )
    assert store["7"]["2026-W32"]["layer"] == SNAPSHOT_LAYER_SYSTEM


def test_growth_allowed_only_when_both_system():
    system = {"layer": SNAPSHOT_LAYER_SYSTEM, "used_bytes": 100}
    assert snapshots_allow_weekly_growth(system, system) is True
    assert snapshots_allow_weekly_growth({"used_bytes": 100}, system) is False
    assert snapshots_allow_weekly_growth(None, system) is False
```

- [ ] **Step 2: Run tests to confirm they fail**

```powershell
python -m pytest tests/test_dell_report_capacity.py tests/test_dell_report_snapshots.py -q
```

Expected: import / assertion failures for the new names.

- [ ] **Step 3: Implement**

In `launchpad/dell_report_capacity.py`, add:

```python
def select_dell_array_snapshot_summary(
    *,
    capacity_summary: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Array/system usable only; never pools or raw."""
    return _usable(capacity_summary, allow_pool_rollup=False)
```

Leave `select_dell_capacity_summary` unchanged.

In `launchpad/dell_report_snapshots.py`:

```python
SNAPSHOT_LAYER_SYSTEM = "system"
```

Add `layer: str = SNAPSHOT_LAYER_SYSTEM` to `upsert_week_snapshot` and include `"layer": layer` in the week dict.

```python
def snapshots_allow_weekly_growth(
    prior: dict | None, current: dict | None
) -> bool:
    if not prior or not current:
        return False
    return (
        prior.get("layer") == SNAPSHOT_LAYER_SYSTEM
        and current.get("layer") == SNAPSHOT_LAYER_SYSTEM
    )
```

- [ ] **Step 4: Run tests to confirm they pass**

```powershell
python -m pytest tests/test_dell_report_capacity.py tests/test_dell_report_snapshots.py -q
```

Expected: pass. Existing upsert tests still pass because `layer` is extra.

- [ ] **Step 5: Commit**

```powershell
git add launchpad/dell_report_capacity.py launchpad/dell_report_snapshots.py tests/test_dell_report_capacity.py tests/test_dell_report_snapshots.py
git commit -m "Stamp Dell snapshots as array/system layer."
```

---

### Task 2: Collect/upsert array bytes + gated Weekly Growth

**Files:**
- Modify: `launchpad/dell_report_export.py` (`collect_dell_report_rows`, `maybe_upsert_dell_snapshot_for_card`, `_row_from_snapshots`)
- Modify: `tests/test_dell_report_collect.py`

**Interfaces:**
- Consumes: `select_dell_array_snapshot_summary`, `SNAPSHOT_LAYER_SYSTEM`, `snapshots_allow_weekly_growth`, `upsert_week_snapshot` (default layer)
- Produces: collect/maybe_upsert write array bytes + `layer: "system"`; `_row_from_snapshots` sets `weekly_growth` only when both weeks are system

- [ ] **Step 1: Write the failing tests**

Replace `test_collect_uses_raw_when_include_pools_false` — only raw, no array summary, must **not** snapshot or emit a data row:

```python
def test_collect_skips_when_only_raw_no_array_summary():
    sites = [
        {
            "card_id": 5,
            "name": "Primera Remote",
            "device_profile": "hpe_primera_600",
            "capacity_summary": None,
            "raw_capacity_summary": {
                "name": "Vdiprimera101",
                "total_bytes": 200 * 1024**3,
                "used_bytes": 50 * 1024**3,
                "used_pct": 25.0,
            },
            "pools": [],
        }
    ]
    ibm, hp, store = collect_dell_report_rows(
        sites,
        snapshot_store={},
        include_pools=False,
        now=datetime(2026, 8, 5, tzinfo=timezone.utc),
    )
    assert ibm == []
    assert hp == []
    assert store == {}
```

Replace `test_collect_refreshes_stale_cpg_snapshot_with_raw` with array-preferred-over-raw (real system name, not All CPGs):

```python
def test_collect_snapshots_array_not_raw_when_both_present():
    sites = [
        {
            "card_id": 5,
            "name": "HPE - VDIPRIMERA101 - WAG2",
            "device_profile": "hpe_primera_600",
            "capacity_summary": {
                "name": "Vdiprimera101",
                "total_bytes": 80 * 1024**3,
                "used_bytes": 40 * 1024**3,
            },
            "raw_capacity_summary": {
                "name": "raw",
                "total_bytes": 200 * 1024**3,
                "used_bytes": 50 * 1024**3,
            },
            "pools": [],
        }
    ]
    _, hp, updated = collect_dell_report_rows(
        sites,
        snapshot_store={},
        include_pools=False,
        now=datetime(2026, 8, 5, tzinfo=timezone.utc),
    )
    assert len(hp) == 1
    assert hp[0]["curr_usable_gib"] == pytest.approx(80.0)
    assert hp[0]["curr_used_gib"] == pytest.approx(40.0)
    snap = updated["5"]["2026-W32"]
    assert snap["usable_bytes"] == pytest.approx(80 * 1024**3)
    assert snap["layer"] == "system"
```

Add All-CPGs + raw → no new snapshot (rollup is not array):

```python
def test_collect_skips_all_cpgs_even_when_raw_present():
    sites = [
        {
            "card_id": 5,
            "name": "HPE - VDIPRIMERA101 - WAG2",
            "device_profile": "hpe_primera_600",
            "capacity_summary": {
                "name": "All CPGs",
                "total_bytes": 10 * 1024**3,
                "used_bytes": 9 * 1024**3,
            },
            "raw_capacity_summary": {
                "name": "Vdiprimera101",
                "total_bytes": 200 * 1024**3,
                "used_bytes": 50 * 1024**3,
            },
            "pools": [],
        }
    ]
    ibm, hp, store = collect_dell_report_rows(
        sites,
        snapshot_store={},
        include_pools=False,
        now=datetime(2026, 8, 5, tzinfo=timezone.utc),
    )
    assert ibm == []
    assert hp == []
    assert store == {}
```

Keep `test_collect_growth_with_two_weeks_in_store` — after Task 1, upsert stamps `layer` on the prior week, and collect stamps current, so `0.25` still holds.

Add untagged prior → blank growth:

```python
def test_collect_untagged_prior_blanks_growth():
    store = upsert_week_snapshot(
        {},
        card_id=7,
        week="2026-W31",
        usable_bytes=200 * 1024**3,
        used_bytes=100 * 1024**3,
        model="FS9500",
        facility="Data center -WAG1",
        family="ibm",
        array_name="WAG1_FS9200_1",
        captured_at="2026-07-28T12:00:00+00:00",
    )
    del store["7"]["2026-W31"]["layer"]
    site = _site(
        card_id=7,
        used_bytes=int(125 * 1024**3),
        total_bytes=int(200 * 1024**3),
    )
    ibm_rows, _, _ = collect_dell_report_rows(
        [site],
        snapshot_store=store,
        now=datetime(2026, 8, 4, tzinfo=timezone.utc),
    )
    assert ibm_rows[0]["weekly_growth"] is None
    assert ibm_rows[0]["prior_used_gib"] == pytest.approx(100.0)
    assert ibm_rows[0]["curr_used_gib"] == pytest.approx(125.0)
```

In `test_maybe_upsert_creates_current_week_snapshot_when_missing`, add:

```python
assert snap["layer"] == "system"
```

- [ ] **Step 2: Run tests to confirm they fail**

```powershell
python -m pytest tests/test_dell_report_collect.py -q
```

Expected: raw-only still produces an HP row; untagged prior still yields `0.25`.

- [ ] **Step 3: Implement**

In `launchpad/dell_report_export.py`:

- Import `select_dell_array_snapshot_summary` instead of (or in addition to) `select_dell_capacity_summary`. Drop the `select_dell_capacity_summary` import if unused.
- Import `snapshots_allow_weekly_growth`.

In `collect_dell_report_rows`, replace the `select_dell_capacity_summary(...)` call with:

```python
summary = select_dell_array_snapshot_summary(
    capacity_summary=_site_value(site, "capacity_summary"),
)
```

`include_pools` stays on the function signature; do not pass it into the selector.

In `maybe_upsert_dell_snapshot_for_card`, replace the selector the same way (`analysis.get("capacity_summary")` only). Keep `include_pools` on the signature; do not use it for selection.

In `_row_from_snapshots`, after computing `growth = weekly_growth_fraction(...)` when prior exists, gate it:

```python
growth = weekly_growth_fraction(prior_used, curr_used)
if not snapshots_allow_weekly_growth(prior, current):
    growth = None
```

Prior usable/used/util columns still fill from the prior snapshot even when growth is blank.

Update the collect comment that says “Always refresh … CPG-off raw” — snapshots now refresh from array/system only.

- [ ] **Step 4: Run tests to confirm they pass**

```powershell
python -m pytest tests/test_dell_report_collect.py tests/test_dell_report_capacity.py tests/test_dell_report_snapshots.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```powershell
git add launchpad/dell_report_export.py tests/test_dell_report_collect.py
git commit -m "Snapshot Dell weeks from array capacity only."
```

---

### Task 3: Project IBM/HP Forecast + cap + version

**Files:**
- Modify: `launchpad/dell_report_export.py` (`_project_util`, `_write_forecast_grouped_rows`, `_FORECAST_COL_WIDTHS`)
- Modify: `tests/test_dell_report_export.py`
- Modify: `launchpad/config.py`
- Modify: `tests/test_system_connectivity_version.py`
- Modify: `tests/test_hadoop_sudo_wire.py`
- Modify: `tests/test_capacity_unit_js.py`

**Interfaces:**
- Consumes: `_project_util`, `_FORECAST_UTIL_COLUMNS`, row `curr_util` / `weekly_growth`
- Produces:
  - `_FORECAST_MONTH_HORIZONS = (13, 26, 39, 52)`
  - `_project_util` returns None when growth is None; caps at `1.0`
  - Date column width `16.0`
  - `APP_VERSION = "1.6.152"`

- [ ] **Step 1: Write the failing tests**

In `tests/test_dell_report_export.py`, import `_project_util` from `launchpad.dell_report_export`.

Replace `test_workbook_includes_ibm_and_hp_forecast_sheets` util assertions. `_minimal_row` defaults `weekly_growth=0.2`, so months cap at 100%:

```python
def test_workbook_includes_ibm_and_hp_forecast_sheets():
    wb = build_dell_report_workbook(
        ibm_rows=[_minimal_row(curr_util=0.61)],
        hp_rows=[_minimal_row(array_name="3PAR001", curr_util=0.82)],
    )
    assert "IBM Forecast" in wb.sheetnames
    assert "HP Forecast" in wb.sheetnames
    ibm_f = wb["IBM Forecast"]
    start = _forecast_data_start_row(ibm_f)
    assert ibm_f.cell(start, 5).value == 0.61
    for col in (6, 7, 8, 9):
        assert ibm_f.cell(start, col).value == 1.0
    rules = [rule for group in ibm_f.conditional_formatting for rule in group.rules]
    assert any(getattr(rule, "type", None) == "iconSet" for rule in rules)
```

Add:

```python
def test_project_util_none_growth_returns_none():
    assert _project_util(0.5, None, 13) is None
    assert _project_util(None, 0.01, 13) is None


def test_project_util_caps_at_one():
    assert _project_util(0.9, 0.5, 13) == 1.0


def test_ibm_forecast_projects_thirteen_week_month():
    growth = 0.01
    curr = 0.50
    wb = build_dell_report_workbook(
        ibm_rows=[_minimal_row(curr_util=curr, weekly_growth=growth)],
        hp_rows=[],
    )
    ws = wb["IBM Forecast"]
    start = _forecast_data_start_row(ws)
    expected = curr * ((1.0 + growth) ** 13)
    assert ws.cell(start, 5).value == curr
    assert ws.cell(start, 6).value == pytest.approx(expected)
    assert ws.cell(start, 7).value == pytest.approx(curr * ((1.0 + growth) ** 26))
    assert ws.cell(start, 8).value == pytest.approx(curr * ((1.0 + growth) ** 39))
    assert ws.cell(start, 9).value == pytest.approx(curr * ((1.0 + growth) ** 52))


def test_ibm_forecast_zero_growth_is_flat():
    wb = build_dell_report_workbook(
        ibm_rows=[_minimal_row(curr_util=0.61, weekly_growth=0.0)],
        hp_rows=[],
    )
    ws = wb["IBM Forecast"]
    start = _forecast_data_start_row(ws)
    for col in (5, 6, 7, 8, 9):
        assert ws.cell(start, col).value == 0.61


def test_ibm_forecast_none_growth_blanks_months():
    wb = build_dell_report_workbook(
        ibm_rows=[_minimal_row(curr_util=0.61, weekly_growth=None)],
        hp_rows=[],
    )
    ws = wb["IBM Forecast"]
    start = _forecast_data_start_row(ws)
    assert ws.cell(start, 5).value == 0.61
    for col in (6, 7, 8, 9):
        assert ws.cell(start, col).value is None
```

Add `import pytest` if the file does not already import it.

Update `test_hp_forecast_wkly_has_data_rows` — `weekly_growth=None` must blank horizon cells, not copy util:

```python
assert ws.cell(row=10, column=5).value == 0.25
assert ws.cell(row=10, column=6).value is None
assert ws.cell(row=10, column=9).value is None
```

Bump version pins to `"1.6.152"` in:

- `tests/test_system_connectivity_version.py`
- `tests/test_hadoop_sudo_wire.py`
- `tests/test_capacity_unit_js.py`

- [ ] **Step 2: Run tests to confirm they fail**

```powershell
python -m pytest tests/test_dell_report_export.py tests/test_system_connectivity_version.py tests/test_hadoop_sudo_wire.py tests/test_capacity_unit_js.py -q
```

Expected: Forecast still copies util into all month cols; Wkly still copies on None growth; version still `1.6.151`.

- [ ] **Step 3: Implement**

In `launchpad/dell_report_export.py`:

```python
_FORECAST_MONTH_HORIZONS = (13, 26, 39, 52)
```

Change `_FORECAST_COL_WIDTHS` Date (index 4) from `14.0` to `16.0`.

Replace `_project_util`:

```python
def _project_util(
    curr_util: float | None, weekly_growth: float | None, weeks_ahead: int
) -> float | None:
    if curr_util is None:
        return None
    if weekly_growth is None:
        return None
    projected = float(curr_util) * ((1.0 + float(weekly_growth)) ** weeks_ahead)
    return max(0.0, min(1.0, projected))
```

Replace the util loop in `_write_forecast_grouped_rows`:

```python
curr_util = row.get("curr_util")
growth = row.get("weekly_growth")
values = [curr_util] + [
    _project_util(curr_util, growth, weeks)
    for weeks in _FORECAST_MONTH_HORIZONS
]
for col, value in zip(_FORECAST_UTIL_COLUMNS, values):
    cell = ws.cell(row=excel_row, column=col, value=value)
    cell.number_format = "0.0%"
```

Forecast-Wkly already calls `_project_util`; no horizon change.

Set `APP_VERSION = "1.6.152"` in `launchpad/config.py`.

- [ ] **Step 4: Run tests to confirm they pass**

```powershell
python -m pytest tests/test_dell_report_export.py tests/test_dell_report_collect.py tests/test_dell_report_capacity.py tests/test_dell_report_snapshots.py tests/test_system_connectivity_version.py tests/test_hadoop_sudo_wire.py tests/test_capacity_unit_js.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```powershell
git add launchpad/dell_report_export.py launchpad/config.py tests/test_dell_report_export.py tests/test_system_connectivity_version.py tests/test_hadoop_sudo_wire.py tests/test_capacity_unit_js.py
git commit -m "Project IBM/HP Forecast months from weekly growth."
```

---

## Self-review

| Spec item | Task |
|-----------|------|
| Array-only snapshot selector | Task 1 |
| `layer: "system"` on upsert | Task 1 |
| Collect/maybe_upsert use array selector | Task 2 |
| No upsert when only pools/raw or All CPGs | Task 2 |
| Growth only when both weeks `layer == system` | Task 2 |
| Untagged prior → blank growth | Task 2 |
| Both system, 100→125 → 0.25 | Task 2 (existing collect test) |
| Both system, same used → 0.0 / flat months | Task 2 (formula) + Task 3 (`weekly_growth=0.0`) |
| Forecast Date = curr_util; months 13/26/39/52 | Task 3 |
| `_project_util` None growth → None; cap 100% | Task 3 |
| Forecast-Wkly inherits gated `_project_util` | Task 3 (Wkly test update) |
| Widen Date column | Task 3 (`16.0`) |
| APP_VERSION 1.6.152 | Task 3 |
| `select_dell_capacity_summary` / CPG toggle / LEDs unchanged | Task 1 leaves selector; no LED edits |

**Placeholder scan:** none. Commands are PowerShell `python -m pytest` / `git commit -m`.

**Type consistency:** `select_dell_array_snapshot_summary(*, capacity_summary=...)`; `snapshots_allow_weekly_growth(prior, current) -> bool`; `_FORECAST_MONTH_HORIZONS = (13, 26, 39, 52)`.
