# Site Lookup Snapshot Policy Tab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show IBM snapshot policies on Site Lookup (name, schedule, retention) with a header count, shipping as **1.6.181**.

**Architecture:** Parse `lssnapshotpolicy` in `site_lookup_data.py`. IBM Live Refresh runs one extra SSH command and stores `policies` on the same payload as hosts/volumes, including offline snapshots. The page adds a Policy tab and Policies count using the existing Consistency Groups profile helper. Export adds a Policies sheet.

**Tech Stack:** Python, HealthServer HTML/JS, existing `_table_records` / `_get`, pytest.

**Spec:** `docs/superpowers/specs/2026-08-18-site-lookup-snapshot-policies-design.md`

## Global Constraints

- APP_VERSION bump to **1.6.181** only in the final version task. Do not bump in Tasks 1–4.
- IBM snapshot policies from `lssnapshotpolicy` only. Not FlashCopy CG schedules. Not volume groups.
- Collect SSH only when `card.device_profile in SVC_PROFILES`. Same as `lsconsistgrp`.
- Page tab + header count only when `device_profile` contains `flashsystem`, `storwize`, or `svc` (reuse `profileSupportsConsistencyGroups`).
- HPE and DS: never run the command; never show the tab or Policies count.
- Commands: `svcinfo lssnapshotpolicy -delim :`, then `svcinfo lssnapshotpolicy` if empty. Do **not** call `collect_esx_snap_inventory`.
- Display: schedule `every {interval} {unit}`; missing interval or unit → `—`. Retention `keep {n} days` (always the word `days`, including `keep 1 days`); missing/non-numeric → `—`.
- Firmware copy: `Snapshot policies need IBM Storage Virtualize 8.5.1 or later`
- Empty success copy: `No snapshot policies on this array`
- Policy SSH failure must not fail Live Refresh or clear hosts/volumes/CGs/pools. Do not write policy errors into HPE `warning`.
- Read-only. No create/edit/delete from Site Lookup.
- Place imports at the top of modules (no inline imports).
- Windows PowerShell commits (`git commit -m "..."`); commit at each task commit step.
- Prefer TDD: failing test → implement → pass → commit.
- Do not commit `.superpowers/sdd*` scratch, `LaunchPad-Install/`, or install zips.
- Work on branch `feature/site-lookup-snapshot-policies` (already exists from the spec commit). Do not start from `main` without that spec.

## File structure

| File | Responsibility |
|------|----------------|
| `launchpad/site_lookup_data.py` | Parse/collect policies; payload `policies` / `stats.policies` / `policies_error` |
| `launchpad/site_lookup_offline.py` | Persist `policies` and `policies_error` |
| `tests/test_site_lookup_data.py` | Parser + live payload |
| `tests/test_site_lookup_offline.py` | Snapshot round-trip |
| `launchpad/health_server.py` | IBM Live Refresh extra SSH |
| `tests/test_site_lookup_api.py` | Refresh includes policies; failure isolation |
| `launchpad/site_lookup.py` | Policy tab, header count, empty/error, filter |
| `tests/test_site_lookup_page.py` | Page contracts |
| `launchpad/site_lookup_export.py` | Policies Excel sheet + CSV member |
| `tests/test_site_lookup_export.py` | Sheet wanted IBM vs HPE |
| `launchpad/config.py` + version pins | **1.6.181** (Task 5 only) |

---

### Task 1: Parse snapshot policies and carry them on payloads

**Files:**
- Modify: `launchpad/site_lookup_data.py`
- Modify: `launchpad/site_lookup_offline.py`
- Modify: `tests/test_site_lookup_data.py`
- Modify: `tests/test_site_lookup_offline.py`

