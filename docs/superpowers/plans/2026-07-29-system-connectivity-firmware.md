# System Connectivity Firmware Tab + Admin Catalog Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Firmware tab to System Connectivity (Current / Latest / Versions behind) driven by an Admin-maintained per-`device_profile` ordered catalog, with Excel/CSV export and version **1.6.73**.

**Architecture:** New `firmware_catalog.py` for DB load/save + behind-count math. Extend `system_connectivity` parsers/TOPICS for firmware Current. Live scan joins catalog by profile; page/export gain a fifth topic. Admin tab edits the same catalog JSON setting.

**Tech Stack:** Python, CustomTkinter Admin, HealthServer SSH scan, openpyxl/CSV ZIP, pytest.

**Spec:** `docs/superpowers/specs/2026-07-29-system-connectivity-firmware-design.md`

## Global Constraints

- **Worktree:** `.worktrees/system-connectivity-firmware` on `feature/system-connectivity-firmware` from `feature/contingency-groups` tip (must include design commit `80af945` or later)
- Fifth tab **Firmware** after NTP on `/system-connectivity`; Excel sheet `Firmware`; CSV `firmware.csv`
- Catalog: ordered oldest→newest **per `device_profile`**; Admin UI only; exact string match
- Current not in catalog / empty catalog / collect fail → Versions behind = `unknown`
- Platforms: same eligibility as System Connectivity (FlashSystem / HPE / DS8884)
- Read-only; no upgrade commands; no semver auto-sort
- Bump `APP_VERSION` to **1.6.73**
- Commit at each task’s commit step
- Run from: `cd C:\Users\BrianColley\LaunchPad\.worktrees\system-connectivity-firmware`

---

## File map

| File | Responsibility |
|------|----------------|
| `launchpad/firmware_catalog.py` | Load/save catalog JSON; eligible profiles; Latest; Versions behind |
| `launchpad/system_connectivity.py` | Add `firmware` to TOPICS; Current parsers; enrich row with Latest/Behind |
| `launchpad/system_connectivity_export.py` | Fifth sheet/CSV with firmware columns |
| `launchpad/system_connectivity_page.py` | Fifth tab + table columns + hint |
| `launchpad/health_server.py` | Collect Current; join catalog; cache `firmware` |
| `launchpad/ui/admin_view.py` | Admin tab Firmware catalog |
| `launchpad/config.py` | `1.6.73` |
| Tests | Catalog math/CRUD, parsers, export, page, version |

---

### Task 0: Confirm baseline

**Files:** none (worktree only)

- [ ] **Step 1: Create worktree**

```powershell
cd C:\Users\BrianColley\LaunchPad
git fetch origin
git worktree add .worktrees/system-connectivity-firmware -b feature/system-connectivity-firmware feature/contingency-groups
cd .worktrees/system-connectivity-firmware
python -c "from launchpad.config import APP_VERSION; print(APP_VERSION)"
Test-Path docs\superpowers\specs\2026-07-29-system-connectivity-firmware-design.md
```

Expected: tip version (e.g. `1.6.70` or later if header-wrap committed), spec `True`. If spec missing, cherry-pick/merge design commit first.

- [ ] **Step 2: No feature commit**

---

### Task 1: Firmware catalog helpers (TDD)

**Files:**
- Create: `launchpad/firmware_catalog.py`
- Create: `tests/test_firmware_catalog.py`

