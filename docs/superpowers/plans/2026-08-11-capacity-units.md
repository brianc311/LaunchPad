# Capacity Unit Toggle (GiB/TiB ↔ GB/TB) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a persisted global capacity-unit mode so LaunchPad displays and exports IEC GiB/TiB by default and can switch to real SI GB/TB (v**1.6.151**).

**Architecture:** New `launchpad/capacity_units.py` owns in-memory mode plus `format_bytes` / `bytes_to_capacity_unit`. `_format_bytes` delegates. Dell headers and cell divisors read the mode at Excel write. Dashboard header switch persists `capacity_unit_mode`. HealthServer injects the mode into page JS. CLI parse stays 1024 → bytes.

**Tech Stack:** Python, CustomTkinter, HealthServer HTML/JS, openpyxl, pytest.

**Spec:** `docs/superpowers/specs/2026-08-11-capacity-units-design.md`

## Global Constraints

- APP_VERSION is currently `1.6.150`; bump to `1.6.151` in the JS/version task.
- Setting key `capacity_unit_mode`; values `iec` | `si`; missing/unknown/empty → `iec`.
- IEC = 1024, labels GiB/TiB/PiB. SI = 1000, labels GB/TB/PB. Numbers change when flipped.
- Parse (`_parse_size_bytes`) stays 1024-based. Snapshots keep `*_bytes`. No SSH on toggle.
- Dell usable/used headers follow the mode (`(GiB)` vs `(GB)`); columns stay fixed giga-unit (no TiB auto-scale).
- Do **not** change LUN Builder / Contingency create CLI (`-unit gb`, `parse_capacity_to_gb`).
- Windows PowerShell commits (`git commit -m "..."`); commit at each task’s commit step.
- Prefer TDD: failing test → implement → pass → commit.
- Do not commit `.superpowers/sdd*` scratch or install zips.
- Reset in-memory mode to `iec` after tests that change it (autouse fixture).

## File structure

| File | Responsibility |
|------|----------------|
| `launchpad/capacity_units.py` | Mode get/set, `format_bytes`, `bytes_to_capacity_unit`, `capacity_unit_header` |
| `launchpad/flashsystem_parse.py` | `_format_bytes` delegates; parse unchanged |
| `tests/test_capacity_units.py` | Formatter + mode + parse contract |
| `tests/conftest.py` | Autouse reset mode to `iec` |
| `launchpad/dell_report_export.py` | Mode-aware headers + write-time conversion |
| `launchpad/ui/dashboard_view.py` | Header switch, persist, refresh cards |
| `launchpad/app.py` | Load mode from DB at startup |
| `launchpad/health_format.py` | `_gb` uses `format_bytes` |
| HealthServer + page JS | Inject mode; align `formatBytes` |
| `launchpad/config.py` | `APP_VERSION` → `1.6.151` |
| `tests/test_system_connectivity_version.py` | Version pin → `1.6.151` |
| `tests/test_hadoop_sudo_wire.py` | Version pin → `1.6.151` |

---

### Task 1: `capacity_units` + `_format_bytes` delegate

**Files:**
- Create: `launchpad/capacity_units.py`
- Create: `tests/test_capacity_units.py`
- Create: `tests/conftest.py`
- Modify: `launchpad/flashsystem_parse.py` (`_format_bytes` only)
- Modify: `tests/test_fc_cg_summary_multisite_api.py` (expected `total_size` label `10.0 GiB` if produced by `_format_bytes`)

**Interfaces:**
- Produces:
  - `SETTING_CAPACITY_UNIT_MODE = "capacity_unit_mode"`
  - `normalize_capacity_unit_mode(raw: str | None) -> str` → `"iec"` or `"si"`
  - `get_capacity_unit_mode() -> str`
  - `set_capacity_unit_mode(mode: str | None) -> str`
  - `load_capacity_unit_mode(db) -> str` (reads `db.get_setting(SETTING_CAPACITY_UNIT_MODE, "iec")`)
  - `format_bytes(num_bytes: float) -> str`
  - `bytes_to_capacity_unit(num_bytes: float) -> float`
  - `capacity_unit_header() -> str` → `"GiB"` or `"GB"`
  - `iec_gib_to_display(gib: float) -> float` → IEC passthrough; SI = `gib * 1024**3 / 1000**3`
- Consumes: none

- [ ] **Step 1: Write the failing tests**

Create `tests/test_capacity_units.py`:

```python
from launchpad.capacity_units import (
    bytes_to_capacity_unit,
    capacity_unit_header,
    format_bytes,
    get_capacity_unit_mode,
    iec_gib_to_display,
    normalize_capacity_unit_mode,
    set_capacity_unit_mode,
)
from launchpad.flashsystem_parse import _format_bytes, _parse_size_bytes


def test_normalize_capacity_unit_mode():
    assert normalize_capacity_unit_mode(None) == "iec"
    assert normalize_capacity_unit_mode("") == "iec"
    assert normalize_capacity_unit_mode("IEC") == "iec"
    assert normalize_capacity_unit_mode("nope") == "iec"
    assert normalize_capacity_unit_mode("si") == "si"
    assert normalize_capacity_unit_mode("SI") == "si"


def test_format_bytes_iec_default():
    set_capacity_unit_mode("iec")
    assert get_capacity_unit_mode() == "iec"
    assert format_bytes(0) == "0 GiB"
    assert format_bytes(-1) == "0 GiB"
    assert format_bytes(1024**3) == "1.0 GiB"
    assert format_bytes(1024**4) == "1.0 TiB"
    assert _format_bytes(1024**3) == "1.0 GiB"
    assert capacity_unit_header() == "GiB"
    assert bytes_to_capacity_unit(1024**3) == 1.0


def test_format_bytes_si_recalculates():
    set_capacity_unit_mode("si")
    assert format_bytes(0) == "0 GB"
    assert format_bytes(1024**3) == "1.1 GB"
    assert format_bytes(1024**4) == "1.1 TB"
    assert _format_bytes(1024**3) == "1.1 GB"
    assert capacity_unit_header() == "GB"
    assert abs(bytes_to_capacity_unit(1024**3) - 1.073741824) < 1e-9
    assert abs(iec_gib_to_display(1.0) - 1.073741824) < 1e-9


def test_parse_size_bytes_ignores_display_mode():
    set_capacity_unit_mode("si")
    assert _parse_size_bytes("1TB") == float(1024**4)
    assert _parse_size_bytes("1TiB") == float(1024**4)
    assert _parse_size_bytes("1GB") == float(1024**3)
```

Create `tests/conftest.py`:

```python
import pytest

from launchpad.capacity_units import set_capacity_unit_mode


@pytest.fixture(autouse=True)
def _reset_capacity_unit_mode():
    set_capacity_unit_mode("iec")
    yield
    set_capacity_unit_mode("iec")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_capacity_units.py -v`  
Expected: FAIL (module missing)

- [ ] **Step 3: Implement `capacity_units.py` and delegate `_format_bytes`**

Create `launchpad/capacity_units.py`:

```python
from __future__ import annotations

from typing import Any

SETTING_CAPACITY_UNIT_MODE = "capacity_unit_mode"

_MODE = "iec"
_IEC_GIGA = 1024**3
_SI_GIGA = 1000**3


def normalize_capacity_unit_mode(raw: str | None) -> str:
    return "si" if str(raw or "").strip().lower() == "si" else "iec"


def get_capacity_unit_mode() -> str:
    return _MODE


def set_capacity_unit_mode(mode: str | None) -> str:
    global _MODE
    _MODE = normalize_capacity_unit_mode(mode)
    return _MODE


def load_capacity_unit_mode(db: Any) -> str:
    raw = db.get_setting(SETTING_CAPACITY_UNIT_MODE, "iec")
    return set_capacity_unit_mode(raw)


def capacity_unit_header() -> str:
    return "GB" if _MODE == "si" else "GiB"


def bytes_to_capacity_unit(num_bytes: float) -> float:
    base = _SI_GIGA if _MODE == "si" else _IEC_GIGA
    return float(num_bytes) / base


def iec_gib_to_display(gib: float) -> float:
    if _MODE == "si":
        return float(gib) * _IEC_GIGA / _SI_GIGA
    return float(gib)


def format_bytes(num_bytes: float) -> str:
    if num_bytes <= 0:
        return f"0 {capacity_unit_header()}"
    if _MODE == "si":
        units = ["GB", "TB", "PB"]
        step = 1000.0
        value = num_bytes / _SI_GIGA
    else:
        units = ["GiB", "TiB", "PiB"]
        step = 1024.0
        value = num_bytes / _IEC_GIGA
    unit = units[0]
    if value >= step:
        value /= step
        unit = units[1]
    if value >= step:
        value /= step
        unit = units[2]
    return f"{value:.1f} {unit}"
```

In `launchpad/flashsystem_parse.py`, replace the body of `_format_bytes` (keep the name and signature). Add the import at the **top** of the file:

