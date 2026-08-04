# Dell Report Excel Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Dell Report `.xlsx` export (IBM Report + HP Report with utilization LEDs, weekly growth snapshots, empty sibling tabs) with Capacity Report / Dashboard buttons and an Admin show/hide switch.

**Architecture:** Pure helpers map Facility, classify IBM vs HP, compute LED bands and weekly growth from AppData snapshots. A dedicated exporter builds an openpyxl workbook matching the Dell Managed Services layout. HealthServer exposes settings + export; Capacity Report and Dashboard call it when enabled.

**Tech Stack:** Python 3, openpyxl, CustomTkinter Admin, HealthServer HTML/JS, pytest.

**Spec:** `docs/superpowers/specs/2026-08-04-dell-report-export-design.md`

## Global Constraints

- **Branch:** continue on `feature/hpe-capacity-parse` (do not create a new worktree unless tip unavailable).
- **Sheets with data:** **IBM Report**, **HP Report** only.
- **Other tabs:** empty shells (headers/TOC only).
- **Output:** `.xlsx` (not `.xlsb`).
- **LEDs:** green &lt;70%, amber 70–89%, red ≥90% (fraction 0.70 / 0.90).
- **Facility:** heuristics from card/site name (`WAG1`/`WAG2`/DC → sample labels; else `Other`).
- **Weekly Growth:** `(current_used - prior_used) / prior_used` when `prior_used > 0`; else blank (`None`).
- **Snapshots:** on Dell Report export and Capacity Refresh On Sites when current ISO week sample missing; retain last **12** weeks.
- **Units on IBM/HP Report:** GiB (bytes / 1024³).
- **Admin:** `dell_report_enabled` default `true`; hide buttons + block API when false.
- Do **not** change existing Capacity Excel sheet layout.
- Prefer system-level `capacity_summary` (not All-CPGs rollup) for usable/used.
- Bump `APP_VERSION` to **1.6.109** in the final task (if 1.6.108 HPE array/CPG already shipped; if not, use next free patch after current tip — confirm `launchpad/config.py` before bumping).
- Commit at each task’s commit step.
- Run from: `C:\Users\BrianColley\LaunchPad`

---

## File map

| File | Responsibility |
|------|----------------|
| `launchpad/dell_report_facility.py` | Name → Facility string |
| `launchpad/dell_report_family.py` | Profile/vendor → `ibm` \| `hp` \| `None` |
| `launchpad/dell_report_leds.py` | Utilization band → fill color hex |
| `launchpad/dell_report_snapshots.py` | Weekly snapshot store + growth |
| `launchpad/dell_report_settings.py` | Admin enable flag load/save |
| `launchpad/dell_report_export.py` | Build workbook bytes |
| `launchpad/health_server.py` | Settings + export API; snapshot hook on capacity refresh |
| `launchpad/capacity_report.py` | Dell Report button + include_off |
| `launchpad/ui/dashboard_view.py` | Export menu item when enabled |
| `launchpad/ui/admin_view.py` | Show Dell Report checkbox |
| `tests/test_dell_report_*.py` | Unit + workbook + API markers |
| `launchpad/config.py` | Version bump |

Reuse existing patterns: `capacity_email_settings.py` for DB settings; `capacity_export.open_exported_workbook` / download headers; `vendor_for_profile` / device_profile checks in `system_connectivity.py` / `storage_presets.py`.

---

### Task 1: Facility, family, LED helpers

**Files:**
- Create: `launchpad/dell_report_facility.py`
- Create: `launchpad/dell_report_family.py`
- Create: `launchpad/dell_report_leds.py`
- Create: `tests/test_dell_report_helpers.py`

**Interfaces:**

```python
def facility_from_name(name: str) -> str:
    """WAG1 → 'Data center -WAG1'; WAG2 → 'Data center -WAG2';
    distribution/DC patterns → 'Distribution center'; else 'Other'."""

def dell_report_family(device_profile: str, *, manufacturer: str = "") -> str | None:
    """Return 'ibm' | 'hp' | None. HP includes HPE/3PAR/Primera; IBM includes
    flashsystem/storwize/svc/xiv/ds8k-style profiles."""

def utilization_led_fill(utilization: float | None) -> str | None:
    """utilization is 0..1 fraction. <0.70 → '22C55E'; <0.90 → 'F59E0B';
    else 'EF4444'. None/invalid → None."""
```

- [ ] **Step 1: Write failing tests** in `tests/test_dell_report_helpers.py`