**Interfaces:**
- Produces:
  - `FIRMWARE_CATALOG_SETTING = "firmware_catalog"`
  - `eligible_firmware_profiles() -> list[str]` — sorted profile keys from `SVC_PROFILES | HPE_SHELL_PROFILES | {"ibm_ds8884"}`
  - `normalize_catalog(raw: Any) -> dict[str, list[str]]` — profile → ordered unique versions (preserve order; drop blanks/dupes)
  - `load_firmware_catalog(db) -> dict[str, list[str]]`
  - `save_firmware_catalog(db, catalog: dict[str, list[str]]) -> dict[str, list[str]]` — normalize then `db.set_setting(FIRMWARE_CATALOG_SETTING, json.dumps(...))`
  - `get_profile_catalog(catalog: dict[str, list[str]], profile: str) -> list[str]`
  - `latest_in_catalog(versions: list[str]) -> str` — last entry or `""`
  - `versions_behind(current: str, versions: list[str]) -> str` — `"0"` / `"N"` / `"unknown"` per spec

- [ ] **Step 1: Write failing tests**

```python
from launchpad.firmware_catalog import (
    eligible_firmware_profiles,
    latest_in_catalog,
    normalize_catalog,
    versions_behind,
)


def test_versions_behind_counts_entries_after_current():
    catalog = ["8.5.0", "8.6.0", "8.6.1", "8.6.2"]
    assert versions_behind("8.6.0", catalog) == "2"
    assert versions_behind("8.6.2", catalog) == "0"
    assert versions_behind("8.7.0", catalog) == "unknown"
    assert versions_behind("8.6.0", []) == "unknown"
    assert versions_behind("", catalog) == "unknown"


def test_latest_in_catalog():
    assert latest_in_catalog(["8.5.0", "8.6.2"]) == "8.6.2"
    assert latest_in_catalog([]) == ""


def test_normalize_catalog_drops_blanks_and_dupes_keeps_order():
    raw = {"flashsystem_7300": ["8.5.0", "", "8.6.0", "8.5.0", "8.6.1"]}
    assert normalize_catalog(raw) == {
        "flashsystem_7300": ["8.5.0", "8.6.0", "8.6.1"]
    }


def test_eligible_firmware_profiles_includes_svc_hpe_ds():
    profiles = eligible_firmware_profiles()
    assert "flashsystem_7300" in profiles
    assert "ibm_ds8884" in profiles
    assert profiles == sorted(profiles)
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `pytest tests/test_firmware_catalog.py -v`  
Expected: FAIL (module missing)

- [ ] **Step 3: Implement `launchpad/firmware_catalog.py`**

```python
"""Per-device_profile firmware release catalogs and behind-count helpers."""

from __future__ import annotations

import json
from typing import Any

from launchpad.storage_presets import HPE_SHELL_PROFILES, SVC_PROFILES

FIRMWARE_CATALOG_SETTING = "firmware_catalog"
_DS8884 = "ibm_ds8884"


def eligible_firmware_profiles() -> list[str]:
    return sorted(set(SVC_PROFILES) | set(HPE_SHELL_PROFILES) | {_DS8884})


def normalize_catalog(raw: Any) -> dict[str, list[str]]:
    if not isinstance(raw, dict):
        return {}
    out: dict[str, list[str]] = {}
    for key, value in raw.items():
        profile = str(key or "").strip().lower()
        if not profile:
            continue
        seen: set[str] = set()
        ordered: list[str] = []
        items = value if isinstance(value, list) else []
        for item in items:
            version = str(item or "").strip()
            if not version or version in seen:
                continue
            seen.add(version)
            ordered.append(version)
        out[profile] = ordered
    return out


def load_firmware_catalog(db) -> dict[str, list[str]]:
    raw = db.get_setting(FIRMWARE_CATALOG_SETTING, "") or ""
    if not str(raw).strip():
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return normalize_catalog(parsed)


def save_firmware_catalog(db, catalog: dict[str, list[str]]) -> dict[str, list[str]]:
    normalized = normalize_catalog(catalog)
    db.set_setting(FIRMWARE_CATALOG_SETTING, json.dumps(normalized))
    return normalized


def get_profile_catalog(catalog: dict[str, list[str]], profile: str) -> list[str]:
    key = str(profile or "").strip().lower()
    return list(catalog.get(key) or [])


