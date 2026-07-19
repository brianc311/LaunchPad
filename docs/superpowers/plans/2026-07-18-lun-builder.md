# LUN Builder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a persistent LUN Builder so operators can save Hartford-style site builds (hosts/FC + LUN batches), export Excel/CSV, and optionally Preview/Run create+map on Spectrum Virtualize and HPE 3PAR/Primera.

**Architecture:** Contingency-style library: `lun_builds` setting, embedded HTML page at `/lun-builder`, pure data helpers, export module, create/preview engine with SSH. Multi-system rows per build. Live Run for SVC + 3PAR/Primera; DS8884/XIV generate CLI text only.

**Tech Stack:** Python, embedded HTML/CSS/JS, `openpyxl`, existing health_server SSH helpers, pytest.

**Spec:** `docs/superpowers/specs/2026-07-18-lun-builder-design.md`

## Global Constraints

- Setting key: `lun_builds`.
- Page path: `/lun-builder`.
- Multi-system builds allowed (each LUN row has `storage_profile` + optional `card_hint`).
- Host entry: manual + Excel/CSV import + FC WWPN inventory pull.
- Storwize picker: Generic + G2 + G3 (add Generic profile key if missing).
- Live Run v1: Spectrum Virtualize + HPE 3PAR/Primera only; DS8884/XIV plan + generated CLI only.
- Preview required before Run; create API requires `confirm: true`; save-before-ops; sanitize CLI tokens; no auto host create.
- Modal CSS: `.modal-backdrop[hidden] { display:none !important; }`.
- Bump `APP_VERSION` to `1.6.22` in the final task.
- Do not commit unless the user asked for commits in this session.
- Follow Contingency Groups patterns for CRUD/export/page structure.

---

## File map

| File | Responsibility |
|------|----------------|
| `launchpad/storage_presets.py` | Add `ibm_storwize_v7000` Generic if missing; keep G2/G3 |
| `launchpad/lun_builder_data.py` | Profiles list, normalize, expand batches, validate, seed optional |
| `launchpad/lun_builder_export.py` | xlsx + csv export |
| `launchpad/lun_builder_import.py` | Parse xlsx/csv into hosts/luns |
| `launchpad/lun_builder_create.py` | Expand → steps → preview/run (SVC + 3PAR) |
| `launchpad/lun_builder.py` | Page HTML/JS + wizard overlay |
| `launchpad/health_server.py` | Routes, dashboard link |
| `launchpad/ui/dashboard_view.py` | Desktop button to open LUN Builder |
| `launchpad/config.py` | `1.6.22` |
| `tests/test_lun_builder_data.py` | Data helpers |
| `tests/test_lun_builder_export.py` | Export |
| `tests/test_lun_builder_import.py` | Import |
| `tests/test_lun_builder_create.py` | Preview/run steps |
| `tests/test_lun_builder_page.py` | Page contracts + API smoke |
| `tests/test_health_server_lun_builder.py` | Route wiring |

---

### Task 1: Data model, profiles, expand + validate

**Files:**
- Create: `launchpad/lun_builder_data.py`
- Modify: `launchpad/storage_presets.py` (Generic Storwize if absent)
- Create: `tests/test_lun_builder_data.py`

**Interfaces:**
- `LUN_BUILDS_SETTING = "lun_builds"`
- `LUN_BUILDER_PROFILES: list[tuple[str, str]]` — `(profile_key, label)` for picker
- `supports_live_run(profile_key: str) -> bool` — True for SVC family + 3PAR/Primera; False for DS/XIV
- `normalize_host_row(raw) -> dict | None`
- `normalize_lun_row(raw) -> dict | None`
- `normalize_build(raw) -> dict | None`
- `normalize_builds(raw) -> list[dict]`
- `upsert_build(builds, build) -> list[dict]`
- `delete_build(builds, build_id) -> list[dict]`
- `new_build_id(name, existing) -> str`
- `expand_lun_batch(lun: dict) -> list[dict]` — each `{ "name", "size", "pool_or_cpg", "shared", "storage_profile", "host_names", "scsi_or_lun_id", "card_hint", "cluster", "source_batch" }`
- Naming rule: if `count == 1` use `purpose` as name; else `{purpose}_{nn:02d}` (1-based)
- `validate_build_for_preview(build) -> list[str]` — blocking messages (≥1 lun; each lun purpose, count≥1, size, pool_or_cpg, storage_profile)