```python
from launchpad.capacity_units import format_bytes as _format_capacity_bytes
```

```python
def _format_bytes(num_bytes: float) -> str:
    return _format_capacity_bytes(num_bytes)
```

Do **not** change `_parse_size_bytes`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_capacity_units.py tests/test_fc_cg_summary_multisite_api.py tests/test_fc_consistgrp_ops.py -v`

If `test_fc_cg_summary_multisite_api.py` fails on `total_size == "10.0 GB"` because the value is produced by `_format_bytes`, change that assertion (and only computed labels) to `"10.0 GiB"`. Leave fixture strings that are not formatted by `_format_bytes`.

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add launchpad/capacity_units.py launchpad/flashsystem_parse.py tests/test_capacity_units.py tests/conftest.py tests/test_fc_cg_summary_multisite_api.py
git commit -m "Add capacity unit mode and IEC GiB/TiB display formatting."
```

---

### Task 2: Dell Report headers and write-time units

**Files:**
- Modify: `launchpad/dell_report_export.py`
- Modify: `tests/test_dell_report_export.py`

**Interfaces:**
- Consumes: `bytes_to_capacity_unit`, `capacity_unit_header`, `iec_gib_to_display`, `set_capacity_unit_mode` from Task 1
- Produces: Dell usable/used headers and numeric cells follow current mode; `bytes_to_gib` stays IEC (`num_bytes / 1024**3`)

- [ ] **Step 1: Write the failing Dell tests**

Add to `tests/test_dell_report_export.py`:

```python
from launchpad.capacity_units import set_capacity_unit_mode
from launchpad.dell_report_export import bytes_to_capacity_unit


def test_dell_headers_follow_capacity_unit_mode():
    set_capacity_unit_mode("iec")
    wb = build_dell_report_workbook(
        ibm_rows=[_minimal_row()],
        hp_rows=[],
        report_date=datetime(2026, 6, 15, tzinfo=timezone.utc),
    )
    ws = wb["IBM Report"]
    c = _FIRST_DATA_COL
    assert ws.cell(9, c + 3).value == "Useable Capacity (GiB)"
    assert ws.cell(9, c + 4).value == "Used Capacity (GiB)"
    assert ws.cell(9, c + 6).value == "Useable Capacity (GiB)"
    assert ws.cell(9, c + 7).value == "Used Capacity (GiB)"

    set_capacity_unit_mode("si")
    wb_si = build_dell_report_workbook(
        ibm_rows=[_minimal_row()],
        hp_rows=[],
        report_date=datetime(2026, 6, 15, tzinfo=timezone.utc),
    )
    ws_si = wb_si["IBM Report"]
    assert ws_si.cell(9, c + 3).value == "Useable Capacity (GB)"
    assert ws_si.cell(9, c + 4).value == "Used Capacity (GB)"
    assert ws_si.cell(9, c + 6).value == "Useable Capacity (GB)"
    assert ws_si.cell(9, c + 7).value == "Used Capacity (GB)"


def test_bytes_to_capacity_unit_matches_mode():
    set_capacity_unit_mode("iec")
    assert bytes_to_capacity_unit(1024**3) == 1.0
    set_capacity_unit_mode("si")
    assert abs(bytes_to_capacity_unit(1024**3) - 1.073741824) < 1e-9
```

Extend `test_workbook_has_report_wkly_sheets_with_week_columns` (or add a sibling) so a Wkly usable header is `(GiB)` in iec and `(GB)` in si. Keep existing `bytes_to_gib` tests (always 1024).

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_dell_report_export.py::test_dell_headers_follow_capacity_unit_mode tests/test_dell_report_export.py::test_bytes_to_capacity_unit_matches_mode -v`  
Expected: FAIL (headers still GiB in si, or import missing)

- [ ] **Step 3: Wire Dell export**

At top of `launchpad/dell_report_export.py` (with the other imports):

```python
from launchpad.capacity_units import (
    bytes_to_capacity_unit,
    capacity_unit_header,
    iec_gib_to_display,
)
```

Keep `bytes_to_gib` as IEC-only:

```python
def bytes_to_gib(num_bytes: float) -> float:
    return num_bytes / _GIB
```

Add helper (near `_HEADER_LABELS`):

```python
def _capacity_header_labels() -> tuple[str, ...]:
    unit = capacity_unit_header()
    return (
        "Facility",
        "Storage Array",
        "Model Number",
        f"Useable Capacity ({unit})",
        f"Used Capacity ({unit})",
        "Utilization % ",
        f"Useable Capacity ({unit})",
        f"Used Capacity ({unit})",
        "Utilization % ",
        "Weekly Growth %",
    )
