# System Connectivity License Key Tab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a sixth System Connectivity tab **License Key** with live HPE `showlicense` feature rows and FlashSystem encryption/date/time (best-effort key generation date), plus Excel/CSV and version **1.6.78**.

**Architecture:** Extend `TOPICS` with `license_key`. Parsers produce license-specific fields; HPE returns multiple flattened rows per card. HealthServer scan `extend`s lists for `license_key`. Page/export mirror the Firmware multi-column pattern. No Admin catalog.

**Tech Stack:** Python, HealthServer SSH scan, openpyxl/CSV ZIP, pytest.

**Spec:** `docs/superpowers/specs/2026-07-29-license-key-tab-design.md`

## Global Constraints

- **Worktree:** `.worktrees/license-key-tab` on `feature/license-key-tab` from `feature/contingency-groups` tip (include design `9244d70` or later)
- Sixth tab **License Key** after Firmware; Excel sheet `License Key`; CSV `license_key.csv`
- HPE: one row per feature; FlashSystem: one row per card; DS8884: one `n/a` row per card
- Columns: identity + Key generation date, Date, Time, Encryption licensed, Feature, Expiration + Configured/Status/Details/Error
- Read-only collectors only (`showlicense`, `lsencryption`, `svqueryclock`)
- No SCU virtualization tables; no license install/change; no per-site firmware catalogs
- Bump `APP_VERSION` to **1.6.78**
- Commit at each task’s commit step
- Run from: `cd C:\Users\BrianColley\LaunchPad\.worktrees\license-key-tab`

---

## File map

| File | Responsibility |
|------|----------------|
| `launchpad/system_connectivity.py` | `license_key` in TOPICS; parsers; `enrich_license_key_row`; topic commands |
| `launchpad/health_server.py` | Collect + flatten rows; SVC clock command exception; HPE `showlicense` |
| `launchpad/system_connectivity_page.py` | Sixth tab + panel + JS render |
| `launchpad/system_connectivity_export.py` | License Key sheet/CSV columns |
| `launchpad/config.py` | `1.6.78` |
| `tests/test_system_connectivity_license_key.py` | Parser/enrich/TOPICS tests |
| Page/export/API/version tests | Tab order, export headers, cache key, version |

---

### Task 0: Confirm baseline

**Files:** none

- [ ] **Step 1: Create worktree**

```powershell
cd C:\Users\BrianColley\LaunchPad
git worktree add .worktrees/license-key-tab -b feature/license-key-tab feature/contingency-groups
cd .worktrees\license-key-tab
python -c "from launchpad.config import APP_VERSION; print(APP_VERSION)"
Test-Path docs\superpowers\specs\2026-07-29-license-key-tab-design.md
```

Expected: tip `1.6.77` (or later), spec `True`.

- [ ] **Step 2: No feature commit**

---

### Task 1: Parsers + TOPICS + enrich (TDD)

**Files:**
- Create: `tests/test_system_connectivity_license_key.py`
- Modify: `launchpad/system_connectivity.py`

**Interfaces:**
- Produces:
  - `TOPICS` ends with `"license_key"` (after `"firmware"`)
  - `LICENSE_KEY_EXTRA_FIELDS = ("key_generation_date", "date", "time", "encryption_licensed", "feature", "expiration")`
  - `parse_hpe_showlicense(output: str) -> list[dict[str, str]]` — each dict has at least `key_generation_date`, `feature`, `expiration`, `status` (`ok` / `expired` / `trial` when detectable), `details`
  - `parse_svc_lsencryption(output: str) -> tuple[str, str, str, str]` — `(configured, status, details, encryption_licensed)` where `encryption_licensed` is `yes`/`no`/`unknown`
  - `parse_svc_svqueryclock(output: str) -> tuple[str, str]` — `(date, time)` strings; blanks if unparseable
  - `enrich_license_key_row(identity, *, configured, status, details, error="", key_generation_date="", date="", time="", encryption_licensed="", feature="", expiration="") -> dict`
  - `parse_ds_license_key() ->` n/a configured + blank extras (or constant helper)
  - `topic_commands_for_profile` includes `license_key` cmds: SVC `["lsencryption -delim :", "svqueryclock"]`; HPE `["showlicense"]`; DS `[]`

