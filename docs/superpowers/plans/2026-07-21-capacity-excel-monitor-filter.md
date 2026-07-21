# Capacity Report Excel + Monitoring-Off Filter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Export Excel to the browser Capacity Report and hide monitoring-off sites by default on both the HTML report and Excel, with an opt-in checkbox.

**Architecture:** Pure filter helpers in `capacity_export.py`; extend `export_storage_capacity_excel` for desktop compatibility; add a health-server export path that refreshes only included cards via existing `HealthServer.refresh_card` (no Database/crypto required). Capacity Report JS filters render + passes `include_off` to `/api/capacity-export`.

**Tech Stack:** Python 3, openpyxl, health-server HTML/JS, pytest.

**Spec:** `docs/superpowers/specs/2026-07-21-capacity-excel-monitor-filter-design.md`

## Global Constraints

- Excel placement: Capacity Report **Export Excel** button + `GET /api/capacity-export`
- Filter applies to HTML **and** Excel via the same checkbox
- Default: monitoring-off sites **excluded** (`include_off=0` / checkbox unchecked)
- Checkbox label: **Include monitoring-off sites**
- Desktop Dashboard **Export Excel ▾ → Capacity** stays all-sites (`include_monitor_off=True` default)
- Reuse Storage Capacity + Pool Capacity workbook styling via existing `_styled_workbook`
- Bump `APP_VERSION` one patch from Task 0 baseline in the final task
- Commit at each task’s commit step; imports at top of modules

---

## File map

| File | Responsibility |
|------|----------------|
| `launchpad/capacity_export.py` | Filter helpers; monitor filter on desktop exporter; health-card workbook builder |
| `launchpad/health_server.py` | `GET /api/capacity-export` |
| `launchpad/capacity_report.py` | Export button, include-off checkbox, render filter, download JS |
| `launchpad/config.py` | Version bump |
| `tests/test_capacity_export_filter.py` | Pure filter + exporter filter tests |
| `tests/test_health_server_capacity_export.py` | API + HTML presence tests |

---

### Task 0: Branch / worktree

**Files:** none (git only)

**Interfaces:**
- Consumes: `feature/contingency-groups` tip (includes capacity Excel design commit)
- Produces: worktree `.worktrees/capacity-excel-filter` on branch `feature/capacity-excel-filter`

- [ ] **Step 1: Create worktree**

```powershell
cd C:\Users\BrianColley\LaunchPad
git fetch origin
git worktree add .worktrees/capacity-excel-filter -b feature/capacity-excel-filter feature/contingency-groups
cd .worktrees/capacity-excel-filter
```

- [ ] **Step 2: Record baseline version**

```powershell
python -c "from launchpad.config import APP_VERSION; print(APP_VERSION)"
```

Note the printed value; final task bumps one patch (e.g. `1.6.41` → `1.6.42`).

- [ ] **Step 3: No commit**

---

### Task 1: Pure monitor-include filter helpers

**Files:**
- Modify: `launchpad/capacity_export.py`
- Create: `tests/test_capacity_export_filter.py`

**Interfaces:**
- Consumes: none
- Produces:
  - `card_ids_included_for_export(card_ids: Iterable[int], *, include_monitor_off: bool, monitor_enabled: Mapping[int, bool]) -> frozenset[int]`
  - `keep_inventory_row(*, matched_card_id: int | None, included_card_ids: AbstractSet[int], include_monitor_off: bool) -> bool`
    - If `include_monitor_off` is True → always `True` (keep every inventory template row).
    - If False → `True` only when `matched_card_id is not None` and `matched_card_id in included_card_ids`.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_capacity_export_filter.py
from launchpad.capacity_export import (
    card_ids_included_for_export,
    keep_inventory_row,
)


def test_include_off_false_keeps_only_monitor_on():
    ids = card_ids_included_for_export(
        [1, 2, 3],
        include_monitor_off=False,
        monitor_enabled={1: True, 2: False},
    )
    assert ids == frozenset({1})


def test_include_off_true_keeps_all_ids():
    ids = card_ids_included_for_export(
        [1, 2],
        include_monitor_off=True,
        monitor_enabled={1: False, 2: False},
    )
    assert ids == frozenset({1, 2})


def test_missing_monitor_key_treated_as_off():
    ids = card_ids_included_for_export(
        [9],
        include_monitor_off=False,
        monitor_enabled={},
    )
    assert ids == frozenset()


