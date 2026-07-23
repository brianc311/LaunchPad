# FC WWPN Modal Mappings Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Export Excel, Export CSV (ZIP), and Print / Save PDF to the FC WWPN Hosts & LUN Mappings modal so operators can export all three tabs for the open site.

**Architecture:** Pure builders in `fc_wwpn_export.py` produce a 3-sheet workbook and a 3-file CSV ZIP from card API payloads (hosts, mappings, fabric). `GET /api/fc-wwpn-mappings-export` requires `card_id` and returns xlsx or zip. The modal wires two fetch downloads plus a print path that renders all three sections then calls `window.print()`.

**Tech Stack:** openpyxl, zipfile/csv, HealthServer embedded HTML/JS, pytest.

**Spec:** `docs/superpowers/specs/2026-07-23-fc-wwpn-modal-mappings-export-design.md`

## Global Constraints

- **Base / worktree:** `feature/fc-wwpn-modal-export` at `.worktrees/fc-wwpn-modal-export` (from `feature/fc-wwpn-site-picker` @ `019dd15`, tip version `1.6.48`)
- Always export **all three** tabs (Hosts, LUN Mappings, Fabric Logins) for the **open site**
- Excel = 3 sheets; CSV = ZIP with `hosts.csv`, `lun_mappings.csv`, `fabric_logins.csv`
- PDF = browser Print / Save as PDF (no server PDF)
- Keep page-level Export Excel and Print unchanged
- Do **not** change page-level FC workbook sheets (Ports / Hosts / Maps)
- API: `card_id` **required**; missing/unknown → `400` JSON error
- `format` must be `xlsx` or `csv`
- Modal columns only (no required Location/Site/IP metadata columns)
- Bump `APP_VERSION` to **1.6.49**
- Commit at each task’s commit step
- Run tests from: `cd C:\Users\BrianColley\LaunchPad\.worktrees\fc-wwpn-modal-export`

---

## File map

| File | Responsibility |
|------|----------------|
| `launchpad/fc_wwpn_export.py` | `mappings_rows_from_card`, `build_fc_mappings_workbook`, `export_fc_mappings_csv_zip` |
| `launchpad/health_server.py` | `GET /api/fc-wwpn-mappings-export` |
| `launchpad/fc_wwpn_report.py` | Modal Export Excel / Export CSV / Print / Save PDF |
| `launchpad/config.py` | `APP_VERSION = "1.6.49"` |
| `tests/test_fc_wwpn_mappings_export.py` | Helper + API contract tests |
| `tests/test_contingency_groups_page.py` | Modal export wiring assertions (or add to same new test file for page HTML) |

---

### Task 0: Confirm worktree baseline

**Files:** none (git only)

**Interfaces:**
- Consumes: existing `.worktrees/fc-wwpn-modal-export` on `feature/fc-wwpn-modal-export`
- Produces: confirmed baseline for Tasks 1–4

- [ ] **Step 1: Confirm branch, version, design spec**

```powershell
cd C:\Users\BrianColley\LaunchPad\.worktrees\fc-wwpn-modal-export
git status -sb
python -c "from launchpad.config import APP_VERSION; print(APP_VERSION)"
Test-Path docs\superpowers\specs\2026-07-23-fc-wwpn-modal-mappings-export-design.md
python -c "from launchpad.fc_wwpn_export import filter_cards_for_fc_export; print(callable(filter_cards_for_fc_export))"
```

Expected: branch `feature/fc-wwpn-modal-export`, version `1.6.48`, design `True`, filter callable `True`.

- [ ] **Step 2: No feature commit**

---

### Task 1: Mappings workbook + CSV ZIP helpers

**Files:**
- Modify: `launchpad/fc_wwpn_export.py`
- Create: `tests/test_fc_wwpn_mappings_export.py`

