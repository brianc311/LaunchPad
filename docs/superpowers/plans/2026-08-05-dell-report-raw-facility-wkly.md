# Dell Report Raw Capacity, Facility Mapping & Weekly Sheets — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dell Report uses live HPE/IBM scrap with CPG-off raw fallback, Facility/Array/Model heuristics + overrides, and live IBM/HP Report - Wkly + Forecast - Wkly sheets.

**Architecture:** Add a capacity selector that prefers raw when `include_pools=False` and system when True; extend facility heuristics and Dell settings with `card_overrides`; enrich collect with array/model defaults from scrap + `DEVICE_PROFILES`; expand workbook builders for Report - Wkly (per snapshot week) and Forecast - Wkly (+1/+4/+8/+12 week util).

**Tech Stack:** Python 3, openpyxl, pytest, existing `dell_report_*` modules, Capacity Report `include_pools` query flag.

**Spec:** `docs/superpowers/specs/2026-08-05-dell-report-raw-facility-wkly-design.md`

## Global Constraints

- Branch: `feature/hpe-capacity-parse`
- App version target: **1.6.119**
- Live data sheets: IBM/HP Report, Report - Wkly, Forecast, Forecast - Wkly only
- LED icons: green &lt; 0.80, yellow ≥ 0.80 (unchanged)
- Output `.xlsx` via openpyxl
- Do not invent prior-week history when only one snapshot week exists
- Windows PowerShell for git commits (here-string), not bash heredoc

## File structure

| File | Responsibility |
|------|----------------|
| `launchpad/dell_report_facility.py` | Facility heuristics including Remote |
| `launchpad/dell_report_capacity.py` | **New** — select system vs raw vs pools for Dell rows |
| `launchpad/dell_report_identity.py` | **New** — resolve facility/array/model with overrides |
| `launchpad/dell_report_settings.py` | Normalize/load/save `card_overrides` |
| `launchpad/dell_report_export.py` | Collect wiring, sheet order, Report/Forecast Wkly builders |
| `launchpad/dell_report_snapshots.py` | Optional helpers for week list / util projection (keep thin) |
| `launchpad/health_server.py` | Pass `include_pools` + overrides into collect |
| `launchpad/ui/admin_view.py` | Minimal overrides JSON field on Dell Report settings |
| `launchpad/config.py` | `APP_VERSION = "1.6.119"` |
| `tests/test_dell_report_*.py` | Coverage for each task |

---

### Task 1: Facility Remote + capacity selector

**Files:**
- Modify: `launchpad/dell_report_facility.py`
- Create: `launchpad/dell_report_capacity.py`
- Modify: `tests/test_dell_report_helpers.py`
- Create: `tests/test_dell_report_capacity.py`

**Interfaces:**
- Consumes: capacity/raw/pools dicts shaped like analyze_health summaries (`total_bytes`, `used_bytes`, `name`, …)
- Produces:
  - `facility_from_name(name: str) -> str` — adds `Remote`
  - `select_dell_capacity_summary(*, capacity_summary, raw_capacity_summary, pools, include_pools: bool) -> dict | None`

- [ ] **Step 1: Write failing facility test**

In `tests/test_dell_report_helpers.py` add:

```python
def test_facility_remote_from_name():
    assert facility_from_name("Anderson, SC - Remote") == "Remote"
    assert facility_from_name("REMOTE site") == "Remote"
```

Keep existing WAG1/WAG2/DC tests. Remote must be checked after distribution/WAG rules so `WAG1 Remote` still prefers WAG1 if that is desired — **spec:** check `remote` after WAG1/WAG2 and distribution, before `Other`.

- [ ] **Step 2: Run facility test — expect FAIL**

Run: `python -m pytest tests/test_dell_report_helpers.py::test_facility_remote_from_name -v`  
Expected: FAIL (returns `Other`)

- [ ] **Step 3: Implement Remote in facility_from_name**

In `launchpad/dell_report_facility.py`, after WAG1/WAG2 and DC-prefix checks, before `return _OTHER`:

```python
_REMOTE = "Remote"
# ...
if "remote" in lowered:
    return _REMOTE
return _OTHER
```

Update module docstring to mention Remote.

- [ ] **Step 4: Write failing capacity selector tests**

Create `tests/test_dell_report_capacity.py`:

```python
from launchpad.dell_report_capacity import select_dell_capacity_summary

SYSTEM = {"name": "sys1", "total_bytes": 100, "used_bytes": 40, "used_pct": 40.0}
RAW = {"name": "sys1", "total_bytes": 200, "used_bytes": 50, "used_pct": 25.0, "raw": True}


def test_include_pools_false_prefers_raw():
    chosen = select_dell_capacity_summary(
        capacity_summary=None,
        raw_capacity_summary=RAW,
        pools=[],
        include_pools=False,
    )
    assert chosen is RAW
    assert chosen["total_bytes"] == 200


def test_include_pools_false_falls_back_to_system():
    chosen = select_dell_capacity_summary(
        capacity_summary=SYSTEM,
        raw_capacity_summary=None,
        pools=[],
        include_pools=False,
    )
    assert chosen is SYSTEM


def test_include_pools_true_prefers_system_over_raw():
    chosen = select_dell_capacity_summary(
        capacity_summary=SYSTEM,
        raw_capacity_summary=RAW,
        pools=[],
        include_pools=True,
    )
    assert chosen is SYSTEM


def test_include_pools_true_raw_last_resort():
    chosen = select_dell_capacity_summary(
        capacity_summary=None,
        raw_capacity_summary=RAW,
        pools=[],
        include_pools=True,
    )
    assert chosen is RAW
```

- [ ] **Step 5: Run capacity tests — expect FAIL**

Run: `python -m pytest tests/test_dell_report_capacity.py -v`  
Expected: FAIL (module missing)

- [ ] **Step 6: Implement select_dell_capacity_summary**

Create `launchpad/dell_report_capacity.py`:

```python
"""Choose system vs raw vs pool rollup for Dell Report rows."""

from __future__ import annotations

from typing import Any

from launchpad.flashsystem_health import capacity_summary_from_pools


def _usable(summary: dict[str, Any] | None) -> dict[str, Any] | None:
    if not summary:
        return None
    if float(summary.get("total_bytes") or 0) <= 0:
        return None
    return summary


def select_dell_capacity_summary(
    *,
    capacity_summary: dict[str, Any] | None,
    raw_capacity_summary: dict[str, Any] | None = None,
    pools: list | None = None,
    include_pools: bool = True,
) -> dict[str, Any] | None:
    """CPG off → raw then system; CPG on → system then pools then raw."""
    system = _usable(capacity_summary)
    raw = _usable(raw_capacity_summary)
    pool_sum = None
    if include_pools and pools:
        pool_sum = _usable(capacity_summary_from_pools(pools))

    if not include_pools:
        return raw or system
    return system or pool_sum or raw
```

- [ ] **Step 7: Run Task 1 tests — expect PASS**

Run: `python -m pytest tests/test_dell_report_helpers.py tests/test_dell_report_capacity.py -q`  
Expected: PASS

- [ ] **Step 8: Commit**

```powershell
git add launchpad/dell_report_facility.py launchpad/dell_report_capacity.py tests/test_dell_report_helpers.py tests/test_dell_report_capacity.py
git commit -m @"
Add Dell Report Remote facility and CPG-off raw capacity selector.

"@
```

---

### Task 2: Identity resolver + settings card_overrides

**Files:**
- Create: `launchpad/dell_report_identity.py`
- Modify: `launchpad/dell_report_settings.py`
- Create: `tests/test_dell_report_identity.py`
- Modify: `tests/test_dell_report_settings.py`

**Interfaces:**
- Consumes: `facility_from_name`, `DEVICE_PROFILES` from `launchpad.storage_presets`
- Produces:
  - `normalize_dell_report_settings` → `{"enabled": bool, "card_overrides": {card_id: {facility?, array_name?, model?}}}`
  - `resolve_dell_identity(*, card_id, site_name, device_profile, summary_name, overrides) -> dict` with keys `facility`, `array_name`, `model`

- [ ] **Step 1: Write failing settings normalize tests**

```python
def test_normalize_keeps_card_overrides():
    raw = {
        "enabled": True,
        "card_overrides": {
            "12": {"facility": "Data center -WAG2", "array_name": "Vdiprimera101"}
        },
    }
    out = normalize_dell_report_settings(raw)
    assert out["card_overrides"]["12"]["facility"] == "Data center -WAG2"
    assert out["card_overrides"]["12"]["array_name"] == "Vdiprimera101"
    assert "model" not in out["card_overrides"]["12"]


def test_normalize_drops_bad_overrides():
    out = normalize_dell_report_settings({"card_overrides": {"x": "nope", "7": {"facility": 1}}})
    assert out["card_overrides"] == {}
```

