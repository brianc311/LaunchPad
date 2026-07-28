# System Connectivity Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a dedicated System Connectivity report page that live-scans Call Home, DNS, SNMP, and NTP on monitor-on FlashSystem, HPE, and DS8884 cards, with Excel/CSV export and Site filter.

**Architecture:** Mirror Hosts & Volumes: pure helpers + parsers in `system_connectivity.py`, HTML/JS page, openpyxl/CSV ZIP export, HealthServer live scan + cache + routes, Dashboard opener + Health link. Platform adapters normalize to a shared row shape with Configured `yes|no|unknown|n/a`.

**Tech Stack:** Python HealthServer, Paramiko SSH (`_lun_run_command` / `run_ssh_auth_hpe_commands` / `run_ssh_commands`), openpyxl, pytest.

**Spec:** `docs/superpowers/specs/2026-07-28-system-connectivity-design.md`

## Global Constraints

- **Worktree:** `.worktrees/system-connectivity` on `feature/system-connectivity` from `feature/contingency-groups` tip (include design doc commit if not yet on tip)
- Path `/system-connectivity`; title **System Connectivity**; four tabs Call Home | DNS | SNMP | NTP
- Eligibility: SSH + monitor-on + `SVC_PROFILES` ∪ `HPE_SHELL_PROFILES` ∪ `{ibm_ds8884}`
- Read-only; never export SNMP communities/passwords/secrets
- HPE Call Home → always `configured=n/a` (SP/SPOCC); DS Call Home/NTP/SNMP best-effort then `n/a`/`unknown`
- Excel sheets: `Call Home`, `DNS`, `SNMP`, `NTP`; CSV ZIP: `call_home.csv`, `dns.csv`, `snmp.csv`, `ntp.csv`
- Bump `APP_VERSION` to **1.6.70**
- Commit at each task’s commit step
- Run from: `cd C:\Users\BrianColley\LaunchPad\.worktrees\system-connectivity`

---

## File map

| File | Responsibility |
|------|----------------|
| `launchpad/system_connectivity.py` | Eligibility, row builder, platform parsers, Configured rules |
| `launchpad/system_connectivity_page.py` | HTML/JS page constant + path |
| `launchpad/system_connectivity_export.py` | Excel + CSV ZIP + Site/`card_id` filter |
| `launchpad/health_server.py` | Live scan, cache, GET page + live + export APIs, Health nav link |
| `launchpad/ui/dashboard_view.py` | Dashboard button + opener |
| `launchpad/config.py` | `1.6.70` |
| Peer report pages (optional) | Link to `/system-connectivity` where Hosts & Volumes is linked |
| Tests | Unit parsers, export, page chrome, API unlock/scan, nav |

---

### Task 0: Confirm baseline

**Files:** none (worktree + ensure design on branch)

- [ ] **Step 1: Create worktree**

```powershell
cd C:\Users\BrianColley\LaunchPad
git fetch origin
git worktree add .worktrees/system-connectivity -b feature/system-connectivity feature/contingency-groups
cd .worktrees/system-connectivity
python -c "from launchpad.config import APP_VERSION; print(APP_VERSION)"
Test-Path docs\superpowers\specs\2026-07-28-system-connectivity-design.md
```

Expected: `1.6.69` (or tip), spec `True`. If spec missing, copy/commit from main workspace first.

- [ ] **Step 2: No feature commit**

---

### Task 1: Core helpers + parsers (TDD)

**Files:**
- Create: `launchpad/system_connectivity.py`
- Create: `tests/test_system_connectivity.py`