```

In `_write_sheet_header`, replace `enumerate(_HEADER_LABELS, ...)` with `enumerate(_capacity_header_labels(), ...)`.

In `_build_report_wkly_sheet`, replace the hardcoded `("Useable Capacity (GiB)", "Used Capacity (GiB)", "Utilization % ")` with:

```python
unit = capacity_unit_header()
("Useable Capacity (" + unit + ")", "Used Capacity (" + unit + ")", "Utilization % ")
```

Replace `bytes_to_gib(usable)` / `bytes_to_gib(used)` in that weekly write loop with `bytes_to_capacity_unit(usable)` / `bytes_to_capacity_unit(used)`.

In `_row_from_snapshots`, replace `bytes_to_gib(...)` with `bytes_to_capacity_unit(...)` for the four usable/used fields (still store under `*_gib` keys — those are display numbers at export time).

When writing IBM/HP Report cells from `_DATA_COLUMNS`, if a `*_gib` value is present it is already in the active unit from `_row_from_snapshots`. Tests that pass pre-baked `_minimal_row()` numbers stay as given (do not run `iec_gib_to_display` on those dicts — they are already display values).

Do not rewrite snapshot store records. Weekly history stays `usable_bytes` / `used_bytes`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_dell_report_export.py tests/test_capacity_units.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add launchpad/dell_report_export.py tests/test_dell_report_export.py
git commit -m "Switch Dell capacity headers and values with the unit mode."
```

---

### Task 3: Dashboard toggle, persistence, `health_format`

**Files:**
- Modify: `launchpad/ui/dashboard_view.py`
- Modify: `launchpad/app.py`
- Modify: `launchpad/health_format.py`
- Modify: `tests/test_dashboard_header_wrap.py`
- Create or extend: `tests/test_health_format.py` (prefer new focused tests in `tests/test_capacity_units.py` if no existing health_format test file)

**Interfaces:**
- Consumes: `SETTING_CAPACITY_UNIT_MODE`, `get_capacity_unit_mode`, `set_capacity_unit_mode`, `load_capacity_unit_mode`, `format_bytes` from Task 1
- Produces: header switch; setting persisted; in-memory mode loaded at app start

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_dashboard_header_wrap.py`:

```python
def test_dashboard_header_has_capacity_unit_switch():
    source = (
        Path(__file__).parents[1] / "launchpad" / "ui" / "dashboard_view.py"
    ).read_text(encoding="utf-8")
    assert "capacity_unit_switch" in source
    assert "SETTING_CAPACITY_UNIT_MODE" in source
    assert "GiB/TiB" in source
    assert "GB/TB" in source
```

Add to `tests/test_capacity_units.py`:

```python
from launchpad.health_format import _gb


def test_health_format_gb_follows_mode():
    set_capacity_unit_mode("iec")
    assert _gb(1024**3) == "1.0 GiB"
    set_capacity_unit_mode("si")
    assert _gb(1024**3) == "1.1 GB"
```

Add a fake-db load test:

```python
class _FakeDb:
    def __init__(self, value=""):
        self.value = value

    def get_setting(self, key, default=""):
        assert key == "capacity_unit_mode"
        return self.value if self.value != "" else default


def test_load_capacity_unit_mode_from_settings():
    assert load_capacity_unit_mode(_FakeDb("")) == "iec"
    assert load_capacity_unit_mode(_FakeDb("si")) == "si"
    assert load_capacity_unit_mode(_FakeDb("bogus")) == "iec"
```

(Import `load_capacity_unit_mode` in the existing import list.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_dashboard_header_wrap.py::test_dashboard_header_has_capacity_unit_switch tests/test_capacity_units.py::test_health_format_gb_follows_mode tests/test_capacity_units.py::test_load_capacity_unit_mode_from_settings -v`  
Expected: FAIL

- [ ] **Step 3: Implement toggle, load, and `_gb`**

In `launchpad/app.py`, after `self.db = Database()`:

```python
from launchpad.capacity_units import load_capacity_unit_mode
```

(Place the import at the **top** of `app.py` with the other imports.)

```python
load_capacity_unit_mode(self.db)
```

In `launchpad/health_format.py`, import at top:

```python
from launchpad.capacity_units import format_bytes
```

Replace `_gb`:

```python
def _gb(value: int) -> str:
    return format_bytes(float(value or 0))
```

