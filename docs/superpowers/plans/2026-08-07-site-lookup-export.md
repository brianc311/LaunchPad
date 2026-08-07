# Site Lookup Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let operators download the current Site Lookup inventory as Excel (optional Offline sheet) or CSV zip without a new SSH pull.

**Architecture:** Pure helpers in `site_lookup_export.py` build XLSX/CSV bytes from the client’s current payload. `POST /api/site-lookup/export` accepts `{format, include_offline, payload}` and returns a file download. Site Lookup UI adds Export Excel, Export CSV, and an Include Offline sheet checkbox (Excel only).

**Tech Stack:** Python, openpyxl, zipfile/csv, HealthServer JSON POST + binary response, pytest.

**Spec:** `docs/superpowers/specs/2026-08-07-site-lookup-export-design.md`

## Global Constraints

- APP_VERSION is currently `1.6.137`; bump to `1.6.138` when shipping the UI/version task.
- Export uses the **current looked-up payload** (POST body) — no refresh-on-export.
- Excel sheets: Hosts, Volumes, CPGs (HPE) or Pools (non-HPE), Consistency Groups only when CG-capable / present.
- Offline sheet: **one combined** sheet when `include_offline` is true; use `status_is_offline_or_degraded`.
- CSV: zip of per-section CSVs; **no** Offline file; checkbox ignored.
- Buttons disabled until a payload is loaded.
- Windows PowerShell commits (`git commit -m "..."`); commit at each task’s commit step.
- Prefer TDD: failing test → implement → pass → commit.
- Do not commit `.superpowers/sdd*` scratch or install zips.

## File structure

| File | Responsibility |
|------|----------------|
| `launchpad/site_lookup_export.py` | Build Offline rows; export XLSX workbook; export CSV zip |
| `tests/test_site_lookup_export.py` | Unit tests for helpers |
| `launchpad/health_server.py` | `POST /api/site-lookup/export` handler + thin wrapper |
| `tests/test_site_lookup_api.py` | API mapping tests for export |
| `launchpad/site_lookup.py` | Export Excel / Export CSV / Include Offline sheet UI |
| `tests/test_site_lookup_page.py` | Page contract markers |
| `launchpad/config.py` | `APP_VERSION` → `1.6.138` |
| Version pin tests | Assert `1.6.138` |

---

### Task 1: Export helpers (XLSX + CSV zip)

**Files:**
- Create: `launchpad/site_lookup_export.py`
- Create: `tests/test_site_lookup_export.py`

**Interfaces:**
- Produces:
  - `is_hpe_lookup_card(card: dict | None) -> bool`
  - `pools_sheet_title(card: dict | None) -> str` — `"CPGs"` if HPE else `"Pools"`
  - `consistency_groups_sheet_wanted(payload: dict) -> bool` — True when `consistency_groups_available` is true **or** non-empty `consistency_groups` list
  - `offline_inventory_rows(payload: dict) -> list[dict]` — combined host/volume problem rows with keys `row_type`, `name`, `status`, `detail` (type/ports or pool/capacity)
  - `export_site_lookup_xlsx(payload: dict, *, include_offline: bool = False) -> bytes`
  - `export_site_lookup_csv_zip(payload: dict) -> bytes` — no Offline; zip member names `Hosts.csv`, `Volumes.csv`, `CPGs.csv`|`Pools.csv`, optional `Consistency_Groups.csv`

- [ ] **Step 1: Write the failing tests**

