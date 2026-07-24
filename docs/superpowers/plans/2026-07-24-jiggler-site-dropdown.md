# Mouse Jiggler + Site Dropdown + Health Excel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add optional mouse jiggler (default Off) on desktop with Health indicator; Site dropdown (None = all) on Health and Capacity; Health Summary Excel export scoped by Site.

**Architecture:** Persist `mouse_jiggler_enabled` via `db.get_setting`/`set_setting`. Pure `mouse_jiggler` helper starts/stops a background nudge on Windows. Health HTML adds Site `<select>` + Excel button + jiggler status from settings GET. Capacity HTML adds Site `<select>`; capacity-export accepts optional `card_id`. Health Excel builder produces one Summary sheet.

**Tech Stack:** CustomTkinter, ctypes/Win32 cursor (Windows), HealthServer embedded HTML/JS, openpyxl (same as other exports), pytest.

**Spec:** `docs/superpowers/specs/2026-07-24-jiggler-site-dropdown-design.md`

## Global Constraints

- **Worktree:** `.worktrees/jiggler-site-dropdown` on `feature/jiggler-site-dropdown` from `feature/contingency-groups` tip (merge design commit if needed)
- Jiggler default **Off**; desktop toggle + Health indicator; persist setting key `mouse_jiggler_enabled` values `"true"` / `"false"`
- Site dropdown: first option **None** (`value=""`); then `Name (host)` A–Z
- Health Print: specific Site → that card only; None → PDF checks if any else all
- Health Excel: Summary sheet only; columns Card, Host / Site IP, Profile / Model, Monitor, Status, Issue count
- Capacity: monitoring-off filter first, then Site; Excel/Print pass optional `card_id`
- Bump `APP_VERSION` to **1.6.65**
- Commit at each task’s commit step
- Run from: `cd C:\Users\BrianColley\LaunchPad\.worktrees\jiggler-site-dropdown`

---

## File map

| File | Responsibility |
|------|----------------|
| `launchpad/mouse_jiggler.py` | Controller: enable/disable, interval nudge (Windows) |
| `launchpad/health_excel_export.py` | Build Summary workbook bytes from card dicts |
| `launchpad/ui/dashboard_view.py` | Mouse jiggler switch; start/stop controller; persist setting |
| `launchpad/health_server.py` | Health HTML/JS Site+Excel+jiggler; APIs; capacity-export `card_id` |
| `launchpad/capacity_report.py` | Site dropdown; filter DOM; pass `card_id` to export/print |
| `launchpad/capacity_export.py` | Filter export entries/sites by optional `card_id` |
| `launchpad/config.py` | `1.6.65` |
| `tests/test_mouse_jiggler.py` | Default/off/on controller behavior (mock nudge) |
| `tests/test_health_excel_export.py` | Summary rows / card_id scope |
| `tests/test_capacity_export_card_id.py` | card_id filter (or extend existing capacity export tests) |
| `tests/test_health_dashboard_site.py` | HTML contracts Site/None/Excel/jiggler |
| `tests/test_capacity_report_site.py` | HTML contracts Site/None |

---

### Task 0: Confirm baseline

**Files:** none

- [ ] **Step 1: Create worktree**

```powershell
cd C:\Users\BrianColley\LaunchPad
git fetch origin
git worktree add .worktrees/jiggler-site-dropdown -b feature/jiggler-site-dropdown feature/contingency-groups
cd .worktrees/jiggler-site-dropdown
# Ensure design spec present (merge docs/jiggler-site-dropdown-design if needed)
python -c "from launchpad.config import APP_VERSION; print(APP_VERSION)"
Test-Path docs\superpowers\specs\2026-07-24-jiggler-site-dropdown-design.md
Test-Path docs\superpowers\plans\2026-07-24-jiggler-site-dropdown.md
```

Expected: `1.6.64` (or tip), both paths `True`.

- [ ] **Step 2: No feature commit**

---

### Task 1: Mouse jiggler helper (TDD)

**Files:**
- Create: `launchpad/mouse_jiggler.py`
- Create: `tests/test_mouse_jiggler.py`