Only string values for facility/array_name/model; skip empty strings.

- [ ] **Step 2: Run settings tests — expect FAIL**

Run: `python -m pytest tests/test_dell_report_settings.py::test_normalize_keeps_card_overrides -v`  
Expected: FAIL (`card_overrides` missing)

- [ ] **Step 3: Extend normalize_dell_report_settings**

```python
def _normalize_overrides(raw: Any) -> dict[str, dict[str, str]]:
    if not isinstance(raw, dict):
        return {}
    out: dict[str, dict[str, str]] = {}
    for card_id, entry in raw.items():
        if not isinstance(entry, dict):
            continue
        cleaned: dict[str, str] = {}
        for key in ("facility", "array_name", "model"):
            val = entry.get(key)
            if isinstance(val, str) and val.strip():
                cleaned[key] = val.strip()
        if cleaned:
            out[str(card_id)] = cleaned
    return out


def normalize_dell_report_settings(raw: Any) -> dict:
    data = raw if isinstance(raw, dict) else {}
    # ... existing enabled logic ...
    return {
        "enabled": enabled,
        "card_overrides": _normalize_overrides(data.get("card_overrides")),
    }
```

Update any tests that assert exact `{"enabled": True}` equality to also expect `"card_overrides": {}`.

- [ ] **Step 4: Write failing identity tests**

Create `tests/test_dell_report_identity.py`:

```python
from launchpad.dell_report_identity import resolve_dell_identity


def test_defaults_array_from_summary_model_from_profile():
    ident = resolve_dell_identity(
        card_id=1,
        site_name="Carolina, PR - Remote",
        device_profile="hpe_primera_600",
        summary_name="Vdiprimera101",
        overrides={},
    )
    assert ident["facility"] == "Remote"
    assert ident["array_name"] == "Vdiprimera101"
    assert ident["model"] == "HPE Primera 600 4-way"


def test_override_wins():
    ident = resolve_dell_identity(
        card_id=9,
        site_name="Other site",
        device_profile="hpe_primera_600",
        summary_name="Vdiprimera101",
        overrides={"9": {"facility": "Data center -WAG2", "model": "Custom"}},
    )
    assert ident["facility"] == "Data center -WAG2"
    assert ident["array_name"] == "Vdiprimera101"
    assert ident["model"] == "Custom"
```

- [ ] **Step 5: Implement resolve_dell_identity**

```python
"""Resolve Dell Report Facility / Storage Array / Model Number."""

from __future__ import annotations

from typing import Any

from launchpad.dell_report_facility import facility_from_name
from launchpad.storage_presets import DEVICE_PROFILES


def resolve_dell_identity(
    *,
    card_id: int | str,
    site_name: str,
    device_profile: str,
    summary_name: str = "",
    overrides: dict[str, dict[str, str]] | None = None,
) -> dict[str, str]:
    ov = (overrides or {}).get(str(card_id), {})
    facility = ov.get("facility") or facility_from_name(site_name)
    array_name = ov.get("array_name") or (summary_name.strip() if summary_name else "") or site_name
    profile_label = DEVICE_PROFILES.get(device_profile) or device_profile or ""
    model = ov.get("model") or profile_label
    return {"facility": facility, "array_name": array_name, "model": model}
```

- [ ] **Step 6: Run Task 2 tests — expect PASS**

Run: `python -m pytest tests/test_dell_report_settings.py tests/test_dell_report_identity.py -q`  
Expected: PASS

- [ ] **Step 7: Commit**

```powershell
git add launchpad/dell_report_settings.py launchpad/dell_report_identity.py tests/test_dell_report_settings.py tests/test_dell_report_identity.py
git commit -m @"
Add Dell Report identity resolver and card_overrides settings.

"@
```

---

### Task 3: Wire collect + export to use selector, identity, include_pools

**Files:**
- Modify: `launchpad/dell_report_export.py` (`collect_dell_report_rows`, `maybe_upsert_dell_snapshot_for_card`, `_capacity_summary_for_site`)
- Modify: `launchpad/health_server.py` (`export_dell_report_excel_bytes`)
- Modify: `tests/test_dell_report_collect.py`
- Modify: `tests/test_dell_report_api.py` if needed

**Interfaces:**
- Consumes: `select_dell_capacity_summary`, `resolve_dell_identity`
- Produces: `collect_dell_report_rows(..., include_pools: bool = True, card_overrides: dict | None = None)`