**Interfaces:**
- Consumes: `launchpad.flashsystem_fc._table_records`, `_get`; `launchpad.flashsystem_parse._parse_key_values`
- Produces:
  - `SNAPSHOT_POLICY_FIRMWARE_MSG = "Snapshot policies need IBM Storage Virtualize 8.5.1 or later"`
  - `parse_lssnapshotpolicy(output: str) -> list[dict[str, str]]` each row `{name, schedule, retention}`
  - `collect_lookup_snapshot_policies(run_cmd: Callable[[str], str]) -> tuple[list[dict[str, str]], str]` → `(policies, policies_error)`
  - `_build_payload(..., policies: list[dict] | None = None, policies_error: str | None = None)` includes `policies`, `stats.policies`, `policies_error` (default `[]` / `""`)
  - `payload_from_live(..., policies: list[dict] | None = None, policies_error: str | None = None)`
  - Offline snapshot round-trip keeps `policies` and `policies_error`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_site_lookup_data.py`:

```python
from launchpad.site_lookup_data import (
    SNAPSHOT_POLICY_FIRMWARE_MSG,
    collect_lookup_snapshot_policies,
    parse_lssnapshotpolicy,
    payload_from_live,
)

POLICY_SAMPLE = """id:name:backup_unit:backup_interval:retention_days
0:other-policy:day:1:7
1::day:1:3
2:hourly:hour:2:1
"""


def test_parse_lssnapshotpolicy_colon_table():
    rows = parse_lssnapshotpolicy(POLICY_SAMPLE)
    assert [r["name"] for r in rows] == ["other-policy", "hourly"]
    assert rows[0]["schedule"] == "every 1 day"
    assert rows[0]["retention"] == "keep 7 days"
    assert rows[1]["schedule"] == "every 2 hour"
    assert rows[1]["retention"] == "keep 1 days"


def test_parse_lssnapshotpolicy_missing_fields_and_key_value():
    rows = parse_lssnapshotpolicy("id:name\n0:bare\n")
    assert rows == [{"name": "bare", "schedule": "—", "retention": "—"}]
    kv = parse_lssnapshotpolicy(
        "name esx_snap\nbackup_unit day\nbackup_interval 1\nretention_days 7\n"
    )
    assert kv[0]["name"] == "esx_snap"
    assert kv[0]["schedule"] == "every 1 day"
    assert kv[0]["retention"] == "keep 7 days"


def test_collect_lookup_snapshot_policies_success_firmware_and_error():
    policies, err = collect_lookup_snapshot_policies(lambda _cmd: POLICY_SAMPLE)
    assert err == ""
    assert policies[0]["name"] == "other-policy"

    calls = []

    def empty_then_plain(cmd: str) -> str:
        calls.append(cmd)
        if "-delim" in cmd:
            return ""
        return POLICY_SAMPLE

    policies, err = collect_lookup_snapshot_policies(empty_then_plain)
    assert calls[0] == "svcinfo lssnapshotpolicy -delim :"
    assert calls[1] == "svcinfo lssnapshotpolicy"
    assert err == ""
    assert policies[0]["name"] == "other-policy"

    policies, err = collect_lookup_snapshot_policies(
        lambda _cmd: "CMMVC5782E The action failed as this is not a valid command."
    )
    assert policies == []
    assert err == SNAPSHOT_POLICY_FIRMWARE_MSG

    def boom(_cmd: str) -> str:
        raise RuntimeError("SSH down")

    policies, err = collect_lookup_snapshot_policies(boom)
    assert policies == []
    assert SNAPSHOT_POLICY_FIRMWARE_MSG in err
    assert "SSH down" in err