Host fields (normalized):
`lpar_name`, `slot`, `state`, `required` (bool), `type`, `remote_lpar`, `remote_slot`, `wwpn1`, `wwpn2`, `physical_fc_slot`, `managed_system_name`, `managed_system_serial`, `notes`

LUN fields (normalized):
`purpose`, `count` (int), `size`, `shared` (bool), `storage_profile`, `pool_or_cpg`, `host_names` (list[str]), `scsi_or_lun_id`, `card_hint`, `cluster`

- [ ] **Step 1: Write failing tests**

```python
from launchpad.lun_builder_data import (
    LUN_BUILDS_SETTING,
    expand_lun_batch,
    normalize_build,
    supports_live_run,
    validate_build_for_preview,
)


def test_setting_key():
    assert LUN_BUILDS_SETTING == "lun_builds"


def test_expand_lun_batch_names():
    rows = expand_lun_batch(
        {
            "purpose": "ora1vg",
            "count": 3,
            "size": "100GB",
            "pool_or_cpg": "P0",
            "storage_profile": "flashsystem_5200",
            "host_names": ["h1"],
            "shared": True,
        }
    )
    assert [r["name"] for r in rows] == ["ora1vg_01", "ora1vg_02", "ora1vg_03"]


def test_expand_single_keeps_purpose_name():
    rows = expand_lun_batch(
        {
            "purpose": "caavg_private",
            "count": 1,
            "size": "10GB",
            "pool_or_cpg": "P0",
            "storage_profile": "flashsystem_5200",
        }
    )
    assert rows[0]["name"] == "caavg_private"


def test_supports_live_run_families():
    assert supports_live_run("flashsystem_5200") is True
    assert supports_live_run("hpe_3par_8200") is True
    assert supports_live_run("ibm_ds8884") is False
    assert supports_live_run("ibm_xiv_gen3") is False


def test_validate_build_requires_lun_fields():
    build = normalize_build(
        {
            "id": "x",
            "name": "Lab",
            "hosts": [],
            "luns": [{"purpose": "", "count": 1, "size": "", "pool_or_cpg": ""}],
        }
    )
    assert validate_build_for_preview(build)
```

- [ ] **Step 2: Run tests — expect FAIL (module missing)**

```powershell
python -m pytest tests/test_lun_builder_data.py -q
```

- [ ] **Step 3: Implement `lun_builder_data.py` + Generic Storwize profile; tests PASS**

Add to `DEVICE_PROFILES` if missing:
`"ibm_storwize_v7000": "IBM Storwize V7000"` and include it in `SVC_PROFILES` / command map like other Storwize keys.

`LUN_BUILDER_PROFILES` must include every locked picker entry from the spec (FlashSystem family, SVC, Storwize Generic/G2/G3, DS8884, XIV both, 3PAR 8200/8450, Primera 600).

- [ ] **Step 4: Commit only if user asked**

---

### Task 2: Page shell + CRUD APIs + entry points

**Files:**
- Create: `launchpad/lun_builder.py`
- Modify: `launchpad/health_server.py`
- Modify: `launchpad/ui/dashboard_view.py` (LUN Builder button next to Contingency Groups)
- Create: `tests/test_lun_builder_page.py`
- Create: `tests/test_health_server_lun_builder.py`

**Interfaces / routes:**
- `LUN_BUILDER_PATH = "/lun-builder"`
- `GET /lun-builder` → HTML with `{{APP_VERSION}}`
- `GET /api/lun-builds` → `{ "builds": [...], "persisted": bool }`
- `POST /api/lun-builds` body `{ "build": {...} }` upsert
- `DELETE` via POST body `{ "delete_id": "..." }` **or** match contingency: inspect existing contingency groups API and mirror exactly

Mirror Contingency Groups GET/POST/delete semantics from `health_server.py` contingency handlers.

**UI minimum:**
- Hero: picker, New, Save, Save as new, Delete, Export Excel, Export CSV, Import, Pull from FC WWPN, Preview, Run Create, Health Dashboard link
- Summary: name, location, notes
- Tables: Hosts/FC, LUN specs (Add row buttons)
- Modal with `[hidden]` + CSS fix
- `window.__lastLunPreviewOk` gate for Run Create