- [ ] **Step 1: Write failing collect test for CPG-off raw**

```python
def test_collect_uses_raw_when_include_pools_false():
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
        sites, snapshot_store={}, include_pools=False, now=datetime(2026, 8, 5, tzinfo=timezone.utc)
    )
    assert ibm == []
    assert len(hp) == 1
    assert hp[0]["array_name"] == "Vdiprimera101"
    assert hp[0]["facility"] == "Remote"
    assert hp[0]["model"] == "HPE Primera 600 4-way"
```

- [ ] **Step 2: Run collect test — expect FAIL**

Run: `python -m pytest tests/test_dell_report_collect.py::test_collect_uses_raw_when_include_pools_false -v`  
Expected: FAIL (no rows or wrong kwargs)

- [ ] **Step 3: Update collect_dell_report_rows**

Replace `_capacity_summary_for_site` usage with:

```python
from launchpad.dell_report_capacity import select_dell_capacity_summary
from launchpad.dell_report_identity import resolve_dell_identity

def collect_dell_report_rows(
    sites,
    *,
    snapshot_store: dict,
    now: datetime | None = None,
    include_pools: bool = True,
    card_overrides: dict | None = None,
) -> tuple[list[dict], list[dict], dict]:
    ...
        summary = select_dell_capacity_summary(
            capacity_summary=_site_value(site, "capacity_summary"),
            raw_capacity_summary=_site_value(site, "raw_capacity_summary"),
            pools=_site_value(site, "pools") or [],
            include_pools=include_pools,
        )
        if not summary:
            continue
        ident = resolve_dell_identity(
            card_id=card_id,
            site_name=name,
            device_profile=device_profile,
            summary_name=str(summary.get("name") or ""),
            overrides=card_overrides or {},
        )
        facility = ident["facility"]
        model = ident["model"]
        array_name = ident["array_name"]
```

Remove old `facility_from_name` / `model = summary.get("name")` / `array_name = name` path. Keep snapshot upsert fields using these identity values.

Update `maybe_upsert_dell_snapshot_for_card` similarly (accept optional `include_pools` / `card_overrides`, or call selector with `include_pools=True` default for background upsert — prefer accepting the same kwargs for consistency).

- [ ] **Step 4: Pass flags from health_server.export_dell_report_excel_bytes**

```python
from launchpad.dell_report_settings import load_dell_report_settings

settings = load_dell_report_settings(self.db) if hasattr(self, "db") else {"card_overrides": {}}
# Or use settings_view / existing settings access pattern in HealthServer
overrides = settings.get("card_overrides") or {}
ibm_rows, hp_rows, store = collect_dell_report_rows(
    sites,
    snapshot_store=store,
    include_pools=include_pools,
    card_overrides=overrides,
)
```

Match how other Dell settings are loaded in this class (reuse the settings DB handle already used for `is_dell_report_enabled`).

- [ ] **Step 5: Run collect + api tests — expect PASS**

Run: `python -m pytest tests/test_dell_report_collect.py tests/test_dell_report_api.py -q`  
Expected: PASS

- [ ] **Step 6: Commit**

```powershell
git add launchpad/dell_report_export.py launchpad/health_server.py tests/test_dell_report_collect.py tests/test_dell_report_api.py
git commit -m @"
Wire Dell Report collect to raw capacity and identity overrides.

"@
```

---

### Task 4: IBM/HP Report - Wkly sheets (per ISO week columns)

**Files:**
- Modify: `launchpad/dell_report_export.py` (`ORDERED_SHEET_NAMES`, `build_dell_report_workbook`, new builders)
- Modify: `launchpad/dell_report_snapshots.py` — add `ordered_weeks_for_cards(store, card_ids) -> list[str]` if helpful
- Modify: `tests/test_dell_report_export.py`

**Interfaces:**
- Consumes: snapshot store weeks via row metadata — each report row must retain `card_id` for week lookup
- Produces: sheets `IBM Report - Wkly`, `HP Report - Wkly` with Facility/Array/Model + week groups

**Row shape note:** Ensure `_row_from_snapshots` / collect includes `"card_id"` on each row so Wkly builder can read that card’s weeks from a store passed into `build_dell_report_workbook`.

- [ ] **Step 1: Extend build_dell_report_workbook signature**

```python
def build_dell_report_workbook(
    *,
    ibm_rows: list[dict],
    hp_rows: list[dict],
    report_date: datetime | None = None,
    snapshot_store: dict | None = None,
) -> Workbook:
```