**Interfaces:**
- Consumes: card dicts with `fc_hosts`, `fc_mappings`, `fc_fabric` (health API shape)
- Produces:
  - `MAPPINGS_HOST_HEADERS: tuple[str, ...]`
  - `MAPPINGS_LUN_HEADERS: tuple[str, ...]`
  - `MAPPINGS_FABRIC_HEADERS: tuple[str, ...]`
  - `mappings_rows_from_card(card: dict[str, Any]) -> tuple[list[tuple[Any, ...]], list[tuple[Any, ...]], list[tuple[Any, ...]]]`
  - `build_fc_mappings_workbook(cards: list[dict[str, Any]]) -> tuple[Workbook, int, int, int]`  # wb, host_rows, map_rows, fabric_rows
  - `export_fc_mappings_csv_zip(cards: list[dict[str, Any]]) -> bytes`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_fc_wwpn_mappings_export.py`:

```python
import csv
import zipfile
from io import BytesIO, StringIO

from launchpad.fc_wwpn_export import (
    MAPPINGS_FABRIC_HEADERS,
    MAPPINGS_HOST_HEADERS,
    MAPPINGS_LUN_HEADERS,
    build_fc_mappings_workbook,
    export_fc_mappings_csv_zip,
    mappings_rows_from_card,
)


def _fixture_card() -> dict:
    return {
        "id": 7,
        "name": "Carolina, PR",
        "fc_hosts": [
            {
                "host_id": "1",
                "host_name": "APR1",
                "status": "online",
                "protocol": "scsi",
                "wwpn_count": "2",
                "wwpns": "AABB",
            }
        ],
        "fc_mappings": [
            {
                "host_name": "APR1",
                "vdisk_name": "vol1",
                "scsi_id": "0",
                "vdisk_id": "10",
                "host_wwpns": "AABB",
            }
        ],
        "fc_fabric": [
            {
                "node_name": "node1",
                "local_wwpn": "500507681018C3FB",
                "remote_wwpn": "C050760C0A500008",
                "host_name": "APR1",
                "state": "active",
                "local_port": "4",
            }
        ],
    }


def test_mappings_rows_from_card_matches_modal_columns():
    hosts, maps, fabric = mappings_rows_from_card(_fixture_card())
    assert hosts == [("1", "APR1", "online", "scsi", "2", "AABB")]
    assert maps == [("APR1", "vol1", "0", "10", "AABB")]
    assert fabric == [
        ("node1", "500507681018C3FB", "C050760C0A500008", "APR1", "active", "4")
    ]


def test_build_fc_mappings_workbook_has_three_sheets():
    wb, h, m, f = build_fc_mappings_workbook([_fixture_card()])
    assert wb.sheetnames == ["Hosts", "LUN Mappings", "Fabric Logins"]
    assert (h, m, f) == (1, 1, 1)
    assert [c.value for c in wb["Hosts"][1]] == list(MAPPINGS_HOST_HEADERS)
    assert [c.value for c in wb["LUN Mappings"][1]] == list(MAPPINGS_LUN_HEADERS)
    assert [c.value for c in wb["Fabric Logins"][1]] == list(MAPPINGS_FABRIC_HEADERS)
    assert wb["Hosts"]["B2"].value == "APR1"
    assert wb["Fabric Logins"]["A2"].value == "node1"


