# Storage Inventory Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a dedicated Storage Inventory page and Word-style Excel (Inventory + Issues Summary, red issue rows, totals) for monitored FlashSystem / HPE / DS8884 cards at app version **1.6.147**.

**Architecture:** Pure helpers in `storage_inventory.py` build rows (reuse SysConn Call Home / DNS / NTP parsers; new SMTP + Data Protection parsers; issue aggregation; Excel). `storage_inventory_page.py` hosts the dark report page. `health_server.py` runs per-card live SSH scan, caches payload, serves `/storage-inventory` + live/export APIs. Connection Dashboard opens the page.

**Tech Stack:** Python, openpyxl, HealthServer SSH (`_snap_run_command` pattern), CustomTkinter dashboard button, pytest.

**Spec:** `docs/superpowers/specs/2026-08-10-storage-inventory-design.md`

## Global Constraints

- APP_VERSION is currently `1.6.146`; bump to `1.6.147` in the dashboard/version task.
- Eligibility: same as System Connectivity — `is_system_connectivity_eligible` (monitor-on SSH + `SVC_PROFILES` / `HPE_SHELL_PROFILES` / `ibm_ds8884`).
- Unlock required for Refresh live; view/export cached payload without unlock.
- Excel only (no CSV). Sheets: **Inventory**, **Issues Summary**.
- Red highlight / Devices with Issues **iff** `issues` (Issues / Notes) is non-empty.
- Reuse SysConn parsers for Call Home / DNS / NTP — do not copy-paste parse logic.
- No secrets in cells (no passwords, SNMP communities).
- Windows PowerShell commits (`git commit -m "..."`); commit at each task’s commit step.
- Prefer TDD: failing test → implement → pass → commit.
- Do not commit `.superpowers/sdd*` scratch or install zips.
- Work from a feature branch / worktree off `main` (do not land unfinished work on `main` mid-plan).

## File structure

| File | Responsibility |
|------|----------------|
| `launchpad/storage_inventory.py` | Row schema, CLI map, SMTP/DP/identity parsers, formatters, issue aggregation, Excel, totals |
| `launchpad/storage_inventory_page.py` | `STORAGE_INVENTORY_PATH`, `STORAGE_INVENTORY_HTML` |
| `launchpad/health_server.py` | Page route, `/api/storage-inventory/live`, `/api/storage-inventory/export`, scan + cache, `open_storage_inventory` |
| `launchpad/ui/dashboard_view.py` | **Storage Inventory** tool button + open handler |
| `launchpad/config.py` | `APP_VERSION` → `1.6.147` |
| `tests/test_storage_inventory.py` | Parsers, aggregation, Excel |
| `tests/test_storage_inventory_page.py` | Page contract markers |
| `tests/test_storage_inventory_api.py` | Scan/cache/API (mocked SSH) |
| `tests/test_system_connectivity_version.py` | Version pin → `1.6.147` |
| `tests/test_hadoop_sudo_wire.py` | Version pin → `1.6.147` |

## Locked CLI (v1)

| Platform | Commands |
|----------|----------|
| FlashSystem / SVC | Identity+NTP: `lssystem -delim :`; Call Home: `lscloudcallhome -delim :`; DNS: `lsdnsserver -delim :`; SMTP: `lsemailserver -delim :`; Data Protection: `lsrcrelationship -delim :` |
| HPE 3PAR/Primera | Identity: `showsys`; DNS+NTP: `shownet`; Call Home: **n/a** (no SSH cmd); SMTP: **n/a**; Data Protection: `showrcopy` |
| DS8884 | Call Home / DNS: reuse SysConn cmds (`dscli showsp`, `dscli lsnetworkport`); SMTP: **n/a**; Data Protection: **n/a**; identity best-effort from card / empty live |

---

### Task 1: Parsers, formatters, issue aggregation

**Files:**
- Create: `launchpad/storage_inventory.py`
- Create: `tests/test_storage_inventory.py`