def test_payload_from_live_includes_policies():
    card = {
        "id": 1,
        "name": "site",
        "host": "1.2.3.4",
        "model": "FS",
        "device_profile": "flashsystem_5200",
    }
    payload = payload_from_live(
        card=card,
        hosts=[],
        volumes=[],
        maps=[],
        consist_groups=[],
        pools=[],
        policies=[{"name": "esx_snap", "schedule": "every 1 day", "retention": "keep 7 days"}],
        policies_error="",
    )
    assert payload["policies"][0]["name"] == "esx_snap"
    assert payload["stats"]["policies"] == 1
    assert payload["policies_error"] == ""
    empty = payload_from_live(
        card=card,
        hosts=[],
        volumes=[],
        maps=[],
        consist_groups=[],
        pools=[],
    )
    assert empty["policies"] == []
    assert empty["stats"]["policies"] == 0
    assert empty["policies_error"] == ""
```

Extend `test_snapshot_from_live_payload_and_offline_source` in `tests/test_site_lookup_offline.py` (keep existing asserts) by adding policies to `live` and asserting the round-trip:

```python
        "policies": [
            {"name": "esx_snap", "schedule": "every 1 day", "retention": "keep 7 days"}
        ],
        "policies_error": "",
```

After `payload = payload_from_offline_snapshot(snap)` add:

```python
    assert payload["policies"][0]["name"] == "esx_snap"
    assert payload["stats"]["policies"] == 1
    assert payload["policies_error"] == ""
```

Add:

```python
def test_offline_snapshot_missing_policies_defaults_empty():
    snap = snapshot_from_live_payload(
        {
            "card": {"id": 4, "name": "old", "host": "1.1.1.1"},
            "hosts": [{"name": "h"}],
            "volumes": [],
            "mappings": [],
            "consistency_groups": [],
            "pools": [],
            "refreshed_at": "2026-08-06T13:00:00Z",
        }
    )
    assert snap is not None
    assert snap["policies"] == []
    payload = payload_from_offline_snapshot(snap)
    assert payload["policies"] == []
    assert payload["stats"]["policies"] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_site_lookup_data.py::test_parse_lssnapshotpolicy_colon_table tests/test_site_lookup_data.py::test_parse_lssnapshotpolicy_missing_fields_and_key_value tests/test_site_lookup_data.py::test_collect_lookup_snapshot_policies_success_firmware_and_error tests/test_site_lookup_data.py::test_payload_from_live_includes_policies tests/test_site_lookup_offline.py::test_snapshot_from_live_payload_and_offline_source tests/test_site_lookup_offline.py::test_offline_snapshot_missing_policies_defaults_empty -v`

Expected: FAIL (import / attribute errors for new names).

- [ ] **Step 3: Write minimal implementation**

In `launchpad/site_lookup_data.py`, add imports at the top:

```python
from collections.abc import Callable

from launchpad.flashsystem_fc import (
    _get,
    _table_records,
    parse_fc_hosts,
    parse_host_lun_maps,
    parse_lsvdisk_volumes,
)
from launchpad.flashsystem_parse import _parse_key_values
```

Keep the existing `HPE_SHELL_PROFILES` / `volume_find` imports. Do not duplicate the `flashsystem_fc` import block.

Add after the imports:

```python
SNAPSHOT_POLICY_FIRMWARE_MSG = (
    "Snapshot policies need IBM Storage Virtualize 8.5.1 or later"
)


def _schedule_label(interval: str, unit: str) -> str:
    if not interval or not unit:
        return "—"
    return f"every {interval} {unit}"


def _retention_label(raw: str) -> str:
    text = str(raw or "").strip()
    if not text:
        return "—"
    try:
        days = int(text)
    except ValueError:
        return "—"
    return f"keep {days} days"


def parse_lssnapshotpolicy(output: str) -> list[dict[str, str]]:
    records = _table_records(output)
    if not records:
        kv = _parse_key_values(output)
        if kv:
            records = [kv]
    rows: list[dict[str, str]] = []
    for record in records:
        name = _get(record, "name")
        if not name:
            continue
        interval = _get(record, "backup_interval", "backupinterval")
        unit = _get(record, "backup_unit", "backupunit")
        retention = _get(record, "retention_days", "retentiondays", "retention")
        rows.append(
            {
                "name": name,
                "schedule": _schedule_label(interval, unit),
                "retention": _retention_label(retention),
            }
        )
    return rows


