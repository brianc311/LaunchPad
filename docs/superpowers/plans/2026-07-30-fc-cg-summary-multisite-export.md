# Multi-Site CG Summary Select + Excel Site Tabs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Multi-site Array FlashCopy CG summary on Contingency Groups with checkboxes/Select all and Excel export of checked rows as one sheet per site (v**1.6.85**).

**Architecture:** New live scan + cache (Status eligibility); extend export helper for multi-sheet by site; Contingency UI site filter + checkboxes; POST export with selected row keys. Reuse `fc_consistgrp_inventory` / `build_cg_summaries` per card.

**Tech Stack:** Python, HealthServer, openpyxl, pytest.

**Spec:** `docs/superpowers/specs/2026-07-30-fc-cg-summary-multisite-export-design.md`

## Global Constraints

- **Worktree:** `.worktrees/fc-cg-summary-multisite` on `feature/fc-cg-summary-multisite` from `feature/contingency-groups` tip (≥ `1.6.84` + spec `6087b20`)
- Eligibility: `is_fc_consistgrp_status_eligible` (monitor_on + ssh + SVC/FlashSystem)
- Export = checked rows only; one Excel sheet per site; Refresh fills cache first
- Panel independent of Contingency group picker
- Bump `APP_VERSION` to **1.6.85**
- Commit per task; run from worktree
- Operator install folder note: `C:\Users\BrianColley\LaunchPad\LaunchPad-install` (build.bat output)

---

## File map

| File | Responsibility |
|------|----------------|
| `launchpad/fc_cg_summary_export.py` | Multi-sheet export; Site column; sheet name sanitize |
| `launchpad/health_server.py` | `scan_fc_cg_summary_live`, cache, POST export selected |
| `launchpad/contingency_groups.py` | Multi-site UI + checkboxes + JS |
| `launchpad/config.py` | `1.6.85` |
| Tests | Export multi-sheet, API live/export, page markers, version |

---

### Task 0: Confirm baseline

```powershell
cd C:\Users\BrianColley\LaunchPad
git worktree add .worktrees/fc-cg-summary-multisite -b feature/fc-cg-summary-multisite feature/contingency-groups
cd .worktrees\fc-cg-summary-multisite
python -c "from launchpad.config import APP_VERSION; print(APP_VERSION)"
Test-Path docs\superpowers\specs\2026-07-30-fc-cg-summary-multisite-export-design.md
```

Expected: ≥ `1.6.84`, spec `True`. No feature commit.

---

### Task 1: Multi-sheet export helper (TDD)

**Files:**
- Modify: `launchpad/fc_cg_summary_export.py`
- Modify: `tests/test_fc_cg_summary_export.py`

**Interfaces:**
- Add `"Site"` as first header/field (`site`)
- Keep single-sheet `export_fc_cg_summary_xlsx(rows)` for backward compat (sheet `FC CG Summary`, include Site column)
- Add `export_fc_cg_summary_multisite_xlsx(rows: list[dict]) -> bytes`:
  - Group by `site` (fallback card_name/name)
  - One sheet per site, titles sanitized (invalid chars → `_`, max 31, unique with suffix)
  - Sites sorted A–Z
  - Same SUMMARY_HEADERS including Site
- Add `sanitize_excel_sheet_name(name: str, *, used: set[str]) -> str`

- [ ] **Step 1: Failing tests** for multisite sheets + only selected rows present; sheet name sanitize

```python
def test_export_multisite_one_sheet_per_site():
    rows = [
        {"site": "Anderson", "name": "CG1", "status": "idle_or_copied", "progress_pct": 100},
        {"site": "Jupiter", "name": "CG2", "status": "copying", "progress_pct": 75},
        {"site": "Anderson", "name": "CG3", "status": "stopped", "progress_pct": 50},
    ]
    body = export_fc_cg_summary_multisite_xlsx(rows)
    wb = load_workbook(BytesIO(body))
    assert wb.sheetnames == ["Anderson", "Jupiter"]
    assert wb["Anderson"]["B2"].value == "CG1"  # Name col after Site
```

- [ ] **Step 2: Implement → PASS → Commit**