**Interfaces:**
- Produces:
  - `TOPICS: tuple[str, ...] = ("call_home", "dns", "snmp", "ntp")`
  - `ROW_FIELDS: tuple[str, ...] = ("site", "card_name", "host", "vendor", "profile", "configured", "status", "details", "error")` — `site` may be card name if no separate site field; use `card_name` for Site column display when LaunchPad cards are site-named (same as Hosts & Volumes Site dropdown = card name)
  - `is_system_connectivity_eligible(card: dict, *, monitor_on: bool) -> bool`
  - `base_row(*, card_name, host, vendor, profile, card_id: int | None = None, site: str = "") -> dict` — fills identity fields; empty topic fields
  - `finalize_row(row: dict, *, configured: str, status: str = "", details: str = "", error: str = "") -> dict`
  - `parse_svc_call_home(output: str) -> tuple[str, str, str]` → `(configured, status, details)`
  - `parse_svc_dns(output: str) -> tuple[str, str, str]`
  - `parse_svc_snmp(output: str) -> tuple[str, str, str]` — never put community/password in details
  - `parse_svc_ntp_from_lssystem(output: str) -> tuple[str, str, str]` — read `cluster_ntp_IP_address`
  - `parse_hpe_shownet_dns_ntp(output: str) -> dict` with keys `dns` and `ntp` each `(configured, status, details)`
  - `parse_hpe_snmpmgr(output: str) -> tuple[str, str, str]`
  - `hpe_call_home_na_row() -> tuple[str, str, str]` → `("n/a", "n/a", "Call Home is on the Service Processor (not collected via array SSH)")`
  - `parse_ds_networkport_dns(output: str) -> tuple[str, str, str]`
  - `parse_ds_showsp_call_home(output: str) -> tuple[str, str, str]` — if empty/unrecognized → `("n/a", "n/a", "Call Home not available via DSCLI on this path (often HMC)")`
  - `topic_commands_for_profile(profile: str) -> dict[str, list[str]]` — map topic → remote command list for that family (SVC / HPE / DS); HPE call_home → `[]`

**Configured rules:** `yes` if usable setting present; `no` if command ok and empty/off; `unknown` on empty/garbage when expected data; parsers that receive successful empty tables return `no`.

- [ ] **Step 1: Write failing tests**

```python
from launchpad.system_connectivity import (
    hpe_call_home_na_row,
    is_system_connectivity_eligible,
    parse_hpe_shownet_dns_ntp,
    parse_svc_call_home,
    parse_svc_dns,
    parse_svc_ntp_from_lssystem,
    parse_svc_snmp,
    parse_ds_networkport_dns,
)


def test_eligible_monitor_on_svc_hpe_ds():
    assert is_system_connectivity_eligible(
        {"card_type": "ssh", "device_profile": "flashsystem_7200"}, monitor_on=True
    )
    assert is_system_connectivity_eligible(
        {"card_type": "ssh", "device_profile": "hpe_primera_600"}, monitor_on=True
    )
    assert is_system_connectivity_eligible(
        {"card_type": "ssh", "device_profile": "ibm_ds8884"}, monitor_on=True
    )
    assert not is_system_connectivity_eligible(
        {"card_type": "ssh", "device_profile": "flashsystem_7200"}, monitor_on=False
    )


def test_parse_svc_call_home_enabled():
    out = "id:status:error_sequence_number\n0:enabled:0\n"
    configured, status, details = parse_svc_call_home(out)
    assert configured == "yes"
    assert "enabled" in status.lower() or "enabled" in details.lower()


def test_parse_svc_dns_yes_and_no():
    yes_out = "id:name:IP_address\n0:dns1:10.1.1.1\n"
    assert parse_svc_dns(yes_out)[0] == "yes"
    no_out = "id:name:IP_address\n"
    assert parse_svc_dns(no_out)[0] == "no"


def test_parse_svc_snmp_strips_secrets():
    out = "id:IP:port:community\n0:10.2.2.2:162:public\n"
    configured, status, details = parse_svc_snmp(out)
    assert configured == "yes"
    assert "public" not in details.lower()
    assert "10.2.2.2" in details


def test_parse_svc_ntp():
    out = "id:name\ncluster_ntp_IP_address:10.3.3.3\n"
    # Also accept key:value lssystem style lines mixed with colon tables
    kv = "name:cluster1\ncluster_ntp_IP_address:10.3.3.3\n"
    assert parse_svc_ntp_from_lssystem(kv)[0] == "yes"
    empty = "name:cluster1\ncluster_ntp_IP_address:\n"
    assert parse_svc_ntp_from_lssystem(empty)[0] == "no"


def test_parse_hpe_shownet():
    out = """
IP Address    Netmask/PrefixLen Nodes Active Speed Duplex AutoNeg Status
10.1.1.10     255.255.255.0      01      1  1000 Full   Yes     Active
Default route :   10.1.1.1
NTP server    :   10.5.5.5
DNS server    :   10.6.6.6
"""
    parsed = parse_hpe_shownet_dns_ntp(out)
    assert parsed["dns"][0] == "yes"
    assert "10.6.6.6" in parsed["dns"][2]
    assert parsed["ntp"][0] == "yes"
    assert "10.5.5.5" in parsed["ntp"][2]


def test_hpe_call_home_na():
    assert hpe_call_home_na_row()[0] == "n/a"


def test_parse_ds_dns():
    out = (
        "ID IP address Subnet Mask Gateway Primary DNS Secondary DNS State\n"
        "I9814 10.0.1.2 255.255.255.0 10.0.1.1 9.0.0.10 9.0.0.11 Online\n"
    )
    configured, status, details = parse_ds_networkport_dns(out)
    assert configured == "yes"
    assert "9.0.0.10" in details
```