def collect_lookup_snapshot_policies(
    run_cmd: Callable[[str], str],
) -> tuple[list[dict[str, str]], str]:
    try:
        output = run_cmd("svcinfo lssnapshotpolicy -delim :")
        if not str(output or "").strip():
            output = run_cmd("svcinfo lssnapshotpolicy")
    except Exception as exc:
        return [], f"{SNAPSHOT_POLICY_FIRMWARE_MSG} ({exc})"
    text = str(output or "")
    if "not a valid command" in text.lower():
        return [], SNAPSHOT_POLICY_FIRMWARE_MSG
    return parse_lssnapshotpolicy(text), ""
```

Update `_build_payload` to accept `policies` and `policies_error` and include them:

```python
def _build_payload(
    *,
    card: dict,
    hosts: list[dict],
    volumes: list[dict],
    maps: list[dict],
    consistency_groups: list[dict],
    pools: list[dict],
    source: str,
    refreshed_at: str | None,
    error: str | None = None,
    warning: str | None = None,
    policies: list[dict] | None = None,
    policies_error: str | None = None,
) -> dict[str, Any]:
    policy_rows = list(policies or [])
    return {
        "card": _card_meta(card),
        "stats": {
            "hosts": len(hosts),
            "volumes": len(volumes),
            "pools": len(pools),
            "nodes": int(card.get("node_count") or 0),
            "consistency_groups": len(consistency_groups),
            "policies": len(policy_rows),
        },
        "hosts": hosts,
        "volumes": volumes,
        "mappings": maps,
        "consistency_groups": consistency_groups,
        "pools": pools,
        "policies": policy_rows,
        "policies_error": str(policies_error or ""),
        "source": source,
        "refreshed_at": refreshed_at,
        "error": error,
        "warning": warning,
    }
```

Update `payload_from_offline_snapshot` to pass snapshot policies:

```python
    return _build_payload(
        card=card,
        hosts=hosts,
        volumes=volumes,
        maps=maps,
        consistency_groups=cgs,
        pools=pools,
        source="offline",
        refreshed_at=snapshot.get("refreshed_at"),
        policies=list(snapshot.get("policies") or [])
        if isinstance(snapshot.get("policies"), list)
        else [],
        policies_error=str(snapshot.get("policies_error") or ""),
    )
```

Update `payload_from_live` signature and `_build_payload` call:

```python
def payload_from_live(
    *,
    card: dict,
    hosts: list[dict],
    volumes: list[dict],
    maps: list[dict],
    consist_groups: list[dict],
    pools: list[dict] | None = None,
    contingency_groups: list[dict] | None = None,
    refreshed_at: str | None = None,
    warning: str | None = None,
    policies: list[dict] | None = None,
    policies_error: str | None = None,
) -> dict[str, Any]:
```

Pass `policies=policies` and `policies_error=policies_error` into `_build_payload`. Cache / LUN offline builders can omit them (defaults empty).

In `launchpad/site_lookup_offline.py` `normalize_snapshot`, add:

```python
        "policies": (
            list(raw.get("policies") or [])
            if isinstance(raw.get("policies"), list)
            else []
        ),
        "policies_error": str(raw.get("policies_error") or ""),
```

In `snapshot_from_live_payload`, pass through:

```python
            "policies": payload.get("policies") or [],
            "policies_error": payload.get("policies_error") or "",
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_site_lookup_data.py tests/test_site_lookup_offline.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add tests/test_site_lookup_data.py tests/test_site_lookup_offline.py launchpad/site_lookup_data.py launchpad/site_lookup_offline.py
git commit -m "Parse IBM snapshot policies into Site Lookup payloads."
```

---

### Task 2: Live Refresh collects policies on IBM cards

**Files:**
- Modify: `launchpad/health_server.py` (`refresh_site_lookup`, import `collect_lookup_snapshot_policies`)
- Modify: `tests/test_site_lookup_api.py`

**Interfaces:**
- Consumes: `collect_lookup_snapshot_policies(run_cmd) -> tuple[list[dict[str, str]], str]`
- Produces: IBM `refresh_site_lookup` payload includes `policies` / `policies_error`; HPE/non-SVC never runs `lssnapshotpolicy`; policy SSH errors do not fail refresh

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_site_lookup_api.py`:

```python
POLICY_OUT = """id:name:backup_unit:backup_interval:retention_days
0:esx_snap:day:1:7
"""


def test_refresh_site_lookup_includes_snapshot_policies(monkeypatch):
    server = HealthServer()
    server._cards[1] = _card()
    commands: list[str] = []

    def fake_refresh(self, card_id, **kwargs):
        card = self._cards[card_id]
        card.command_results = [
            {
                "label": "FC - Hosts",
                "command": "svcinfo lshost -delim :",
                "output": "id:name:status:port_count\n1:h1:online:2\n",
                "error": None,
            }
        ]
        card.error = None
        return card

    def run_for_card(_card):
        def run(command: str) -> str:
            commands.append(command)
            if "lssnapshotpolicy" in command:
                return POLICY_OUT
            return "id:name:status\n"
        return run

    monkeypatch.setattr(HealthServer, "refresh_card", fake_refresh)
    monkeypatch.setattr(HealthServer, "_lun_run_command", staticmethod(run_for_card))
    monkeypatch.setattr(server, "get_contingency_groups", lambda: [])

    payload = server.refresh_site_lookup(1)
    assert any("lssnapshotpolicy" in cmd for cmd in commands)
    assert payload["policies"][0]["name"] == "esx_snap"
    assert payload["policies"][0]["schedule"] == "every 1 day"
    assert payload["policies"][0]["retention"] == "keep 7 days"
    assert payload["stats"]["policies"] == 1
    assert payload["policies_error"] == ""
    assert payload["hosts"][0]["host_name"] == "h1"


def test_refresh_site_lookup_policy_failure_keeps_hosts(monkeypatch):
    server = HealthServer()
    server._cards[1] = _card()

    def fake_refresh(self, card_id, **kwargs):
        card = self._cards[card_id]
        card.command_results = [
            {
                "label": "FC - Hosts",
                "command": "svcinfo lshost -delim :",
                "output": "id:name:status:port_count\n1:h1:online:2\n",
                "error": None,
            }
        ]
        card.error = None
        return card

    def run_for_card(_card):
        def run(command: str) -> str:
            if "lssnapshotpolicy" in command:
                raise RuntimeError("SSH down")
            return "id:name:status\n"
        return run

    monkeypatch.setattr(HealthServer, "refresh_card", fake_refresh)
    monkeypatch.setattr(HealthServer, "_lun_run_command", staticmethod(run_for_card))
    monkeypatch.setattr(server, "get_contingency_groups", lambda: [])

    payload = server.refresh_site_lookup(1)
    assert payload["hosts"][0]["host_name"] == "h1"
    assert payload["policies"] == []
    assert payload["policies_error"]
    assert payload.get("warning") in (None, "")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_site_lookup_api.py::test_refresh_site_lookup_includes_snapshot_policies tests/test_site_lookup_api.py::test_refresh_site_lookup_policy_failure_keeps_hosts -v`

Expected: FAIL (`policies` missing or empty).

- [ ] **Step 3: Write minimal implementation**

In `launchpad/health_server.py`, add `collect_lookup_snapshot_policies` to the `site_lookup_data` import.

In `refresh_site_lookup`, after the `lsconsistgrp` block (the `if card.device_profile in SVC_PROFILES:` that fills `consist_groups`), collect policies:

```python
            policies: list[dict] = []
            policies_error = ""
            if card.device_profile in SVC_PROFILES:
                policies, policies_error = collect_lookup_snapshot_policies(
                    self._lun_run_command(card)
                )
```

Pass them into `payload_from_live(...)`:

```python
                policies=policies,
                policies_error=policies_error,
```

Do not run `lssnapshotpolicy` for HPE or other non-SVC profiles. Do not wrap the whole refresh in a new try that would drop hosts.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_site_lookup_api.py -v`

Expected: PASS (including existing persist/cache tests).

- [ ] **Step 5: Commit**

```powershell
git add launchpad/health_server.py tests/test_site_lookup_api.py
git commit -m "Collect snapshot policies during IBM Site Lookup refresh."
```

---

### Task 3: Policy tab and header count

**Files:**
- Modify: `launchpad/site_lookup.py`
- Modify: `tests/test_site_lookup_page.py`

**Interfaces:**
- Consumes: payload `policies`, `stats.policies`, `policies_error`; `profileSupportsConsistencyGroups(card)`
- Produces: IBM header **Policies** after CGs before Pools; tab **Policy** in that order; table Name / Schedule / Retention; empty `No snapshot policies on this array` or `policies_error`; `snapshot_policies_available` on cache/normalize payloads for export; filter matches policy name

- [ ] **Step 1: Write the failing tests**

Add `"Policy"` to the label loop in `test_site_lookup_path_and_markers`. Add:

```python
def test_site_lookup_policy_tab_and_empty_copy():
    html = SITE_LOOKUP_HTML
    assert 'tabs.push(["policies", "Policy"])' in html
    assert "</b>Policies</div>" in html
    assert "No snapshot policies on this array" in html
    assert "snapshot_policies_available" in html
    assert "function renderPolicies" in html
    assert "<th>Name</th><th>Schedule</th><th>Retention</th>" in html
    render = html.split("function renderPayload() {", 1)[1].split(
        "async function selectCard", 1
    )[0]
    assert render.find('["consistency_groups", "Consistency Groups"]') < render.find(
        '["policies", "Policy"]'
    )
    assert render.find('["policies", "Policy"]') < render.find('["pools", poolsName]')
    assert "const showPolicies = profileSupportsConsistencyGroups(card);" in render
    assert "snapshot_policies_available: profileSupportsConsistencyGroups(card)" in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_site_lookup_page.py::test_site_lookup_policy_tab_and_empty_copy tests/test_site_lookup_page.py::test_site_lookup_path_and_markers -v`

Expected: FAIL (Policy strings missing).

- [ ] **Step 3: Write minimal implementation**

In `launchpad/site_lookup.py`:

1. `cachePayload` stats add `policies: 0`. Payload add `policies: []`, `policies_error: ""`, `snapshot_policies_available: profileSupportsConsistencyGroups(card)`.

2. `normalizePayload` add `policies: asRows(data.policies)`, `policies_error: data.policies_error || ""`, `snapshot_policies_available: profileSupportsConsistencyGroups(data.card || currentCard)`.

3. Add `renderPolicies` immediately before `function numberValue`:

```javascript
    function renderPolicies(data) {
      const rows = (data.policies || []).filter((row) => matchesFilter(row));
      const errorText = String(data.policies_error || "").trim();
      if (!rows.length) {
        return emptyMessage(false, errorText || "No snapshot policies on this array");
      }
      return '<div class="table-wrap"><table><thead><tr>'
        + "<th>Name</th><th>Schedule</th><th>Retention</th>"
        + "</tr></thead><tbody>" + rows.map((row) => (
          "<tr><td>" + escapeHtml(row.name || "") + "</td>"
          + "<td>" + escapeHtml(row.schedule || "—") + "</td>"
          + "<td>" + escapeHtml(row.retention || "—") + "</td></tr>"
        )).join("") + "</tbody></table></div>";
    }
