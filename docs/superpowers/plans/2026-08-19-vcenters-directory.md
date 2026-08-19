# vCenters Directory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a dashboard **vCenters** button that opens a Health Server directory page where operators add name, location, address, and an optional vSphere URL, shipping as **1.6.186**.

**Architecture:** A JSON list in LaunchPad settings (`vcenters_directory`) is normalized by a small helper module. Health Server serves `/vcenters` plus GET/POST APIs. The dashboard opens the page with `_open_sync_browser_report` (no SSH cards required). Default link is `https://{address}/ui`.

**Tech Stack:** Python, Health Server (`ThreadingHTTPServer`), CustomTkinter dashboard, pytest.

**Spec:** `docs/superpowers/specs/2026-08-19-vcenters-directory-design.md`

## Global Constraints

- APP_VERSION bump to **1.6.186** only in the final version task. Do not bump in Tasks 1–4.
- Button label exactly **vCenters**. Placement: tools row immediately after Ansible Pad.
- Setting key: `vcenters_directory`. Missing, empty, or corrupt JSON → empty list.
- Default vSphere URL: `https://{address}/ui`. Optional `url` override must start with `http://` or `https://`.
- Address is IP or hostname only (no `://`). Name and address required. Location optional.
- View/list/links do not require Unlock. Add / Edit / Delete require Unlock (`_set_setting` present); locked writes raise `RuntimeError` and the handler returns **503** (same as Ansible Pad settings save).
- Do not require SSH cards to open the page (use `_open_sync_browser_report`, not `_open_entries_browser_report`).
- No live vCenter API, no Admin card type, no SQLite table, no notes field, no peer-page nav links.
- Place imports at the top of modules (no inline imports).
- Windows PowerShell commits (`git commit -m "..."`); commit at each task commit step.
- Prefer TDD: failing test → implement → pass → commit.
- Do not commit `.superpowers/sdd*` scratch, `LaunchPad-Install/`, or install zips.
- Work on branch `feature/vcenters-directory`.

## File structure

| File | Responsibility |
|------|----------------|
| `launchpad/vcenters_directory.py` | Setting key, normalize, default URL, upsert/delete |
| `tests/test_vcenters_directory.py` | Helper tests |
| `launchpad/vcenters.py` | `/vcenters` HTML/JS |
| `tests/test_vcenters_page.py` | Page contract tests |
| `launchpad/health_server.py` | Route, APIs, `open_vcenters()` |
| `tests/test_vcenters_api.py` | GET/POST save + locked |
| `launchpad/ui/dashboard_view.py` | Button + `_open_vcenters` |
| `tests/test_vcenters_dashboard.py` | Dashboard button contract |
| `tests/test_dashboard_ui_freeze.py` | Add `_open_vcenters` to `HEADER_OPENERS` |
| `launchpad/config.py` + version pins | **1.6.186** (Task 5 only) |

---

### Task 1: vCenters directory helpers

**Files:**
- Create: `launchpad/vcenters_directory.py`
- Create: `tests/test_vcenters_directory.py`

**Interfaces:**
- Consumes: none
- Produces:
  - `SETTING_VCENTERS_DIRECTORY = "vcenters_directory"`
  - `vcenter_default_url(address: str) -> str`
  - `effective_vcenter_url(record: dict) -> str`
  - `normalize_vcenter(raw: dict, *, assign_id: bool = False) -> dict` — raises `ValueError` on invalid input
  - `normalize_vcenters(raw: object) -> list[dict]` — skips invalid rows; never raises
  - `parse_vcenters_setting(raw: str | None) -> list[dict]` — corrupt JSON → `[]`
  - `upsert_vcenter(store: list[dict], raw: dict) -> list[dict]` — assigns `id` when missing; sorts by name case-insensitive
  - `delete_vcenter(store: list[dict], vcenter_id: str) -> list[dict]` — unknown id is a no-op

- [ ] **Step 1: Write the failing tests**

Create `tests/test_vcenters_directory.py`:

```python
import pytest

from launchpad.vcenters_directory import (
    SETTING_VCENTERS_DIRECTORY,
    delete_vcenter,
    effective_vcenter_url,
    normalize_vcenter,
    normalize_vcenters,
    parse_vcenters_setting,
    upsert_vcenter,
    vcenter_default_url,
)


def test_setting_key_and_default_url():
    assert SETTING_VCENTERS_DIRECTORY == "vcenters_directory"
    assert vcenter_default_url("10.1.2.3") == "https://10.1.2.3/ui"
    assert effective_vcenter_url({"address": "vc.example.com", "url": ""}) == (
        "https://vc.example.com/ui"
    )
    assert effective_vcenter_url(
        {"address": "10.1.2.3", "url": "https://10.1.2.3/vsphere-client"}
    ) == "https://10.1.2.3/vsphere-client"


def test_normalize_vcenter_requires_name_and_address():
    with pytest.raises(ValueError):
        normalize_vcenter({"name": "", "address": "10.0.0.1"})
    with pytest.raises(ValueError):
        normalize_vcenter({"name": "VC1", "address": ""})
    with pytest.raises(ValueError):
        normalize_vcenter({"name": "VC1", "address": "https://10.0.0.1"})
    with pytest.raises(ValueError):
        normalize_vcenter({"name": "VC1", "address": "10.0.0.1", "url": "vc.local/ui"})


def test_parse_corrupt_or_missing_setting_is_empty():
    assert parse_vcenters_setting(None) == []
    assert parse_vcenters_setting("") == []
    assert parse_vcenters_setting("{not json") == []
    assert normalize_vcenters("nope") == []
    assert normalize_vcenters([{"name": "", "address": "x"}]) == []


def test_upsert_assigns_id_sorts_and_delete_unknown_is_noop():
    store = upsert_vcenter([], {"name": "Bravo", "address": "10.0.0.2", "location": "DVN"})
    store = upsert_vcenter(
        store, {"name": "alpha", "address": "10.0.0.1", "location": "WAG"}
    )
    assert [row["name"] for row in store] == ["alpha", "Bravo"]
    assert all(row["id"] for row in store)
    vid = store[0]["id"]
    updated = upsert_vcenter(
        store,
        {
            "id": vid,
            "name": "alpha",
            "address": "10.0.0.9",
            "location": "WAG",
            "url": "https://10.0.0.9/ui",
        },
    )
    assert len(updated) == 2
    assert updated[0]["address"] == "10.0.0.9"
    assert delete_vcenter(updated, "missing") == updated
    assert len(delete_vcenter(updated, vid)) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_vcenters_directory.py -v`

Expected: FAIL (import error — `launchpad.vcenters_directory` missing)

- [ ] **Step 3: Write minimal implementation**

Create `launchpad/vcenters_directory.py`:

```python
"""Persisted vCenters directory (settings-backed JSON list)."""

from __future__ import annotations

import json
import uuid
from typing import Any

SETTING_VCENTERS_DIRECTORY = "vcenters_directory"


def vcenter_default_url(address: str) -> str:
    return f"https://{str(address).strip()}/ui"


def effective_vcenter_url(record: dict) -> str:
    override = str(record.get("url") or "").strip()
    if override:
        return override
    return vcenter_default_url(str(record.get("address") or ""))


def normalize_vcenter(raw: dict, *, assign_id: bool = False) -> dict:
    if not isinstance(raw, dict):
        raise ValueError("vCenter must be an object")
    name = str(raw.get("name") or "").strip()
    location = str(raw.get("location") or "").strip()
    address = str(raw.get("address") or "").strip()
    url = str(raw.get("url") or "").strip()
    if not name:
        raise ValueError("name is required")
    if not address:
        raise ValueError("address is required")
    if "://" in address:
        raise ValueError("address must be an IP or hostname")
    if url and not (
        url.lower().startswith("http://") or url.lower().startswith("https://")
    ):
        raise ValueError("url must start with http:// or https://")
    record_id = str(raw.get("id") or "").strip()
    if not record_id:
        if not assign_id:
            raise ValueError("id is required")
        record_id = uuid.uuid4().hex
    return {
        "id": record_id,
        "name": name,
        "location": location,
        "address": address,
        "url": url,
    }


def normalize_vcenters(raw: Any) -> list[dict]:
    if not isinstance(raw, list):
        return []
    out: list[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            out.append(normalize_vcenter(item, assign_id=True))
        except ValueError:
            continue
    out.sort(key=lambda row: row["name"].casefold())
    return out


def parse_vcenters_setting(raw: str | None) -> list[dict]:
    text = str(raw or "").strip() or "[]"
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return []
    return normalize_vcenters(parsed)


def upsert_vcenter(store: list[dict], raw: dict) -> list[dict]:
    cleaned = normalize_vcenter(raw, assign_id=True)
    by_id = {row["id"]: row for row in normalize_vcenters(store)}
    by_id[cleaned["id"]] = cleaned
    return normalize_vcenters(list(by_id.values()))


def delete_vcenter(store: list[dict], vcenter_id: str) -> list[dict]:
    target = str(vcenter_id or "").strip()
    kept = [row for row in normalize_vcenters(store) if row["id"] != target]
    return kept
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_vcenters_directory.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add launchpad/vcenters_directory.py tests/test_vcenters_directory.py
git commit -m "Add vCenters directory setting helpers."
```

