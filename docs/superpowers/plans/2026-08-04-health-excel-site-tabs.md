# Health Excel Per-Site Tabs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend Health Dashboard Export Excel with section toggles and one detail sheet per selected site (issues + command summaries / optional raw output).

**Architecture:** Pure helpers in `health_excel_export.py` build Summary and per-site sheets from card payloads and section flags. `/api/health-export` accepts multi `card_id` + section query flags. Health Dashboard HTML adds four `localStorage`-backed checkboxes and passes selection + flags from the existing Export Excel button.

**Tech Stack:** Python 3, openpyxl, HealthServer HTML/JS, pytest.

**Spec:** `docs/superpowers/specs/2026-08-04-health-excel-site-tabs-design.md`

## Global Constraints

- **Branch:** continue on `feature/hpe-capacity-parse` (do not create a new worktree unless tip unavailable).
- **Entry point:** existing **Export Excel** only (no second button).
- **Section toggles:** Summary · Issues · Command summaries · Raw output.
- **Defaults:** Summary / Issues / Command summaries **on**; Raw output **off**.
- **Site tabs:** PDF selection (`printSelectedIds`), or Site filter when one site is chosen.
- **Summary-only:** when Summary on and no sites selected → Summary workbook for all cards; when Summary off and no sites → client error (do not call API) or API 400.
- **Skip site sheets** when Issues and Command summaries and Raw are all off (even if sites selected); if Summary also off → 400 `Nothing to export`.
- **No live SSH** on export — use cached card `health_issues` / `command_results`.
- Excel sheet titles ≤ 31 chars; sanitize illegal `[]:*?/\` chars; disambiguate with ` (2)`.
- Excel cell max ~32767 chars: truncate raw with `… (truncated)` when needed.
- Bump `APP_VERSION` to **1.6.110** in the final task.
- Commit at each task’s commit step.
- Run from: `C:\Users\BrianColley\LaunchPad`

---

## File map

| File | Responsibility |
|------|----------------|
| `launchpad/health_excel_export.py` | Section flags, safe sheet names, Summary + per-site sheets, `build_health_workbook` |
| `launchpad/health_server.py` | Toggle UI, `downloadHealthExcel` query params, `/api/health-export` parsing, `export_health_excel_bytes` |
| `tests/test_health_excel_export.py` | Workbook unit tests (extend) |
| `tests/test_health_excel_export_api.py` (or extend existing) | API flags / 400 / multi card_id |
| `launchpad/config.py` | `APP_VERSION = "1.6.110"` |

Reuse: existing `HEALTH_SUMMARY_HEADERS`, `_styled_summary_workbook` patterns, `summarize_command_output` from `flashsystem_parse` when payload lacks a summary field, Print selection helpers in `DASHBOARD_HTML`.

---

### Task 1: Sheet naming + section options helpers

**Files:**
- Modify: `launchpad/health_excel_export.py`
- Modify: `tests/test_health_excel_export.py`

**Interfaces:**

```python
@dataclass(frozen=True)
class HealthExcelSections:
    summary: bool = True
    issues: bool = True
    command_summaries: bool = True
    raw: bool = False

def parse_health_excel_sections(
    *,
    summary: str | bool = True,
    issues: str | bool = True,
    command_summaries: str | bool = True,
    raw: str | bool = False,
) -> HealthExcelSections:
    """Coerce 0/1/true/false query values; defaults match spec."""

def excel_safe_sheet_title(name: str, *, used: set[str], max_len: int = 31) -> str:
    """Sanitize + truncate + disambiguate into `used`."""

def truncate_excel_cell(text: str, *, limit: int = 32767) -> str:
    """Append '… (truncated)' when over limit."""
```

- [ ] **Step 1: Write failing tests** for safe titles (illegal chars, length, collision) and section parsing defaults / `raw=0`

- [ ] **Step 2: Run — expect FAIL**

```bash
python -m pytest tests/test_health_excel_export.py -q -k "sheet_title or sections or truncate"
```

- [ ] **Step 3: Implement helpers**

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit**

```bash
git commit -m "Add Health Excel section flags and safe sheet-title helpers."
```

---

### Task 2: Per-site sheet builder + unified workbook API

**Files:**
- Modify: `launchpad/health_excel_export.py`
- Modify: `tests/test_health_excel_export.py`

**Interfaces:**

```python
def command_summary_text(item: dict) -> str:
    """Prefer item['summary']; else summarize_command_output(label, command, output)."""

def build_health_workbook(
    cards: list[dict],
    *,
    monitor_enabled: Mapping[int | str, bool],
    sections: HealthExcelSections,
    detail_card_ids: list[int] | None = None,
) -> bytes:
    """
    - If sections.summary: Summary sheet for summary_cards
      (detail_card_ids if provided else all cards).
    - If detail_card_ids and (issues or command_summaries or raw):
      one sheet per matching card with enabled sections.
    - If nothing to write: raise ValueError("Nothing to export").
    Keep build_health_summary_workbook as thin wrapper calling
    build_health_workbook(..., sections=HealthExcelSections(summary=True,
    issues=False, command_summaries=False, raw=False), detail_card_ids=None)
    for backward compatibility OR update call sites only.
    """