```

4. In `renderPayload`, after `const showCgs = profileSupportsConsistencyGroups(card);` add `const showPolicies = profileSupportsConsistencyGroups(card);`

Insert the Policy tab after CGs and before Pools:

```javascript
      if (showCgs) tabs.push(["consistency_groups", "Consistency Groups"]);
      if (showPolicies) tabs.push(["policies", "Policy"]);
      tabs.push(["pools", poolsName]);
      if (!showCgs && activeTab === "consistency_groups") activeTab = "hosts";
      if (!showPolicies && activeTab === "policies") activeTab = "hosts";
```

Body switch:

```javascript
      if (activeTab === "hosts") body = renderHosts(data);
      else if (activeTab === "volumes") body = renderVolumes(data);
      else if (activeTab === "consistency_groups") body = renderConsistencyGroups(data);
      else if (activeTab === "policies") body = renderPolicies(data);
      else body = renderPools(data);
```

Header count after CGs, before Pools:

```javascript
      if (showPolicies) {
        statsHtml += '<div class="stat"><b>'
          + escapeHtml(stats.policies == null ? (data.policies || []).length : stats.policies)
          + "</b>Policies</div>";
      }
```

5. Filter listener: add `else if (activeTab === "policies") bodyEl.innerHTML = renderPolicies(currentPayload);` before the pools branch.

Reuse `emptyMessage(false, hint)` so firmware/`policies_error` shows in the tab. Do not change the filter placeholder.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_site_lookup_page.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add launchpad/site_lookup.py tests/test_site_lookup_page.py
git commit -m "Add Site Lookup Policy tab and Policies header count."
```

---

### Task 4: Excel/CSV Policies sheet

**Files:**
- Modify: `launchpad/site_lookup_export.py`
- Modify: `tests/test_site_lookup_export.py`

**Interfaces:**
- Consumes: `payload["policies"]`, `payload["snapshot_policies_available"]`
- Produces:
  - `POLICY_HEADERS = ("Name", "Schedule", "Retention")`
  - `snapshot_policies_sheet_wanted(payload: dict) -> bool` — true when `snapshot_policies_available` or non-empty `policies` list (same shape as `consistency_groups_sheet_wanted`)
  - Excel sheet **Policies**; CSV member **Policies.csv**
  - Sheet order: after Consistency Groups, before Offline

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_site_lookup_export.py`:

```python
from launchpad.site_lookup_export import snapshot_policies_sheet_wanted


def _ibm_payload():
    return {
        "card": {"name": "Hartford", "device_profile": "flashsystem_7200"},
        "hosts": [],
        "volumes": [],
        "pools": [],
        "consistency_groups": [],
        "consistency_groups_available": True,
        "snapshot_policies_available": True,
        "policies": [
            {"name": "esx_snap", "schedule": "every 1 day", "retention": "keep 7 days"}
        ],
    }


def test_snapshot_policies_sheet_wanted():
    assert snapshot_policies_sheet_wanted(_ibm_payload()) is True
    assert snapshot_policies_sheet_wanted(_hpe_payload()) is False
    assert snapshot_policies_sheet_wanted(
        {"snapshot_policies_available": False, "policies": [{"name": "x"}]}
    ) is True


def test_export_xlsx_and_csv_include_policies_for_ibm():
    wb = load_workbook(BytesIO(export_site_lookup_xlsx(_ibm_payload())))
    assert "Policies" in wb.sheetnames
    assert [cell.value for cell in wb["Policies"][1]] == [
        "Name",
        "Schedule",
        "Retention",
    ]
    assert [cell.value for cell in wb["Policies"][2]] == [
        "esx_snap",
        "every 1 day",
        "keep 7 days",
    ]
    raw = export_site_lookup_csv_zip(_ibm_payload())
    with zipfile.ZipFile(BytesIO(raw)) as zf:
        assert "Policies.csv" in zf.namelist()
        text = zf.read("Policies.csv").decode("utf-8")
    assert "esx_snap" in text
    assert "keep 7 days" in text