def latest_in_catalog(versions: list[str]) -> str:
    return versions[-1] if versions else ""


def versions_behind(current: str, versions: list[str]) -> str:
    cur = str(current or "").strip()
    if not cur or not versions:
        return "unknown"
    try:
        idx = versions.index(cur)
    except ValueError:
        return "unknown"
    return str(len(versions) - idx - 1)
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `pytest tests/test_firmware_catalog.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add launchpad/firmware_catalog.py tests/test_firmware_catalog.py
git commit -m "Add per-profile firmware catalog helpers and behind-count."
```

---

### Task 2: Firmware Current parsers (TDD)

**Files:**
- Modify: `launchpad/system_connectivity.py`
- Create: `tests/test_system_connectivity_firmware.py`

**Interfaces:**
- Consumes: `versions_behind`, `latest_in_catalog`, `get_profile_catalog` from Task 1
- Produces:
  - Extend `TOPICS` to `("call_home", "dns", "snmp", "ntp", "firmware")`
  - `FIRMWARE_EXTRA_FIELDS: tuple[str, ...] = ("current", "latest", "versions_behind")`
  - `parse_svc_firmware_from_lssystem(output: str) -> tuple[str, str, str, str]` → `(configured, status, details, current)`
  - `parse_hpe_showversion_firmware(output: str) -> tuple[str, str, str, str]` — parse a `Version:` / `Release version:` style line; if output non-empty but no version → `("no", "empty", "no firmware version", "")`
  - `parse_ds_firmware(output: str) -> tuple[str, str, str, str]` — best-effort; empty/unrecognized → `("n/a", "n/a", "Firmware not available via DSCLI on this path", "")`
  - `enrich_firmware_row(row: dict, *, current: str, catalog: list[str], configured: str, status: str = "", details: str = "", error: str = "") -> dict` — sets `current`, `latest`, `versions_behind`, plus finalize fields; Status hint: `current` if behind `0`, `behind` if numeric >0, `unknown` if behind unknown
  - Extend `topic_commands_for_profile`: firmware → SVC `["lssystem -delim :"]`, HPE `["showversion"]`, DS `[]` (n/a path) or best-effort command if already used elsewhere

- [ ] **Step 1: Write failing tests**