Sheet order for IBM/HP family:

```python
IBM_SHEET_NAME,                    # IBM Report
"IBM Report - Wkly",
IBM_FORECAST_SHEET_NAME,
IBM_FORECAST_WKLY_SHEET_NAME,
HP_SHEET_NAME,
"HP Report - Wkly",
HP_FORECAST_SHEET_NAME,
HP_FORECAST_WKLY_SHEET_NAME,
```

Add constants `IBM_REPORT_WKLY_SHEET_NAME = "IBM Report - Wkly"` etc. Update `STUB_SHEET_NAMES` so live Wkly report sheets are **not** stubs.

- [ ] **Step 2: Write failing export test**

```python
def test_workbook_has_report_wkly_sheets_with_week_columns():
    store = {}
    # upsert two weeks for card 1 via upsert_week_snapshot
    rows = [_minimal_row(card_id=1, facility="Remote", array_name="A1", model="M1")]
    wb = build_dell_report_workbook(
        ibm_rows=rows, hp_rows=[], snapshot_store=store, report_date=datetime(2026, 8, 5, tzinfo=timezone.utc)
    )
    assert "IBM Report - Wkly" in wb.sheetnames
    assert "HP Report - Wkly" in wb.sheetnames
    ws = wb["IBM Report - Wkly"]
    # Header row includes Utilization for each week present in store
    headers = [ws.cell(row=9, column=c).value for c in range(3, 20)]
    assert "Facility" in headers
    assert any(h and "Utilization" in str(h) for h in headers)
```

Seed `store` with two ISO weeks before build so at least two util header groups exist.

- [ ] **Step 3: Implement _build_report_wkly_sheet**

Logic:
1. Collect union of ISO weeks across relevant family card_ids from `snapshot_store`, sorted oldest→newest (max `DELL_SNAPSHOT_RETENTION_WEEKS`).
2. Header: Facility, Storage Array, Model Number; then for each week three columns Useable/Used/Utilization %; date labels on row 8 spanning each triad.
3. Rows: grouped facility; for each week look up snapshot bytes → GiB + util fraction; blank if missing.
4. Apply icon LEDs on every Utilization column index.

Also pass `snapshot_store` from `export_dell_report_excel_bytes` into `build_dell_report_workbook`.

Ensure collect rows include `card_id`:

```python
row = _row_from_snapshots(prior, current)
row["card_id"] = card_id
```

- [ ] **Step 4: Run export tests — expect PASS**

Run: `python -m pytest tests/test_dell_report_export.py -q`  
Expected: PASS (update any sheet-order assertions)

- [ ] **Step 5: Commit**

```powershell
git add launchpad/dell_report_export.py launchpad/dell_report_snapshots.py tests/test_dell_report_export.py
git commit -m @"
Add live IBM/HP Report - Wkly sheets with per-week capacity columns.

"@
```

---

### Task 5: Populate IBM/HP Forecast - Wkly

**Files:**
- Modify: `launchpad/dell_report_export.py`
- Modify: `tests/test_dell_report_export.py`

**Interfaces:**
- Produces: `_build_forecast_wkly_sheet(ws, rows, report_date=...)` writing current util + projected +1/+4/+8/+12 week utils

- [ ] **Step 1: Write failing test**

```python
def test_hp_forecast_wkly_has_data_rows():
    wb = build_dell_report_workbook(ibm_rows=[], hp_rows=[_minimal_row(curr_util=0.25)])
    ws = wb["HP Forecast - Wkly"]
    assert ws.cell(row=10, column=3).value  # facility or first data
    # util columns present
    assert ws.cell(row=10, column=6).value == 0.25
```

Adjust column indices to match implementation (Facility at col 3).

- [ ] **Step 2: Implement forecast weekly projection helper**

```python
_FORECAST_WKLY_HORIZONS = (1, 4, 8, 12)

def _project_util(curr_util: float | None, weekly_growth: float | None, weeks_ahead: int) -> float | None:
    if curr_util is None:
        return None
    if weekly_growth is None:
        return float(curr_util)
    # compound: curr * (1 + g)^n, clamp to [0, 1.5] display-safe or just leave uncapped
    projected = float(curr_util) * ((1.0 + float(weekly_growth)) ** weeks_ahead)
    return max(0.0, projected)
```

Use `row["curr_util"]` and `row["weekly_growth"]` (already on report rows). Headers: Facility, Storage Array, Model Number, Date (current), +1 Week, +4 Week, +8 Week, +12 Week. Apply icon LEDs on util columns. Banner via `_add_logos`.