```

Existing HPE tests must still omit Policies.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_site_lookup_export.py -v`

Expected: FAIL (`snapshot_policies_sheet_wanted` missing; HPE sheet list still passes until implementation).

- [ ] **Step 3: Write minimal implementation**

In `launchpad/site_lookup_export.py`:

```python
POLICY_HEADERS = ("Name", "Schedule", "Retention")


def snapshot_policies_sheet_wanted(payload: dict) -> bool:
    if payload.get("snapshot_policies_available"):
        return True
    rows = payload.get("policies") or []
    return isinstance(rows, list) and bool(rows)
```

Helper used by both xlsx and csv:

```python
def _policy_export_rows(payload: dict) -> list[tuple[Any, ...]]:
    return [
        (
            p.get("name") or "",
            p.get("schedule") or "",
            p.get("retention") or "",
        )
        for p in (payload.get("policies") or [])
        if isinstance(p, dict)
    ]
```

After the Consistency Groups sheet/member (and before Offline in xlsx), if `snapshot_policies_sheet_wanted(payload)`: write Policies / `Policies.csv`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_site_lookup_export.py -v`

Expected: PASS. HPE still `["Hosts", "Volumes", "CPGs"]`.

- [ ] **Step 5: Commit**

```powershell
git add launchpad/site_lookup_export.py tests/test_site_lookup_export.py
git commit -m "Export Site Lookup snapshot policies to Excel and CSV."
```

---

### Task 5: Bump APP_VERSION to 1.6.181

**Files:**
- Modify: `launchpad/config.py`
- Modify: `tests/test_capacity_unit_js.py`
- Modify: `tests/test_hadoop_sudo_wire.py`
- Modify: `tests/test_system_connectivity_version.py`

**Interfaces:**
- Consumes: current `APP_VERSION = "1.6.180"`
- Produces: `APP_VERSION = "1.6.181"` and matching pin tests

- [ ] **Step 1: Write the failing tests**

Change the version pin asserts from `"1.6.180"` to `"1.6.181"`:

- `tests/test_capacity_unit_js.py` → `test_app_version_153`
- `tests/test_hadoop_sudo_wire.py` → `test_version_174`
- `tests/test_system_connectivity_version.py` → `test_app_version_16174`

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_capacity_unit_js.py::test_app_version_153 tests/test_hadoop_sudo_wire.py::test_version_174 tests/test_system_connectivity_version.py::test_app_version_16174 -v`

Expected: FAIL (`1.6.180 != 1.6.181`).

- [ ] **Step 3: Write minimal implementation**

In `launchpad/config.py`: `APP_VERSION = "1.6.181"`

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_capacity_unit_js.py::test_app_version_153 tests/test_hadoop_sudo_wire.py::test_version_174 tests/test_system_connectivity_version.py::test_app_version_16174 tests/test_site_lookup_data.py tests/test_site_lookup_offline.py tests/test_site_lookup_api.py tests/test_site_lookup_page.py tests/test_site_lookup_export.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add launchpad/config.py tests/test_capacity_unit_js.py tests/test_hadoop_sudo_wire.py tests/test_system_connectivity_version.py
git commit -m "Bump version to 1.6.181 for Site Lookup snapshot policies."
```

---

## Self-review

- Spec coverage: parse/format, collect SSH, IBM-only, payload/offline, refresh error isolation, Policy tab + Policies count + empty/firmware copy, filter via `matchesFilter`, export sheet, version **1.6.181**. Non-goals (create, VGs, FlashCopy, extra HPE SSH) are not tasked.
- Placeholders: none.
- Types: `parse_lssnapshotpolicy` → `list[dict[str, str]]` with `name`/`schedule`/`retention`; `collect_lookup_snapshot_policies` → `(list, str)`; payload keys `policies`, `stats.policies`, `policies_error`, `snapshot_policies_available`.