```python
from launchpad.system_connectivity import (
    base_row,
    enrich_firmware_row,
    parse_hpe_showversion_firmware,
    parse_svc_firmware_from_lssystem,
    TOPICS,
)


def test_topics_include_firmware():
    assert TOPICS[-1] == "firmware"
    assert "ntp" in TOPICS


def test_parse_svc_firmware_code_level():
    output = "id:1\nname:fs1\ncode_level:8.6.0.0 (build 152.24.2403051134)\n"
    configured, status, details, current = parse_svc_firmware_from_lssystem(output)
    assert configured == "yes"
    assert current == "8.6.0.0 (build 152.24.2403051134)"
    assert "8.6.0.0" in details


def test_enrich_firmware_row_behind_count():
    row = base_row(
        card_name="SiteA", host="1.2.3.4", vendor="ibm", profile="flashsystem_7300"
    )
    catalog = ["8.5.0", "8.6.0", "8.6.1"]
    out = enrich_firmware_row(
        row,
        current="8.6.0",
        catalog=catalog,
        configured="yes",
        status="behind",
        details="8.6.0 → 8.6.1",
    )
    assert out["current"] == "8.6.0"
    assert out["latest"] == "8.6.1"
    assert out["versions_behind"] == "1"


def test_enrich_firmware_unknown_when_current_missing_from_catalog():
    row = base_row(
        card_name="SiteA", host="1.2.3.4", vendor="ibm", profile="flashsystem_7300"
    )
    out = enrich_firmware_row(
        row, current="9.0.0", catalog=["8.5.0", "8.6.0"], configured="yes"
    )
    assert out["versions_behind"] == "unknown"
    assert out["latest"] == "8.6.0"


def test_parse_hpe_showversion_firmware():
    output = "System Name: array1\nVersion: 4.1.2\n"
    configured, status, details, current = parse_hpe_showversion_firmware(output)
    assert configured == "yes"
    assert current == "4.1.2"
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `pytest tests/test_system_connectivity_firmware.py -v`  
Expected: FAIL (symbols missing / TOPICS without firmware)

- [ ] **Step 3: Implement parsers + enrich in `system_connectivity.py`**

Add imports from `firmware_catalog`. Append `"firmware"` to `TOPICS`. Implement parsers:

- SVC: scan `lssystem` lines for `code_level:` (same partition style as NTP); empty → unknown; missing key → unknown; blank value → no.
- HPE: regex/line scan for `Version:` or `Release version:` (case-insensitive); never treat community-like tokens.
- DS: if no usable output → n/a tuple as specified.
- `enrich_firmware_row`: copy base via `finalize_row`; set `current`, `latest=latest_in_catalog(catalog)`, `versions_behind=versions_behind(current, catalog)`; if configured is `yes` and behind is `"0"` set status default `current`; if behind is digit `>0` default status `behind`; if `unknown` default status `unknown` unless error set.

Update `topic_commands_for_profile` firmware commands as in Interfaces.

- [ ] **Step 4: Run tests — expect PASS**

Run: `pytest tests/test_system_connectivity_firmware.py tests/test_system_connectivity.py -v`  
Expected: PASS (existing connectivity tests still pass)

- [ ] **Step 5: Commit**

```powershell
git add launchpad/system_connectivity.py tests/test_system_connectivity_firmware.py
git commit -m "Add firmware Current parsers and catalog enrich for System Connectivity."
```

---

### Task 3: Live scan + cache include firmware

**Files:**
- Modify: `launchpad/health_server.py` (system connectivity scan/cache methods)
- Create: `tests/test_system_connectivity_firmware_api.py`

**Interfaces:**
- Consumes: Task 1–2 helpers; existing `_scan_system_connectivity_*_card`
- Produces: cache payload key `firmware: list[dict]`; each scan path fills firmware row

- [ ] **Step 1: Write failing test**

```python
from launchpad.health_server import HealthServer
from launchpad.firmware_catalog import save_firmware_catalog


class _FakeDB:
    def __init__(self):
        self._s = {}

    def get_setting(self, key, default=""):
        return self._s.get(key, default)

    def set_setting(self, key, value):
        self._s[key] = value


def test_scan_payload_includes_firmware_key(monkeypatch):
    server = HealthServer()
    db = _FakeDB()
    save_firmware_catalog(db, {"flashsystem_7300": ["8.5.0", "8.6.0"]})

    # Minimal: set_system_connectivity_cache round-trip includes firmware
    server.set_system_connectivity_cache(
        {
            "call_home": [],
            "dns": [],
            "snmp": [],
            "ntp": [],
            "firmware": [{"card_name": "A", "current": "8.5.0", "versions_behind": "1"}],
            "errors": [],
        }
    )
    cached = server.get_system_connectivity_cache()
    assert "firmware" in cached
    assert cached["firmware"][0]["versions_behind"] == "1"