- [ ] **Step 2: Run — expect FAIL**

```powershell
python -m pytest tests/test_system_connectivity.py -v
```

Expected: import errors / missing functions.

- [ ] **Step 3: Implement `launchpad/system_connectivity.py`**

Reuse `_parse_colon_table` from `flashsystem_parse` for SVC delimited tables. For `lssystem` NTP, scan lines for `cluster_ntp_IP_address` (split on first `:`). For HPE `shownet`, regex/line parse `DNS server` / `NTP server` labels. For DS `lsnetworkport`, parse header row for Primary/Secondary DNS columns. Import `HPE_SHELL_PROFILES`, `SVC_PROFILES` (or `is_svc_fc_profile`), and treat `ibm_ds8884` explicitly. Use `vendor_for_profile` from `volume_find` but map DS to `"ibm"`.

`topic_commands_for_profile` examples:

```python
# SVC
{"call_home": ["lscloudcallhome -delim :"],
 "dns": ["lsdnsserver -delim :"],
 "snmp": ["lssnmpserver -delim :"],
 "ntp": ["lssystem -delim :"]}
# HPE
{"call_home": [], "dns": ["shownet"], "snmp": ["showsnmpmgr"], "ntp": ["shownet"]}
# DS
{"call_home": ["dscli showsp"],  # best-effort; parser may return n/a
 "dns": ["dscli lsnetworkport"],
 "snmp": [],  # n/a or unknown unless a safe show command is confirmed in implementation
 "ntp": []}
```

If DS SNMP/NTP commands stay empty, scan layer sets `n/a` with clear details (do not invent CLI).

- [ ] **Step 4: Tests PASS**

```powershell
python -m pytest tests/test_system_connectivity.py -v
```

- [ ] **Step 5: Commit**

```powershell
git add launchpad/system_connectivity.py tests/test_system_connectivity.py
git commit -m "Add System Connectivity parsers and eligibility for Call Home, DNS, SNMP, NTP."
```

---

### Task 2: Export Excel + CSV ZIP (TDD)

**Files:**
- Create: `launchpad/system_connectivity_export.py`
- Create: `tests/test_system_connectivity_export.py`

**Interfaces:**
- `TOPIC_SHEETS: dict[str, str] = {"call_home": "Call Home", "dns": "DNS", "snmp": "SNMP", "ntp": "NTP"}`
- `TOPIC_CSV_NAMES: dict[str, str] = {"call_home": "call_home.csv", ...}`
- `HEADERS: tuple[str, ...] = ("Site", "Card", "Host", "Vendor", "Profile", "Configured", "Status", "Details", "Error")`
- `_FIELDS: tuple[str, ...] = ("site", "card_name", "host", "vendor", "profile", "configured", "status", "details", "error")`
- `filter_payload_by_card_id(payload, *, card_id=None, card_name=None) -> dict` — filter each of `call_home`/`dns`/`snmp`/`ntp` (+ pass through `errors` filtered similarly)
- `export_system_connectivity_xlsx(payload) -> bytes`
- `export_system_connectivity_csv_zip(payload) -> bytes`

Mirror styling helpers from `host_volume_health_export.py` (copy `_write_sheet` pattern locally — do not create a shared framework in v1).

- [ ] **Step 1: Failing tests**