Wire in `build_dell_report_workbook`:

```python
elif name == IBM_FORECAST_WKLY_SHEET_NAME:
    _build_forecast_wkly_sheet(ws, ibm_rows, report_date=when)
elif name == HP_FORECAST_WKLY_SHEET_NAME:
    _build_forecast_wkly_sheet(ws, hp_rows, report_date=when)
elif "Forecast" in name:
    _build_forecast_sheet(ws, [], report_date=when)  # other vendor stubs
```

Stop treating IBM/HP Forecast - Wkly as empty `_build_forecast_sheet([], ...)`.

- [ ] **Step 3: Run export tests — expect PASS**

Run: `python -m pytest tests/test_dell_report_export.py -q`  
Expected: PASS

- [ ] **Step 4: Commit**

```powershell
git add launchpad/dell_report_export.py tests/test_dell_report_export.py
git commit -m @"
Populate IBM/HP Forecast - Wkly with +1/+4/+8/+12 week projections.

"@
```

---

### Task 6: Admin overrides UI + version 1.6.119 + full regression

**Files:**
- Modify: `launchpad/ui/admin_view.py` (`_load_dell_report_form`, `_save_dell_report_form`)
- Modify: `launchpad/config.py` — `APP_VERSION = "1.6.119"`
- Modify: `docs/superpowers/specs/2026-08-05-dell-report-raw-facility-wkly-design.md` — Status: Approved
- Modify: `tests/test_capacity_report_dell_button.py` or settings tests if Admin strings asserted

- [ ] **Step 1: Add Admin JSON textbox for card_overrides**

Below the Dell Report enable checkbox, add a multiline CTkTextbox labeled “Card overrides (JSON)” with placeholder example. On load, dump `settings["card_overrides"]` with `json.dumps(..., indent=2)`. On save:

```python
try:
    parsed = json.loads(self.dell_report_overrides_text.get("1.0", "end").strip() or "{}")
except json.JSONDecodeError:
    messagebox.showerror("Dell Report", "Card overrides must be valid JSON object.")
    return
raw = {"enabled": bool(self.dell_report_enabled_var.get()), "card_overrides": parsed}
saved = save_dell_report_settings(self.db, raw)
```

If the textbox holds the overrides object only (not wrapping enabled), merge as above. Do not require a full card grid UI.

- [ ] **Step 2: Bump version to 1.6.119**

In `launchpad/config.py`: `APP_VERSION = "1.6.119"`

- [ ] **Step 3: Full Dell Report + related regression**

Run:

```powershell
python -m pytest tests/test_dell_report_export.py tests/test_dell_report_helpers.py tests/test_dell_report_api.py tests/test_dell_report_collect.py tests/test_dell_report_capacity.py tests/test_dell_report_identity.py tests/test_dell_report_settings.py tests/test_dell_report_snapshots.py tests/test_capacity_report_dell_button.py -q
```

Expected: all PASS

- [ ] **Step 4: Commit**

```powershell
git add launchpad/ui/admin_view.py launchpad/config.py docs/superpowers/specs/2026-08-05-dell-report-raw-facility-wkly-design.md tests
git commit -m @"
Ship Dell Report raw/facility/wkly sheets as 1.6.119 with Admin overrides.

"@
```

---

## Spec coverage checklist

| Spec requirement | Task |
|------------------|------|
| CPG off → raw rows | 1, 3 |
| CPG on → system then pools then raw | 1, 3 |
| Pass include_pools into collect | 3 |
| Remote facility heuristic | 1 |
| Array from summary name; model from DEVICE_PROFILES | 2, 3 |
| card_overrides | 2, 3, 6 |
| IBM/HP Report unchanged chrome, better data | 3 |
| Report - Wkly per ISO week | 4 |
| Sheet order Report → Report-Wkly → Forecast → Forecast-Wkly | 4 |
| Forecast monthly unchanged | (no change) |
| Forecast - Wkly +1/+4/+8/+12 | 5 |
| Admin override editor | 6 |
| Version 1.6.119 | 6 |
| Tests listed in spec | 1–6 |

## Self-review notes

- No TBD placeholders; Forecast - Wkly horizons locked to +1/+4/+8/+12.
- `card_id` on rows required for Task 4 — called out explicitly.
- Settings equality tests must expect `card_overrides: {}` after Task 2.