```

- [ ] **Step 2: Run test — expect FAIL** if cache ignores `firmware`

Run: `pytest tests/test_system_connectivity_firmware_api.py -v`  
Expected: FAIL or incomplete firmware in get/set until patched

- [ ] **Step 3: Wire scan + cache**

In `get_system_connectivity_cache` / `set_system_connectivity_cache` / live payload builder, include `"firmware"` alongside other topics.

In each `_scan_system_connectivity_*_card`:
- SVC: reuse `lssystem` output already fetched for NTP when possible; parse firmware via `parse_svc_firmware_from_lssystem`; load catalog from server DB (same pattern as other settings access used by Capacity Email — pass `db` already available on HealthServer/monitor path). If HealthServer has no direct `db`, load catalog once in `scan_system_connectivity_live` and pass `catalog` dict into scanners.
- HPE: run `showversion` (or add to the existing multi-command batch); parse; enrich.
- DS: n/a / unknown path via `parse_ds_firmware("")` or best-effort if a command is run.

Always `enrich_firmware_row(...)` before appending to `rows["firmware"]`.

- [ ] **Step 4: Run tests — expect PASS**

Run: `pytest tests/test_system_connectivity_firmware_api.py tests/test_system_connectivity_api.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add launchpad/health_server.py tests/test_system_connectivity_firmware_api.py
git commit -m "Include firmware rows in System Connectivity live scan and cache."
```

---

### Task 4: Export Firmware sheet + CSV

**Files:**
- Modify: `launchpad/system_connectivity_export.py`
- Modify: `tests/test_system_connectivity_export.py`

**Interfaces:**
- Produces:
  - `TOPIC_SHEETS["firmware"] = "Firmware"`
  - `TOPIC_CSV_NAMES["firmware"] = "firmware.csv"`
  - `FIRMWARE_HEADERS` / `FIRMWARE_FIELDS` including Current, Latest, Versions behind (identity + configured/status/details/error + the three firmware fields)
  - `_TOPIC_KEYS` includes `"firmware"`
  - Excel/CSV writers use firmware headers/fields for the firmware topic only; other topics keep existing `HEADERS`/`_FIELDS`

- [ ] **Step 1: Extend failing assertions in export test**

```python
from launchpad.system_connectivity_export import (
    TOPIC_SHEETS,
    TOPIC_CSV_NAMES,
    export_system_connectivity_csv_zip,
    export_system_connectivity_xlsx,
)
import zipfile
from io import BytesIO
from openpyxl import load_workbook


def test_export_includes_firmware_sheet_and_columns():
    payload = {
        "call_home": [],
        "dns": [],
        "snmp": [],
        "ntp": [],
        "firmware": [
            {
                "site": "A",
                "card_name": "A",
                "host": "1.1.1.1",
                "vendor": "ibm",
                "profile": "flashsystem_7300",
                "configured": "yes",
                "status": "behind",
                "details": "8.6.0 → 8.6.1",
                "error": "",
                "current": "8.6.0",
                "latest": "8.6.1",
                "versions_behind": "1",
            }
        ],
        "errors": [],
    }
    assert TOPIC_SHEETS["firmware"] == "Firmware"
    wb = load_workbook(BytesIO(export_system_connectivity_xlsx(payload)))
    assert "Firmware" in wb.sheetnames
    sheet = wb["Firmware"]
    headers = [cell.value for cell in sheet[1]]
    assert "Current" in headers
    assert "Versions behind" in headers
    z = zipfile.ZipFile(BytesIO(export_system_connectivity_csv_zip(payload)))
    assert "firmware.csv" in z.namelist()
```

- [ ] **Step 2: Run — expect FAIL**

Run: `pytest tests/test_system_connectivity_export.py -v`  
Expected: FAIL missing Firmware

- [ ] **Step 3: Implement export changes**

```python
TOPIC_SHEETS = {
    "call_home": "Call Home",
    "dns": "DNS",
    "snmp": "SNMP",
    "ntp": "NTP",
    "firmware": "Firmware",
}
TOPIC_CSV_NAMES = {
    "call_home": "call_home.csv",
    "dns": "dns.csv",
    "snmp": "snmp.csv",
    "ntp": "ntp.csv",
    "firmware": "firmware.csv",
}
_TOPIC_KEYS = ("call_home", "dns", "snmp", "ntp", "firmware")