**Interfaces:**
- Produces:
  - `SETTING_MOUSE_JIGGLER = "mouse_jiggler_enabled"`
  - `DEFAULT_JIGGLE_INTERVAL_SEC = 50` (or 45–60 per spec)
  - `class MouseJiggler`: `enabled: bool`, `start()`, `stop()`, `set_enabled(bool)`, `nudge()` (testable)
  - Parsing: setting string `"true"` → enabled; missing/other → False

- [ ] **Step 1: Failing tests**

```python
from launchpad.mouse_jiggler import (
    SETTING_MOUSE_JIGGLER,
    MouseJiggler,
    setting_to_enabled,
)


def test_setting_default_off():
    assert setting_to_enabled("") is False
    assert setting_to_enabled("false") is False
    assert setting_to_enabled("true") is True
    assert SETTING_MOUSE_JIGGLER == "mouse_jiggler_enabled"


def test_jiggler_set_enabled_calls_nudge_on_timer(monkeypatch):
    calls = []
    j = MouseJiggler(interval_sec=0.05, nudge_fn=lambda: calls.append(1))
    j.set_enabled(True)
    import time
    time.sleep(0.2)
    j.set_enabled(False)
    assert len(calls) >= 1
```

- [ ] **Step 2: Run — expect FAIL**

```powershell
python -m pytest tests/test_mouse_jiggler.py -v
```

- [ ] **Step 3: Implement** `MouseJiggler` with daemon thread or `after`-friendly timer; on Windows `nudge` uses ctypes `SetCursorPos` / `GetCursorPos` ±1px and restore. Non-Windows: no-op nudge. `set_enabled(False)` stops thread cleanly.

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit**

```powershell
git add launchpad/mouse_jiggler.py tests/test_mouse_jiggler.py
git commit -m "Add mouse jiggler helper with default-off setting."
```

---

### Task 2: Desktop toggle + persist

**Files:**
- Modify: `launchpad/ui/dashboard_view.py`
- Test: optional light test if dashboard hard to unit-test; otherwise manual note in report + assert setting round-trip via Database in `tests/test_mouse_jiggler.py`

**Interfaces:**
- Consumes: `MouseJiggler`, `SETTING_MOUSE_JIGGLER`, `db.get_setting` / `set_setting`
- On dashboard init: read setting; create `self._mouse_jiggler`; if true start
- Add `CTkSwitch` text **Mouse jiggler** near Compact / All monitoring (bulk bar)
- On toggle: `set_setting(SETTING_MOUSE_JIGGLER, "true"|"false")`; `jiggler.set_enabled(...)`
- On app destroy/close path: `jiggler.stop()` if hooked

- [ ] **Step 1: Add DB round-trip test**

```python
def test_jiggler_setting_persists(tmp_path):
    # use Database(tmp_path / "t.db") pattern from other tests
    ...
```

- [ ] **Step 2–4: Implement switch + wire lifecycle; run tests; commit**

```powershell
git add launchpad/ui/dashboard_view.py tests/test_mouse_jiggler.py
git commit -m "Add desktop Mouse jiggler switch persisted in settings."
```

Wire HealthServer settings backend already exposes `get_setting` when unlocked — ensure jiggler key is readable when getter is set (Task 3).

---

### Task 3: Health jiggler indicator + GET API

**Files:**
- Modify: `launchpad/health_server.py` (Health HTML + route)
- Create/modify tests for API or HTML contract

**Interfaces:**
- `GET /api/mouse-jiggler` → `{"enabled": bool}` (readable even if locked if getter available; if no getter, `enabled: false`)
- Health hero: `<span id="jiggler-status">Mouse jiggler: Off</span>`; poll on load / every ~30s or after sync
- Desktop remains primary toggle (read-only on Health for v1 unless POST is trivial via existing set_setting backend)

- [ ] **Step 1: Contract test** — Health HTML contains `jiggler-status` and `/api/mouse-jiggler`

- [ ] **Step 2: Implement route + JS poll**

- [ ] **Step 3: Commit**

```powershell
git commit -m "Show mouse jiggler status on Health Dashboard."
```

---

### Task 4: Health Site dropdown + print scope

**Files:**
- Modify: `launchpad/health_server.py` Health HTML/JS