def test_keep_inventory_row_rules():
    included = frozenset({5})
    assert keep_inventory_row(
        matched_card_id=5,
        included_card_ids=included,
        include_monitor_off=False,
    )
    assert not keep_inventory_row(
        matched_card_id=6,
        included_card_ids=included,
        include_monitor_off=False,
    )
    assert not keep_inventory_row(
        matched_card_id=None,
        included_card_ids=included,
        include_monitor_off=False,
    )
    assert keep_inventory_row(
        matched_card_id=None,
        included_card_ids=included,
        include_monitor_off=True,
    )
```

- [ ] **Step 2: Run tests — expect FAIL**

```powershell
python -m pytest tests/test_capacity_export_filter.py -v
```

Expected: FAIL (functions not defined).

- [ ] **Step 3: Implement helpers at top of helpers section in `capacity_export.py`**

```python
from collections.abc import AbstractSet, Iterable, Mapping

def card_ids_included_for_export(
    card_ids: Iterable[int],
    *,
    include_monitor_off: bool,
    monitor_enabled: Mapping[int, bool],
) -> frozenset[int]:
    ids = [int(card_id) for card_id in card_ids]
    if include_monitor_off:
        return frozenset(ids)
    return frozenset(
        card_id for card_id in ids if bool(monitor_enabled.get(card_id, False))
    )


def keep_inventory_row(
    *,
    matched_card_id: int | None,
    included_card_ids: AbstractSet[int],
    include_monitor_off: bool,
) -> bool:
    if include_monitor_off:
        return True
    return matched_card_id is not None and matched_card_id in included_card_ids
```

- [ ] **Step 4: Run tests — expect PASS**

```powershell
python -m pytest tests/test_capacity_export_filter.py -v
```

- [ ] **Step 5: Commit**

```powershell
git add launchpad/capacity_export.py tests/test_capacity_export_filter.py
git commit -m "Add capacity export monitor-include filter helpers."
```

---

### Task 2: Wire filter into `export_storage_capacity_excel`

**Files:**
- Modify: `launchpad/capacity_export.py` (`export_storage_capacity_excel`)
- Modify: `tests/test_capacity_export_filter.py`

**Interfaces:**
- Consumes: `card_ids_included_for_export`, `keep_inventory_row`
- Produces: `export_storage_capacity_excel(..., include_monitor_off: bool = True, monitor_enabled: Mapping[int, bool] | None = None) -> ExportResult`
  - Default `include_monitor_off=True` preserves desktop Dashboard behavior.
  - When `include_monitor_off=False`, use `monitor_enabled or {}`; only refresh / include those card IDs; drop inventory rows via `keep_inventory_row`; drop extra unmatched cards not in included set.

- [ ] **Step 1: Write failing integration-style test with monkeypatch**

Add to `tests/test_capacity_export_filter.py`:

```python
from pathlib import Path
from unittest.mock import MagicMock

from launchpad.capacity_export import export_storage_capacity_excel


def test_export_skips_monitor_off_cards(monkeypatch, tmp_path: Path):
    entry_on = MagicMock(card_id=1, name="On")
    entry_off = MagicMock(card_id=2, name="Off")
    monkeypatch.setattr(
        "launchpad.capacity_export.build_health_dashboard_entries",
        lambda db, key: [entry_on, entry_off],
    )
    monkeypatch.setattr(
        "launchpad.capacity_export._refresh_entry_capacity",
        lambda entry: ({"name": entry.name, "used_pct": 1, "used_bytes": 1, "total_bytes": 100}, [], None),
    )
    # Empty DB cards → no inventory match; both become extra rows when included
    db = MagicMock()
    db.list_cards.return_value = []

    # Force empty INVENTORY_ROWS for this test
    monkeypatch.setattr("launchpad.capacity_export.INVENTORY_ROWS", [])

    out = tmp_path / "cap.xlsx"
    result = export_storage_capacity_excel(
        db,
        b"0" * 32,
        out,
        include_monitor_off=False,
        monitor_enabled={1: True, 2: False},
    )
    assert out.exists()
    assert result.extra_rows == 1  # only monitor-on