```python
import zipfile
from io import BytesIO

from openpyxl import load_workbook

from launchpad.site_lookup_export import (
    export_site_lookup_csv_zip,
    export_site_lookup_xlsx,
    offline_inventory_rows,
    pools_sheet_title,
)


def _hpe_payload():
    return {
        "card": {"name": "HPE-site", "device_profile": "hpe_3par_8400"},
        "hosts": [
            {"host_name": "esx_ok", "status": "online", "type": "VMware", "port_count": "2"},
            {"host_name": "esx_bad", "status": "offline", "type": "VMware", "port_count": "0"},
        ],
        "volumes": [
            {"name": "vv_ok", "status": "normal", "pool": "cpg_a", "capacity": "10"},
            {"name": "vv_bad", "status": "degraded", "pool": "cpg_b", "capacity": "20"},
        ],
        "pools": [{"name": "cpg_a", "used_pct": 10}],
        "consistency_groups": [],
        "consistency_groups_available": False,
    }


def test_pools_sheet_title_hpe_vs_ibm():
    assert pools_sheet_title({"device_profile": "hpe_3par_8400"}) == "CPGs"
    assert pools_sheet_title({"device_profile": "flashsystem_7200"}) == "Pools"


def test_offline_inventory_rows_combined():
    rows = offline_inventory_rows(_hpe_payload())
    assert {(r["row_type"], r["name"]) for r in rows} == {
        ("host", "esx_bad"),
        ("volume", "vv_bad"),
    }


def test_export_xlsx_sheets_and_optional_offline():
    payload = _hpe_payload()
    wb = load_workbook(BytesIO(export_site_lookup_xlsx(payload, include_offline=False)))
    assert wb.sheetnames == ["Hosts", "Volumes", "CPGs"]
    wb2 = load_workbook(BytesIO(export_site_lookup_xlsx(payload, include_offline=True)))
    assert "Offline" in wb2.sheetnames
    assert wb2["Offline"].max_row >= 2


def test_export_csv_zip_no_offline_member():
    raw = export_site_lookup_csv_zip(_hpe_payload())
    with zipfile.ZipFile(BytesIO(raw)) as zf:
        names = set(zf.namelist())
    assert names == {"Hosts.csv", "Volumes.csv", "CPGs.csv"}
    assert "Offline.csv" not in names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_site_lookup_export.py -v`

Expected: FAIL (module missing)

- [ ] **Step 3: Write minimal implementation**

Create `launchpad/site_lookup_export.py`:

```python
"""Export Site Lookup inventory to Excel or CSV ZIP."""

from __future__ import annotations

import csv
import zipfile
from io import BytesIO, StringIO
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Font

from launchpad.host_volume_health import status_is_offline_or_degraded

HOST_HEADERS = ("Host", "Status", "Type", "Ports", "Protocol")
VOLUME_HEADERS = ("Volume", "Status", "Capacity", "Pool/CPG", "UID")
POOL_HEADERS = ("Name", "Used %", "Used", "Free", "Total")
CG_HEADERS = ("Name", "Status", "Location", "Volumes", "Maps")
OFFLINE_HEADERS = ("Type", "Name", "Status", "Detail")


def is_hpe_lookup_card(card: dict | None) -> bool:
    profile = str((card or {}).get("device_profile") or "").lower()
    return "hpe" in profile or "3par" in profile or "primera" in profile


def pools_sheet_title(card: dict | None) -> str:
    return "CPGs" if is_hpe_lookup_card(card) else "Pools"


def consistency_groups_sheet_wanted(payload: dict) -> bool:
    if payload.get("consistency_groups_available"):
        return True
    rows = payload.get("consistency_groups") or []
    return isinstance(rows, list) and bool(rows)


def offline_inventory_rows(payload: dict) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for host in payload.get("hosts") or []:
        if not isinstance(host, dict):
            continue
        status = str(host.get("status") or host.get("state") or "")
        if not status_is_offline_or_degraded(status):
            continue
        name = str(host.get("host_name") or host.get("name") or "").strip()
        detail = " · ".join(
            part
            for part in (
                str(host.get("type") or "").strip(),
                (f"{host.get('port_count') or host.get('ports') or ''} ports").strip()
                if (host.get("port_count") or host.get("ports"))
                else "",
            )
            if part
        )
        out.append({"row_type": "host", "name": name, "status": status, "detail": detail})
    for vol in payload.get("volumes") or []:
        if not isinstance(vol, dict):
            continue
        status = str(vol.get("status") or vol.get("state") or "")
        if not status_is_offline_or_degraded(status):
            continue
        name = str(vol.get("name") or vol.get("vdisk_name") or "").strip()
        detail = " · ".join(
            part
            for part in (
                str(vol.get("pool") or vol.get("mdisk_grp_name") or "").strip(),
                str(vol.get("capacity") or "").strip(),
            )
            if part
        )
        out.append({"row_type": "volume", "name": name, "status": status, "detail": detail})
    return out


def _write_sheet(wb: Workbook, title: str, headers: tuple[str, ...], rows: list[tuple[Any, ...]]) -> None:
    ws = wb.create_sheet(title)
    ws.append(list(headers))
    for cell in ws[1]:
        cell.font = Font(bold=True)
    for row in rows:
        ws.append(list(row))


def export_site_lookup_xlsx(payload: dict, *, include_offline: bool = False) -> bytes:
    card = payload.get("card") if isinstance(payload.get("card"), dict) else {}
    wb = Workbook()
    wb.remove(wb.active)
    hosts = [
        (
            h.get("host_name") or h.get("name") or "",
            h.get("status") or h.get("state") or "",
            h.get("type") or h.get("host_type") or "",
            h.get("port_count") or h.get("ports") or "",
            h.get("protocol") or "SCSI",
        )
        for h in (payload.get("hosts") or [])
        if isinstance(h, dict)
    ]
    volumes = [
        (
            v.get("name") or v.get("vdisk_name") or "",
            v.get("status") or v.get("state") or "",
            v.get("capacity") or "",
            v.get("pool") or v.get("mdisk_grp_name") or "",
            v.get("uid") or v.get("vdisk_UID") or "",
        )
        for v in (payload.get("volumes") or [])
        if isinstance(v, dict)
    ]
    pools = [
        (
            p.get("name") or "",
            p.get("used_pct") if p.get("used_pct") is not None else "",
            p.get("used_bytes") if p.get("used_bytes") is not None else "",
            p.get("free_bytes") if p.get("free_bytes") is not None else "",
            p.get("total_bytes") if p.get("total_bytes") is not None else "",
        )
        for p in (payload.get("pools") or [])
        if isinstance(p, dict)
    ]
    _write_sheet(wb, "Hosts", HOST_HEADERS, hosts)
    _write_sheet(wb, "Volumes", VOLUME_HEADERS, volumes)
    _write_sheet(wb, pools_sheet_title(card), POOL_HEADERS, pools)
    if consistency_groups_sheet_wanted(payload):
        cgs = [
            (
                g.get("name") or g.get("id") or "",
                g.get("status") or "",
                g.get("location") or "",
                len(g.get("volumes") or []) if isinstance(g.get("volumes"), list) else "",
                len(g.get("maps") or []) if isinstance(g.get("maps"), list) else "",
            )
            for g in (payload.get("consistency_groups") or [])
            if isinstance(g, dict)
        ]
        _write_sheet(wb, "Consistency Groups", CG_HEADERS, cgs)
    if include_offline:
        offline = [
            (r["row_type"], r["name"], r["status"], r["detail"])
            for r in offline_inventory_rows(payload)
        ]
        _write_sheet(wb, "Offline", OFFLINE_HEADERS, offline)
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _csv_bytes(headers: tuple[str, ...], rows: list[tuple[Any, ...]]) -> bytes:
    buf = StringIO()
    writer = csv.writer(buf)
    writer.writerow(headers)
    writer.writerows(rows)
    return buf.getvalue().encode("utf-8")


def export_site_lookup_csv_zip(payload: dict) -> bytes:
    card = payload.get("card") if isinstance(payload.get("card"), dict) else {}
    hosts = [
        (
            h.get("host_name") or h.get("name") or "",
            h.get("status") or h.get("state") or "",
            h.get("type") or h.get("host_type") or "",
            h.get("port_count") or h.get("ports") or "",
            h.get("protocol") or "SCSI",
        )
        for h in (payload.get("hosts") or [])
        if isinstance(h, dict)
    ]
    volumes = [
        (
            v.get("name") or v.get("vdisk_name") or "",
            v.get("status") or v.get("state") or "",
            v.get("capacity") or "",
            v.get("pool") or v.get("mdisk_grp_name") or "",
            v.get("uid") or v.get("vdisk_UID") or "",
        )
        for v in (payload.get("volumes") or [])
        if isinstance(v, dict)
    ]
    pools = [
        (
            p.get("name") or "",
            p.get("used_pct") if p.get("used_pct") is not None else "",
            p.get("used_bytes") if p.get("used_bytes") is not None else "",
            p.get("free_bytes") if p.get("free_bytes") is not None else "",
            p.get("total_bytes") if p.get("total_bytes") is not None else "",
        )
        for p in (payload.get("pools") or [])
        if isinstance(p, dict)
    ]
    members: list[tuple[str, bytes]] = [
        ("Hosts.csv", _csv_bytes(HOST_HEADERS, hosts)),
        ("Volumes.csv", _csv_bytes(VOLUME_HEADERS, volumes)),
        (f"{pools_sheet_title(card)}.csv", _csv_bytes(POOL_HEADERS, pools)),
    ]
    if consistency_groups_sheet_wanted(payload):
        cgs = [
            (
                g.get("name") or g.get("id") or "",
                g.get("status") or "",
                g.get("location") or "",
                len(g.get("volumes") or []) if isinstance(g.get("volumes"), list) else "",
                len(g.get("maps") or []) if isinstance(g.get("maps"), list) else "",
            )
            for g in (payload.get("consistency_groups") or [])
            if isinstance(g, dict)
        ]
        members.append(("Consistency_Groups.csv", _csv_bytes(CG_HEADERS, cgs)))
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, data in members:
            zf.writestr(name, data)
    return buf.getvalue()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_site_lookup_export.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add launchpad/site_lookup_export.py tests/test_site_lookup_export.py
git commit -m "Add Site Lookup Excel and CSV export helpers."
```