```python
from launchpad.dell_report_facility import facility_from_name
from launchpad.dell_report_family import dell_report_family
from launchpad.dell_report_leds import utilization_led_fill

def test_facility_wag_and_other():
    assert facility_from_name("HPE - foo - WAG1") == "Data center -WAG1"
    assert facility_from_name("site wag2 bar") == "Data center -WAG2"
    assert "Distribution" in facility_from_name("v5kPEN-g3v1 Distribution")
    assert facility_from_name("mystery-box") == "Other"

def test_family_ibm_hp():
    assert dell_report_family("flashsystem_9500") == "ibm"
    assert dell_report_family("hpe_3par_8450") == "hp"
    assert dell_report_family("dell_powermax") is None

def test_led_bands():
    assert utilization_led_fill(0.69) == "22C55E"
    assert utilization_led_fill(0.70) == "F59E0B"
    assert utilization_led_fill(0.89) == "F59E0B"
    assert utilization_led_fill(0.90) == "EF4444"
```

(Tune distribution heuristic tests to match the implementation you choose — document the substrings in the module docstring.)

- [ ] **Step 2: Run — expect FAIL**

```bash
python -m pytest tests/test_dell_report_helpers.py -q
```

- [ ] **Step 3: Implement the three modules**

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit**

```bash
git add launchpad/dell_report_facility.py launchpad/dell_report_family.py launchpad/dell_report_leds.py tests/test_dell_report_helpers.py
git commit -m "Add Dell Report facility, family, and LED helpers."
```

---

### Task 2: Weekly snapshots + growth

**Files:**
- Create: `launchpad/dell_report_snapshots.py`
- Create: `tests/test_dell_report_snapshots.py`

**Interfaces:**

```python
DELL_SNAPSHOT_RETENTION_WEEKS = 12

def iso_week_key(dt: datetime | None = None) -> str:
    """UTC ISO year-week string, e.g. '2026-W32'."""

def upsert_week_snapshot(
    store: dict,
    *,
    card_id: int | str,
    week: str,
    usable_bytes: float,
    used_bytes: float,
    model: str,
    facility: str,
    family: str,
    array_name: str,
    captured_at: str,
) -> dict:
    """Insert/replace that card+week; trim older than retention; return store."""

def has_week_snapshot(store: dict, card_id: int | str, week: str) -> bool: ...

def prior_and_current_for_card(
    store: dict, card_id: int | str, *, current_week: str | None = None
) -> tuple[dict | None, dict | None]:
    """Return (prior_snapshot, current_snapshot) for growth columns."""

def weekly_growth_fraction(prior_used: float, current_used: float) -> float | None:
    """(current - prior) / prior if prior > 0 else None."""

def load_dell_snapshots(path: Path | None = None) -> dict: ...
def save_dell_snapshots(store: dict, path: Path | None = None) -> None: ...
```

Default path: under `APP_DATA_DIR` e.g. `dell_report_snapshots.json`.

- [ ] **Step 1: Failing tests** — one week → prior None; two weeks → growth; prior_used 0 → None; retention trims

- [ ] **Step 2: Run — FAIL**

- [ ] **Step 3: Implement**

- [ ] **Step 4: Run — PASS**

- [ ] **Step 5: Commit**

```bash
git commit -m "Add Dell Report weekly capacity snapshot store."
```

---

### Task 3: Admin settings module

**Files:**
- Create: `launchpad/dell_report_settings.py`
- Create: `tests/test_dell_report_settings.py`

**Interfaces:** (mirror `capacity_email_settings` style)

```python
DELL_REPORT_SETTING = "dell_report_settings"

def normalize_dell_report_settings(raw: Any) -> dict:
    """{"enabled": bool} default enabled True."""

def load_dell_report_settings(db) -> dict: ...
def save_dell_report_settings(db, settings: dict) -> dict: ...
def is_dell_report_enabled(db) -> bool: ...
```

- [ ] **Step 1–4:** TDD normalize/load/save defaults

- [ ] **Step 5: Commit**

```bash
git commit -m "Add Dell Report Admin enable settings helpers."
```

---

### Task 4: Workbook builder

**Files:**
- Create: `launchpad/dell_report_export.py`
- Create: `tests/test_dell_report_export.py`

**Interfaces:**

```python
STUB_SHEET_NAMES: list[str]  # PowerMax Report, PowerStore Report, NetApp Report, ...

def bytes_to_gib(num_bytes: float) -> float: ...

def build_dell_report_workbook(
    *,
    ibm_rows: list[dict],
    hp_rows: list[dict],
    report_date: datetime | None = None,
) -> Workbook:
    """
    Each row dict keys:
      facility, array_name, model,
      prior_usable_gib, prior_used_gib, prior_util,  # optional/None
      curr_usable_gib, curr_used_gib, curr_util,
      weekly_growth,  # float|None fraction
    Sheets: TOC/home, IBM Report, HP Report, stubs.
    Apply % number formats + conditional formatting using utilization_led_fill bands.
    """

def workbook_to_bytes(wb: Workbook) -> bytes: ...
```

Layout must mirror reference IBM/HP Report header rows (Home, Date pair, Facility / Array / Model / dual Usable-Used-Util / Weekly Growth %). Group/sort rows by facility then array_name before write.

- [ ] **Step 1: Failing workbook smoke tests**