**Interfaces:**
- Produces:
  - `INVENTORY_COLUMNS: tuple[str, ...]` — `("site","host","ip","model","serial","location","phone_home","data_protection","smtp","issues","card_id","profile","vendor")`
  - `inventory_commands_for_profile(profile: str) -> dict[str, list[str]]` — keys `identity`, `call_home`, `dns`, `ntp`, `smtp`, `data_protection` (empty list = skip / n/a)
  - `parse_svc_lssystem_identity(output: str) -> tuple[str, str]` — `(model, serial)` from `product_name` / `id` colon pairs
  - `parse_svc_lsemailserver(output: str) -> tuple[str, str, str]` — `(configured, status, details)` like SysConn (`yes`/`no`/`unknown`); details = joined IPs or `No IP — Not configured`
  - `parse_svc_lsrcrelationship(output: str) -> tuple[str, str, str]` — yes if data rows; no if header-only/empty; unknown if unparseable
  - `parse_hpe_showrcopy_protection(output: str) -> tuple[str, str, str]` — yes if remote-copy targets/groups present; no if clearly empty/disabled; else unknown
  - `format_phone_home_cell(*, configured: str, details: str, vendor: str) -> str`
  - `format_yes_no_cell(*, configured: str, details: str = "", na_label: str = "n/a") -> str`
  - `format_smtp_cell(*, configured: str, details: str) -> str`
  - `health_issue_messages(health_issues: list) -> list[str]` — extract `message` from dicts or stringify
  - `build_issues_notes(*, phone_configured: str, data_protection_configured: str, smtp_configured: str, dns_configured: str, ntp_configured: str, health_issues: list, extra_errors: list[str]) -> str`
  - `row_has_issues(row: dict) -> bool` — `bool(str(row.get("issues") or "").strip())`
  - `inventory_totals(rows: list[dict]) -> dict` — `{"total_devices": N, "devices_with_issues": M}`
  - `build_inventory_row(...)` — assemble one row dict from parsed topic tuples + card identity fields (see Step 3)

- [ ] **Step 1: Write the failing tests**

```python
from launchpad.storage_inventory import (
    build_issues_notes,
    format_phone_home_cell,
    format_smtp_cell,
    inventory_commands_for_profile,
    inventory_totals,
    parse_svc_lsemailserver,
    parse_svc_lsrcrelationship,
    parse_svc_lssystem_identity,
    row_has_issues,
)


def test_inventory_commands_svc_includes_smtp_and_rcrelationship():
    cmds = inventory_commands_for_profile("flashsystem_7200")
    assert cmds["smtp"] == ["lsemailserver -delim :"]
    assert cmds["data_protection"] == ["lsrcrelationship -delim :"]
    assert cmds["call_home"] == ["lscloudcallhome -delim :"]


def test_inventory_commands_hpe_smtp_empty_call_home_empty():
    cmds = inventory_commands_for_profile("hpe_3par_8400")
    assert cmds["smtp"] == []
    assert cmds["call_home"] == []
    assert cmds["data_protection"] == ["showrcopy"]


def test_parse_svc_identity_and_smtp_and_rcrelationship():
    model, serial = parse_svc_lssystem_identity(
        "id:78E31NF\nname:v7kand-g3v1\nproduct_name:IBM FlashSystem 7200\n"
    )
    assert model == "IBM FlashSystem 7200"
    assert serial == "78E31NF"
    cfg, status, details = parse_svc_lsemailserver(
        "id:name:IP_address:port\n0:smtp1:172.29.62.98:25\n"
    )
    assert cfg == "yes"
    assert "172.29.62.98" in details
    cfg2, _, details2 = parse_svc_lsemailserver("id:name:IP_address:port\n")
    assert cfg2 == "no"
    assert "Not configured" in details2
    yes_cfg, _, _ = parse_svc_lsrcrelationship(
        "id:name:master_cluster_id:master_cluster_name\n0:rel1:1:clusterA\n"
    )
    assert yes_cfg == "yes"
    no_cfg, _, _ = parse_svc_lsrcrelationship(
        "id:name:master_cluster_id:master_cluster_name\n"
    )
    assert no_cfg == "no"


def test_issues_notes_and_totals():
    notes = build_issues_notes(
        phone_configured="no",
        data_protection_configured="no",
        smtp_configured="no",
        dns_configured="yes",
        ntp_configured="no",
        health_issues=[{"message": "Running at 91.0% capacity"}],
        extra_errors=[],
    )
    assert "Phone Home not configured" in notes
    assert "Data Protection not configured" in notes
    assert "SMTP not configured" in notes
    assert "NTP not configured" in notes
    assert "Running at 91.0% capacity" in notes
    assert format_phone_home_cell(configured="no", details="", vendor="IBM") == (
        "No — Not configured"
    )
    assert format_smtp_cell(configured="yes", details="172.29.62.98") == "172.29.62.98"
    rows = [
        {"issues": ""},
        {"issues": notes},
    ]
    assert row_has_issues(rows[1]) is True
    assert inventory_totals(rows) == {"total_devices": 2, "devices_with_issues": 1}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_storage_inventory.py -v`  
