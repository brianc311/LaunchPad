# Array FlashCopy CG Summary Excel Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add **Export Excel** beside Refresh on Contingency Groups’ Array FlashCopy CG summary — refresh-on-export live collect + `.xlsx` download (v**1.6.81**).

**Architecture:** New `fc_cg_summary_export` helper builds the workbook from summary rows. HealthServer adds `GET /api/contingency-groups/fc-cg-summary/export` that reuses `contingency_fc_cg_summary(group_id)` then exports. Page JS refreshes the table first, then opens the export URL (`open=1`).

**Tech Stack:** Python, openpyxl, HealthServer, pytest.

**Spec:** `docs/superpowers/specs/2026-07-30-fc-cg-summary-excel-export-design.md`

## Global Constraints

- **Worktree:** `.worktrees/fc-cg-summary-excel-export` on `feature/fc-cg-summary-excel-export` from `feature/contingency-groups` tip (includes design `0b20820` / APP_VERSION ≥ `1.6.80`)
- Refresh-on-export: export endpoint **always** live-collects via `contingency_fc_cg_summary`
- Button beside Refresh; columns match UI table
- Do **not** change `/api/contingency-groups-export` workbook
- No CSV in v1
- Two SSH collects per Export (refresh then export) is OK
- Bump `APP_VERSION` to **1.6.81**
- Commit at each task’s commit step
- Run from: `cd C:\Users\BrianColley\LaunchPad\.worktrees\fc-cg-summary-excel-export`

---

## File map

| File | Responsibility |
|------|----------------|
| `launchpad/fc_cg_summary_export.py` | `SUMMARY_HEADERS` / fields + `export_fc_cg_summary_xlsx(rows) -> bytes` |
| `launchpad/health_server.py` | Export route + `export_fc_cg_summary_bytes(group_id)` wrapper |
| `launchpad/contingency_groups.py` | Export button + JS (refresh then download) |
| `launchpad/config.py` | `1.6.81` |
| Tests | Helper, API, page markers, version |

---

### Task 0: Confirm baseline

**Files:** none

- [ ] **Step 1: Create worktree**

```powershell
cd C:\Users\BrianColley\LaunchPad
git worktree add .worktrees/fc-cg-summary-excel-export -b feature/fc-cg-summary-excel-export feature/contingency-groups
cd .worktrees\fc-cg-summary-excel-export
python -c "from launchpad.config import APP_VERSION; print(APP_VERSION)"
Test-Path docs\superpowers\specs\2026-07-30-fc-cg-summary-excel-export-design.md
```

Expected: tip ≥ `1.6.80`, spec `True`.

- [ ] **Step 2: No feature commit**

---

### Task 1: Summary Excel export helper (TDD)

**Files:**
- Create: `launchpad/fc_cg_summary_export.py`
- Create: `tests/test_fc_cg_summary_export.py`

**Interfaces:**
- Produces:
  - `SUMMARY_HEADERS`: `("Name", "Status", "Maps", "Host maps", "Size", "Policy", "Snaps/week")`
  - `SUMMARY_FIELDS`: `("name", "status", "fc_map_count", "host_map_count", "total_size", "policy", "snaps_per_week")`
  - `export_fc_cg_summary_xlsx(rows: list[dict]) -> bytes` — sheet title `FC CG Summary`
- Style headers like `launchpad/fc_consistgrp_status_export.py` (blue header, freeze panes, autofilter).

- [ ] **Step 1: Failing tests**