---

### Task 2: HealthServer export API

**Files:**
- Modify: `launchpad/health_server.py` (POST handler near other site-lookup routes; add `export_site_lookup_bytes`)
- Modify: `tests/test_site_lookup_api.py`

**Interfaces:**
- Consumes: `export_site_lookup_xlsx`, `export_site_lookup_csv_zip`
- Produces:
  - `HealthServer.export_site_lookup_bytes(*, export_format: str, include_offline: bool, payload: dict) -> tuple[bytes, str, str]`
  - `POST /api/site-lookup/export` JSON body `{ "format": "xlsx"|"csv", "include_offline": bool, "payload": object }` → file bytes

- [ ] **Step 1: Write the failing API tests**

Append to `tests/test_site_lookup_api.py`:

```python
def test_site_lookup_export_post_xlsx_and_errors(monkeypatch):
    class FakeServer:
        def export_site_lookup_bytes(self, *, export_format, include_offline, payload):
            if export_format == "bad":
                raise ValueError("Export format must be xlsx or csv.")
            if not payload:
                raise ValueError("payload is required.")
            return b"XLSX", "Site_Lookup.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    monkeypatch.setattr(health_server_module, "get_health_server", lambda: FakeServer())

    def post(body):
        handler = _HealthHandler.__new__(_HealthHandler)
        handler.path = "/api/site-lookup/export"
        handler.headers = {"Content-Length": str(len(json.dumps(body)))}
        handler.rfile = io.BytesIO(json.dumps(body).encode("utf-8"))
        sent = {}
        handler._send_json = lambda payload, status=200: sent.update(payload=payload, status=status)
        handler._send_bytes = lambda body, *, content_type, filename=None, status=200: sent.update(
            body=body, content_type=content_type, filename=filename, status=status
        )
        handler.do_POST()
        return sent

    ok = post({"format": "xlsx", "include_offline": True, "payload": {"hosts": []}})
    assert ok["status"] == 200
    assert ok["body"] == b"XLSX"
    assert post({"format": "bad", "payload": {}})["status"] == 400
```