```python
from io import BytesIO
import zipfile
from openpyxl import load_workbook
from launchpad.system_connectivity_export import (
    export_system_connectivity_csv_zip,
    export_system_connectivity_xlsx,
    filter_payload_by_card_id,
)


def _sample():
    row_a = {
        "card_id": 1, "site": "Hartford", "card_name": "Hartford", "host": "10.0.0.1",
        "vendor": "ibm", "profile": "flashsystem_7200", "configured": "yes",
        "status": "enabled", "details": "10.1.1.1", "error": "",
    }
    row_b = {**row_a, "card_id": 2, "site": "Primera", "card_name": "Primera", "host": "10.0.0.2", "vendor": "hpe"}
    return {
        "call_home": [row_a, row_b],
        "dns": [row_a],
        "snmp": [],
        "ntp": [row_a],
        "errors": [],
    }


def test_filter_by_card_id():
    scoped = filter_payload_by_card_id(_sample(), card_id=1)
    assert len(scoped["call_home"]) == 1
    assert scoped["call_home"][0]["card_name"] == "Hartford"


def test_xlsx_four_sheets():
    body = export_system_connectivity_xlsx(_sample())
    wb = load_workbook(BytesIO(body))
    assert wb.sheetnames == ["Call Home", "DNS", "SNMP", "NTP"]


def test_csv_zip_members():
    body = export_system_connectivity_csv_zip(_sample())
    with zipfile.ZipFile(BytesIO(body)) as zf:
        names = set(zf.namelist())
    assert names == {"call_home.csv", "dns.csv", "snmp.csv", "ntp.csv"}
```

- [ ] **Step 2: Run — expect FAIL**

```powershell
python -m pytest tests/test_system_connectivity_export.py -v
```

- [ ] **Step 3: Implement export module**

- [ ] **Step 4: Tests PASS**

- [ ] **Step 5: Commit**

```powershell
git add launchpad/system_connectivity_export.py tests/test_system_connectivity_export.py
git commit -m "Add System Connectivity Excel and CSV ZIP export."
```

---

### Task 3: Page HTML/JS chrome (TDD)

**Files:**
- Create: `launchpad/system_connectivity_page.py`
- Create: `tests/test_system_connectivity_page.py`

**Interfaces:**
- `SYSTEM_CONNECTIVITY_PATH = "/system-connectivity"`
- `SYSTEM_CONNECTIVITY_HTML` — template string with `{{APP_VERSION}}` placeholder (same as Hosts & Volumes)

**UI requirements:**
- Hero title System Connectivity; blurb mentioning FlashSystem, HPE, DS8884
- Site select `id="sc-site-select"` with None option
- Buttons: `sc-refresh-btn`, `sc-export-xlsx-btn`, `sc-export-csv-btn` (exports disabled until successful refresh)
- Nav links: Health `/`, Capacity, Hosts & Volumes, Volume Find, FlashCopy CGs
- Tab buttons `data-tab="call_home|dns|snmp|ntp"` and four table bodies `sc-call_home-body` etc.
- Columns: Site, Card, Host, Vendor, Profile, Configured, Status, Details, Error
- Call Home hint paragraph about HPE SP / DS HMC
- JS: `loadSiteOptions` via `/api/cards`; Refresh → `/api/system-connectivity/live?card_id=`; Export → `/api/system-connectivity/export?format=xlsx|csv&open=1` (+ card_id); tab switching shows one section

Base structure on `host_volume_health_page.py` (copy dark theme CSS; replace two sections with tabbed four tables).

- [ ] **Step 1: Failing page contract test**

```python
from launchpad.system_connectivity_page import (
    SYSTEM_CONNECTIVITY_HTML,
    SYSTEM_CONNECTIVITY_PATH,
)


def test_system_connectivity_path_and_controls():
    assert SYSTEM_CONNECTIVITY_PATH == "/system-connectivity"
    for text in (
        "System Connectivity",
        'id="sc-site-select"',
        '<option value="">None</option>',
        'id="sc-refresh-btn"',
        'id="sc-export-xlsx-btn"',
        'id="sc-export-csv-btn"',
        "/api/system-connectivity/live",
        "/api/system-connectivity/export",
        'id="sc-call_home-body"',
        'id="sc-dns-body"',
        'id="sc-snmp-body"',
        'id="sc-ntp-body"',
        "Service Processor",
        "{{APP_VERSION}}",
        'href="/host-volume-health"',
    ):
        assert text in SYSTEM_CONNECTIVITY_HTML
```

- [ ] **Step 2: Run — expect FAIL**

```powershell
python -m pytest tests/test_system_connectivity_page.py -v
```

- [ ] **Step 3: Implement page module** (full HTML+JS; keep JS self-contained like Hosts & Volumes)

- [ ] **Step 4: Tests PASS**

- [ ] **Step 5: Commit**