- [ ] **Step 1: Write failing tests**

```python
from launchpad.system_connectivity import (
    TOPICS,
    base_row,
    enrich_license_key_row,
    parse_hpe_showlicense,
    parse_svc_lsencryption,
    parse_svc_svqueryclock,
    topic_commands_for_profile,
)


def test_topics_include_license_key_after_firmware():
    assert TOPICS.index("firmware") < TOPICS.index("license_key")
    assert TOPICS[-1] == "license_key"


def test_parse_hpe_showlicense_features_and_key_date():
    output = """
License key was generated on Tue Sep 19 10:37:04 2017
License features currently enabled:
3PAR OS Suite
Peer Motion
  Expiration Date: Sep 24, 2017 8:00:00 PM EDT
Thin Provisioning (20480000G)
"""
    rows = parse_hpe_showlicense(output)
    assert len(rows) >= 2
    assert all(r.get("key_generation_date") for r in rows)
    names = {r["feature"] for r in rows}
    assert "3PAR OS Suite" in names or any("3PAR OS Suite" in n for n in names)
    peer = next(r for r in rows if "Peer Motion" in r["feature"])
    assert peer["expiration"]  # non-empty when dated


def test_parse_hpe_showlicense_emdash_expiration_empty_or_dash():
    output = """
License key was generated on Mon Sep 20 16:37:50 2018
License features currently enabled:
Compression
"""
    rows = parse_hpe_showlicense(output)
    assert rows
    assert rows[0]["key_generation_date"]
    # no dated expiry → empty or em-dash
    assert rows[0].get("expiration", "") in ("", "—", "-")


def test_parse_svc_lsencryption_licensed():
    output = "status:licensed\nerror_sequence_number:\n"
    configured, status, details, enc = parse_svc_lsencryption(output)
    assert configured == "yes"
    assert enc in ("yes", "licensed") or enc == "yes"
    # Prefer normalized enc == "yes" for licensed/enabled


def test_parse_svc_svqueryclock():
    date_s, time_s = parse_svc_svqueryclock("Fri Nov  5 14:53:21 CET 2021")
    assert date_s
    assert time_s


def test_enrich_license_key_row_fields():
    row = base_row(
        card_name="HPE1", host="1.2.3.4", vendor="hpe", profile="hpe_3par"
    )
    out = enrich_license_key_row(
        row,
        configured="yes",
        status="ok",
        details="3 features",
        key_generation_date="2017-09-19",
        feature="Remote Copy",
        expiration="—",
    )
    assert out["feature"] == "Remote Copy"
    assert out["key_generation_date"] == "2017-09-19"


def test_topic_commands_license_key():
    svc = topic_commands_for_profile("flashsystem_7300")
    assert "lsencryption" in " ".join(svc["license_key"])
    assert any("svqueryclock" in c for c in svc["license_key"])
    hpe = topic_commands_for_profile("hpe_3par")
    assert hpe["license_key"] == ["showlicense"]
    ds = topic_commands_for_profile("ibm_ds8884")
    assert ds["license_key"] == []
```

Adjust HPE fixture parsing expectations to match the real `showlicense` text formats you implement (CLI often prints feature names one-per-line and expirations on following lines or in a separate expired section). Prefer robust parsing over matching GUI wording exactly.

- [ ] **Step 2: Run tests — expect FAIL**

```powershell
python -m pytest tests/test_system_connectivity_license_key.py -v --tb=short
```

- [ ] **Step 3: Implement parsers + TOPICS + enrich + topic_commands**

In `system_connectivity.py`:

1. Append `"license_key"` to `TOPICS`.
2. Add `LICENSE_KEY_EXTRA_FIELDS`.
3. Implement parsers + `enrich_license_key_row` (call `finalize_row`, then set the six extra fields).
4. For `parse_svc_lsencryption`: if status/key fields indicate licensed/enabled → `encryption_licensed="yes"`; clearly not licensed → `"no"`; else `"unknown"`.
5. For `parse_hpe_showlicense`: extract generation date from `License key was generated on ...`; build feature rows; map missing expiration to `""`.
6. Update all three branches of `topic_commands_for_profile` with `license_key` command lists (and empty dict default via `TOPICS`).

