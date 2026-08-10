# FC WWPN Port Labels (fc0/fc1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show FC WWPN Port as `fc0` / `fc1` / … on the page and Excel without changing stored `port_id` (v**1.6.150**).

**Architecture:** Add `format_fc_port_label` in `flashsystem_fc.py`. Excel uses it when writing the Port column. The page mirrors the same rules in a small JS `formatFcPortLabel` used by `portTable`. Raw `port_id` / `fc_io_port_id` stay unchanged for fabric matching.

**Tech Stack:** Python, openpyxl (existing export), FC WWPN HTML/JS page, pytest.

**Spec:** `docs/superpowers/specs/2026-08-10-fc-wwpn-port-labels-design.md`

## Global Constraints

- APP_VERSION is currently `1.6.149`; bump to `1.6.150` in the page/version task.
- Display-only: do **not** mutate `port_id` / `fc_io_port_id` on parsed ports or API payloads.
- Port source unchanged: `port_id` if present, else `fc_io_port_id`.
- Label rules: empty→`""`; digits→`fc{digits}`; `fc`/`FC`+digits→normalize to `fc{digits}`; other text unchanged.
- Page + Excel both use the label.
- Windows PowerShell commits (`git commit -m "..."`); commit at each task’s commit step.
- Prefer TDD: failing test → implement → pass → commit.
- Do not commit `.superpowers/sdd*` scratch or install zips.

## File structure

| File | Responsibility |
|------|----------------|
| `launchpad/flashsystem_fc.py` | `format_fc_port_label` |
| `launchpad/fc_wwpn_export.py` | Port column uses helper |
| `launchpad/fc_wwpn_report.py` | JS Port cell uses matching formatter |
| `launchpad/config.py` | `APP_VERSION` → `1.6.150` |
| `tests/test_format_fc_port_label.py` | Helper unit tests |
| `tests/test_fc_wwpn_export_filter.py` or export test | Port cell `fc0` when id is `0` |
| `tests/test_fc_wwpn_page.py` | Assert JS helper / Port formatting present |
| `tests/test_system_connectivity_version.py` | Version pin → `1.6.150` |
| `tests/test_hadoop_sudo_wire.py` | Version pin → `1.6.150` |

---

### Task 1: `format_fc_port_label` + Excel Port column

**Files:**
- Modify: `launchpad/flashsystem_fc.py`
- Modify: `launchpad/fc_wwpn_export.py`
- Create: `tests/test_format_fc_port_label.py`
- Modify: `tests/test_fc_wwpn_export_filter.py` (or add focused export assert in a new test in that file / `test_fc_wwpn_mappings_export.py` — prefer extending export filter tests if they already build port rows)

**Interfaces:**
- Produces: `format_fc_port_label(raw: str | None) -> str`

- [ ] **Step 1: Write the failing helper tests**

```python
from launchpad.flashsystem_fc import format_fc_port_label


def test_format_fc_port_label_rules():
    assert format_fc_port_label(None) == ""
    assert format_fc_port_label("") == ""
    assert format_fc_port_label("0") == "fc0"
    assert format_fc_port_label("3") == "fc3"
    assert format_fc_port_label("12") == "fc12"
    assert format_fc_port_label("fc0") == "fc0"
    assert format_fc_port_label("FC1") == "fc1"
    assert format_fc_port_label("1/1") == "1/1"
    assert format_fc_port_label("host") == "host"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_format_fc_port_label.py -v`  
Expected: FAIL (symbol missing)

- [ ] **Step 3: Implement helper**

In `launchpad/flashsystem_fc.py`:

```python
import re

_FC_DIGITS = re.compile(r"^(\d+)$")
_FC_PREFIXED = re.compile(r"^fc(\d+)$", re.IGNORECASE)


def format_fc_port_label(raw: str | None) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""
    m = _FC_DIGITS.match(text)
    if m:
        return f"fc{m.group(1)}"
    m = _FC_PREFIXED.match(text)
    if m:
        return f"fc{m.group(1)}"
    return text
```

- [ ] **Step 4: Wire Excel + failing export assert**

In `fc_wwpn_export.py`, import `format_fc_port_label` and replace the Port cell value:

```python
format_fc_port_label(port.get("port_id") or port.get("fc_io_port_id")),
```

Add to `tests/test_format_fc_port_label.py`:

```python
from launchpad.fc_wwpn_export import rows_from_card_api


def test_export_rows_port_column_uses_fc_label():
    card = {
        "name": "Hartford",
        "category": "DC",
        "host": "10.0.0.1",
        "model": "flashsystem_7200",
        "fc_ports": [
            {
                "node_name": "node1",
                "port_id": "0",
                "wwpn": "AABBCCDDEEFF0011",
                "status": "active",
                "speed": "16Gb",
                "attachment": "host",
                "logged_in_count": "1",
                "remote_wwpns": "",
                "fabric_hosts": "",
            }
        ],
        "fc_hosts": [],
        "fc_host_maps": [],
    }
    port_rows, _hosts, _maps = rows_from_card_api(card)
    assert port_rows[0][5] == "fc0"
```

(Port is the 6th field in each `rows_from_card_api` port tuple — after site/name/host/model/node_name.)

- [ ] **Step 5: Run tests**

Run: `python -m pytest tests/test_format_fc_port_label.py tests/test_fc_wwpn_export_filter.py -v`  
Expected: PASS (and any new export test file you added)

- [ ] **Step 6: Commit**

```bash
git add launchpad/flashsystem_fc.py launchpad/fc_wwpn_export.py tests/test_format_fc_port_label.py tests/test_fc_wwpn_export_filter.py
git commit -m "Format FC WWPN Port column as fc0/fc1 in Excel."
```

---

### Task 2: Page Port column + version 1.6.150

**Files:**
- Modify: `launchpad/fc_wwpn_report.py` — add JS `formatFcPortLabel` and use it in `portTable`
- Modify: `launchpad/config.py` — `APP_VERSION = "1.6.150"`
- Modify: `tests/test_fc_wwpn_page.py`
- Modify: `tests/test_system_connectivity_version.py`
- Modify: `tests/test_hadoop_sudo_wire.py`

**Interfaces:**
- Consumes: same label rules as Task 1 (mirrored in JS)
- Produces: Port `<td>` shows `fcN`

- [ ] **Step 1: Write failing page/version tests**

```python
# tests/test_fc_wwpn_page.py
def test_fc_wwpn_formats_port_as_fc_label():
    html = FC_WWPN_REPORT_HTML
    assert "function formatFcPortLabel" in html
    assert "formatFcPortLabel(p.port_id || p.fc_io_port_id || \"\")" in html or (
        "formatFcPortLabel(p.port_id || p.fc_io_port_id || '')" in html
    )
```

Update version pins to `1.6.150`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_fc_wwpn_page.py::test_fc_wwpn_formats_port_as_fc_label tests/test_system_connectivity_version.py -v`  
Expected: FAIL

- [ ] **Step 3: Implement JS helper + wire portTable**

Near other JS helpers in `FC_WWPN_REPORT_HTML`, add:

```javascript
    function formatFcPortLabel(raw) {
      const text = String(raw || "").trim();
      if (!text) return "";
      if (/^\d+$/.test(text)) return "fc" + text;
      const m = /^fc(\d+)$/i.exec(text);
      if (m) return "fc" + m[1];
      return text;
    }
```

Change Port cell from:

```javascript
<td>${escapeHtml(p.port_id || p.fc_io_port_id || "")}</td>
```

to:

```javascript
<td>${escapeHtml(formatFcPortLabel(p.port_id || p.fc_io_port_id || ""))}</td>
```

Set `APP_VERSION = "1.6.150"`.

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_fc_wwpn_page.py tests/test_format_fc_port_label.py tests/test_fc_wwpn_export_filter.py tests/test_system_connectivity_version.py tests/test_hadoop_sudo_wire.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add launchpad/fc_wwpn_report.py launchpad/config.py tests/test_fc_wwpn_page.py tests/test_system_connectivity_version.py tests/test_hadoop_sudo_wire.py
git commit -m "Show fc0/fc1 Port labels on FC WWPN page and bump to 1.6.150."
```

---

## Spec coverage

| Spec requirement | Task |
|------------------|------|
| `format_fc_port_label` rules | 1 |
| Excel Port column | 1 |
| Page Port column | 2 |
| Do not mutate stored port_id | 1–2 |
| APP_VERSION 1.6.150 | 2 |

## Self-review

- No placeholders; helper signature consistent across tasks.
- JS and Python rules intentionally duplicated (spec-allowed) with matching tests/markers.
