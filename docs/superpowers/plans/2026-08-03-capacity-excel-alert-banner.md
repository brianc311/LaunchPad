# Capacity Excel Alert Banner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a severity-specific merged alert banner above Excel Capacity headers when any exported pool/site is ≥80% used.

**Architecture:** Pure helpers compute max used %, site/pool over-threshold counts, and banner text/severity. `_styled_workbook` inserts a merged row-1 banner on both sheets (or leaves layout unchanged under 80%), shifting headers/freeze/filter to row 2 when present.

**Tech Stack:** Python 3, openpyxl, pytest.

**Spec:** `docs/superpowers/specs/2026-08-03-capacity-excel-alert-banner-design.md`

## Global Constraints

- **Branch:** continue on `feature/hpe-capacity-parse` (do not create a new worktree unless tip unavailable).
- **Thresholds:** ≥80% warn, ≥90% critical; “drives are full” at ≥99.5%.
- **Copy (exact):**
  - warn: `WARNING: Please check storage — capacity over 80%.`
  - critical 90: `CRITICAL: Please check storage — capacity over 90%.`
  - critical full: `CRITICAL: Please check storage — drives are full.`
- **Suffix:** ` (N site(s) / M pool(s) over threshold)` when banner shown.
- **Sheets:** both **Storage Capacity** and **Pool Capacity**.
- **No banner** when max used % &lt; 80.
- Prefer **pool detail `Used %`** as primary input; also accept an optional list of site-level percents.
- Bump `APP_VERSION` to **1.6.102** in the final task.
- Commit at each task’s commit step.
- Run from: `C:\Users\BrianColley\LaunchPad`

---

## File map

| File | Responsibility |
|------|----------------|
| `launchpad/capacity_excel_alerts.py` | Pure banner summary + message helpers |
| `tests/test_capacity_excel_alerts.py` | Unit tests for message/counts + workbook smoke |
| `launchpad/capacity_export.py` | Wire banner into `_styled_workbook` |
| `launchpad/config.py` | `APP_VERSION = "1.6.102"` |

---

### Task 1: Pure banner helpers

**Files:**
- Create: `launchpad/capacity_excel_alerts.py`
- Create: `tests/test_capacity_excel_alerts.py`

**Interfaces:**
- Produces:
  - `capacity_excel_banner_summary(*, pool_used_pcts: list[float], site_used_pcts: list[float] | None = None, site_keys_over: set[str] | None = None) -> dict | None`
    - returns `None` if max &lt; 80
    - else `{"severity": "warn"|"critical", "max_pct": float, "site_count": int, "pool_count": int, "message": str}`
  - `banner_message_for_max_pct(max_pct: float) -> str | None` (None if &lt; 80)
  - Colors as constants: `BANNER_WARN_FILL = "F59E0B"`, `BANNER_CRITICAL_FILL = "EF4444"`, `BANNER_FONT_COLOR = "FFFFFF"`

Counting rules:
- `pool_count` = number of pool percents ≥ 80
- `site_count` = if `site_keys_over` provided, its size; else number of site percents ≥ 80 (or 0 if neither provided)
- `max_pct` = max of all pool + site percents (default 0)

Message = `banner_message_for_max_pct(max_pct) + f" ({site_count} site(s) / {pool_count} pool(s) over threshold)"`

- [ ] **Step 1: Write failing tests**

```python
from launchpad.capacity_excel_alerts import (
    banner_message_for_max_pct,
    capacity_excel_banner_summary,
)


def test_banner_message_thresholds():
    assert banner_message_for_max_pct(79.9) is None
    assert banner_message_for_max_pct(80.0) == (
        "WARNING: Please check storage — capacity over 80%."
    )
    assert banner_message_for_max_pct(89.9) == (
        "WARNING: Please check storage — capacity over 80%."
    )
    assert banner_message_for_max_pct(90.0) == (
        "CRITICAL: Please check storage — capacity over 90%."
    )
    assert banner_message_for_max_pct(99.4) == (
        "CRITICAL: Please check storage — capacity over 90%."
    )
    assert banner_message_for_max_pct(99.5) == (
        "CRITICAL: Please check storage — drives are full."
    )
    assert banner_message_for_max_pct(100.0) == (
        "CRITICAL: Please check storage — drives are full."
    )


def test_summary_none_under_80():
    assert capacity_excel_banner_summary(pool_used_pcts=[10.0, 50.0]) is None


def test_summary_warn_and_counts():
    summary = capacity_excel_banner_summary(
        pool_used_pcts=[82.0, 50.0, 81.0],
        site_keys_over={"A", "B"},
    )
    assert summary is not None
    assert summary["severity"] == "warn"
    assert summary["pool_count"] == 2
    assert summary["site_count"] == 2
    assert summary["message"].startswith("WARNING:")
    assert "2 site(s) / 2 pool(s) over threshold" in summary["message"]


def test_summary_critical_from_max_pool():
    summary = capacity_excel_banner_summary(
        pool_used_pcts=[91.0],
        site_keys_over={"A"},
    )
    assert summary is not None
    assert summary["severity"] == "critical"
    assert "capacity over 90%" in summary["message"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_capacity_excel_alerts.py -v`