Normalize `encryption_licensed` display values to `yes` / `no` / `unknown` (not raw `licensed`).

- [ ] **Step 4: Run tests — expect PASS**

```powershell
python -m pytest tests/test_system_connectivity_license_key.py -q --tb=short
```

- [ ] **Step 5: Commit**

```powershell
git add launchpad/system_connectivity.py tests/test_system_connectivity_license_key.py
git commit -m "Add License Key parsers and topic wiring for System Connectivity."
```

---

### Task 2: HealthServer live scan (multi-row HPE)

**Files:**
- Modify: `launchpad/health_server.py`
- Modify/Create: `tests/test_system_connectivity_license_key_api.py` (or extend `test_system_connectivity_firmware_api.py`)

**Interfaces:**
- Consumes: parsers + `enrich_license_key_row` + `topic_commands_for_profile` from Task 1
- Produces: live payload key `license_key: list[dict]`; HPE may contribute multiple rows per card
- Update `_system_connectivity_svc_command` so `svqueryclock` is **not** prefixed with `svcinfo`

- [ ] **Step 1: Failing API/cache test**

```python
def test_scan_payload_includes_license_key_key(monkeypatch):
    # Mirror firmware API test: mock SVC/HPE runners so scan returns license_key list
    # Assert "license_key" in payload and isinstance(payload["license_key"], list)
    ...
```

Copy structure from `tests/test_system_connectivity_firmware_api.py` / `test_system_connectivity_api.py` — keep mocks minimal.

- [ ] **Step 2: Run — expect FAIL** (missing key)

- [ ] **Step 3: Wire scan**

1. Import new parsers + `enrich_license_key_row`.
2. `_system_connectivity_svc_command`: if command is `svqueryclock` (or starts with it), return unchanged.
3. `_scan_system_connectivity_svc_card`: after firmware block, run `lsencryption` + `svqueryclock`, build one enriched license row (key_generation_date blank unless parser finds it).
4. `_scan_system_connectivity_hpe_card`: add `showlicense` to `run_ssh_auth_hpe_commands` list; parse → **list** of enriched rows; return `"license_key": list` (not a single dict).
5. `_scan_system_connectivity_ds_card`: n/a enrich row for `license_key`.
6. In `scan_system_connectivity_live` append loop: if topic is `license_key` and value is a list → `extend`; if dict → `append`.
7. Sort `license_key` rows by `(card_name, feature)`.
8. Exception fallback: handle `license_key` like firmware (enrich/n/a), not only unknown.
9. Ensure cache get/set/export payload includes `license_key` via `TOPICS` iteration where applicable.

- [ ] **Step 4: Run API + license unit tests — PASS**

```powershell
python -m pytest tests/test_system_connectivity_license_key.py tests/test_system_connectivity_license_key_api.py tests/test_system_connectivity_api.py tests/test_system_connectivity_firmware_api.py -q --tb=short
```

- [ ] **Step 5: Commit**

```powershell
git add launchpad/health_server.py tests/test_system_connectivity_license_key_api.py
git commit -m "Collect License Key rows in System Connectivity live scan."
```

---

### Task 3: Page UI tab + render

**Files:**
- Modify: `launchpad/system_connectivity_page.py`
- Modify: `tests/test_system_connectivity_page.py`

**Interfaces:**
- Produces: tab `license_key` after `firmware`; panel with columns matching spec; JS `TOPICS` includes `license_key`; colspan for license columns

- [ ] **Step 1: Failing page test**

```python
def test_page_has_license_key_tab_after_firmware():
    html = SYSTEM_CONNECTIVITY_HTML
    assert 'data-tab="license_key"' in html
    assert html.index('data-tab="firmware"') < html.index('data-tab="license_key"')
    assert 'id="sc-panel-license_key"' in html
    assert 'id="sc-license_key-body"' in html
    assert "Key generation date" in html
    assert "Encryption licensed" in html
    compact = html.replace(" ", "")
    assert compact.index('"firmware"') < compact.index('"license_key"')
```