def test_export_fc_mappings_csv_zip_contains_three_files():
    raw = export_fc_mappings_csv_zip([_fixture_card()])
    with zipfile.ZipFile(BytesIO(raw)) as archive:
        assert set(archive.namelist()) == {
            "hosts.csv",
            "lun_mappings.csv",
            "fabric_logins.csv",
        }
        hosts = list(csv.reader(StringIO(archive.read("hosts.csv").decode("utf-8-sig"))))
        assert hosts[0] == list(MAPPINGS_HOST_HEADERS)
        assert hosts[1][1] == "APR1"
        fabric = list(
            csv.reader(StringIO(archive.read("fabric_logins.csv").decode("utf-8-sig")))
        )
        assert fabric[0] == list(MAPPINGS_FABRIC_HEADERS)
        assert fabric[1][0] == "node1"
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
python -m pytest tests/test_fc_wwpn_mappings_export.py -v
```

Expected: FAIL with `ImportError` / missing symbols.

- [ ] **Step 3: Implement helpers in `fc_wwpn_export.py`**

Add near the existing export helpers (after `filter_cards_for_fc_export` / near `rows_from_card_api`). Import `csv`, `zipfile`, and `StringIO` at module top if not already present:

```python
import csv
import zipfile
from io import BytesIO, StringIO
```

```python
MAPPINGS_HOST_HEADERS = (
    "ID",
    "Host",
    "Status",
    "Protocol",
    "WWPN count",
    "Host WWPNs",
)
MAPPINGS_LUN_HEADERS = (
    "Host",
    "Volume / VDisk",
    "SCSI / LUN ID",
    "VDisk ID",
    "Host WWPNs",
)
MAPPINGS_FABRIC_HEADERS = (
    "Node",
    "Local WWPN",
    "Remote WWPN",
    "Host",
    "State",
    "Local port",
)


def mappings_rows_from_card(
    card: dict[str, Any],
) -> tuple[list[tuple[Any, ...]], list[tuple[Any, ...]], list[tuple[Any, ...]]]:
    hosts: list[tuple[Any, ...]] = []
    maps: list[tuple[Any, ...]] = []
    fabric: list[tuple[Any, ...]] = []
    for fc_host in card.get("fc_hosts") or []:
        hosts.append(
            (
                fc_host.get("host_id"),
                fc_host.get("host_name"),
                fc_host.get("status"),
                fc_host.get("protocol"),
                fc_host.get("wwpn_count"),
                fc_host.get("wwpns"),
            )
        )
    for mapping in card.get("fc_mappings") or []:
        maps.append(
            (
                mapping.get("host_name"),
                mapping.get("vdisk_name"),
                mapping.get("scsi_id"),
                mapping.get("vdisk_id"),
                mapping.get("host_wwpns"),
            )
        )
    for login in card.get("fc_fabric") or []:
        fabric.append(
            (
                login.get("node_name"),
                login.get("local_wwpn"),
                login.get("remote_wwpn"),
                login.get("host_name"),
                login.get("state"),
                login.get("local_port"),
            )
        )
    return hosts, maps, fabric


def build_fc_mappings_workbook(
    cards: list[dict[str, Any]],
) -> tuple[Workbook, int, int, int]:
    host_rows: list[tuple[Any, ...]] = []
    map_rows: list[tuple[Any, ...]] = []
    fabric_rows: list[tuple[Any, ...]] = []
    for card in cards:
        hosts, maps, fabric = mappings_rows_from_card(card)
        host_rows.extend(hosts)
        map_rows.extend(maps)
        fabric_rows.extend(fabric)

    wb = Workbook()
    ws_hosts = wb.active
    ws_hosts.title = "Hosts"
    _write_rows(ws_hosts, MAPPINGS_HOST_HEADERS, host_rows)
    ws_maps = wb.create_sheet("LUN Mappings")
    _write_rows(ws_maps, MAPPINGS_LUN_HEADERS, map_rows)
    ws_fabric = wb.create_sheet("Fabric Logins")
    _write_rows(ws_fabric, MAPPINGS_FABRIC_HEADERS, fabric_rows)
    return wb, len(host_rows), len(map_rows), len(fabric_rows)


def _mappings_csv_bytes(headers: tuple[str, ...], rows: list[tuple[Any, ...]]) -> bytes:
    output = StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(headers)
    writer.writerows(rows)
    return output.getvalue().encode("utf-8-sig")


def export_fc_mappings_csv_zip(cards: list[dict[str, Any]]) -> bytes:
    host_rows: list[tuple[Any, ...]] = []
    map_rows: list[tuple[Any, ...]] = []
    fabric_rows: list[tuple[Any, ...]] = []
    for card in cards:
        hosts, maps, fabric = mappings_rows_from_card(card)
        host_rows.extend(hosts)
        map_rows.extend(maps)
        fabric_rows.extend(fabric)
    output = BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "hosts.csv", _mappings_csv_bytes(MAPPINGS_HOST_HEADERS, host_rows)
        )
        archive.writestr(
            "lun_mappings.csv", _mappings_csv_bytes(MAPPINGS_LUN_HEADERS, map_rows)
        )
        archive.writestr(
            "fabric_logins.csv",
            _mappings_csv_bytes(MAPPINGS_FABRIC_HEADERS, fabric_rows),
        )
    return output.getvalue()