Expected: FAIL (module / symbols missing)

- [ ] **Step 3: Implement `launchpad/storage_inventory.py`**

Implement the interfaces above. Reuse from `launchpad.system_connectivity`:

- `is_system_connectivity_eligible` (re-export or call-through for scan code)
- `parse_svc_call_home`, `parse_svc_dns`, `parse_svc_ntp_from_lssystem`
- `parse_hpe_shownet_dns_ntp`, `hpe_call_home_na_row`
- `parse_ds_showsp_call_home`, `parse_ds_networkport_dns`
- `_parse_colon_table`, `_header_index`, `_cell` — either import private helpers if already used cross-module, or duplicate only the tiny table helpers **inside** `storage_inventory.py` if imports of `_`-names are awkward; prefer importing public parsers.

`build_issues_notes` order (skip blanks; join with `"; "`):

1. Phone Home not configured — when `phone_configured == "no"`
2. Data Protection not configured — when `data_protection_configured == "no"`
3. SMTP not configured — when `smtp_configured == "no"`
4. DNS not configured — when `dns_configured == "no"`
5. NTP not configured — when `ntp_configured == "no"`
6. Each health issue message
7. Each `extra_errors` string

Do **not** emit notes for `n/a` or `unknown` unless the string is in `extra_errors`.

`format_phone_home_cell`: `n/a` → `n/a`; `unknown` → `unknown`; `no` → `No — Not configured`; `yes` → `Yes — {vendor}` if details empty else `Yes — {short details}`.

`format_smtp_cell`: `n/a`/`unknown` as-is; `no` → details or `No IP — Not configured`; `yes` → details (IPs).

`build_inventory_row` signature:

```python
def build_inventory_row(
    *,
    site: str,
    host: str,
    ip: str,
    model: str,
    serial: str,
    location: str,
    vendor: str,
    profile: str,
    card_id: int | None,
    phone: tuple[str, str, str],
    data_protection: tuple[str, str, str],
    smtp: tuple[str, str, str],
    dns: tuple[str, str, str],
    ntp: tuple[str, str, str],
    health_issues: list | None = None,
    extra_errors: list[str] | None = None,
) -> dict:
    ...
```

Phone/DP/SMTP cells use formatters; `issues` from `build_issues_notes`.

For HPE `showrcopy`: treat output containing a clear “not configured” / empty target table as `no`; any target/group name lines as `yes`; garbage → `unknown`. Keep parser conservative.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_storage_inventory.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add launchpad/storage_inventory.py tests/test_storage_inventory.py
git commit -m "Add Storage Inventory parsers, formatters, and issue aggregation."
```

---

### Task 2: Excel export (Inventory + Issues Summary)

**Files:**
- Modify: `launchpad/storage_inventory.py`
- Modify: `tests/test_storage_inventory.py`

**Interfaces:**
- Produces:
  - `export_storage_inventory_xlsx(rows: list[dict], *, generated_at: str | None = None) -> bytes`
  - Sheet **Inventory**: meta line `Generated: … | Total Devices: N | Devices with Issues: M`; header row with Word-aligned labels; one data row per device; red fill `PatternFill(start_color="FFCDD2", end_color="FFCDD2", fill_type="solid")` when `row_has_issues`
  - Sheet **Issues Summary**: only issue rows; columns Site, Host, IP Address, Model, Serial Number (SN), Issues / Notes

- [ ] **Step 1: Write the failing tests**

```python
from io import BytesIO
from openpyxl import load_workbook
from launchpad.storage_inventory import export_storage_inventory_xlsx