Expected: FAIL with import/module not found.

- [ ] **Step 3: Implement helpers**

Create `launchpad/capacity_excel_alerts.py`:

```python
"""Alert banner text/severity for Capacity Excel exports."""

from __future__ import annotations

from typing import Any

BANNER_WARN_FILL = "F59E0B"
BANNER_CRITICAL_FILL = "EF4444"
BANNER_FONT_COLOR = "FFFFFF"


def banner_message_for_max_pct(max_pct: float) -> str | None:
    if max_pct < 80:
        return None
    if max_pct >= 99.5:
        return "CRITICAL: Please check storage — drives are full."
    if max_pct >= 90:
        return "CRITICAL: Please check storage — capacity over 90%."
    return "WARNING: Please check storage — capacity over 80%."


def capacity_excel_banner_summary(
    *,
    pool_used_pcts: list[float],
    site_used_pcts: list[float] | None = None,
    site_keys_over: set[str] | None = None,
) -> dict[str, Any] | None:
    site_pcts = list(site_used_pcts or [])
    all_pcts = list(pool_used_pcts) + site_pcts
    max_pct = max(all_pcts) if all_pcts else 0.0
    base = banner_message_for_max_pct(max_pct)
    if base is None:
        return None
    pool_count = sum(1 for pct in pool_used_pcts if pct >= 80)
    if site_keys_over is not None:
        site_count = len(site_keys_over)
    else:
        site_count = sum(1 for pct in site_pcts if pct >= 80)
    severity = "critical" if max_pct >= 90 else "warn"
    return {
        "severity": severity,
        "max_pct": float(max_pct),
        "site_count": site_count,
        "pool_count": pool_count,
        "message": f"{base} ({site_count} site(s) / {pool_count} pool(s) over threshold)",
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_capacity_excel_alerts.py -v`

Expected: all PASS.

- [ ] **Step 5: Commit**

```powershell
git add launchpad/capacity_excel_alerts.py tests/test_capacity_excel_alerts.py
git commit -m "Add Capacity Excel alert banner message helpers."
```

---

### Task 2: Wire banner into `_styled_workbook`

**Files:**
- Modify: `launchpad/capacity_export.py`
- Modify: `tests/test_capacity_excel_alerts.py`

**Interfaces:**
- Consumes: `capacity_excel_banner_summary`, fill/font color constants
- Produces: `_styled_workbook(..., pool_detail_rows)` inserts banner when pools ≥80%; helper `_apply_capacity_alert_banner(ws, message, severity, col_count)`
- Site keys over threshold: unique `f"{location}|{device_sn}|{ip}"` for any pool row with used % ≥ 80
- Pool percents: 5th element of each `PoolDetailRow` (index 4)

Layout rules when banner present:
- Row 1 = merged banner
- Headers start at row 2
- Data starts at row 3
- `freeze_panes = "A3"`
- `auto_filter.ref` starts at header row 2
- Banner fill: warn `F59E0B`, critical `EF4444`; bold white font; wrap text; vertical center

When no banner: keep current row-1 headers / `freeze_panes = "A2"` behavior.

- [ ] **Step 1: Add failing workbook smoke tests**

Append to `tests/test_capacity_excel_alerts.py`:

```python
from launchpad.capacity_export import HEADERS, POOL_HEADERS, _styled_workbook


def test_styled_workbook_no_banner_under_80():
    inv = [("Loc", "Dev", "1.1.1.1", "Name", "SN", "IBM")]
    fills = [("ok", "pools")]
    pools = [("Loc", "Dev", "1.1.1.1", "CPG_A", 50.0, "1 GB", "2 GB", "1 GB")]
    wb = _styled_workbook(inv, fills, [], pools)
    ws = wb["Storage Capacity"]
    assert ws.cell(1, 1).value == HEADERS[0]
    assert ws.cell(2, 1).value == "Loc"
    ws_pools = wb["Pool Capacity"]
    assert ws_pools.cell(1, 1).value == POOL_HEADERS[0]


def test_styled_workbook_banner_on_both_sheets_when_critical():
    inv = [("Loc", "Dev", "1.1.1.1", "Name", "SN", "IBM")]
    fills = [("91%", "pools")]
    pools = [
        ("Loc", "Dev", "1.1.1.1", "CPG_A", 91.0, "9 GB", "10 GB", "1 GB"),
        ("Loc", "Dev", "1.1.1.1", "CPG_B", 50.0, "1 GB", "2 GB", "1 GB"),
    ]
    wb = _styled_workbook(inv, fills, [], pools)
    for title, col_count in (("Storage Capacity", len(HEADERS)), ("Pool Capacity", len(POOL_HEADERS))):
        ws = wb[title]
        assert "CRITICAL:" in str(ws.cell(1, 1).value)
        assert "1 site(s) / 1 pool(s) over threshold" in str(ws.cell(1, 1).value)
        assert list(ws.merged_cells.ranges)
        expected_header = HEADERS[0] if title == "Storage Capacity" else POOL_HEADERS[0]
        assert ws.cell(2, 1).value == expected_header
```