In `launchpad/ui/dashboard_view.py`, import at top:

```python
from launchpad.capacity_units import (
    SETTING_CAPACITY_UNIT_MODE,
    get_capacity_unit_mode,
    load_capacity_unit_mode,
    set_capacity_unit_mode,
)
```

In `DashboardView.__init__`, after other setting loads:

```python
load_capacity_unit_mode(self.db)
```

In `_build_header`, on the `controls` frame, add a switch **before** `theme_switch` (column 0). Shift theme / Admin / Lock to columns 1, 2, 3.

```python
self.capacity_unit_switch = ctk.CTkSwitch(
    controls,
    text="GB/TB" if get_capacity_unit_mode() == "si" else "GiB/TiB",
    command=self._toggle_capacity_unit_mode,
)
self.capacity_unit_switch.grid(row=0, column=0, padx=6)
if get_capacity_unit_mode() == "si":
    self.capacity_unit_switch.select()
```

Re-grid existing `theme_switch` to column 1, Admin to column 2, Lock to column 3.

Add:

```python
def _capacity_unit_switch_label(self) -> str:
    return "GB/TB" if get_capacity_unit_mode() == "si" else "GiB/TiB"

def _toggle_capacity_unit_mode(self) -> None:
    mode = "si" if bool(self.capacity_unit_switch.get()) else "iec"
    set_capacity_unit_mode(mode)
    self.db.set_setting(SETTING_CAPACITY_UNIT_MODE, mode)
    self.capacity_unit_switch.configure(text=self._capacity_unit_switch_label())
    self.refresh_cards()
```

In `apply_theme`, also:

```python
if hasattr(self, "capacity_unit_switch"):
    self.capacity_unit_switch.configure(text=self._capacity_unit_switch_label())
```

Do not re-run SSH. `refresh_cards()` rebuilds labels from existing snapshots via `_format_bytes`. Browser pages pick up the mode on next load (Task 4).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_dashboard_header_wrap.py tests/test_capacity_units.py tests/test_health_format.py -v`  
If `tests/test_health_format.py` does not exist, omit it.

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add launchpad/ui/dashboard_view.py launchpad/app.py launchpad/health_format.py tests/test_dashboard_header_wrap.py tests/test_capacity_units.py
git commit -m "Add dashboard GiB/TiB vs GB/TB switch and persist it."
```

---

### Task 4: HealthServer JS mode + version 1.6.151

**Files:**
- Modify: `launchpad/health_server.py` (`_send_html` callers / page fill)
- Modify: `launchpad/fc_consistgrp.py` (`formatBytes`)
- Modify: `launchpad/site_lookup.py` (`formatBytes`)
- Modify: `launchpad/snapshot_schedule.py` (`formatBytes`)
- Modify: `launchpad/config.py` — `APP_VERSION = "1.6.151"`
- Modify: `tests/test_system_connectivity_version.py`
- Modify: `tests/test_hadoop_sudo_wire.py`
- Create: `tests/test_capacity_unit_js.py` (source markers)

**Interfaces:**
- Consumes: `get_capacity_unit_mode` from Task 1
- Produces: pages receive `CAPACITY_UNIT_MODE`; JS formatters use 1024+GiB or 1000+GB

- [ ] **Step 1: Write the failing tests**

Create `tests/test_capacity_unit_js.py`:

```python
from pathlib import Path

from launchpad.config import APP_VERSION
from launchpad.fc_consistgrp import FC_CONSISTGRP_HTML
from launchpad.health_server import DASHBOARD_HTML
from launchpad.site_lookup import SITE_LOOKUP_HTML
from launchpad.snapshot_schedule import SNAPSHOT_SCHEDULE_HTML


def test_pages_include_capacity_unit_mode_placeholder():
    for html in (DASHBOARD_HTML, SITE_LOOKUP_HTML, SNAPSHOT_SCHEDULE_HTML, FC_CONSISTGRP_HTML):
        assert "{{CAPACITY_UNIT_MODE}}" in html
        assert "CAPACITY_UNIT_MODE" in html


def test_fc_consistgrp_format_bytes_uses_mode():
    assert "GiB" in FC_CONSISTGRP_HTML
    assert "1024" in FC_CONSISTGRP_HTML
    assert "1000" in FC_CONSISTGRP_HTML


def test_app_version_151():
    assert APP_VERSION == "1.6.151"
```