def test_export_xlsx_sheets_meta_and_red_issue_row():
    rows = [
        {
            "site": "SiteA",
            "host": "array1",
            "ip": "10.0.0.1",
            "model": "IBM FlashSystem 7200",
            "serial": "ABC",
            "location": "SiteA",
            "phone_home": "Yes — IBM",
            "data_protection": "Yes",
            "smtp": "10.1.1.1",
            "issues": "",
        },
        {
            "site": "SiteB",
            "host": "array2",
            "ip": "10.0.0.2",
            "model": "IBM FlashSystem 7200",
            "serial": "DEF",
            "location": "SiteB",
            "phone_home": "No — Not configured",
            "data_protection": "No — Not configured",
            "smtp": "No IP — Not configured",
            "issues": "Phone Home not configured; SMTP not configured",
        },
    ]
    wb = load_workbook(BytesIO(export_storage_inventory_xlsx(rows, generated_at="2026-08-10T12:00:00")))
    assert wb.sheetnames == ["Inventory", "Issues Summary"]
    inv = wb["Inventory"]
    assert "Total Devices: 2" in str(inv["A1"].value)
    assert "Devices with Issues: 1" in str(inv["A1"].value)
    # Find issue data row by host array2 and assert red-ish fill
    found = False
    for row in inv.iter_rows(min_row=2, max_row=inv.max_row):
        vals = [c.value for c in row]
        if "array2" in vals:
            found = True
            assert row[0].fill.fgColor.rgb in ("00FFCDD2", "FFCDD2")
    assert found
    summary = wb["Issues Summary"]
    assert summary.max_row == 2  # header + one issue
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_storage_inventory.py::test_export_xlsx_sheets_meta_and_red_issue_row -v`  
Expected: FAIL (`export_storage_inventory_xlsx` missing)

- [ ] **Step 3: Implement Excel builder**

Use openpyxl `Workbook`. Inventory column headers (row 2):

`Site | Host | IP Address | Model | Serial Number (SN) | Location | Phone Home | Data Protection | SMTP IP(s) | Issues / Notes`

Map from row keys `site, host, ip, model, serial, location, phone_home, data_protection, smtp, issues`.

Issues Summary headers: `Site | Host | IP Address | Model | Serial Number (SN) | Issues / Notes`.

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_storage_inventory.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add launchpad/storage_inventory.py tests/test_storage_inventory.py
git commit -m "Add Storage Inventory Excel export with red issue rows."
```

---

### Task 3: Storage Inventory HTML page

**Files:**
- Create: `launchpad/storage_inventory_page.py`
- Create: `tests/test_storage_inventory_page.py`

**Interfaces:**
- Produces:
  - `STORAGE_INVENTORY_PATH = "/storage-inventory"`
  - `STORAGE_INVENTORY_HTML` — dark theme page (same CSS tokens as System Connectivity: `--bg #0b0f14`, accent orange)

- [ ] **Step 1: Write the failing tests**

```python
from launchpad.storage_inventory_page import STORAGE_INVENTORY_HTML, STORAGE_INVENTORY_PATH


def test_storage_inventory_page_markers():
    assert STORAGE_INVENTORY_PATH == "/storage-inventory"
    html = STORAGE_INVENTORY_HTML
    assert "Storage Inventory" in html
    assert 'id="site-filter"' in html or 'id="siteFilter"' in html
    assert "Refresh live" in html
    assert "Export Excel" in html
    assert "/api/storage-inventory/live" in html
    assert "/api/storage-inventory/export" in html
    assert "Total Devices" in html
    assert "Devices with Issues" in html
    assert "Issues Summary" in html
    assert "{{APP_VERSION}}" in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_storage_inventory_page.py -v`  