```

Per-site sheet layout (rows grow downward):

1. Title row: card name  
2. Host / Profile / Monitor  
3. Blank  
4. **Issues** header + table (severity, category, message) if `sections.issues`  
5. **Commands** header if `command_summaries or raw`  
6. For each command_results item: Label, Command, Error; optional Summary; optional Raw (truncated)

- [ ] **Step 1: Failing tests**

```python
def test_workbook_summary_plus_two_site_sheets():
    ...
    assert "Summary" in wb.sheetnames
    assert len([n for n in wb.sheetnames if n != "Summary"]) == 2

def test_workbook_command_summary_without_raw():
    # raw cells absent / no long output column

def test_workbook_includes_raw_when_flag_on():
    ...

def test_nothing_to_export_raises():
    with pytest.raises(ValueError, match="Nothing to export"):
        build_health_workbook(..., sections=all_false, detail_card_ids=None)
```

- [ ] **Step 2–4:** Implement + pass

- [ ] **Step 5: Commit**

```bash
git commit -m "Build Health Excel workbooks with per-site detail sheets."
```

---

### Task 3: API multi card_id + section flags

**Files:**
- Modify: `launchpad/health_server.py` (`/api/health-export` + `export_health_excel_bytes`)
- Create or extend: `tests/test_health_excel_export_api.py` / `tests/test_health_excel_export.py`

**Behavior:**

```python
def export_health_excel_bytes(
    self,
    *,
    card_id: int | None = None,  # legacy single
    card_ids: list[int] | None = None,  # detail tabs
    sections: HealthExcelSections | None = None,
) -> tuple[bytes, str]:
```

- Parse query: `summary`, `issues`, `command_summaries`, `raw` via `parse_health_excel_sections`.
- Parse sites: all `card_id` query values → `card_ids` list; if exactly one and no multi, keep legacy filter for Summary scope when detail flags off… Spec: Site filter / multi PDF ids are **detail** sites; Summary uses those ids when any detail ids present, else all cards for Summary-only.
- Map `ValueError("Nothing to export")` → HTTP 400 JSON.

- [ ] **Step 1: Failing API tests** — multi ids create N sheets; 400 when nothing; defaults preserve Summary-only when no section params and no card_id (backward compatible)

- [ ] **Step 2–4:** Wire + pass

- [ ] **Step 5: Commit**

```bash
git commit -m "Extend health-export API for section flags and multi-site tabs."
```

---

### Task 4: Health Dashboard toggles + Export Excel wiring

**Files:**
- Modify: `launchpad/health_server.py` (`DASHBOARD_HTML` near `#health-excel-btn` and `downloadHealthExcel`)
- Extend: `tests/test_health_excel_export.py` (or page marker test) asserting toggle ids and query param names in HTML/JS

**UI:**

```html
<label class="toggle-row"><input type="checkbox" id="health-excel-summary" checked> Summary</label>
<label class="toggle-row"><input type="checkbox" id="health-excel-issues" checked> Issues</label>
<label class="toggle-row"><input type="checkbox" id="health-excel-cmd-summaries" checked> Command summaries</label>
<label class="toggle-row"><input type="checkbox" id="health-excel-raw"> Raw output</label>
```

JS:

- Keys: `launchpad.healthExcel.summary|issues|commandSummaries|rawOutput`
- Init from localStorage (raw defaults false; others true if missing)
- `downloadHealthExcel`:
  - `detailIds` = site filter id if set, else `[...printSelectedIds]`
  - If `detailIds` empty and Summary unchecked → status error, return
  - If `detailIds` empty and Summary checked → Summary-only (no `card_id` params)
  - Else append repeated `card_id=` for each detail id
  - Append `summary=`, `issues=`, `command_summaries=`, `raw=` as `1`/`0`
  - Keep `open=1`

- [ ] **Step 1: Marker tests** for ids + localStorage keys + query param names in `DASHBOARD_HTML`

- [ ] **Step 2–4:** Implement + pass

- [ ] **Step 5: Commit**

```bash
git commit -m "Add Health Excel section toggles and multi-site export wiring."
```

---

### Task 5: Version bump + verification

**Files:**
- Modify: `launchpad/config.py` → `APP_VERSION = "1.6.110"`
- Modify: `tests/test_system_connectivity_version.py`

**Steps:**

- [ ] **Step 1: Bump + pin**

- [ ] **Step 2: Focused pytest**

```bash
python -m pytest tests/test_health_excel_export.py tests/test_health_excel_export_api.py tests/test_system_connectivity_version.py -q
```

(Use whichever test file names Task 3 created.)

- [ ] **Step 3: Manual smoke**

1. Open Health Dashboard; confirm four toggles (Raw unchecked).
2. Check two PDF sites → Export Excel → Summary + two site tabs with issues/command summaries, no huge raw.
3. Enable Raw → re-export → raw present.
4. Uncheck all PDF, Site=All, Summary on → Summary-only.
5. Summary off, no PDF → client error message.

- [ ] **Step 4: Commit**

```bash
git commit -m "Bump app version to 1.6.110 for Health Excel site tabs."
```

---

## Done when

- [ ] Section toggles persist and drive the workbook.
- [ ] Per-site tabs for PDF/Site selection with Issues / summaries / optional raw.
- [ ] Summary-only and empty-export behaviors match the spec.
- [ ] Existing Export Excel button remains the only entry point.
- [ ] `APP_VERSION` is **1.6.110** and focused tests pass.