```powershell
git add launchpad/system_connectivity_page.py tests/test_system_connectivity_page.py
git commit -m "Add System Connectivity report page chrome with four topic tabs."
```

---

### Task 4: HealthServer live scan + APIs (TDD)

**Files:**
- Modify: `launchpad/health_server.py`
- Create: `tests/test_system_connectivity_api.py`

**Interfaces:**
- `HealthServer._system_connectivity_cache: dict | None`
- `scan_system_connectivity_live(*, card_id: int | None = None) -> dict`
  - Unlock required (`RuntimeError` with “unlock”)
  - For each eligible card (optional `card_id` filter): run topic commands for profile family
  - SVC: `_lun_run_command(card)` for each topic command
  - HPE: `run_ssh_auth_hpe_commands(..., ["shownet", "showsnmpmgr"], ...)` once; parse DNS/NTP from shownet; SNMP from showsnmpmgr; Call Home = `hpe_call_home_na_row()`
  - DS: `_lun_run_command` or `run_ssh_commands` with `dscli ...` strings from `topic_commands_for_profile`
  - Build four lists of rows via `base_row` + `finalize_row`; on exception append to `errors` and still emit topic rows with `configured=unknown` and Error set when practical
  - Sort each topic list by `(card_name.lower(),)`
  - Cache and return `{"call_home": [...], "dns": [...], "snmp": [...], "ntp": [...], "errors": [...]}`
- `get_system_connectivity_cache` / `set_system_connectivity_cache`
- `export_system_connectivity_bytes(*, export_format, card_id=None) -> (bytes, filename, content_type)`
- Handler:
  - `GET SYSTEM_CONNECTIVITY_PATH` → HTML with `APP_VERSION` substituted
  - `GET /api/system-connectivity/live` → unlock check → JSON (same pattern as host-volume-health live)
  - `GET /api/system-connectivity/export` → format + card_id + optional open=1
- `system_connectivity_url` / `open_system_connectivity` (webbrowser) mirroring Hosts & Volumes

- [ ] **Step 1: API tests**

```python
from launchpad.health_server import HealthCard, HealthServer
from launchpad.system_connectivity_page import SYSTEM_CONNECTIVITY_PATH


def _unlock(server: HealthServer) -> None:
    server.set_settings_backend(lambda _key, default: default, lambda _key, _value: None)


def test_live_requires_unlock(monkeypatch):
    server = HealthServer()
    monkeypatch.setattr(server, "is_unlocked", lambda: False)
    try:
        server.scan_system_connectivity_live()
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "unlock" in str(exc).lower()


def test_live_svc_happy_path(monkeypatch):
    server = HealthServer()
    _unlock(server)
    card = HealthCard(
        card_id=1, name="Hartford", host="10.0.0.1", port=22, username="u",
        key_path="/tmp/key", device_profile="flashsystem_7200",
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
            if "lssnmpserver" in command:
                return "id:IP:port\n0:10.2.2.2:162\n"
            if "lssystem" in command:
                return "name:c1\ncluster_ntp_IP_address:10.3.3.3\n"
            return ""
        return run

    monkeypatch.setattr(server, "_lun_run_command", _runner)
    result = server.scan_system_connectivity_live()
    assert result["errors"] == []
    assert result["dns"][0]["configured"] == "yes"
    assert result["ntp"][0]["configured"] == "yes"
    assert result["call_home"][0]["configured"] == "yes"


def test_page_route_constant():
    assert SYSTEM_CONNECTIVITY_PATH == "/system-connectivity"
```

Also test HPE Call Home `n/a` when scanning an HPE card (monkeypatch `run_ssh_auth_hpe_commands`).

- [ ] **Step 2: Run — expect FAIL**

```powershell
python -m pytest tests/test_system_connectivity_api.py -v
```

- [ ] **Step 3: Implement HealthServer methods + handler branches**

Follow `scan_host_volume_health_live` / export / `do_GET` patterns at ~1959, ~2188, ~4057. Import page/export/helpers at top of `health_server.py` like Hosts & Volumes.

- [ ] **Step 4: Tests PASS**

```powershell
python -m pytest tests/test_system_connectivity_api.py tests/test_system_connectivity.py -q
```

- [ ] **Step 5: Commit**

```powershell
git add launchpad/health_server.py tests/test_system_connectivity_api.py
git commit -m "Wire System Connectivity live scan, cache, and export APIs."
```

---