Expected: FAIL

- [ ] **Step 3: Implement page**

Page behavior (JS):

1. On load: `GET /api/storage-inventory/cache` → render rows if present (no unlock).
2. **Refresh live** → `GET /api/storage-inventory/live` (optional future `?card_id=`; v1 estate-wide) → on success replace table + update cache display.
3. **Export Excel** → `GET /api/storage-inventory/export?format=xlsx&open=1` (uses server cache; works when unlocked or not if cache exists).
4. Site filter: `<select id="siteFilter">` with empty value labeled `None` (all sites); filter table client-side by `row.site`.
5. Table columns match Excel inventory headers; issue rows use CSS class `row-issue` (light red).
6. Summary: Total Devices, Devices with Issues; Issues Summary table below.
7. Nav: Home `/`, System Connectivity, Hosts & Volumes.

Keep HTML in one triple-quoted string like `SYSTEM_CONNECTIVITY_HTML`. Inside the Python string, JS newline escapes must be written as `\\n` (not a raw newline inside quotes).

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_storage_inventory_page.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add launchpad/storage_inventory_page.py tests/test_storage_inventory_page.py
git commit -m "Add Storage Inventory report page HTML."
```

---

### Task 4: HealthServer scan, cache, routes

**Files:**
- Modify: `launchpad/health_server.py` (imports, path handlers, scan/cache/export/open methods)
- Create: `tests/test_storage_inventory_api.py`

**Interfaces:**
- Produces on `HealthServer`:
  - `_storage_inventory_cache: dict | None`
  - `scan_storage_inventory_live(*, card_id: int | None = None) -> dict` — unlock required; returns `{"rows": [...], "generated_at": iso, "errors": [...], "total_devices": N, "devices_with_issues": M}`
  - `get_storage_inventory_cache() -> dict | None`
  - `set_storage_inventory_cache(payload: dict) -> None`
  - `export_storage_inventory_bytes() -> tuple[bytes, str, str]` — `(body, filename, content_type)` from cache; raise if empty
  - `open_storage_inventory() -> str` — ensure running + webbrowser open
  - `storage_inventory_url` property → `http://127.0.0.1:{port}/storage-inventory`
- HTTP:
  - `GET /storage-inventory` → HTML with `APP_VERSION`
  - `GET /api/storage-inventory/cache` → JSON cache or `{"rows":[], ...}`
  - `GET /api/storage-inventory/live` → unlock gate then scan (optional `?card_id=`)
  - `GET /api/storage-inventory/export?format=xlsx` → xlsx bytes; `open=1` optional same as SysConn

**Scan per eligible card:**

1. Resolve `inventory_commands_for_profile(profile)`.
2. For each non-empty command list, run via existing SSH helper used by SysConn (`_snap_run_command` / card runner — **same helper SysConn SVC/HPE paths use**).
3. Parse with Task 1 parsers + SysConn call_home/dns/ntp parsers.
4. For empty command topics: configured=`n/a` (HPE call_home/smtp, DS smtp/data_protection).
5. Load `health_issues` from the card’s last analysis if present on `HealthCard` / cached card dict (`card` object or `list_cards` payload — use whatever SysConn/health already exposes for that card id; if missing, `[]`).
6. `build_inventory_row(...)`; on total card failure still append row with card name/host/ip and `extra_errors=[str(exc)]`.
7. Store cache; return payload.

- [ ] **Step 1: Write the failing API tests**