---

### Task 2: vCenters browser page

**Files:**
- Create: `launchpad/vcenters.py`
- Create: `tests/test_vcenters_page.py`

**Interfaces:**
- Consumes: none (HTML/JS talks to `/api/vcenters` by path string)
- Produces:
  - `VCENTERS_PATH = "/vcenters"`
  - `VCENTERS_HTML` — page with list, Add/Edit form, detail card, `target="_blank"` links, `{{APP_VERSION}}`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_vcenters_page.py`:

```python
from launchpad.vcenters import VCENTERS_HTML, VCENTERS_PATH


def test_vcenters_page_markers():
    assert VCENTERS_PATH == "/vcenters"
    assert "vCenters" in VCENTERS_HTML
    assert "No vCenters yet" in VCENTERS_HTML
    assert "/api/vcenters" in VCENTERS_HTML
    assert "/api/vcenters/delete" in VCENTERS_HTML
    assert 'id="name"' in VCENTERS_HTML
    assert 'id="location"' in VCENTERS_HTML
    assert 'id="address"' in VCENTERS_HTML
    assert 'id="url"' in VCENTERS_HTML
    assert 'target="_blank"' in VCENTERS_HTML
    assert 'rel="noopener"' in VCENTERS_HTML
    assert "Unlock LaunchPad" in VCENTERS_HTML
    assert "{{APP_VERSION}}" in VCENTERS_HTML
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_vcenters_page.py -v`

Expected: FAIL (import error — `launchpad.vcenters` missing)

- [ ] **Step 3: Write the page module**

Create `launchpad/vcenters.py`:

```python
"""Browser page for the operator-maintained vCenters directory."""

VCENTERS_PATH = "/vcenters"