```

If `MagicMock` cards break `_card_to_extra_row`, construct a tiny real `Card` or a SimpleNamespace with required attrs instead — adjust the test to whatever `_card_to_extra_row` needs (`category`, `name`, `host`, `device_profile`, `serial_number`). Prefer building one real `Card`-shaped object for the on-card only path by stubbing `cards_by_id` via a patched `db.list_cards` returning two SSH cards and patching entries accordingly.

Minimal Card stub pattern used elsewhere in the repo is fine; if creating DB Card is heavy, extract a local helper in the test file.

- [ ] **Step 2: Run test — expect FAIL** (missing kwargs or still exporting 2 extras)

```powershell
python -m pytest tests/test_capacity_export_filter.py::test_export_skips_monitor_off_cards -v
```

- [ ] **Step 3: Implement filter inside `export_storage_capacity_excel`**

Signature change:

```python
def export_storage_capacity_excel(
    db: Database,
    crypto_key: bytes,
    output_path: Path,
    *,
    progress: ProgressCallback | None = None,
    include_monitor_off: bool = True,
    monitor_enabled: Mapping[int, bool] | None = None,
) -> ExportResult:
```

After building `entries`, compute:

```python
monitor_map = monitor_enabled or {}
included = card_ids_included_for_export(
    [e.card_id for e in entries],
    include_monitor_off=include_monitor_off,
    monitor_enabled=monitor_map,
)
entries = [e for e in entries if e.card_id in included]
```

When iterating inventory rows, after `match_inventory_row(...)`:

```python
if not keep_inventory_row(
    matched_card_id=card_id,
    included_card_ids=included,
    include_monitor_off=include_monitor_off,
):
    continue  # do not append to inventory_fills / pool rows
```

Do **not** append blank fills for dropped rows when filtering (sheet should omit those devices). When `include_monitor_off=True`, keep today’s behavior (always append a fill for every `INVENTORY_ROWS` entry).

Extra-row loop already iterates `entries` (now filtered) — no change needed beyond the entry filter.

- [ ] **Step 4: Run filter tests — expect PASS**

```powershell
python -m pytest tests/test_capacity_export_filter.py -v
```

- [ ] **Step 5: Commit**

```powershell
git add launchpad/capacity_export.py tests/test_capacity_export_filter.py
git commit -m "Filter capacity Excel export by monitor-enabled cards."
```

---

### Task 3: Health-server workbook export (no Database required)

**Files:**
- Modify: `launchpad/capacity_export.py`
- Modify: `tests/test_capacity_export_filter.py`

**Interfaces:**
- Consumes: filter helpers, `format_capacity_text`, `format_pool_stats_text`, `_styled_workbook`, `match_inventory_row`, `_build_card_lookups` (adapt), `_pool_detail_rows_for_site`
- Produces:
  - `@dataclass` or Protocol-friendly **`ExportSite`** with fields: `card_id: int`, `name: str`, `host: str`, `serial_number: str`, `category: str`, `device_profile: str`, `capacity_summary: dict | None`, `pools: list[dict]`, `error: str | None`
  - `export_storage_capacity_excel_from_sites(sites: list[ExportSite], output_path: Path, *, include_monitor_off: bool, monitor_enabled: Mapping[int, bool]) -> ExportResult`
    - Filter sites with `card_ids_included_for_export`
    - Build lookups from included sites (reuse match logic; if `_build_card_lookups` requires `Card`, add `_build_site_lookups(sites)` mirroring IP/serial/name indexes)
    - Inventory: keep/drop via `keep_inventory_row`
    - Capacity/pool text from site fields (no live SSH here)
    - Extra rows for included sites not matched to inventory

- [ ] **Step 1: Failing test — from_sites omits monitor-off**

```python
from launchpad.capacity_export import ExportSite, export_storage_capacity_excel_from_sites