FIRMWARE_HEADERS = (
    "Site", "Card", "Host", "Vendor", "Profile",
    "Current", "Latest", "Versions behind",
    "Configured", "Status", "Details", "Error",
)
FIRMWARE_FIELDS = (
    "site", "card_name", "host", "vendor", "profile",
    "current", "latest", "versions_behind",
    "configured", "status", "details", "error",
)
```

In `export_system_connectivity_xlsx` / `export_system_connectivity_csv_zip`, when `topic_key == "firmware"` use `FIRMWARE_HEADERS`/`FIRMWARE_FIELDS`; else existing headers/fields. Update `filter_payload_by_card_id` to include firmware in `_TOPIC_KEYS`.

- [ ] **Step 4: Run — expect PASS**

Run: `pytest tests/test_system_connectivity_export.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add launchpad/system_connectivity_export.py tests/test_system_connectivity_export.py
git commit -m "Export System Connectivity Firmware sheet and CSV."
```

---

### Task 5: Page Firmware tab UI

**Files:**
- Modify: `launchpad/system_connectivity_page.py`
- Modify: `tests/test_system_connectivity_page.py`

**Interfaces:**
- Produces: tab button + panel after NTP; JS `TOPICS` includes `firmware`; render columns Current / Latest / Versions behind for firmware rows (colspan 12); hint text from spec

- [ ] **Step 1: Failing page assertions**

```python
from launchpad.system_connectivity_page import SYSTEM_CONNECTIVITY_HTML


def test_page_has_firmware_tab_after_ntp():
    html = SYSTEM_CONNECTIVITY_HTML
    assert 'data-tab="firmware"' in html
    assert html.index('data-tab="ntp"') < html.index('data-tab="firmware"')
    assert "Versions behind" in html
    assert "Admin Firmware catalog" in html
    assert 'const TOPICS = ["call_home", "dns", "snmp", "ntp", "firmware"]' in html.replace(" ", "") or (
        '"firmware"' in html and "TOPICS" in html
    )
```

(Prefer a robust check: `"firmware"` in TOPICS array and Firmware panel id `sc-panel-firmware`.)

- [ ] **Step 2: Run — expect FAIL**

Run: `pytest tests/test_system_connectivity_page.py -v`  
Expected: FAIL

- [ ] **Step 3: Update HTML/JS**

- Hero blurb: mention firmware.
- Tab: `<button ... data-tab="firmware">Firmware</button>` after NTP.
- Panel with hint: *Versions behind uses the Admin Firmware catalog for this device profile. If Current is not in the catalog, behind shows unknown.*
- Table headers: Site, Card, Host, Vendor, Profile, Current, Latest, Versions behind, Configured, Status, Details, Error.
- JS: add `firmware` to `TOPICS`, `TOPIC_LABELS`, `bodies`; in `renderTopic`, if topic === `firmware` render the extra three cells and colspan 12 for empty state.

- [ ] **Step 4: Run — expect PASS**

Run: `pytest tests/test_system_connectivity_page.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add launchpad/system_connectivity_page.py tests/test_system_connectivity_page.py
git commit -m "Add Firmware tab to System Connectivity page."
```

---

### Task 6: Admin Firmware catalog tab

**Files:**
- Modify: `launchpad/ui/admin_view.py`
- Create: `tests/test_firmware_catalog_admin.py` (source/string assertions and/or pure helper round-trip already covered; add save/load integration with fake db)

**Interfaces:**
- Consumes: `eligible_firmware_profiles`, `load_firmware_catalog`, `save_firmware_catalog`, `get_profile_catalog`
- Produces: Admin tab **Firmware catalog** with profile dropdown, listbox/CTkTextbox or scrollable labels, Add / Remove / Move up / Move down / Save

- [ ] **Step 1: Failing test (module presence + save round-trip already in Task 1; add Admin source asserts)**

```python
from pathlib import Path


def test_admin_view_has_firmware_catalog_tab():
    source = (
        Path(__file__).parents[1] / "launchpad" / "ui" / "admin_view.py"
    ).read_text(encoding="utf-8")
    assert 'self.tabs.add("Firmware catalog")' in source or '"Firmware catalog"' in source
    assert "save_firmware_catalog" in source
    assert "load_firmware_catalog" in source