Update version pins to `1.6.151` in `tests/test_system_connectivity_version.py` and `tests/test_hadoop_sudo_wire.py`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_capacity_unit_js.py tests/test_system_connectivity_version.py tests/test_hadoop_sudo_wire.py -v`  
Expected: FAIL (placeholder / version)

- [ ] **Step 3: Inject mode and align JS**

In `launchpad/health_server.py`, add a helper next to `_send_html` and use it for every `*.replace("{{APP_VERSION}}", APP_VERSION)` HTML response:

```python
from launchpad.capacity_units import get_capacity_unit_mode
```

```python
def _fill_page(html: str) -> str:
    return (
        html.replace("{{APP_VERSION}}", APP_VERSION).replace(
            "{{CAPACITY_UNIT_MODE}}", get_capacity_unit_mode()
        )
    )
```

Change each `_send_html(FOO.replace("{{APP_VERSION}}", APP_VERSION))` to `_send_html(_fill_page(FOO))`.

Near the top of the `<script>` in `DASHBOARD_HTML` (health_server.py), `SITE_LOOKUP_HTML`, `SNAPSHOT_SCHEDULE_HTML`, and `FC_CONSISTGRP_HTML`, add:

```javascript
const CAPACITY_UNIT_MODE = "{{CAPACITY_UNIT_MODE}}";
```

Replace **storage** `formatBytes` in `fc_consistgrp.py` with a Python-matching helper (giga-start, one decimal):

```javascript
function formatBytes(n) {
  const si = CAPACITY_UNIT_MODE === "si";
  if (n <= 0) return si ? "0 GB" : "0 GiB";
  const step = si ? 1000 : 1024;
  let value = n / (si ? (1000 ** 3) : (1024 ** 3));
  let unit = si ? "GB" : "GiB";
  if (value >= step) { value /= step; unit = si ? "TB" : "TiB"; }
  if (value >= step) { value /= step; unit = si ? "PB" : "PiB"; }
  return value.toFixed(1) + " " + unit;
}
```

Use that same function body for **pool/storage** `formatBytes` in `site_lookup.py`.

For **host RAM/disk** `formatBytes` in `health_server.py` and `snapshot_schedule.py` (values often below 1 GiB), keep scaling from bytes but use the mode’s base and labels:

```javascript
function formatBytes(value) {
  if (!value || value <= 0) return "0 B";
  const si = CAPACITY_UNIT_MODE === "si";
  const units = si
    ? ["B", "KB", "MB", "GB", "TB", "PB"]
    : ["B", "KiB", "MiB", "GiB", "TiB", "PiB"];
  const step = si ? 1000 : 1024;
  let size = value;
  let unit = 0;
  while (size >= step && unit < units.length - 1) {
    size /= step;
    unit += 1;
  }
  return unit === 0 ? `${Math.round(size)} ${units[unit]}` : `${size.toFixed(1)} ${units[unit]}`;
}
```

Do **not** change `launchpad/capacity_report.py`: it has no JS `formatBytes`. Capacity strings come from Python `_format_bytes` (Task 1).

Set `APP_VERSION = "1.6.151"` in `launchpad/config.py`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_capacity_unit_js.py tests/test_system_connectivity_version.py tests/test_hadoop_sudo_wire.py tests/test_capacity_units.py tests/test_dell_report_export.py tests/test_dashboard_header_wrap.py tests/test_fc_consistgrp_ops.py tests/test_fc_cg_summary_multisite_api.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add launchpad/health_server.py launchpad/fc_consistgrp.py launchpad/site_lookup.py launchpad/snapshot_schedule.py launchpad/config.py tests/test_capacity_unit_js.py tests/test_system_connectivity_version.py tests/test_hadoop_sudo_wire.py
git commit -m "Inject capacity unit mode into HealthServer pages and bump to 1.6.151."
```

---

## Spec coverage

| Spec requirement | Task |
|------------------|------|
| `capacity_units.py` mode + formatters | 1 |
| `_format_bytes` delegates; parse unchanged | 1 |
| Default `iec`; unknown → `iec` | 1 |
| Dell headers `(GiB)`/`(GB)` + write-time numbers | 2 |
| Weekly Dell headers/values from bytes | 2 |
| Snapshot store stays bytes | 2 |
| Dashboard header switch | 3 |
| Persist `capacity_unit_mode` | 3 |
| Load at app start | 3 |
| `health_format._gb` uses shared formatter | 3 |
| Refresh cards, no SSH | 3 |
| JS `formatBytes` + inject mode | 4 |
| APP_VERSION 1.6.151 | 4 |
| LUN Builder CLI untouched | (non-goal; no task) |