```

- [ ] **Step 4: Run tests to verify they pass**

```powershell
python -m pytest tests/test_fc_wwpn_mappings_export.py -v
```

Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```powershell
git add launchpad/fc_wwpn_export.py tests/test_fc_wwpn_mappings_export.py
git commit -m "Add FC mappings workbook and CSV ZIP builders for modal export."
```

---

### Task 2: `/api/fc-wwpn-mappings-export` endpoint

**Files:**
- Modify: `launchpad/health_server.py` (add handler next to `/api/fc-wwpn-export`, after that block returns)
- Modify: `tests/test_fc_wwpn_mappings_export.py`

**Interfaces:**
- Consumes: `filter_cards_for_fc_export`, `build_fc_mappings_workbook`, `export_fc_mappings_csv_zip`, `workbook_to_bytes`
- Produces: `GET /api/fc-wwpn-mappings-export?card_id=…&format=xlsx|csv&open=0|1`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_fc_wwpn_mappings_export.py`:

```python
from pathlib import Path

from launchpad import health_server as health_server_mod


def test_health_server_exposes_fc_wwpn_mappings_export_route():
    source = Path(health_server_mod.__file__).read_text(encoding="utf-8")
    assert 'path == "/api/fc-wwpn-mappings-export"' in source
    assert "build_fc_mappings_workbook" in source
    assert "export_fc_mappings_csv_zip" in source
    assert 'format not in {"xlsx", "csv"}' in source or "format must be" in source.lower()
    assert "card_id required" in source or "card_id is required" in source
```

(Adjust the format/card_id assertion strings to match the exact error messages you implement in Step 3 — keep them stable.)

Prefer these exact error strings in the implementation so tests can assert:

```python
{"error": "card_id required"}
{"error": "Unknown card_id"}
{"error": "format must be xlsx or csv"}
```

Update the test accordingly:

```python
def test_health_server_exposes_fc_wwpn_mappings_export_route():
    source = Path(health_server_mod.__file__).read_text(encoding="utf-8")
    assert 'path == "/api/fc-wwpn-mappings-export"' in source
    assert "build_fc_mappings_workbook" in source
    assert "export_fc_mappings_csv_zip" in source
    assert '{"error": "card_id required"}' in source or '"card_id required"' in source
    assert '"Unknown card_id"' in source
    assert '"format must be xlsx or csv"' in source
```

- [ ] **Step 2: Run test to verify it fails**

```powershell
python -m pytest tests/test_fc_wwpn_mappings_export.py::test_health_server_exposes_fc_wwpn_mappings_export_route -v
```

Expected: FAIL (route string missing).

- [ ] **Step 3: Implement the GET handler**

Insert immediately after the `/api/fc-wwpn-export` block (before `self.send_error(404)`):