```

- [ ] **Step 2: Run — expect FAIL**

Run: `pytest tests/test_firmware_catalog_admin.py -v`  
Expected: FAIL

- [ ] **Step 3: Implement Admin tab**

In `_build_admin_ui` after Capacity Email tab:

```python
firmware_tab = self.tabs.add("Firmware catalog")
firmware_tab.grid_columnconfigure(0, weight=1)
firmware_tab.grid_rowconfigure(0, weight=1)
self._build_firmware_catalog_panel(firmware_tab)
```

Implement `_build_firmware_catalog_panel(self, parent)`:
- Profile `CTkOptionMenu` values=`eligible_firmware_profiles()`
- `CTkTextbox` or scrollable list showing one version per line for selected profile (oldest at top)
- Entry + **Add** (append; reject blank/duplicate with status label)
- **Remove** selected line / last line if using textbox selection
- **Move up** / **Move down** reorder selected index
- **Save** → rebuild full catalog dict from in-memory map, `save_firmware_catalog(self.db, ...)`
- On profile change: stash edits for previous profile into in-memory map; load list for new profile from map (initialized from `load_firmware_catalog(self.db)` on panel build)

Keep UI consistent with Capacity Email panel spacing/theme colors.

- [ ] **Step 4: Run — expect PASS**

Run: `pytest tests/test_firmware_catalog_admin.py tests/test_firmware_catalog.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add launchpad/ui/admin_view.py tests/test_firmware_catalog_admin.py
git commit -m "Add Admin Firmware catalog tab for per-profile releases."
```

---

### Task 7: Version bump 1.6.73

**Files:**
- Modify: `launchpad/config.py`
- Modify: `tests/test_system_connectivity_version.py` (or create `tests/test_firmware_version.py`)

- [ ] **Step 1: Failing version test**

```python
from launchpad.config import APP_VERSION


def test_app_version_1673():
    assert APP_VERSION == "1.6.73"
```

- [ ] **Step 2: Run — expect FAIL**

Run: `pytest tests/test_system_connectivity_version.py -v`  
Expected: FAIL (still 1.6.70/71/72)

- [ ] **Step 3: Set version**

```python
APP_VERSION = "1.6.73"
```

Update/replace prior version assert function name/value to `1.6.73` only (single source of truth).

- [ ] **Step 4: Run focused suite**

```powershell
pytest tests/test_firmware_catalog.py tests/test_system_connectivity_firmware.py tests/test_system_connectivity_firmware_api.py tests/test_system_connectivity_export.py tests/test_system_connectivity_page.py tests/test_firmware_catalog_admin.py tests/test_system_connectivity_version.py tests/test_system_connectivity.py -q
```

Expected: all PASS

- [ ] **Step 5: Commit**

```powershell
git add launchpad/config.py tests/test_system_connectivity_version.py
git commit -m "Bump LaunchPad to 1.6.73 for System Connectivity Firmware."
```

---

## Spec coverage checklist

| Spec item | Task |
|-----------|------|
| Firmware tab after NTP | 5 |
| Current / Latest / Versions behind | 1, 2, 5 |
| Behind count after Current | 1 |
| Unknown if missing/empty/fail | 1, 2 |
| Per-profile Admin catalog | 1, 6 |
| FlashSystem + HPE + DS8884 | 2, 3 |
| Excel Firmware sheet + CSV | 4 |
| Live cache key `firmware` | 3 |
| No upgrade / no auto-fetch | Global + 6 |
| Version 1.6.73 | 7 |

---

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-29-system-connectivity-firmware.md`. Two execution options:

**1. Subagent-Driven (recommended)** — fresh subagent per task, review between tasks  
**2. Inline Execution** — execute tasks in this session with checkpoints  

Which approach?