### Task 5: Dashboard + Health nav

**Files:**
- Modify: `launchpad/ui/dashboard_view.py` — button next to Hosts & Volumes; `_open_system_connectivity` mirroring `_open_host_volume_health`
- Modify: `launchpad/health_server.py` — Health hero link beside Hosts & Volumes (`href="/system-connectivity"`)
- Optionally add peer link on `host_volume_health_page.py` / capacity / volume_find (same pattern as existing peer links)
- Create: `tests/test_system_connectivity_nav.py`

- [ ] **Step 1: Nav contract tests**

```python
from launchpad.ui import dashboard_view
from launchpad.health_server import HEALTH_HTML  # or whatever constant holds the hero HTML
# Prefer: assert "/system-connectivity" appears in health dashboard HTML string used for hero actions
# and dashboard_view source contains System Connectivity / open_system_connectivity


def test_dashboard_has_system_connectivity_opener():
    import inspect
    src = inspect.getsource(dashboard_view.DashboardView)
    assert "System Connectivity" in src
    assert "_open_system_connectivity" in src
```

If `HEALTH_HTML` is inline in `health_server.py`, grep the hero-actions block for the new link in a test that reads the string near Hosts & Volumes (same approach as `tests/test_host_volume_health_nav.py`).

- [ ] **Step 2: Implement button + Health link + `open_system_connectivity`**

- [ ] **Step 3: Tests PASS**

```powershell
python -m pytest tests/test_system_connectivity_nav.py -q
```

- [ ] **Step 4: Commit**

```powershell
git add launchpad/ui/dashboard_view.py launchpad/health_server.py tests/test_system_connectivity_nav.py
git commit -m "Add System Connectivity Dashboard button and Health link."
```

---

### Task 6: Version bump + page version substitution

**Files:**
- Modify: `launchpad/config.py` → `APP_VERSION = "1.6.70"`
- Verify page serve path substitutes `{{APP_VERSION}}` (already done in Task 4 if following Hosts & Volumes `replace`)
- Create/extend: `tests/test_system_connectivity_version.py` or assert in API/page serve test

- [ ] **Step 1: Failing version test**

```python
from launchpad.config import APP_VERSION


def test_app_version_1670():
    assert APP_VERSION == "1.6.70"
```

- [ ] **Step 2: Bump config**

- [ ] **Step 3: Full related suite PASS**

```powershell
python -m pytest tests/test_system_connectivity.py tests/test_system_connectivity_export.py tests/test_system_connectivity_page.py tests/test_system_connectivity_api.py tests/test_system_connectivity_nav.py -q
```

- [ ] **Step 4: Commit**

```powershell
git add launchpad/config.py tests/
git commit -m "Bump LaunchPad to 1.6.70 for System Connectivity report."
```

---

### Task 7: Spec self-check + PR-ready smoke

**Files:** none required (fix gaps only)

- [ ] **Step 1: Spec coverage checklist**

Confirm implemented: dedicated page, four tabs, Site None, Refresh unlock, Excel 4 sheets, CSV ZIP, monitor-on FlashSystem+HPE+DS8884, HPE Call Home `n/a`, no secrets, Dashboard + Health, version 1.6.70.

- [ ] **Step 2: Run full connectivity test suite once more**

```powershell
python -m pytest tests/test_system_connectivity*.py -v
```

- [ ] **Step 3: No commit unless fixes** — if fixes needed, commit with a focused message

---

## Spec coverage (plan self-review)

| Spec item | Task |
|-----------|------|
| `/system-connectivity` + four tabs | 3 |
| Site dropdown None=all | 3, 4 |
| Refresh live unlock | 4 |
| Monitor-on SVC/HPE/DS8884 | 1, 4 |
| Call Home / DNS / SNMP / NTP parsers | 1 |
| HPE Call Home n/a; DS gaps | 1, 4 |
| No secrets in SNMP details | 1 |
| Excel 4 sheets + CSV ZIP | 2, 4 |
| Dashboard + Health nav | 5 |
| APP_VERSION 1.6.70 | 6 |
| Read-only | all (no mutate CLIs) |

**Placeholder scan:** none intentional.  
**Type consistency:** payload keys `call_home`/`dns`/`snmp`/`ntp`/`errors`; row fields `site`/`card_name`/`host`/`vendor`/`profile`/`configured`/`status`/`details`/`error`/`card_id`.