```python
        if path == "/api/fc-wwpn-mappings-export":
            import re

            from launchpad.capacity_export import open_exported_workbook
            from launchpad.config import TEMP_DIR
            from launchpad.fc_wwpn_export import (
                build_fc_mappings_workbook,
                export_fc_mappings_csv_zip,
                filter_cards_for_fc_export,
                workbook_to_bytes,
            )
            from launchpad.storage_presets import is_svc_fc_profile

            query = parse_qs(parsed.query)
            card_id = (query.get("card_id") or [""])[0].strip()
            if not card_id:
                self._send_json({"error": "card_id required"}, status=400)
                return
            export_format = (query.get("format") or ["xlsx"])[0].strip().lower()
            if export_format not in {"xlsx", "csv"}:
                self._send_json(
                    {"error": "format must be xlsx or csv"}, status=400
                )
                return
            open_after = (query.get("open") or ["0"])[0].strip().lower() in {
                "1",
                "true",
                "yes",
            }
            try:
                server.sync_from_app()
                cards = [
                    card
                    for card in server.list_cards(allow_sync=False)
                    if is_svc_fc_profile(str(card.get("device_profile") or ""))
                    or bool(card.get("fc_available"))
                ]
                cards = filter_cards_for_fc_export(cards, card_id=card_id)
                if not cards:
                    self._send_json({"error": "Unknown card_id"}, status=400)
                    return
                site_name = str(cards[0].get("name") or card_id)
                safe_name = re.sub(r"[^\w\-]+", "_", site_name).strip("_") or "site"
                stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
                if export_format == "csv":
                    body = export_fc_mappings_csv_zip(cards)
                    filename = f"FC_Mappings_{safe_name}_{stamp}.zip"
                    content_type = "application/zip"
                else:
                    wb, host_count, map_count, fabric_count = build_fc_mappings_workbook(
                        cards
                    )
                    body = workbook_to_bytes(wb)
                    filename = f"FC_Mappings_{safe_name}_{stamp}.xlsx"
                    content_type = (
                        "application/vnd.openxmlformats-officedocument"
                        ".spreadsheetml.sheet"
                    )
                    if open_after:
                        try:
                            TEMP_DIR.mkdir(parents=True, exist_ok=True)
                            saved = TEMP_DIR / filename
                            saved.write_bytes(body)
                            open_exported_workbook(saved)
                            _log(
                                f"FC mappings Excel opened: {saved} "
                                f"({host_count} hosts, {map_count} maps, "
                                f"{fabric_count} fabric)"
                            )
                        except Exception as open_exc:
                            _log(
                                "FC mappings Excel saved for download but "
                                f"could not open: {open_exc}"
                            )
            except Exception as exc:
                self._send_json({"error": str(exc)}, status=500)
                return
            self._send_bytes(body, content_type=content_type, filename=filename)
            return
```

Note: `re` may already be imported at module top in `health_server.py` — if so, drop the inline `import re`.

- [ ] **Step 4: Run tests to verify they pass**

```powershell
python -m pytest tests/test_fc_wwpn_mappings_export.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add launchpad/health_server.py tests/test_fc_wwpn_mappings_export.py
git commit -m "Add FC WWPN mappings export API for per-site Excel and CSV ZIP."
```

---

### Task 3: Modal Export Excel / CSV / Print PDF UI

**Files:**
- Modify: `launchpad/fc_wwpn_report.py`
- Modify: `tests/test_contingency_groups_page.py` (add modal export contract tests) **or** append page tests to `tests/test_fc_wwpn_mappings_export.py`

**Interfaces:**
- Consumes: `/api/fc-wwpn-mappings-export` with `card_id` + `format`
- Produces: modal buttons + JS handlers; print shows all three sections

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_fc_wwpn_mappings_export.py`:

```python
from launchpad.fc_wwpn_report import FC_WWPN_REPORT_HTML


def test_fc_wwpn_modal_exposes_mappings_export_controls():
    for text in (
        'id="modal-export-excel-btn"',
        'id="modal-export-csv-btn"',
        'id="modal-print-btn"',
        "Export Excel",
        "Export CSV",
        "Print / Save PDF",
        "/api/fc-wwpn-mappings-export",
        'params.set("card_id", String(activeCard.id))',
        'params.set("format", format)',
        "function printModalMappings(",
        "Hosts & WWPNs",
        "LUN Mappings",
        "Fabric Logins",
        "window.print()",
    ):
        assert text in FC_WWPN_REPORT_HTML
```

- [ ] **Step 2: Run test to verify it fails**

```powershell
python -m pytest tests/test_fc_wwpn_mappings_export.py::test_fc_wwpn_modal_exposes_mappings_export_controls -v
```

Expected: FAIL (button ids missing).

- [ ] **Step 3: Update modal HTML**

Replace the modal header controls area so Close sits with the new actions. Change:

```html
      <button type="button" class="btn secondary modal-close" id="modal-close">Close</button>
      <h3 id="modal-title">Mappings</h3>