- [ ] **Step 1: Failing page/API tests**

```python
from launchpad.lun_builder import LUN_BUILDER_HTML, LUN_BUILDER_PATH


def test_lun_builder_path():
    assert LUN_BUILDER_PATH == "/lun-builder"


def test_lun_builder_page_contract():
    for text in (
        "LUN Builder",
        "Hosts",
        "LUN specs",
        "Export Excel",
        "Export CSV",
        "Preview / Dry-run",
        "Run Create",
        ".modal-backdrop[hidden] { display:none !important; }",
        "__lastLunPreviewOk",
    ):
        assert text in LUN_BUILDER_HTML
```

```python
# tests/test_health_server_lun_builder.py
from launchpad.health_server import HealthServer
from launchpad.lun_builder import LUN_BUILDER_PATH


def test_health_server_exposes_lun_builder_url():
    server = HealthServer()
    assert LUN_BUILDER_PATH in server.lun_builder_url() or hasattr(server, "lun_builder_url")
```

Implement `lun_builder_url()` like `contingency_groups_url()`.

- [ ] **Step 2: Implement page + routes + dashboard button; tests PASS**

Dashboard: add button `LUN Builder` calling open URL pattern used for Contingency Groups.

Health dashboard HTML: add link button to `/lun-builder` near Snapshot Schedule / Contingency if those exist in the dashboard hero.

- [ ] **Step 3: Commit only if user asked**

---

### Task 3: Excel + CSV export

**Files:**
- Create: `launchpad/lun_builder_export.py`
- Modify: `launchpad/health_server.py` — `GET /api/lun-builds-export?id=&format=xlsx|csv`
- Create: `tests/test_lun_builder_export.py`
- Modify: `tests/test_lun_builder_page.py` — export button wiring strings

**Interfaces:**
- `export_lun_build_xlsx(build: dict) -> bytes`
- `export_lun_build_csv_zip(build: dict) -> bytes` — ZIP with `hosts.csv` + `luns.csv` (use stdlib `zipfile` + `csv`)
- Sheets/files:
  1. Hosts — Hartford columns from host fields
  2. LUN Plan — one row per **expanded** volume (`expand_lun_batch`)
  3. By System — group expanded rows by `storage_profile`

- [ ] **Step 1: Failing export tests**

```python
from launchpad.lun_builder_data import normalize_build
from launchpad.lun_builder_export import export_lun_build_xlsx, export_lun_build_csv_zip
from openpyxl import load_workbook
from io import BytesIO
import zipfile


def _sample_build():
    return normalize_build(
        {
            "id": "hartford-ct",
            "name": "Hartford, CT",
            "hosts": [
                {
                    "lpar_name": "pconsps3",
                    "wwpn1": "c050760c9594000e",
                    "wwpn2": "c050760c9594000f",
                }
            ],
            "luns": [
                {
                    "purpose": "ora1vg",
                    "count": 2,
                    "size": "100GB",
                    "pool_or_cpg": "P0",
                    "storage_profile": "flashsystem_5200",
                    "shared": True,
                    "cluster": "SPS",
                }
            ],
        }
    )


def test_xlsx_has_three_sheets():
    data = export_lun_build_xlsx(_sample_build())
    wb = load_workbook(BytesIO(data))
    assert set(wb.sheetnames) >= {"Hosts", "LUN Plan", "By System"}


def test_csv_zip_contains_hosts_and_luns():
    data = export_lun_build_csv_zip(_sample_build())
    with zipfile.ZipFile(BytesIO(data)) as zf:
        names = set(zf.namelist())
    assert "hosts.csv" in names
    assert "luns.csv" in names
```

- [ ] **Step 2: Implement export + route; wire Export buttons; tests PASS**

CSV button downloads ZIP (`LUN_Builder_{id}_{stamp}.zip`). Excel downloads `.xlsx`.

- [ ] **Step 3: Commit only if user asked**

---

### Task 4: Import Excel/CSV + Pull from FC WWPN