def test_from_sites_respects_monitor_filter(tmp_path: Path):
    sites = [
        ExportSite(
            card_id=1,
            name="A",
            host="10.0.0.1",
            serial_number="S1",
            category="Remote",
            device_profile="flashsystem",
            capacity_summary={"name": "A", "used_pct": 2, "used_bytes": 2, "total_bytes": 100},
            pools=[],
            error=None,
        ),
        ExportSite(
            card_id=2,
            name="B",
            host="10.0.0.2",
            serial_number="S2",
            category="Remote",
            device_profile="flashsystem",
            capacity_summary=None,
            pools=[],
            error="Authentication failed.",
        ),
    ]
    out = tmp_path / "sites.xlsx"
    result = export_storage_capacity_excel_from_sites(
        sites,
        out,
        include_monitor_off=False,
        monitor_enabled={1: True, 2: False},
    )
    assert out.exists()
    assert result.extra_rows + result.filled_count >= 1
    # Open workbook: Storage Capacity sheet must not contain host 10.0.0.2
    from openpyxl import load_workbook
    wb = load_workbook(out)
    ws = wb["Storage Capacity"]
    blob = "\n".join(
        str(c.value or "") for row in ws.iter_rows(values_only=True) for c in row
    )
    assert "10.0.0.1" in blob or "A" in blob
    assert "10.0.0.2" not in blob
```

- [ ] **Step 2: Run — expect FAIL**

```powershell
python -m pytest tests/test_capacity_export_filter.py::test_from_sites_respects_monitor_filter -v
```

- [ ] **Step 3: Implement `ExportSite` + `export_storage_capacity_excel_from_sites`**

Reuse `_styled_workbook` fill construction parallel to `export_storage_capacity_excel`, but source capacity from `ExportSite` instead of `_refresh_entry_capacity`. For site→extra row, mirror `_card_to_extra_row` using site fields.

- [ ] **Step 4: Tests PASS**

```powershell
python -m pytest tests/test_capacity_export_filter.py -v
```

- [ ] **Step 5: Commit**

```powershell
git add launchpad/capacity_export.py tests/test_capacity_export_filter.py
git commit -m "Add capacity Excel builder from health-report sites."
```

---

### Task 4: `/api/capacity-export` route

**Files:**
- Modify: `launchpad/health_server.py` (GET handler near `/api/fc-wwpn-export`)
- Create: `tests/test_health_server_capacity_export.py`

**Interfaces:**
- Consumes: `export_storage_capacity_excel_from_sites`, `ExportSite`, `open_exported_workbook`, `TEMP_DIR`, `pool_capacity_from_commands` / `analyze_health` as needed to fill ExportSite from `HealthCard`
- Produces: `GET /api/capacity-export?include_off=0|1&open=1`
  - Parse `include_off` truthy like FC WWPN `open` (`1`/`true`/`yes`; default **false** / excluded)
  - `server.sync_from_app()` then list cards
  - For each included card (after filter): call `server.refresh_card(card_id)` inside try/except so one failure does not abort the workbook; map to `ExportSite` using analysis + pools
  - Write bytes; optional open; `_send_bytes` xlsx `Storage_Capacity_Report_{stamp}.xlsx`

Helper on HealthServer (optional but clean):

```python
def build_capacity_export_sites(self, *, include_monitor_off: bool) -> list[ExportSite]:
    ...
```

- [ ] **Step 1: Failing API test**

```python
# tests/test_health_server_capacity_export.py
from launchpad.capacity_report import CAPACITY_REPORT_HTML  # or whatever constant name exists
from launchpad.health_server import CAPACITY_REPORT_HTML as HTML  # adjust to real import


def test_capacity_report_html_has_export_controls():
    # Will pass after Task 5; for Task 4 only assert route exists via handler unit test
    pass


def test_capacity_export_endpoint_returns_xlsx(monkeypatch):
    from launchpad import health_server as hs
    server = hs.HealthServer()
    # register one fake card + monitor on; monkeypatch refresh_card / build sites
    ...
```

Prefer a focused test that instantiates `_HealthHandler` or calls a new `HealthServer.export_capacity_excel_bytes(include_monitor_off: bool) -> tuple[bytes, str]` and asserts ZIP/xlsx magic `PK` and filename.

Concrete preferred surface:

```python
def export_capacity_excel_bytes(self, *, include_monitor_off: bool = False) -> tuple[bytes, str]:
    """Returns (xlsx_bytes, filename)."""