Adapt to the project’s existing `_HealthHandler` / POST test helpers if they differ — mirror `test_site_lookup_refresh_post_maps_errors` style in the same file.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_site_lookup_api.py::test_site_lookup_export_post_xlsx_and_errors -v`

Expected: FAIL (route missing)

- [ ] **Step 3: Implement API**

Add on `HealthServer`:

```python
def export_site_lookup_bytes(
    self,
    *,
    export_format: str,
    include_offline: bool,
    payload: dict,
) -> tuple[bytes, str, str]:
    from launchpad.site_lookup_export import (
        export_site_lookup_csv_zip,
        export_site_lookup_xlsx,
    )

    fmt = str(export_format or "").strip().lower()
    if fmt not in {"xlsx", "csv"}:
        raise ValueError("Export format must be xlsx or csv.")
    if not isinstance(payload, dict) or not payload:
        raise ValueError("payload is required.")
    card = payload.get("card") if isinstance(payload.get("card"), dict) else {}
    site = str(card.get("name") or card.get("id") or "site").strip() or "site"
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in site)[:60]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
    if fmt == "xlsx":
        body = export_site_lookup_xlsx(payload, include_offline=bool(include_offline))
        return (
            body,
            f"Site_Lookup_{safe}_{stamp}.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    body = export_site_lookup_csv_zip(payload)
    return body, f"Site_Lookup_{safe}_{stamp}.zip", "application/zip"
```

In `_HealthHandler.do_POST`, near site-lookup refresh:

```python
if path == "/api/site-lookup/export":
    # parse JSON body: format, include_offline, payload
    # call server.export_site_lookup_bytes(...)
    # on ValueError → 400 JSON; else _send_bytes with Content-Disposition filename
```

Follow the same `_send_bytes` / Content-Disposition pattern as `/api/host-volume-health/export`.

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_site_lookup_api.py tests/test_site_lookup_export.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add launchpad/health_server.py tests/test_site_lookup_api.py
git commit -m "Add Site Lookup export API endpoint."
```

---

### Task 3: Site Lookup UI + version

**Files:**
- Modify: `launchpad/site_lookup.py` (searchbar controls + export JS)
- Modify: `tests/test_site_lookup_page.py`
- Modify: `launchpad/config.py` — `APP_VERSION = "1.6.138"`
- Modify: any tests pinning `1.6.137` → `1.6.138`

**Interfaces:**
- Consumes: `POST /api/site-lookup/export` with `currentPayload`
- Produces: UI buttons/checkbox; version `1.6.138`

- [ ] **Step 1: Write failing page contract tests**

Extend `tests/test_site_lookup_page.py`:

```python
def test_site_lookup_export_controls():
    html = SITE_LOOKUP_HTML
    assert "Export Excel" in html
    assert "Export CSV" in html
    assert "Include Offline sheet" in html
    assert "/api/site-lookup/export" in html
    assert "include_offline" in html
    assert "exportExcelBtn.disabled" in html or "export-excel-btn" in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_site_lookup_page.py::test_site_lookup_export_controls -v`

Expected: FAIL

- [ ] **Step 3: Wire UI**

In `site_lookup.py` searchbar (after Live Refresh):

```html
<button type="button" class="secondary" id="export-excel-btn" disabled>Export Excel</button>
<button type="button" class="secondary" id="export-csv-btn" disabled>Export CSV</button>
<label class="offline-opt"><input type="checkbox" id="include-offline-sheet"> Include Offline sheet</label>
```

Add CSS so the checkbox sits cleanly in the searchbar (flex align).

JS:

- `exportExcelBtn` / `exportCsvBtn` / `includeOfflineEl`
- `function updateExportEnabled()` — enable both when `currentPayload` is non-null
- Call `updateExportEnabled()` after successful Look Up / cache / Live Refresh; disable on clear/error paths as needed
- `async function exportLookup(format)`:
  - if (!currentPayload) return
  - POST `/api/site-lookup/export` with JSON `{ format, include_offline: includeOfflineEl.checked, payload: currentPayload }`
  - download blob with filename from `Content-Disposition` (same pattern as Hosts & Volumes page)
  - show brief status via existing error banner or status line on success/failure

Mirror download helper from `host_volume_health_page.py` (`exportReport`).

Bump `APP_VERSION` to `1.6.138` and update version pin tests.

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_site_lookup_page.py tests/test_site_lookup_export.py tests/test_site_lookup_api.py tests/test_system_connectivity_version.py tests/test_hadoop_sudo_wire.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add launchpad/site_lookup.py launchpad/config.py tests/test_site_lookup_page.py tests/test_system_connectivity_version.py tests/test_hadoop_sudo_wire.py
git commit -m "Add Site Lookup Export Excel/CSV UI (1.6.138)."
```

---

## Spec coverage checklist

| Spec requirement | Task |
|------------------|------|
| Export Excel + Export CSV buttons | 3 |
| Include Offline sheet checkbox (Excel only) | 1 + 3 |
| Sheets: Hosts, Volumes, CPGs/Pools, optional CGs | 1 |
| Combined Offline sheet offline/degraded | 1 |
| CSV zip, no Offline | 1 |
| Current payload, no refresh-on-export | 2 + 3 |
| Server API Approach B | 2 |
| Disabled until payload loaded | 3 |
| Version bump | 3 |

## Placeholder / consistency scan

- No TBD/TODO placeholders in steps.
- Function names consistent: `export_site_lookup_xlsx`, `export_site_lookup_csv_zip`, `export_site_lookup_bytes`, `/api/site-lookup/export`.
- Offline filter reuses `status_is_offline_or_degraded`.