**Files:**
- Create: `launchpad/lun_builder_import.py`
- Modify: `launchpad/lun_builder.py` — import UI (file input + merge/replace)
- Modify: `launchpad/health_server.py` — `POST /api/lun-builds/import` (multipart or JSON base64 — prefer JSON `{ "filename", "content_base64", "mode": "merge"|"replace", "build_id" }`)
- Modify: `launchpad/health_server.py` — `POST /api/lun-builds/pull-fc` `{ "build_id", "card_name"? }` merging FC hosts into build hosts
- Create: `tests/test_lun_builder_import.py`

**Interfaces:**
- `parse_lun_builder_upload(filename: str, content: bytes) -> dict`  
  returns `{ "hosts": [...], "luns": [...], "warnings": [str] }`
- Recognize `.xlsx` sheets named Hosts / LUN Plan (flexible header match) and `.csv` / zip of csv
- `merge_hosts(existing, incoming) -> list` — de-dupe by `lpar_name`+`wwpn1`
- Pull FC: reuse FC WWPN card data already available to health_server (same source as FC report). Map host name → `lpar_name`, WWPNs → `wwpn1`/`wwpn2`. Do not invent VIOS columns.

- [ ] **Step 1: Failing import tests**

```python
from launchpad.lun_builder_import import parse_lun_builder_upload, merge_hosts
import csv
from io import StringIO


def test_parse_simple_luns_csv():
    buf = StringIO()
    w = csv.DictWriter(
        buf,
        fieldnames=["purpose", "count", "size", "pool_or_cpg", "storage_profile"],
    )
    w.writeheader()
    w.writerow(
        {
            "purpose": "ora1vg",
            "count": "2",
            "size": "100GB",
            "pool_or_cpg": "P0",
            "storage_profile": "flashsystem_5200",
        }
    )
    result = parse_lun_builder_upload("luns.csv", buf.getvalue().encode("utf-8"))
    assert len(result["luns"]) == 1
    assert result["luns"][0]["purpose"] == "ora1vg"


def test_merge_hosts_dedupes():
    existing = [{"lpar_name": "h1", "wwpn1": "AA"}]
    incoming = [{"lpar_name": "h1", "wwpn1": "AA"}, {"lpar_name": "h2", "wwpn1": "BB"}]
    merged = merge_hosts(existing, incoming)
    assert len(merged) == 2
```

- [ ] **Step 2: Implement import + pull-fc + UI; tests PASS**

Import never auto-runs create. Show warnings in status/modal.

- [ ] **Step 3: Commit only if user asked**

---

### Task 5: Preview / Run create engine

**Files:**
- Create: `launchpad/lun_builder_create.py`
- Modify: `launchpad/health_server.py` —  
  `POST /api/lun-builds/preview` `{ "build_id" }`  
  `POST /api/lun-builds/create` `{ "build_id", "confirm": true }`
- Create: `tests/test_lun_builder_create.py`
- Modify: `launchpad/lun_builder.py` — wire Preview/Run + modal (gate Run on `__lastLunPreviewOk`)

**Interfaces:**
- Reuse `cli_token` pattern from `contingency_snap_create.py` (import that helper or duplicate a tiny shared-safe copy in this module — prefer **import** `cli_token` / `parse_capacity_to_gb` from `contingency_snap_create` to avoid drift)
- `build_lun_steps(build, inventory_by_card: dict | None) -> list[dict]`  
  each step: `{ "kind", "label", "cmd", "card_hint", "profile", "live": bool, "skip": bool }`
- SVC live: `svctask mkvdisk -name … -mdiskgrp … -size … -unit gb` then `svctask mkvdiskhostmap -host … -scsi … {vdisk}` when host_names present
- 3PAR/Primera live: `createvv {cpg} {name} {size}` and `createvlun {name} {lun_id} {host}` (use scsi_or_lun_id or auto-increment per host starting at 0)
- DS/XIV: `live=False`, `cmd` is generated CLI text; Preview shows them; Create API **skips** non-live steps (does not SSH)
- `run_lun_steps(steps, run_cmd_for_card) -> list[dict]` results — only execute `live and not skip`
- Resolve card via `card_hint` like contingency `resolve_card_by_storage_hint`

Preview response includes steps + blocking warnings. Set client `__lastLunPreviewOk` only when no blocking warnings and at least one live step is runnable **or** build is plan-only (all DS/XIV) — for plan-only, Run Create stays disabled; Preview still succeeds for review.