```

Handler only parses query, calls this, optionally opens temp file, sends bytes.

- [ ] **Step 2: Implement method + GET route** (mirror `/api/fc-wwpn-export` open/temp pattern)

- [ ] **Step 3: Tests PASS**

```powershell
python -m pytest tests/test_health_server_capacity_export.py tests/test_capacity_export_filter.py -v
```

- [ ] **Step 4: Commit**

```powershell
git add launchpad/health_server.py launchpad/capacity_export.py tests/test_health_server_capacity_export.py
git commit -m "Add capacity Excel export API for the browser report."
```

---

### Task 5: Capacity Report UI — checkbox + Export Excel + render filter

**Files:**
- Modify: `launchpad/capacity_report.py`
- Modify: `tests/test_health_server_capacity_export.py`

**Interfaces:**
- Consumes: `/api/monitor`, `/api/capacity-export`
- Produces: HTML/JS controls wired as specified

- [ ] **Step 1: Failing HTML assertion test**

```python
def test_capacity_report_html_has_export_and_include_off():
    from launchpad.capacity_report import CAPACITY_REPORT_HTML
    assert "Export Excel" in CAPACITY_REPORT_HTML
    assert "Include monitoring-off sites" in CAPACITY_REPORT_HTML
    assert 'id="excel-btn"' in CAPACITY_REPORT_HTML
    assert 'id="include-off-toggle"' in CAPACITY_REPORT_HTML
```

(Use the real HTML constant name from `capacity_report.py`.)

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Toolbar HTML**

Next to Print / Refresh:

```html
<button type="button" id="excel-btn" class="secondary">Export Excel</button>
...
<label class="toggle-row" for="include-off-toggle" title="When unchecked, sites with Monitor off are hidden on this page and omitted from Excel.">
  <input type="checkbox" id="include-off-toggle">
  Include monitoring-off sites
</label>
```

- [ ] **Step 4: JS filter + export**

- `includeOffToggle` default unchecked.
- In `renderAll(cards)`:  
  `const visible = includeOffToggle.checked ? cards : cards.filter((c) => isMonitorOn(c.id));`  
  then render `visible`; update status like `` `${visible.length} site(s) shown` `` (keep loaded count if useful: `` `${visible.length} of ${cards.length} site(s) shown` ``).
- On `includeOffToggle.change` → `renderAll(cardsCache)` (no SSH).
- When monitor toggles change, re-render so a site turned off disappears when include-off is unchecked.
- `downloadExcel()`:

```javascript
async function downloadExcel() {
  excelBtn.disabled = true;
  statusEl.textContent = "Building Excel workbook…";
  try {
    const includeOff = includeOffToggle && includeOffToggle.checked ? "1" : "0";
    const res = await fetch(`/api/capacity-export?include_off=${includeOff}&open=1`);
    if (!res.ok) { /* parse JSON error like FC WWPN */ throw new Error(detail); }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    const stamp = new Date().toISOString().slice(0, 16).replace(/[:-]/g, "");
    a.href = url;
    a.download = `Storage_Capacity_Report_${stamp}.xlsx`;
    a.click();
    URL.revokeObjectURL(url);
    statusEl.textContent = "Excel (.xlsx) downloaded.";
  } catch (err) {
    statusEl.textContent = `Excel export failed: ${err.message || err}`;
  } finally {
    excelBtn.disabled = false;
  }
}
```

Wire `excelBtn.addEventListener("click", downloadExcel)`.

- [ ] **Step 5: Tests PASS**

```powershell
python -m pytest tests/test_health_server_capacity_export.py tests/test_capacity_export_filter.py -v
```

- [ ] **Step 6: Commit**

```powershell
git add launchpad/capacity_report.py tests/test_health_server_capacity_export.py
git commit -m "Add Capacity Report Excel button and monitoring-off filter."
```

---

### Task 6: Version bump + full regression

**Files:**
- Modify: `launchpad/config.py`

- [ ] **Step 1: Bump** `APP_VERSION` to Task 0 baseline + one patch

- [ ] **Step 2: Full suite**

```powershell
python -m pytest tests -q
```

Expected: all PASS.

- [ ] **Step 3: Commit**

```powershell
git add launchpad/config.py
git commit -m "Bump version for Capacity Report Excel and monitor filter."
```

---

## Spec coverage check

| Spec item | Task |
|-----------|------|
| Export Excel on Capacity Report | 5 |
| `/api/capacity-export` | 4 |
| Same workbook sheets/styling | 2–3 (`_styled_workbook`) |
| Include monitoring-off checkbox (default off) | 5 |
| HTML hides monitor-off by default | 5 |
| Excel excludes monitor-off by default | 2–4 |
| Skip SSH refresh for off cards | 4 (only refresh included) |
| Desktop Dashboard Excel unchanged | 2 (`include_monitor_off=True` default) |
| Version bump | 6 |