```powershell
python -m pytest tests/test_fc_cg_summary_export.py -q --tb=short
git add launchpad/fc_cg_summary_export.py tests/test_fc_cg_summary_export.py
git commit -m "Add multi-site FlashCopy CG summary Excel sheets by site."
```

---

### Task 2: Live scan + cache + POST export API (TDD)

**Files:**
- Modify: `launchpad/health_server.py`
- Create: `tests/test_fc_cg_summary_multisite_api.py`

**Interfaces:**
- `scan_fc_cg_summary_live(self, *, card_id: int | None = None) -> dict`
  - Unlock required (RuntimeError)
  - Loop eligible cards like Status; per card `fc_consistgrp_inventory` → `summaries` (or build from groups/maps if needed — inventory already returns summaries)
  - Each row: site, card_name, host, card_id, name, status, flash_time, progress_pct, fc_map_count, host_map_count, total_size, policy, snaps_per_week, `row_key` = `f"{card_id}:{name}"`
  - Cache under `_fc_cg_summary_live_cache`
  - Return `{rows, errors}`
- `export_fc_cg_summary_selected_bytes(self, *, selected: list[str], open_after unused here) -> tuple[bytes,str,str]`
  - LookupError if no cache
  - ValueError if selected empty
  - Filter cache rows where `row_key` in selected; then `export_fc_cg_summary_multisite_xlsx`
- Routes:
  - `GET /api/contingency-groups/fc-cg-summary/live`
  - `POST /api/contingency-groups/fc-cg-summary/export-selected` with JSON `{"selected":[...],"open":true}` (keep existing GET export for single-group if still used, or leave it)
- Keep legacy `GET .../fc-cg-summary?group_id=` for now (optional unused by new UI)

- [ ] **Step 1: API tests** unlock; happy path mocked inventory; export selected only; empty selection raises

- [ ] **Step 2: Implement → PASS → Commit**

```powershell
python -m pytest tests/test_fc_cg_summary_multisite_api.py tests/test_fc_cg_summary_export.py -q --tb=short
git add launchpad/health_server.py tests/test_fc_cg_summary_multisite_api.py
git commit -m "Add multi-site CG summary live scan and selected export API."
```

---

### Task 3: Contingency page UI (TDD)

**Files:**
- Modify: `launchpad/contingency_groups.py`
- Modify: `tests/test_contingency_groups_page.py`

**UI:**
- Site `<select id="fc-cg-summary-site">` (load from `/api/fc-consistgrp/cards` or `/api/cards`)
- Refresh → `GET /api/contingency-groups/fc-cg-summary/live`
- Table: select-all checkbox + row checkboxes (`data-row-key`); Site column; existing fields
- Export → gather checked keys; `POST /api/contingency-groups/fc-cg-summary/export-selected` then download blob / or open=1 response — match HV pattern: if POST returns file bytes, trigger download; support `open` in JSON for server-side open
- No longer require `currentId` for Refresh

- [ ] **Step 1: Page tests** for select-all, live path, export-selected, site select, checkbox markers

- [ ] **Step 2: Implement → PASS → Commit**

```powershell
python -m pytest tests/test_contingency_groups_page.py -q --tb=short
git add launchpad/contingency_groups.py tests/test_contingency_groups_page.py
git commit -m "Add multi-site CG summary checkboxes and site-tab export UI."
```

---

### Task 4: Version 1.6.85

- [ ] Assert + set `APP_VERSION = "1.6.85"`
- [ ] Commit: `Bump LaunchPad to 1.6.85 for multi-site CG summary export.`

---

### Task 5: Final verification

```powershell
python -m pytest tests/test_fc_cg_summary_export.py tests/test_fc_cg_summary_multisite_api.py tests/test_contingency_groups_page.py tests/test_system_connectivity_version.py -q --tb=short
python -c "from launchpad.config import APP_VERSION; print(APP_VERSION)"
```

Expected: PASS, `1.6.85`.

---

## Spec coverage checklist

| Spec item | Task |
|-----------|------|
| Multi-sheet export by site | 1 |
| Live scan + cache + selected export | 2 |
| Checkboxes / Select all / site UI | 3 |
| Version 1.6.85 | 4 |
| Checked-only; no Status mode change | Global |