```

to:

```html
      <div class="modal-actions no-print" style="float:right;display:flex;gap:8px;flex-wrap:wrap;">
        <button type="button" class="btn secondary" id="modal-export-excel-btn">Export Excel</button>
        <button type="button" class="btn secondary" id="modal-export-csv-btn">Export CSV</button>
        <button type="button" class="btn secondary" id="modal-print-btn">Print / Save PDF</button>
        <button type="button" class="btn secondary modal-close" id="modal-close">Close</button>
      </div>
      <h3 id="modal-title">Mappings</h3>
```

Add print CSS (inside existing `@media print` or a new block) so modal export chrome hides and print content shows:

```css
    #modal-print { display: none; }
    @media print {
      #modal-print { display: block !important; }
      #modal-print h4 { margin: 16px 0 8px; color: #c2410c; }
      .modal-actions, .tabs, #modal-body { display: none !important; }
    }
```

Add inside the modal (after `#modal-body`):

```html
      <div id="modal-print"></div>
```

- [ ] **Step 4: Wire JavaScript**

After modal element consts, add:

```javascript
    const modalExportExcelBtn = document.getElementById("modal-export-excel-btn");
    const modalExportCsvBtn = document.getElementById("modal-export-csv-btn");
    const modalPrintBtn = document.getElementById("modal-print-btn");
    const modalPrintEl = document.getElementById("modal-print");
```

Add helpers (reuse existing `tableFromRows` / modal column mapping from `renderModalBody`):

```javascript
    function setModalExportEnabled(enabled) {
      modalExportExcelBtn.disabled = !enabled;
      modalExportCsvBtn.disabled = !enabled;
      modalPrintBtn.disabled = !enabled;
    }

    async function downloadModalMappings(format) {
      if (!activeCard || activeCard.id == null) return;
      const btn = format === "csv" ? modalExportCsvBtn : modalExportExcelBtn;
      btn.disabled = true;
      statusEl.textContent = format === "csv"
        ? "Building mappings CSV ZIP…"
        : "Building mappings Excel…";
      try {
        const params = new URLSearchParams({ open: format === "xlsx" ? "1" : "0" });
        params.set("card_id", String(activeCard.id));
        params.set("format", format);
        const res = await fetch(`/api/fc-wwpn-mappings-export?${params.toString()}`);
        if (!res.ok) {
          let detail = `HTTP ${res.status}`;
          try {
            const err = await res.json();
            if (err && err.error) detail = err.error;
          } catch (_err) { /* ignore */ }
          throw new Error(detail);
        }
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        const stamp = new Date().toISOString().slice(0, 16).replace(/[:-]/g, "");
        const safe = String(activeCard.name || activeCard.id).replace(/[^\w\-]+/g, "_");
        a.href = url;
        a.download = format === "csv"
          ? `FC_Mappings_${safe}_${stamp}.zip`
          : `FC_Mappings_${safe}_${stamp}.xlsx`;
        a.click();
        URL.revokeObjectURL(url);
        statusEl.textContent = format === "csv"
          ? "Mappings CSV ZIP downloaded (hosts / lun_mappings / fabric_logins)."
          : "Mappings Excel downloaded (Hosts / LUN Mappings / Fabric Logins).";
      } catch (err) {
        statusEl.textContent = `Mappings export failed: ${err.message || err}`;
      } finally {
        setModalExportEnabled(Boolean(activeCard));
      }
    }

    function printModalMappings() {
      if (!activeCard) return;
      const hostRows = (activeCard.fc_hosts || []).map((h) => [
        h.host_id, h.host_name, h.status, h.protocol, h.wwpn_count, h.wwpns,
      ]);
      const mapRows = (activeCard.fc_mappings || []).map((m) => [
        m.host_name, m.vdisk_name, m.scsi_id, m.vdisk_id, m.host_wwpns,
      ]);
      const fabricRows = (activeCard.fc_fabric || []).map((f) => [
        f.node_name, f.local_wwpn, f.remote_wwpn, f.host_name, f.state, f.local_port,
      ]);
      modalPrintEl.innerHTML = `
        <h3>${escapeHtml(activeCard.name)} — Hosts &amp; LUN Mappings</h3>
        <h4>Hosts &amp; WWPNs</h4>
        ${tableFromRows(["ID", "Host", "Status", "Protocol", "WWPN count", "Host WWPNs"], hostRows)}
        <h4>LUN Mappings</h4>
        ${tableFromRows(["Host", "Volume / VDisk", "SCSI / LUN ID", "VDisk ID", "Host WWPNs"], mapRows)}
        <h4>Fabric Logins</h4>
        ${tableFromRows(["Node", "Local WWPN", "Remote WWPN", "Host", "State", "Local port"], fabricRows)}
      `;
      window.print();
    }
```