```python
from io import BytesIO

from openpyxl import load_workbook

from launchpad.health_server import HealthCard, HealthServer
from launchpad.storage_inventory_page import STORAGE_INVENTORY_PATH


def _unlock(server: HealthServer) -> None:
    server.set_settings_backend(lambda _key, default: default, lambda _key, _value: None)


def test_storage_inventory_page_route_constant():
    assert STORAGE_INVENTORY_PATH == "/storage-inventory"


def test_scan_storage_inventory_requires_unlock(monkeypatch):
    server = HealthServer()
    monkeypatch.setattr(server, "is_unlocked", lambda: False)
    try:
        server.scan_storage_inventory_live()
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "unlock" in str(exc).lower()


def test_scan_storage_inventory_svc_happy_path(monkeypatch):
    server = HealthServer()
    _unlock(server)
    card = HealthCard(
        card_id=1,
        name="Hartford",
        host="10.0.0.1",
        port=22,
        username="u",
        key_path="/tmp/key",
        device_profile="flashsystem_7200",
    )
    server._cards[1] = card
    server.set_monitor_enabled(card_id=1, enabled=True)
    monkeypatch.setattr(server, "sync_from_app", lambda: 0)

    def _runner(_card):
        def run(command):
            if "lscloudcallhome" in command:
                return "id:status\n0:enabled\n"
            if "lsdnsserver" in command:
                return "id:name:IP_address\n0:dns1:10.1.1.1\n"
            if "lsemailserver" in command:
                return "id:name:IP_address:port\n0:smtp1:172.29.62.98:25\n"
            if "lsrcrelationship" in command:
                return "id:name:master_cluster_id\n0:rel1:1\n"
            if "lssystem" in command:
                return (
                    "id:78E37V9\nname:v7kcon-g3v1\n"
                    "product_name:IBM FlashSystem 7200\n"
                    "cluster_ntp_IP_address:10.3.3.3\n"
                )
            return ""

        return run

    monkeypatch.setattr(server, "_lun_run_command", _runner)
    result = server.scan_storage_inventory_live()
    assert result["errors"] == []
    assert len(result["rows"]) == 1
    row = result["rows"][0]
    assert row["ip"] == "10.0.0.1"
    assert "7200" in row["model"]
    assert row["serial"] == "78E37V9"
    assert "172.29.62.98" in row["smtp"]
    assert row["data_protection"].lower().startswith("yes")
    cached = server.get_storage_inventory_cache()
    assert cached is not None
    assert len(cached["rows"]) == 1


def test_export_storage_inventory_uses_cache_without_unlock(monkeypatch):
    server = HealthServer()
    monkeypatch.setattr(server, "is_unlocked", lambda: False)
    server.set_storage_inventory_cache(
        {
            "generated_at": "2026-08-10T12:00:00",
            "rows": [
                {
                    "site": "Hartford",
                    "host": "Hartford",
                    "ip": "10.0.0.1",
                    "model": "IBM FlashSystem 7200",
                    "serial": "ABC",
                    "location": "Hartford",
                    "phone_home": "Yes — IBM",
                    "data_protection": "Yes",
                    "smtp": "172.29.62.98",
                    "issues": "",
                },
                {
                    "site": "Bad",
                    "host": "Bad",
                    "ip": "10.0.0.2",
                    "model": "IBM FlashSystem 7200",
                    "serial": "DEF",
                    "location": "Bad",
                    "phone_home": "No — Not configured",
                    "data_protection": "No — Not configured",
                    "smtp": "No IP — Not configured",
                    "issues": "Phone Home not configured",
                },
            ],
            "errors": [],
            "total_devices": 2,
            "devices_with_issues": 1,
        }
    )
    body, filename, content_type = server.export_storage_inventory_bytes()
    assert filename.endswith(".xlsx")
    assert "sheet" in content_type or "spreadsheet" in content_type or "octet" in content_type
    wb = load_workbook(BytesIO(body))
    assert wb.sheetnames == ["Inventory", "Issues Summary"]
```

Also add `set_storage_inventory_cache` alongside `get_storage_inventory_cache` (same pattern as System Connectivity cache setters).

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_storage_inventory_api.py -v`  
Expected: FAIL (methods / routes missing)

- [ ] **Step 3: Implement HealthServer wiring**

- Import `STORAGE_INVENTORY_HTML`, `STORAGE_INVENTORY_PATH`, and inventory helpers.
- Add path branches next to System Connectivity handlers.
- Implement scan using profile branches (SVC / HPE / DS) parallel to `_scan_system_connectivity_*` but producing **one inventory row** per card (not topic lists).
- Filename e.g. `LaunchPad_Storage_Inventory.xlsx`.

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_storage_inventory_api.py tests/test_storage_inventory.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add launchpad/health_server.py tests/test_storage_inventory_api.py
git commit -m "Wire Storage Inventory live scan, cache, and export APIs."
```