```python
from io import BytesIO

from openpyxl import load_workbook

from launchpad.fc_cg_summary_export import SUMMARY_HEADERS, export_fc_cg_summary_xlsx


def test_export_fc_cg_summary_xlsx_sheet_headers_and_rows():
    rows = [
        {
            "name": "AAN1_FC",
            "status": "idle_or_copied",
            "fc_map_count": 84,
            "host_map_count": 48,
            "total_size": "5.8 TB",
            "policy": "",
            "snaps_per_week": 0.44,
        }
    ]
    body = export_fc_cg_summary_xlsx(rows)
    wb = load_workbook(BytesIO(body))
    assert wb.sheetnames == ["FC CG Summary"]
    ws = wb["FC CG Summary"]
    assert [cell.value for cell in ws[1]] == list(SUMMARY_HEADERS)
    assert ws["A2"].value == "AAN1_FC"
    assert ws["C2"].value == 84
    assert ws["E2"].value == "5.8 TB"
    assert ws["G2"].value == 0.44
```

- [ ] **Step 2: Run — FAIL** then implement — PASS

```powershell
python -m pytest tests/test_fc_cg_summary_export.py -q --tb=short
```

- [ ] **Step 3: Commit**

```powershell
git add launchpad/fc_cg_summary_export.py tests/test_fc_cg_summary_export.py
git commit -m "Add Array FlashCopy CG summary Excel export helper."
```

---

### Task 2: HealthServer export API (TDD)

**Files:**
- Modify: `launchpad/health_server.py`
- Create: `tests/test_fc_cg_summary_export_api.py`

**Interfaces:**
- Produces:
  - `export_fc_cg_summary_bytes(self, *, group_id: str) -> tuple[bytes, str, str]`
    - Calls `contingency_fc_cg_summary(group_id)`
    - If not `ok`: raise `LookupError` (or `ValueError`) with joined warnings — handler maps to JSON 400 (same family as existing summary GET; unlock stays a warning inside `ok: False`)
    - Else `export_fc_cg_summary_xlsx(result["summaries"])`
    - Filename: `FC_CG_Summary_<safe_card>_<YYYYMMDD_HHMM>.xlsx` where card name comes from `result["card"]["name"]` when present, else `group`
    - content_type: `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`
  - GET `/api/contingency-groups/fc-cg-summary/export?group_id=&format=xlsx&open=1`
    - Place **immediately after** existing `/api/contingency-groups/fc-cg-summary` handler (~line 2104)
    - Require `group_id`; `format` must be `xlsx` (400 otherwise)
    - On success: optional `open=1` → TEMP_DIR + `open_exported_workbook` (copy Host Volume / Status export pattern)
    - On failure: JSON error, **no** empty xlsx

- [ ] **Step 1: Failing tests**

```python
from launchpad.health_server import HealthServer


def _unlock(server: HealthServer) -> None:
    server.set_settings_backend(lambda _key, default: default, lambda _key, _value: None)


def test_export_fc_cg_summary_requires_group_id_in_handler_source():
    import inspect
    from launchpad.health_server import _HealthHandler

    source = inspect.getsource(_HealthHandler.do_GET)
    assert "/api/contingency-groups/fc-cg-summary/export" in source


def test_export_fc_cg_summary_bytes_happy_path(monkeypatch):
    server = HealthServer()
    _unlock(server)

    def fake_summary(group_id):
        assert group_id == "g1"
        return {
            "ok": True,
            "warnings": [],
            "card": {"name": "Hartford", "id": 1},
            "summaries": [
                {
                    "name": "AAN1_FC",
                    "status": "idle_or_copied",
                    "fc_map_count": 1,
                    "host_map_count": 1,
                    "total_size": "10.0 GB",
                    "policy": "",
                    "snaps_per_week": 1,
                }
            ],
        }

    monkeypatch.setattr(server, "contingency_fc_cg_summary", fake_summary)
    body, filename, content_type = server.export_fc_cg_summary_bytes(group_id="g1")
    assert body[:2] == b"PK"
    assert filename.startswith("FC_CG_Summary_Hartford_")
    assert filename.endswith(".xlsx")
    assert "spreadsheetml" in content_type


def test_export_fc_cg_summary_bytes_raises_when_not_ok(monkeypatch):
    server = HealthServer()
    monkeypatch.setattr(
        server,
        "contingency_fc_cg_summary",
        lambda _gid: {
            "ok": False,
            "warnings": ["LaunchPad must be unlocked to collect FlashCopy CG summary."],
            "summaries": [],
            "card": None,
        },
    )
    try:
        server.export_fc_cg_summary_bytes(group_id="g1")
        assert False, "expected LookupError"
    except LookupError as exc:
        assert "unlock" in str(exc).lower()
```