In `openModal`, after setting `activeCard`, call `setModalExportEnabled(true)`.  
In `closeModal`, clear `modalPrintEl.innerHTML = ""` and `setModalExportEnabled(false)`.

Wire listeners (near other modal listeners):

```javascript
    modalExportExcelBtn.addEventListener("click", () => downloadModalMappings("xlsx"));
    modalExportCsvBtn.addEventListener("click", () => downloadModalMappings("csv"));
    modalPrintBtn.addEventListener("click", printModalMappings);
    setModalExportEnabled(false);
```

Ensure page-level `printBtn` / `excelBtn` handlers are untouched.

- [ ] **Step 5: Run tests to verify they pass**

```powershell
python -m pytest tests/test_fc_wwpn_mappings_export.py tests/test_contingency_groups_page.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add launchpad/fc_wwpn_report.py tests/test_fc_wwpn_mappings_export.py
git commit -m "Add modal Excel, CSV, and Print/Save PDF for FC Hosts and LUN mappings."
```

---

### Task 4: Version bump and smoke

**Files:**
- Modify: `launchpad/config.py`

**Interfaces:**
- Consumes: Tasks 1–3 complete
- Produces: `APP_VERSION = "1.6.49"`

- [ ] **Step 1: Bump version**

```python
APP_VERSION = "1.6.49"
```

- [ ] **Step 2: Run focused regression**

```powershell
python -m pytest tests/test_fc_wwpn_mappings_export.py tests/test_fc_wwpn_export_filter.py tests/test_contingency_groups_page.py -v
python -c "from launchpad.config import APP_VERSION; from launchpad.fc_wwpn_report import FC_WWPN_REPORT_HTML; assert APP_VERSION == '1.6.49'; assert 'id=\"modal-export-excel-btn\"' in FC_WWPN_REPORT_HTML; assert '/api/fc-wwpn-mappings-export' in FC_WWPN_REPORT_HTML; print('ok', APP_VERSION)"
```

Expected: all PASS / `ok 1.6.49`.

- [ ] **Step 3: Commit**

```powershell
git add launchpad/config.py
git commit -m "Bump version to 1.6.49 for FC modal mappings export."
```

---

## Spec coverage checklist

| Spec requirement | Task |
|------------------|------|
| Modal Export Excel (3 sheets, all tabs) | Tasks 1, 2, 3 |
| Modal Export CSV ZIP (3 files) | Tasks 1, 2, 3 |
| Print / Save PDF all three sections | Task 3 |
| Per open site / `card_id` required | Task 2 |
| Keep page-level Export Excel / Print | Task 3 (untouched) |
| No server PDF / no active-tab-only | Global |
| Version next patch | Task 4 → `1.6.49` |

## Self-review notes

- Page-level `/api/fc-wwpn-export` unchanged (still Ports/Hosts/Maps).
- Unknown `card_id` returns 400 (not empty workbook) for this mappings endpoint only.
- Print uses `#modal-print` so all three sections print regardless of active tab.