---

### Task 5: Dashboard button + version 1.6.147

**Files:**
- Modify: `launchpad/ui/dashboard_view.py` — tool button after System Connectivity; `_open_storage_inventory` mirroring `_open_system_connectivity`
- Modify: `launchpad/config.py` — `APP_VERSION = "1.6.147"`
- Modify: `tests/test_system_connectivity_version.py` — assert `1.6.147`
- Modify: `tests/test_hadoop_sudo_wire.py` — assert `1.6.147`
- Modify: `tests/test_storage_inventory_page.py` — optional assert dashboard open method exists via importlib source check **or** add `tests/test_storage_inventory_dashboard.py` that greps/imports dashboard for `"Storage Inventory"` and `_open_storage_inventory`

**Interfaces:**
- Produces: Dashboard tool **Storage Inventory** → `get_health_server().open_storage_inventory()`

- [ ] **Step 1: Write / update failing version + dashboard tests**

```python
# tests/test_storage_inventory_dashboard.py
from pathlib import Path

def test_dashboard_has_storage_inventory_button():
    text = Path("launchpad/ui/dashboard_view.py").read_text(encoding="utf-8")
    assert '("Storage Inventory"' in text or "(\"Storage Inventory\"" in text
    assert "_open_storage_inventory" in text
```

Update version pins to `1.6.147`.

- [ ] **Step 2: Run tests to verify version pins fail**

Run: `python -m pytest tests/test_storage_inventory_dashboard.py tests/test_system_connectivity_version.py tests/test_hadoop_sudo_wire.py -v`  
Expected: FAIL on version and/or missing button

- [ ] **Step 3: Implement button + version bump**

In `dashboard_view.py` tool_specs, insert after System Connectivity:

```python
("Storage Inventory", self._open_storage_inventory, None),
```

Add method mirroring `_open_system_connectivity` calling `server.open_storage_inventory()` with status text `Opening Storage Inventory…`.

Set `APP_VERSION = "1.6.147"`.

- [ ] **Step 4: Run full storage inventory + version suite**

Run: `python -m pytest tests/test_storage_inventory.py tests/test_storage_inventory_page.py tests/test_storage_inventory_api.py tests/test_storage_inventory_dashboard.py tests/test_system_connectivity_version.py tests/test_hadoop_sudo_wire.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add launchpad/ui/dashboard_view.py launchpad/config.py tests/test_system_connectivity_version.py tests/test_hadoop_sudo_wire.py tests/test_storage_inventory_dashboard.py
git commit -m "Add Storage Inventory dashboard button and bump to 1.6.147."
```

---

## Spec coverage checklist

| Spec requirement | Task |
|------------------|------|
| Dedicated `/storage-inventory` page | 3, 4 |
| Connection Dashboard button | 5 |
| Site filter None=all, Refresh live, Export Excel | 3, 4 |
| Monitor-on SSH SysConn platforms | 1, 4 |
| Columns Word-aligned | 1, 2, 3 |
| Phone Home reuse SysConn | 1, 4 |
| New SMTP + Data Protection collectors | 1, 4 |
| DNS/NTP into Issues only | 1 |
| Health Active Issues merge | 1, 4 |
| Red rows iff Issues non-empty | 1, 2, 3 |
| Totals + Issues Summary | 1, 2, 3 |
| Excel Inventory + Issues Summary | 2 |
| Cache view/export without unlock | 4 |
| Per-card error still emits row | 4 |
| APP_VERSION 1.6.147 | 5 |
| No CSV / no config mutations | (non-goal — not implemented) |

## Self-review notes

- No TBD placeholders; CLI strings locked in plan table.
- `build_inventory_row` / export / scan interfaces consistent across tasks.
- Exact Excel fill color asserted as `FFCDD2` / `00FFCDD2` (openpyxl may prefix alpha).
- Task 4 API tests are fully specified (SysConn-style `_lun_run_command` / unlock fixtures).