**Interfaces:**
- `<label>Site <select id="health-site-select"><option value="">None</option></select></label>` near filter bar
- Populate from cards: `Name (host)`, sorted by name
- On change: show/hide `.server` sections by `data-id`
- `printSelectedHealth`: if site select has id → print that id only; else existing PDF-check logic (if any checked use them; else all)

- [ ] **Step 1: HTML contract tests** for `health-site-select`, `None`

- [ ] **Step 2: Implement JS filter + print rules**

- [ ] **Step 3: Commit**

```powershell
git commit -m "Add Health Site dropdown for view and print scope."
```

---

### Task 5: Health Summary Excel export

**Files:**
- Create: `launchpad/health_excel_export.py`
- Modify: `launchpad/health_server.py` — button + `GET /api/health-export?card_id=&open=1`
- Create: `tests/test_health_excel_export.py`

**Interfaces:**
- `build_health_summary_workbook(cards: list[dict], *, monitor_enabled: dict) -> bytes`
- Row fields per spec; Status: `monitoring off` | `has issues` | `healthy` (derive from monitor + health_issues / existing flags)
- Export uses Site scope: `card_id` query if set else all cards from `list_cards`

- [ ] **Step 1: Unit tests for row building / single card filter**

- [ ] **Step 2: Implement builder + API + Excel button calling fetch blob download**

- [ ] **Step 3: Commit**

```powershell
git commit -m "Add Health Dashboard Summary Excel export."
```

---

### Task 6: Capacity Site dropdown + card_id export

**Files:**
- Modify: `launchpad/capacity_report.py`
- Modify: `launchpad/capacity_export.py` + `health_server.py` capacity-export handler
- Create: `tests/test_capacity_report_site.py` and/or extend export tests

**Interfaces:**
- Site `<select id="capacity-site-select">` with None + cards
- Filter visible site sections by id after include_off filtering in JS
- Excel URL: `&card_id=` when selected
- Server: if `card_id` present, restrict export set to that id (after include_off)

- [ ] **Step 1: Failing tests** for HTML contract + export filter helper

```python
def test_filter_capacity_entries_by_card_id():
    # helper or export path: only matching card_id remains
    ...
```

- [ ] **Step 2: Implement**

- [ ] **Step 3: Commit**

```powershell
git commit -m "Add Capacity Site dropdown and card_id export filter."
```

---

### Task 7: Version 1.6.65

**Files:**
- Modify: `launchpad/config.py`

- [ ] **Step 1:** `APP_VERSION = "1.6.65"`

- [ ] **Step 2:**

```powershell
python -c "from launchpad.config import APP_VERSION; assert APP_VERSION == '1.6.65'"
python -m pytest tests/test_mouse_jiggler.py tests/test_health_excel_export.py tests/test_health_dashboard_site.py tests/test_capacity_report_site.py -q
# plus any capacity export card_id tests
```

- [ ] **Step 3: Commit**

```powershell
git commit -m "Bump version to 1.6.65 for jiggler and site dropdowns."
```

---

### Task 8: Final review + PR

- [ ] Full related suite green
- [ ] Spec checklist: jiggler default off; Health Site+Excel; Capacity Site; version
- [ ] PR into `feature/contingency-groups`

```powershell
git push -u origin HEAD
gh pr create --base feature/contingency-groups --title "Mouse jiggler + Health/Capacity Site dropdown (v1.6.65)" --body "## Summary
- Desktop mouse jiggler (default Off) + Health status
- Health Site dropdown + Summary Excel
- Capacity Site dropdown scopes Print/Excel

## Test plan
- [ ] pytest related suites
- [ ] Toggle jiggler on desktop; Health shows On
- [ ] Health Site one vs None; Print + Excel
- [ ] Capacity Site one vs None; Print + Excel
"
```

---

## Spec coverage (self-review)

| Spec item | Task |
|-----------|------|
| Jiggler helper + default off | 1 |
| Desktop toggle + persist | 2 |
| Health indicator | 3 |
| Health Site + print rules | 4 |
| Health Summary Excel | 5 |
| Capacity Site + export card_id | 6 |
| Version 1.6.65 | 7 |
| Non-goals (no capacity sheets on Health Excel, etc.) | respected |

**Placeholder scan:** none intentional.  
**Type consistency:** `mouse_jiggler_enabled`, `card_id`, Site `value=""`.