- [ ] **Step 2: Implement → PASS → Commit**

```powershell
python -m pytest tests/test_fc_cg_summary_export_api.py tests/test_fc_cg_summary_export.py -q --tb=short
git add launchpad/health_server.py tests/test_fc_cg_summary_export_api.py
git commit -m "Add FlashCopy CG summary Excel export API."
```

---

### Task 3: Contingency Groups page UI (TDD)

**Files:**
- Modify: `launchpad/contingency_groups.py`
- Modify: `tests/test_contingency_groups_page.py`

**Interfaces:**
- HTML: button `id="fc-cg-summary-export"` label **Export Excel** immediately after `#fc-cg-summary-refresh`
- JS `exportFcCgSummary()`:
  1. If `!currentId` → status text “Select a group to export CG summary.”
  2. `await refreshFcCgSummary()` (reuse existing; if it sets error status and returns early on failure, do not open export — have refresh return `boolean` ok, or check status after; **prefer** make `refreshFcCgSummary` return `true`/`false`)
  3. On success: `window.location.assign(`/api/contingency-groups/fc-cg-summary/export?group_id=${encodeURIComponent(currentId)}&format=xlsx&open=1`)`
- Wire click listener next to refresh listener

- [ ] **Step 1: Page tests**

```python
def test_contingency_groups_fc_cg_summary_export_control():
    html = CONTINGENCY_GROUPS_HTML
    section = html.split('id="fc-cg-summary-section"', 1)[1].split(
        'id="wizard-panel"', 1
    )[0]
    assert 'id="fc-cg-summary-export"' in section
    assert "Export Excel" in section
    assert section.index('id="fc-cg-summary-refresh"') < section.index(
        'id="fc-cg-summary-export"'
    )
    assert "/api/contingency-groups/fc-cg-summary/export" in html
    assert "format=xlsx" in html
    assert "function exportFcCgSummary" in html or "exportFcCgSummary(" in html
```

- [ ] **Step 2: Implement UI → PASS → Commit**

```powershell
python -m pytest tests/test_contingency_groups_page.py -q --tb=short
git add launchpad/contingency_groups.py tests/test_contingency_groups_page.py
git commit -m "Add Export Excel to Array FlashCopy CG summary section."
```

---

### Task 4: Version bump to 1.6.81

**Files:**
- Modify: `launchpad/config.py`
- Modify: `tests/test_system_connectivity_version.py`

- [ ] **Step 1:** Assert `1.6.81` (RED) → set `APP_VERSION = "1.6.81"` (GREEN)

```powershell
python -m pytest tests/test_system_connectivity_version.py -q --tb=short
```

- [ ] **Step 2: Commit**

```powershell
git add launchpad/config.py tests/test_system_connectivity_version.py
git commit -m "Bump LaunchPad to 1.6.81 for CG summary Excel export."
```

---

### Task 5: Final verification

```powershell
python -m pytest tests/test_fc_cg_summary_export.py tests/test_fc_cg_summary_export_api.py tests/test_contingency_groups_page.py tests/test_system_connectivity_version.py -q --tb=short
python -c "from launchpad.config import APP_VERSION; print(APP_VERSION)"
```

Expected: PASS, `1.6.81`. No commit unless fixes.

---

## Spec coverage checklist

| Spec item | Task |
|-----------|------|
| Export helper sheet/columns | 1 |
| Live collect + export API + open=1 | 2 |
| Button beside Refresh + JS refresh-then-export | 3 |
| Version 1.6.81 | 4 |
| No Contingency workbook change / no CSV | Global |