```python
def test_workbook_has_ibm_hp_and_stub():
    wb = build_dell_report_workbook(
        ibm_rows=[{... minimal ...}],
        hp_rows=[{... minimal ...}],
    )
    assert "IBM Report" in wb.sheetnames
    assert "HP Report" in wb.sheetnames
    assert any("PowerMax" in n for n in wb.sheetnames)
    # stub has header only / max_row small
```

- [ ] **Step 2: Run — FAIL**

- [ ] **Step 3: Implement builder + conditional formatting**

- [ ] **Step 4: Run — PASS**

- [ ] **Step 5: Commit**

```bash
git commit -m "Build Dell Report xlsx with IBM/HP sheets and stubs."
```

---

### Task 5: Collect rows + snapshot on export/refresh

**Files:**
- Modify: `launchpad/dell_report_export.py` (or new `dell_report_collect.py`)
- Modify: `launchpad/health_server.py` — capacity refresh path + new export route
- Create: `tests/test_dell_report_api.py` (markers / handler path asserts; light functional if fixtures exist)

**Behavior:**

```python
def collect_dell_report_rows(
    sites: list[ExportSite | dict],
    *,
    snapshot_store: dict,
    now: datetime | None = None,
) -> tuple[list[dict], list[dict], dict]:
    """Split ibm/hp rows from capacity_summary; upsert current week if missing;
    attach prior/current/growth; return (ibm_rows, hp_rows, updated_store)."""
```

- API: `GET /api/dell-report-export?include_off=0|1&open=1`
  - If not `is_dell_report_enabled` → 403 JSON `{"error": "Dell Report is disabled in Admin."}`
  - Build workbook from monitored (or include_off) IBM/HP sites using same card listing as capacity export
  - Save snapshots; return `.xlsx` download; optional open
- On Capacity Report refresh-all / per-card capacity refresh success: call snapshot upsert when week missing (best-effort; do not fail refresh)

- [ ] **Step 1: Failing tests** for disabled 403 path string + route declared; collect growth with fake store

- [ ] **Step 2–4:** Implement + pass

- [ ] **Step 5: Commit**

```bash
git commit -m "Wire Dell Report export API and weekly snapshot capture."
```

---

### Task 6: Capacity Report + Dashboard + Admin UI

**Files:**
- Modify: `launchpad/capacity_report.py`
- Modify: `launchpad/ui/dashboard_view.py`
- Modify: `launchpad/ui/admin_view.py`
- Modify: `launchpad/health_server.py` — expose `dell_report_enabled` to Capacity HTML (template flag or `/api/dell-report-settings` GET)
- Create/extend: `tests/test_capacity_report_dell_button.py` (or page marker tests)

**UI:**

- Capacity Report: button `id="dell-report-btn"` label **Dell Report** near Export Excel; hidden when setting off; passes `include_off` like Excel export.
- Dashboard Export menu: **Dell Report…** when enabled (same download/open flow).
- Admin (Capacity email tab or new small Reports panel): checkbox **Show Dell Report button**; save with existing settings save pattern.

- [ ] **Step 1: Marker tests** — `Dell Report` in capacity HTML; admin checkbox string; dashboard menu label when wired

- [ ] **Step 2–4:** Implement visibility + click handlers

- [ ] **Step 5: Commit**

```bash
git commit -m "Add Dell Report buttons and Admin show/hide control."
```

---

### Task 7: Version bump + verification

**Files:**
- Modify: `launchpad/config.py` → `APP_VERSION = "1.6.109"` (confirm tip version first)
- Modify: `tests/test_system_connectivity_version.py`

**Steps:**

- [ ] **Step 1: Bump version + pin test**

- [ ] **Step 2: Focused pytest**

```bash
python -m pytest tests/test_dell_report_helpers.py tests/test_dell_report_snapshots.py tests/test_dell_report_settings.py tests/test_dell_report_export.py tests/test_dell_report_api.py tests/test_system_connectivity_version.py -q
```

- [ ] **Step 3: Manual smoke**

1. Admin: confirm Show Dell Report on; Capacity Report shows button.
2. Unlock, Refresh On Sites for IBM + HPE cards.
3. Dell Report → open `.xlsx`; IBM/HP sheets populated; PowerMax stub empty; utilization cells colored.
4. Admin: turn off → button disappears; direct API fails.
5. After changing used capacity and advancing week key in a unit test, growth non-zero.

- [ ] **Step 4: Commit**

```bash
git commit -m "Bump app version to 1.6.109 for Dell Report export."
```

---

## Done when

- [ ] IBM Report + HP Report match agreed columns, GiB, LEDs, facility grouping.
- [ ] Stub tabs exist without data.
- [ ] Weekly snapshots persist and drive growth when two weeks exist.
- [ ] Capacity Report + Dashboard (if fitted) + Admin off-switch work.
- [ ] Existing Capacity Excel unchanged.
- [ ] `APP_VERSION` bumped and tests green.