VCENTERS_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>LaunchPad vCenters</title>
  <style>
    :root { --bg:#0b0f14; --panel:#151c27; --panel-alt:#0f141d; --text:#e8edf5; --muted:#a9b6c8; --accent:#ff6b00; --border:#2a3444; --danger:#ef4444; }
    * { box-sizing:border-box; }
    body { margin:0; min-height:100vh; color:var(--text); font-family:Segoe UI,Inter,Arial,sans-serif; background:radial-gradient(circle at top,#172033 0%,var(--bg) 45%); }
    main { max-width:1120px; margin:0 auto; padding:28px 20px 48px; }
    section { margin-bottom:18px; padding:20px; border:1px solid var(--border); border-radius:14px; background:var(--panel); }
    .hero { background:linear-gradient(135deg,#1a2230,#101722); }
    h1 { margin:0 0 8px; color:var(--accent); font-size:1.9rem; }
    h2 { margin:0 0 14px; color:#ff9a56; font-size:1.12rem; }
    p, .hint, .status { color:var(--muted); line-height:1.5; }
    table { width:100%; border-collapse:collapse; }
    th, td { text-align:left; padding:8px 10px; border-bottom:1px solid var(--border); }
    th { color:var(--muted); font-size:.82rem; }
    a { color:#93c5fd; }
    button, a.button { min-height:36px; padding:0 14px; border:0; border-radius:9px; background:var(--accent); color:#111; font:inherit; font-weight:700; cursor:pointer; text-decoration:none; display:inline-flex; align-items:center; }
    button.secondary, a.secondary { color:var(--text); background:var(--panel-alt); border:1px solid var(--border); }
    button.danger { background:var(--danger); color:#fff; }
    button:disabled { opacity:.55; cursor:not-allowed; }
    .grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:12px; }
    label { display:flex; flex-direction:column; gap:6px; color:var(--muted); font-size:.86rem; font-weight:600; }
    input { width:100%; padding:9px 10px; color:var(--text); background:var(--panel-alt); border:1px solid var(--border); border-radius:8px; font:inherit; }
    .actions { display:flex; flex-wrap:wrap; gap:10px; margin-top:14px; }
    .name-btn { background:none; border:0; color:#93c5fd; padding:0; min-height:auto; font:inherit; font-weight:600; cursor:pointer; }
    .empty { color:var(--muted); padding:12px 0; }
    @media (max-width:700px) { .grid { grid-template-columns:1fr; } }
  </style>
</head>
<body>
  <main>
    <section class="hero">
      <h1>vCenters</h1>
      <p>Directory of vCenter names, locations, and addresses. Click a name for details. The link opens the vSphere web client.</p>
      <a class="button secondary" href="/">Back to dashboard</a>
    </section>
    <section id="list-section">
      <h2>Directory</h2>
      <div class="actions"><button id="add-btn" type="button">Add</button></div>
      <div id="list-wrap"></div>
      <p id="list-status" class="status" role="status"></p>
    </section>
    <section id="detail-section" hidden>
      <h2>vCenter</h2>
      <p><strong>Name</strong><br><span id="d-name"></span></p>
      <p><strong>Location</strong><br><span id="d-location"></span></p>
      <p><strong>Address</strong><br><span id="d-address"></span></p>
      <p><strong>Link</strong><br><a id="d-link" href="#" target="_blank" rel="noopener"></a></p>
      <div class="actions">
        <button id="edit-btn" type="button">Edit</button>
        <button id="delete-btn" class="danger" type="button">Delete</button>
        <button id="back-btn" class="secondary" type="button">Back</button>
      </div>
    </section>
    <section id="form-section" hidden>
      <h2 id="form-title">Add vCenter</h2>
      <form id="vc-form" class="grid">
        <input type="hidden" id="vc-id">
        <label>Name<input id="name" name="name" required></label>
        <label>Location<input id="location" name="location"></label>
        <label>Address<input id="address" name="address" required placeholder="10.0.0.1 or vc.example.com"></label>
        <label>URL override (optional)<input id="url" name="url" placeholder="https://host/ui"></label>
      </form>
      <div class="actions">
        <button id="save-btn" type="button">Save</button>
        <button id="cancel-btn" class="secondary" type="button">Cancel</button>
      </div>
      <p id="form-status" class="status" role="status"></p>
    </section>
    <p class="hint">LaunchPad Health v{{APP_VERSION}}</p>
  </main>
  <script>
    const listWrap = document.getElementById("list-wrap");
    const listStatus = document.getElementById("list-status");
    const listSection = document.getElementById("list-section");
    const detailSection = document.getElementById("detail-section");
    const formSection = document.getElementById("form-section");
    const addBtn = document.getElementById("add-btn");
    const editBtn = document.getElementById("edit-btn");
    const deleteBtn = document.getElementById("delete-btn");
    const saveBtn = document.getElementById("save-btn");
    let rows = [];
    let unlocked = false;
    let selectedId = new URLSearchParams(location.search).get("id") || "";

    function escapeHtml(value) {
      return String(value || "").replace(/[&<>"']/g, (ch) => (
        ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[ch]
      ));
    }

    function effectiveUrl(row) {
      return (row.url || "").trim() || ("https://" + row.address + "/ui");
    }

    function setMutationsEnabled(on) {
      addBtn.disabled = !on;
      editBtn.disabled = !on;
      deleteBtn.disabled = !on;
      saveBtn.disabled = !on;
      if (!on) listStatus.textContent = "Unlock LaunchPad to add or edit vCenters.";
    }

    async function loadList() {
      const res = await fetch("/api/vcenters");
      const data = await res.json();
      rows = data.vcenters || [];
      unlocked = data.unlocked === true;
      setMutationsEnabled(unlocked);
      render();
    }

    function showList() {
      selectedId = "";
      history.replaceState({}, "", "/vcenters");
      listSection.hidden = false;
      detailSection.hidden = true;
      formSection.hidden = true;
      renderTable();
    }

    function renderTable() {
      if (!rows.length) {
        listWrap.innerHTML = '<p class="empty">No vCenters yet</p>';
        return;
      }
      const body = rows.map((row) => {
        const href = escapeHtml(effectiveUrl(row));
        return `<tr>
          <td><button class="name-btn" data-id="${escapeHtml(row.id)}" type="button">${escapeHtml(row.name)}</button></td>
          <td>${escapeHtml(row.location)}</td>
          <td>${escapeHtml(row.address)}</td>
          <td><a href="${href}" target="_blank" rel="noopener">Open</a></td>
        </tr>`;
      }).join("");
      listWrap.innerHTML = `<table><thead><tr><th>Name</th><th>Location</th><th>Address</th><th>Link</th></tr></thead><tbody>${body}</tbody></table>`;
      listWrap.querySelectorAll(".name-btn").forEach((btn) => {
        btn.addEventListener("click", () => showDetail(btn.dataset.id));
      });
    }

    function rowById(id) {
      return rows.find((row) => row.id === id);
    }

    function showDetail(id) {
      const row = rowById(id);
      if (!row) { showList(); return; }
      selectedId = id;
      history.replaceState({}, "", "/vcenters?id=" + encodeURIComponent(id));
      document.getElementById("d-name").textContent = row.name;
      document.getElementById("d-location").textContent = row.location || "—";
      document.getElementById("d-address").textContent = row.address;
      const link = document.getElementById("d-link");
      link.href = effectiveUrl(row);
      link.textContent = effectiveUrl(row);
      listSection.hidden = true;
      formSection.hidden = true;
      detailSection.hidden = false;
    }

    function showForm(row) {
      document.getElementById("form-title").textContent = row ? "Edit vCenter" : "Add vCenter";
      document.getElementById("vc-id").value = row ? row.id : "";
      document.getElementById("name").value = row ? row.name : "";
      document.getElementById("location").value = row ? row.location : "";
      document.getElementById("address").value = row ? row.address : "";
      document.getElementById("url").value = row ? row.url : "";
      document.getElementById("form-status").textContent = "";
      listSection.hidden = true;
      detailSection.hidden = true;
      formSection.hidden = false;
    }

    function render() {
      if (selectedId) showDetail(selectedId);
      else showList();
    }

    addBtn.addEventListener("click", () => showForm(null));
    editBtn.addEventListener("click", () => showForm(rowById(selectedId)));
    document.getElementById("back-btn").addEventListener("click", showList);
    document.getElementById("cancel-btn").addEventListener("click", () => {
      if (selectedId) showDetail(selectedId);
      else showList();
    });
    deleteBtn.addEventListener("click", async () => {
      if (!selectedId || !confirm("Delete this vCenter?")) return;
      const res = await fetch("/api/vcenters/delete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: selectedId }),
      });
      const data = await res.json();
      if (!res.ok) {
        listStatus.textContent = data.error || "Delete failed.";
        return;
      }
      rows = data.vcenters || [];
      showList();
    });
    saveBtn.addEventListener("click", async () => {
      const payload = {
        id: document.getElementById("vc-id").value,
        name: document.getElementById("name").value,
        location: document.getElementById("location").value,
        address: document.getElementById("address").value,
        url: document.getElementById("url").value,
      };
      const res = await fetch("/api/vcenters", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) {
        document.getElementById("form-status").textContent = data.error || "Save failed.";
        return;
      }
      rows = data.vcenters || [];
      unlocked = data.unlocked === true;
      const keepId = payload.id || (rows.find((row) => row.name === payload.name.trim()) || {}).id;
      selectedId = keepId || "";
      render();
    });
    loadList().catch((err) => {
      listStatus.textContent = err.message || String(err);
    });
  </script>
</body>
</html>
"""
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_vcenters_page.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add launchpad/vcenters.py tests/test_vcenters_page.py
git commit -m "Add vCenters directory browser page."
```

---

### Task 3: Health Server routes and APIs

**Files:**
- Modify: `launchpad/health_server.py`
- Create: `tests/test_vcenters_api.py`

**Interfaces:**
- Consumes: `SETTING_VCENTERS_DIRECTORY`, `parse_vcenters_setting`, `upsert_vcenter`, `delete_vcenter` from `launchpad.vcenters_directory`; `VCENTERS_HTML`, `VCENTERS_PATH` from `launchpad.vcenters`
- Produces:
  - `HealthServer.get_vcenters() -> dict` with keys `vcenters` (list) and `unlocked` (bool)
  - `HealthServer.upsert_vcenter_record(payload: dict) -> dict`
  - `HealthServer.delete_vcenter_record(vcenter_id: str) -> dict`
  - `HealthServer.vcenters_url` property
  - `HealthServer.open_vcenters() -> str`
  - `GET /vcenters`, `GET /api/vcenters`, `POST /api/vcenters`, `POST /api/vcenters/delete`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_vcenters_api.py`:

```python
import io
import json

import launchpad.health_server as health_server_module
from launchpad.health_server import HealthServer, _HealthHandler
from launchpad.vcenters import VCENTERS_PATH
from launchpad.vcenters_directory import SETTING_VCENTERS_DIRECTORY


def _settings_backend(initial: dict[str, str] | None = None):
    settings = dict(initial or {})

    def get_setting(key: str, default: str) -> str:
        return settings.get(key, default)

    def set_setting(key: str, value: str) -> None:
        settings[key] = value

    return settings, get_setting, set_setting


def _get(path: str, monkeypatch, server: HealthServer) -> dict:
    handler = object.__new__(_HealthHandler)
    handler.path = path
    sent: dict = {}

    def _send_html(body, status=200):
        sent["html"] = body
        sent["status"] = status

    def _send_json(data, status=200):
        sent["json"] = data
        sent["status"] = status

    handler._send_html = _send_html
    handler._send_json = _send_json
    monkeypatch.setattr(health_server_module, "get_health_server", lambda: server)
    handler.do_GET()
    return sent


def _post(path: str, payload: dict, monkeypatch, server: HealthServer) -> dict:
    body = json.dumps(payload).encode()
    handler = object.__new__(_HealthHandler)
    handler.path = path
    handler.headers = {"Content-Length": str(len(body))}
    handler.rfile = io.BytesIO(body)
    sent: dict = {}

    def _send_json(response, status=200):
        sent.update(payload=response, status=status)

    handler._send_json = _send_json
    monkeypatch.setattr(health_server_module, "get_health_server", lambda: server)
    handler.do_POST()
    return sent


def test_get_vcenters_page_and_empty_list(monkeypatch):
    server = HealthServer()
    _settings, getter, setter = _settings_backend()
    server.set_settings_backend(getter, setter)
    page = _get(VCENTERS_PATH, monkeypatch, server)
    assert page["status"] == 200
    assert "vCenters" in page["html"]
    sent = _get("/api/vcenters", monkeypatch, server)
    assert sent["json"]["vcenters"] == []
    assert sent["json"]["unlocked"] is True


def test_post_vcenter_saves_and_locked_write_fails(monkeypatch):
    server = HealthServer()
    settings, getter, setter = _settings_backend()
    server.set_settings_backend(getter, setter)
    saved = _post(
        "/api/vcenters",
        {"name": "WAG VC", "address": "10.1.2.3", "location": "Wagga"},
        monkeypatch,
        server,
    )
    assert saved["status"] == 200
    rows = saved["payload"]["vcenters"]
    assert len(rows) == 1
    assert rows[0]["name"] == "WAG VC"
    assert json.loads(settings[SETTING_VCENTERS_DIRECTORY])
    locked = HealthServer()
    denied = _post(
        "/api/vcenters",
        {"name": "X", "address": "10.0.0.1"},
        monkeypatch,
        locked,
    )
    assert denied["status"] == 503
    assert "unlocked" in denied["payload"]["error"].lower()


def test_open_vcenters_opens_browser(monkeypatch):
    server = HealthServer()
    opened: list[str] = []
    monkeypatch.setattr(server, "ensure_running", lambda: None)
    monkeypatch.setattr(
        "launchpad.health_server.webbrowser.open",
        lambda url: opened.append(url),
    )
    url = server.open_vcenters()
    assert url.endswith(VCENTERS_PATH)
    assert opened == [url]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_vcenters_api.py -v`

Expected: FAIL (`open_vcenters` missing and/or `/vcenters` 404)

- [ ] **Step 3: Wire Health Server**

In `launchpad/health_server.py` imports (next to the Ansible Pad import), add:

```python
from launchpad.vcenters import VCENTERS_HTML, VCENTERS_PATH
from launchpad.vcenters_directory import (
    SETTING_VCENTERS_DIRECTORY,
    delete_vcenter,
    parse_vcenters_setting,
    upsert_vcenter,
)
```

In `_HealthHandler.do_GET`, immediately after the `ANSIBLE_PAD_PATH` HTML branch:

```python
        if path == VCENTERS_PATH:
            self._send_html(_fill_page(VCENTERS_HTML))
            return
```

In `_HealthHandler.do_GET`, immediately after `if path == "/api/ansible-pad/settings":` GET block:

```python
        if path == "/api/vcenters":
            self._send_json(server.get_vcenters())
            return
```

In `_HealthHandler.do_POST`, immediately after the `/api/ansible-pad/settings` block, add:

```python
        if path == "/api/vcenters":
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b"{}"
            try:
                payload = json.loads(raw.decode("utf-8") or "{}")
            except json.JSONDecodeError:
                self._send_json({"error": "Invalid JSON"}, status=400)
                return
            if not isinstance(payload, dict):
                self._send_json({"error": "JSON object required"}, status=400)
                return
            try:
                self._send_json(server.upsert_vcenter_record(payload))
            except RuntimeError as exc:
                self._send_json({"error": str(exc)}, status=503)
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=400)
            return
        if path == "/api/vcenters/delete":
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b"{}"
            try:
                payload = json.loads(raw.decode("utf-8") or "{}")
            except json.JSONDecodeError:
                self._send_json({"error": "Invalid JSON"}, status=400)
                return
            if not isinstance(payload, dict):
                self._send_json({"error": "JSON object required"}, status=400)
                return
            try:
                self._send_json(
                    server.delete_vcenter_record(str(payload.get("id") or ""))
                )
            except RuntimeError as exc:
                self._send_json({"error": str(exc)}, status=503)
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=400)
            return
```

On `HealthServer`, immediately after `set_ansible_pad_settings`, add:

```python
    def get_vcenters(self) -> dict:
        with self._lock:
            getter = self._get_setting
            setter = self._set_setting
        unlocked = getter is not None and setter is not None
        if not getter:
            return {"vcenters": [], "unlocked": False}
        raw = getter(SETTING_VCENTERS_DIRECTORY, "[]") or "[]"
        return {
            "vcenters": parse_vcenters_setting(raw),
            "unlocked": unlocked,
        }

    def upsert_vcenter_record(self, payload: dict) -> dict:
        if not isinstance(payload, dict):
            raise ValueError("JSON object required")
        with self._lock:
            getter = self._get_setting
            setter = self._set_setting
        if not setter:
            raise RuntimeError("LaunchPad must be unlocked to save vCenters.")
        raw = (getter(SETTING_VCENTERS_DIRECTORY, "[]") or "[]") if getter else "[]"
        cleaned = upsert_vcenter(parse_vcenters_setting(raw), payload)
        setter(SETTING_VCENTERS_DIRECTORY, json.dumps(cleaned))
        return {"vcenters": cleaned, "unlocked": True}

    def delete_vcenter_record(self, vcenter_id: str) -> dict:
        with self._lock:
            getter = self._get_setting
            setter = self._set_setting
        if not setter:
            raise RuntimeError("LaunchPad must be unlocked to save vCenters.")
        raw = (getter(SETTING_VCENTERS_DIRECTORY, "[]") or "[]") if getter else "[]"
        cleaned = delete_vcenter(parse_vcenters_setting(raw), vcenter_id)
        setter(SETTING_VCENTERS_DIRECTORY, json.dumps(cleaned))
        return {"vcenters": cleaned, "unlocked": True}
```

Add the URL property next to `ansible_pad_url`:

```python
    @property
    def vcenters_url(self) -> str:
        return f"http://127.0.0.1:{self._port}{VCENTERS_PATH}"
```

Add `open_vcenters` immediately after `open_storage_inventory`:

```python
    def open_vcenters(self) -> str:
        """Open the vCenters directory page in the default browser."""
        self.ensure_running()
        webbrowser.open(self.vcenters_url)
        _log(f"Opened vCenters in browser: {self.vcenters_url}")
        return self.vcenters_url
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_vcenters_api.py tests/test_vcenters_page.py tests/test_vcenters_directory.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add launchpad/health_server.py tests/test_vcenters_api.py
git commit -m "Wire vCenters directory page and save APIs."
```

---

### Task 4: Dashboard vCenters button

**Files:**
- Modify: `launchpad/ui/dashboard_view.py`
- Create: `tests/test_vcenters_dashboard.py`
- Modify: `tests/test_dashboard_ui_freeze.py`

**Interfaces:**
- Consumes: `HealthServer.open_vcenters()` via `get_health_server()` inside `_open_sync_browser_report`
- Produces: `DashboardView._open_vcenters()`; tools-row entry `("vCenters", self._open_vcenters, None)` immediately after Ansible Pad

- [ ] **Step 1: Write the failing tests**

Create `tests/test_vcenters_dashboard.py`:

```python
from pathlib import Path


def test_dashboard_has_vcenters_button():
    text = Path("launchpad/ui/dashboard_view.py").read_text(encoding="utf-8")
    assert '("vCenters"' in text
    assert "_open_vcenters" in text
    ansible = text.index('("Ansible Pad"')
    vcenters = text.index('("vCenters"')
    host_power = text.index('("Host Power"')
    assert ansible < vcenters < host_power
    assert "open_url=lambda server: server.open_vcenters()" in text
    assert "_open_entries_browser_report" not in text.split("def _open_vcenters", 1)[1].split("def ", 1)[0]
```

In `tests/test_dashboard_ui_freeze.py`, add `"_open_vcenters"` to `HEADER_OPENERS` immediately after `"_open_ansible_pad"`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_vcenters_dashboard.py tests/test_dashboard_ui_freeze.py::test_header_openers_register_off_ui_thread -v`

Expected: FAIL (missing `("vCenters"` / `_open_vcenters`)

- [ ] **Step 3: Add the button and opener**

In `launchpad/ui/dashboard_view.py` `tool_specs`, insert after the Ansible Pad tuple:

```python
            ("Ansible Pad", self._open_ansible_pad, None),
            ("vCenters", self._open_vcenters, None),
            ("Host Power", self._open_host_power, None),
```

Add this method immediately after `_open_storage_inventory`:

```python
    def _open_vcenters(self) -> None:
        worker = self._open_sync_browser_report(
            status="Opening vCenters…",
            fail_log="vCenters failed",
            open_url=lambda server: server.open_vcenters(),
            summary="vCenters opened — add name, location, and address, then use the vSphere link.",
        )
        threading.Thread(target=worker, daemon=True).start()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_vcenters_dashboard.py tests/test_dashboard_ui_freeze.py tests/test_vcenters_api.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add launchpad/ui/dashboard_view.py tests/test_vcenters_dashboard.py tests/test_dashboard_ui_freeze.py
git commit -m "Add dashboard vCenters button."
```

---

### Task 5: Bump APP_VERSION to 1.6.186

**Files:**
- Modify: `launchpad/config.py`
- Modify: `tests/test_capacity_unit_js.py`
- Modify: `tests/test_hadoop_sudo_wire.py`
- Modify: `tests/test_system_connectivity_version.py`

**Interfaces:**
- Consumes: none
- Produces: `APP_VERSION = "1.6.186"`

- [ ] **Step 1: Write the failing pin updates**

Set the three version assertions to `"1.6.186"` (they currently expect `1.6.185`). Do not change `config.py` yet.

- [ ] **Step 2: Run pins to verify they fail**

Run: `python -m pytest tests/test_capacity_unit_js.py::test_app_version_153 tests/test_hadoop_sudo_wire.py::test_version_174 tests/test_system_connectivity_version.py -v`

Expected: FAIL (`1.6.185` != `1.6.186`)

- [ ] **Step 3: Bump config**

In `launchpad/config.py`: `APP_VERSION = "1.6.186"`

- [ ] **Step 4: Run pins to verify they pass**

Run: `python -m pytest tests/test_capacity_unit_js.py::test_app_version_153 tests/test_hadoop_sudo_wire.py::test_version_174 tests/test_system_connectivity_version.py tests/test_vcenters_directory.py tests/test_vcenters_page.py tests/test_vcenters_api.py tests/test_vcenters_dashboard.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add launchpad/config.py tests/test_capacity_unit_js.py tests/test_hadoop_sudo_wire.py tests/test_system_connectivity_version.py
git commit -m "Bump version to 1.6.186 for vCenters directory."
```

---

## Spec coverage

| Spec item | Task |
|-----------|------|
| Dashboard **vCenters** after Ansible Pad | 4 |
| Opens `/vcenters` without SSH cards | 3, 4 |
| Fields name, location, address, optional URL | 1, 2 |
| Default `https://{address}/ui`; override http(s) | 1, 2 |
| Add / Edit / Delete on the page | 2, 3 |
| Detail via `?id=` on the same page | 2 |
| Persist `vcenters_directory`; corrupt → empty | 1, 3 |
| Unlock required for writes; 503 | 3 |
| GET list while settings backend present | 3 |
| No live inventory / Admin cards / SQLite | (omitted) |
| APP_VERSION 1.6.186 | 5 |