- [ ] **Step 2: Run new tests to verify they fail**

Run: `python -m pytest tests/test_capacity_excel_alerts.py::test_styled_workbook_banner_on_both_sheets_when_critical -v`

Expected: FAIL (no banner / headers still row 1).

- [ ] **Step 3: Implement workbook wiring**

In `launchpad/capacity_export.py`:

1. Import helpers at module top:

```python
from launchpad.capacity_excel_alerts import (
    BANNER_CRITICAL_FILL,
    BANNER_FONT_COLOR,
    BANNER_WARN_FILL,
    capacity_excel_banner_summary,
)
```

2. Add:

```python
def _apply_capacity_alert_banner(ws, message: str, severity: str, col_count: int) -> None:
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=col_count)
    cell = ws.cell(row=1, column=1, value=message)
    fill = BANNER_CRITICAL_FILL if severity == "critical" else BANNER_WARN_FILL
    cell.fill = PatternFill("solid", fgColor=fill)
    cell.font = Font(bold=True, color=BANNER_FONT_COLOR, size=12)
    cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
    ws.row_dimensions[1].height = 28


def _banner_from_pool_detail_rows(pool_detail_rows: list[PoolDetailRow]) -> dict | None:
    pool_pcts = [float(row[4]) for row in pool_detail_rows]
    site_keys = {
        f"{row[0]}|{row[1]}|{row[2]}"
        for row in pool_detail_rows
        if float(row[4]) >= 80
    }
    return capacity_excel_banner_summary(
        pool_used_pcts=pool_pcts,
        site_keys_over=site_keys,
    )
```

3. Refactor `_styled_workbook` so header/data writing uses `header_row = 2 if banner else 1` and `data_start = header_row + 1`. Apply banner to both sheets when summary is not None **before** writing headers. Update freeze/filter refs accordingly:

```python
banner = _banner_from_pool_detail_rows(pool_detail_rows)
header_row = 2 if banner else 1
data_start = header_row + 1
if banner:
    _apply_capacity_alert_banner(ws, banner["message"], banner["severity"], len(HEADERS))
# write HEADERS at header_row
# write inventory/extra starting at data_start
ws.freeze_panes = f"A{header_row + 1}"
ws.auto_filter.ref = f"A{header_row}:{get_column_letter(len(HEADERS))}{last_row}"
# same pattern for Pool Capacity sheet
```

Do not change export refresh/SSH behavior.

- [ ] **Step 4: Run all excel-alert tests**

Run: `python -m pytest tests/test_capacity_excel_alerts.py -v`

Expected: all PASS. Also run: `python -m pytest tests/test_capacity_export_filter.py -q` — Expected: PASS (layout still valid).

- [ ] **Step 5: Commit**

```powershell
git add launchpad/capacity_export.py tests/test_capacity_excel_alerts.py
git commit -m "Show capacity alert banner at top of Capacity Excel sheets."
```

---

### Task 3: Version bump + verification

**Files:**
- Modify: `launchpad/config.py` (`APP_VERSION = "1.6.102"`)
- Modify: `tests/test_system_connectivity_version.py` (assert `1.6.102`)

**Interfaces:**
- Consumes: Tasks 1–2 complete
- Produces: version 1.6.102

- [ ] **Step 1: Bump version strings**

Set `APP_VERSION = "1.6.102"` and update the version pin test to `1.6.102`.

- [ ] **Step 2: Run focused regression**

```powershell
python -m pytest tests/test_capacity_excel_alerts.py tests/test_capacity_export_filter.py tests/test_system_connectivity_version.py -q
```

Expected: all PASS.

- [ ] **Step 3: Manual check (operator)**

1. Export Capacity Excel for a monitored site with a pool ≥80% and one ≥90%.
2. Open workbook: both sheets show the correct CRITICAL/WARNING top banner.
3. Export a low-utilization-only set (or blank inventory path with no high pools): no banner; headers on row 1.

- [ ] **Step 4: Commit**

```powershell
git add launchpad/config.py tests/test_system_connectivity_version.py
git commit -m "Bump version to 1.6.102 for Capacity Excel alert banner."
```

---

## Spec coverage checklist

| Spec requirement | Task |
|------------------|------|
| Severity-specific copy (80 / 90 / full) | Task 1 |
| Site/pool over-threshold suffix | Task 1 |
| No banner under 80% | Tasks 1–2 |
| Merged banner on both sheets | Task 2 |
| Headers/freeze/filter shift | Task 2 |
| Workbook smoke tests | Task 2 |
| Version 1.6.102+ | Task 3 |

## Placeholder / consistency self-review

- No TBD/TODO placeholders.
- Helper names (`capacity_excel_banner_summary`, `_apply_capacity_alert_banner`) consistent across tasks.
- Exact message strings match the spec.