Blocking warnings:
- Missing card for any live-run LUN row
- Invalid size / empty pool
- Unsafe CLI token failures

- [ ] **Step 1: Failing create tests**

```python
from launchpad.lun_builder_create import build_lun_steps
from launchpad.lun_builder_data import normalize_build


def test_svc_steps_include_mkvdisk():
    build = normalize_build(
        {
            "id": "b1",
            "name": "Lab",
            "hosts": [{"lpar_name": "host1"}],
            "luns": [
                {
                    "purpose": "vol",
                    "count": 1,
                    "size": "10GB",
                    "pool_or_cpg": "Pool0",
                    "storage_profile": "flashsystem_5200",
                    "host_names": ["host1"],
                    "scsi_or_lun_id": "0",
                    "card_hint": "cardA",
                }
            ],
        }
    )
    steps = build_lun_steps(build, inventory_by_card=None)
    assert any(s["kind"] == "mkvdisk" and s["live"] for s in steps)
    assert any(s["kind"] == "mkvdiskhostmap" and s["live"] for s in steps)


def test_ds_steps_are_not_live():
    build = normalize_build(
        {
            "id": "b2",
            "name": "DS",
            "hosts": [],
            "luns": [
                {
                    "purpose": "root",
                    "count": 1,
                    "size": "50GB",
                    "pool_or_cpg": "P0",
                    "storage_profile": "ibm_ds8884",
                    "card_hint": "dscli-host",
                }
            ],
        }
    )
    steps = build_lun_steps(build, None)
    assert steps
    assert all(s["live"] is False for s in steps)
```

- [ ] **Step 2: Implement engine + APIs + UI; tests PASS**

```powershell
python -m pytest tests/test_lun_builder_create.py tests/test_lun_builder_data.py -q
```

- [ ] **Step 3: Commit only if user asked**

---

### Task 6: First-time wizard overlay + version 1.6.22

**Files:**
- Modify: `launchpad/lun_builder.py` — dismissible wizard: Site → Hosts → LUN batches → Review
- Modify: `launchpad/config.py` → `APP_VERSION = "1.6.22"`
- Modify: `tests/test_lun_builder_page.py` — wizard contract strings
- Optional: mark spec Status Implemented

**Wizard behavior:**
- Show on first visit if `localStorage` key `launchpad.lunBuilder.wizardDone` unset
- Steps update the same in-memory build (not a separate store)
- Finish sets localStorage and hides overlay; tables remain usable throughout via "Skip wizard"
- Does not persist wizard step to DB

- [ ] **Step 1: Page tests for wizard**

```python
def test_lun_builder_wizard_overlay():
    for text in (
        "first-time wizard",
        "wizard-step",
        "Skip wizard",
        "launchpad.lunBuilder.wizardDone",
    ):
        assert text in LUN_BUILDER_HTML
```

- [ ] **Step 2: Implement wizard + bump version**

```powershell
python -m pytest tests/test_lun_builder_data.py tests/test_lun_builder_export.py tests/test_lun_builder_import.py tests/test_lun_builder_create.py tests/test_lun_builder_page.py tests/test_health_server_lun_builder.py -q
python -c "from launchpad.config import APP_VERSION; assert APP_VERSION=='1.6.22'"
```

- [ ] **Step 3: Commit only if user asked**

---

## Spec coverage checklist

| Spec item | Task |
|-----------|------|
| `lun_builds` persistence + CRUD | 1, 2 |
| Hosts/FC + LUN tables UI | 2 |
| Multi-system profiles + Storwize Generic/G2/G3 | 1 |
| Excel + CSV export | 3 |
| Import Excel/CSV | 4 |
| Pull from FC WWPN | 4 |
| Preview/Run SVC + 3PAR | 5 |
| DS/XIV plan-only CLI | 5 |
| First-time wizard | 6 |
| Version 1.6.22 | 6 |
| Dashboard / Health entry | 2 |
| Safety: preview gate, confirm, token sanitize | 5 |

## Placeholder / consistency self-review

- No live Run for DS/XIV in v1 (explicit).
- CSV export = ZIP of two CSVs (locked here).
- Expand naming `{purpose}_{nn:02d}` locked.
- Commit steps optional per session rules.