- [ ] **Step 2: Run — FAIL**

- [ ] **Step 3: Add tab, panel, JS**

Mirror Firmware panel: hint text like “HPE shows one row per enabled feature. FlashSystem shows encryption licensed and system date/time.”

Update `TOPICS`, `TOPIC_LABELS`, `bodies`, `topicColspan`, `renderTopic` to emit the six extra cells for `license_key`.

Update hero blurb if it lists topics (“… Firmware, and License Key”).

- [ ] **Step 4: Run page tests — PASS**

```powershell
python -m pytest tests/test_system_connectivity_page.py -q --tb=short
```

- [ ] **Step 5: Commit**

```powershell
git add launchpad/system_connectivity_page.py tests/test_system_connectivity_page.py
git commit -m "Add License Key tab to System Connectivity page."
```

---

### Task 4: Excel / CSV export columns

**Files:**
- Modify: `launchpad/system_connectivity_export.py`
- Modify: `tests/test_system_connectivity_export.py`

**Interfaces:**
- Produces: `TOPIC_SHEETS["license_key"] = "License Key"`; `TOPIC_CSV_NAMES["license_key"] = "license_key.csv"`
- `LICENSE_KEY_HEADERS` / `LICENSE_KEY_FIELDS` including the six extras between Profile and Configured
- `_TOPIC_KEYS` includes `license_key`; `_topic_headers_fields` branches like firmware

- [ ] **Step 1: Failing export test**

Assert six sheets / zip members include License Key; headers include `Key generation date`, `Feature`, `Expiration`, `Encryption licensed`.

- [ ] **Step 2: Implement headers/fields + wiring**

- [ ] **Step 3: Run export tests — PASS**

```powershell
python -m pytest tests/test_system_connectivity_export.py -q --tb=short
```

- [ ] **Step 4: Commit**

```powershell
git add launchpad/system_connectivity_export.py tests/test_system_connectivity_export.py
git commit -m "Export License Key sheet and CSV in System Connectivity."
```

---

### Task 5: Version bump to 1.6.78

**Files:**
- Modify: `launchpad/config.py`
- Modify: `tests/test_system_connectivity_version.py`

- [ ] **Step 1: Assert `APP_VERSION == "1.6.78"` (RED)** then set `APP_VERSION = "1.6.78"` (GREEN)

- [ ] **Step 2: Run**

```powershell
python -m pytest tests/test_system_connectivity_version.py tests/test_system_connectivity_license_key.py tests/test_system_connectivity_page.py tests/test_system_connectivity_export.py -q --tb=short
```

- [ ] **Step 3: Commit**

```powershell
git add launchpad/config.py tests/test_system_connectivity_version.py
git commit -m "Bump LaunchPad to 1.6.78 for System Connectivity License Key tab."
```

---

### Task 6: Final verification

- [ ] **Step 1: Related suite**

```powershell
python -m pytest tests/test_system_connectivity_license_key.py tests/test_system_connectivity_license_key_api.py tests/test_system_connectivity_page.py tests/test_system_connectivity_export.py tests/test_system_connectivity_api.py tests/test_system_connectivity_firmware_api.py tests/test_system_connectivity_version.py tests/test_system_connectivity_nav.py -q --tb=short
```

Expected: PASS.

- [ ] **Step 2: Confirm TOPICS order**

```powershell
python -c "from launchpad.system_connectivity import TOPICS; from launchpad.config import APP_VERSION; print(TOPICS); print(APP_VERSION)"
```

Expected: `..., 'firmware', 'license_key'` and `1.6.78`.

- [ ] **Step 3: No commit unless fixes**

---

## Spec coverage checklist

| Spec item | Task |
|-----------|------|
| Sixth tab after Firmware | 3 |
| HPE full feature rows + key gen date | 1–2 |
| FlashSystem encryption + date/time + best-effort key gen | 1–2 |
| DS8884 n/a | 1–2 |
| Excel/CSV License Key | 4 |
| Flattened HPE rows + sort | 2 |
| Version 1.6.78 | 5 |
| Read-only / no install | Global |
| No SCU tables / no slice A | Global |
