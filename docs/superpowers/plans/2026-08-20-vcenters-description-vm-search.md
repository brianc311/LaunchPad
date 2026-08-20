# vCenters Description, VM Search, and Client Path Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add per-vCenter **Description** and collapsible **VM names**, Directory search (name / IP / VM text), and point **Open vSphere Client** at the working `VpxClient.exe` path, shipping as **1.6.188**.

**Architecture:** Extend `vcenters_directory` JSON with `description` and `vm_notes`. Search is client-side on the already-loaded list, using the same match rules as `vcenter_matches_query`. Launch keeps using imported `VPXCLIENT_PATH` (Health Server has no path string of its own).

**Tech Stack:** Python, Health Server, pytest, existing vCenters page JS.

**Spec:** `docs/superpowers/specs/2026-08-20-vcenters-description-vm-search-design.md`

## Global Constraints

- APP_VERSION bump to **1.6.188** only in the final version task. Do not bump in Tasks 1–2.
- Form/detail labels exactly **Description** and **VM names**.
- Search placeholder exactly `Search name, IP, or VM`.
- Search matches case-insensitive substring of **name**, **address**, and **vm_notes** only (not Description, Location, URL, or username). Empty query shows all rows.
- VM names on detail: closed `<details>` (no `open` attribute). Re-open of the card must set `open = false`.
- Empty Description on detail is `—`. Empty VM names still show the collapsed header with empty body.
- Exe path exactly `C:\Program Files (x86)\VMware\Infrastructure\Virtual Infrastructure Client\Launcher\VpxClient.exe`. Do not search other folders. `cwd` is that file’s parent.
- No new Directory columns. No structured VM rows. Do not encrypt Description or VM names.
- Place imports at the top of modules (no inline imports).
- Windows PowerShell commits (`git commit -m "..."`); commit at each task commit step.
- Prefer TDD: failing test → implement → pass → commit.
- Do not commit `.superpowers/sdd*` scratch, `LaunchPad-Install/`, or install zips.
- Work on branch `feature/vcenters-description-vm-search`.
- Do not edit `launchpad/health_server.py` unless a test proves GET/upsert drops the new fields (it already uses `public_vcenters` / `upsert_vcenter`).

## File structure

| File | Responsibility |
|------|----------------|
| `launchpad/vcenters_directory.py` | `description`, `vm_notes`, `vcenter_matches_query`, new `VPXCLIENT_PATH` |
| `tests/test_vcenters_directory.py` | Defaults, match helper, path string |
| `launchpad/vcenters.py` | Form fields, detail Description + collapsed VM names, Directory search |
| `tests/test_vcenters_page.py` | Page markers |
| `launchpad/config.py` + version pins | **1.6.188** (Task 3 only) |

---

### Task 1: Directory fields, search matcher, VpxClient path

**Files:**
- Modify: `launchpad/vcenters_directory.py`
- Modify: `tests/test_vcenters_directory.py`

**Interfaces:**
- Consumes: existing `normalize_vcenter`, `public_vcenter`, `VPXCLIENT_PATH`, `vpxclient_argv`
- Produces:
  - `VPXCLIENT_PATH = Path(r"C:\Program Files (x86)\VMware\Infrastructure\Virtual Infrastructure Client\Launcher\VpxClient.exe")`
  - `vcenter_matches_query(row: dict, query: str) -> bool`
  - `normalize_vcenter` stored shape also includes `description: str`, `vm_notes: str` (missing → `""`)
  - `public_vcenter` includes `description` and `vm_notes` as plain text

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_vcenters_directory.py` and add `vcenter_matches_query` to the existing import list:

```python
from launchpad.vcenters_directory import (
    SETTING_VCENTERS_DIRECTORY,
    VCENTER_PASSWORD_PLACEHOLDER,
    VPXCLIENT_PATH,
    delete_vcenter,
    effective_vcenter_url,
    normalize_vcenter,
    normalize_vcenters,
    parse_vcenters_setting,
    public_vcenter,
    resolve_password_encrypted,
    upsert_vcenter,
    use_vsphere_client_enabled,
    vcenter_default_url,
    vcenter_matches_query,
    vpxclient_argv,
)
```

Add these tests (keep existing tests). Update `test_vpxclient_argv_and_path` path assertion to the new exe string.

```python
def test_description_and_vm_notes_default_empty_and_public():
    row = normalize_vcenter(
        {"name": "VC1", "address": "10.0.0.1"}, assign_id=True
    )
    assert row["description"] == ""
    assert row["vm_notes"] == ""
    stored = normalize_vcenter(
        {
            "name": "VC1",
            "address": "10.0.0.1",
            "description": "  purpose line  ",
            "vm_notes": "  web01\napp02  ",
        },
        assign_id=True,
    )
    assert stored["description"] == "purpose line"
    assert stored["vm_notes"] == "web01\napp02"
    pub = public_vcenter(stored)
    assert pub["description"] == "purpose line"
    assert pub["vm_notes"] == "web01\napp02"


def test_vcenter_matches_query_name_address_vm_notes_not_description():
    row = {
        "name": "HPEW101VCENTER6",
        "address": "172.19.195.31",
        "description": "WAG1 compute cluster",
        "vm_notes": "sql01\nweb-prod",
    }
    assert vcenter_matches_query(row, "") is True
    assert vcenter_matches_query(row, "   ") is True
    assert vcenter_matches_query(row, "hpew101") is True
    assert vcenter_matches_query(row, "195.31") is True
    assert vcenter_matches_query(row, "SQL01") is True
    assert vcenter_matches_query(row, "compute cluster") is False
    assert vcenter_matches_query(row, "no-such") is False
```

In `test_vpxclient_argv_and_path`, replace the path assertion with:

```python
    assert str(VPXCLIENT_PATH) == (
        r"C:\Program Files (x86)\VMware\Infrastructure\Virtual Infrastructure Client\Launcher\VpxClient.exe"
    )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_vcenters_directory.py::test_description_and_vm_notes_default_empty_and_public tests/test_vcenters_directory.py::test_vcenter_matches_query_name_address_vm_notes_not_description tests/test_vcenters_directory.py::test_vpxclient_argv_and_path -v`

Expected: FAIL (`vcenter_matches_query` missing and/or old path / missing `description`)

- [ ] **Step 3: Implement helpers**

Set:

```python
VPXCLIENT_PATH = Path(
    r"C:\Program Files (x86)\VMware\Infrastructure\Virtual Infrastructure Client\Launcher\VpxClient.exe"
)
```

Add after `public_vcenters`:

```python
def vcenter_matches_query(row: dict, query: str) -> bool:
    needle = str(query or "").strip().casefold()
    if not needle:
        return True
    haystacks = (
        str(row.get("name") or ""),
        str(row.get("address") or ""),
        str(row.get("vm_notes") or ""),
    )
    return any(needle in part.casefold() for part in haystacks)
```

In `public_vcenter`, add `"description"` and `"vm_notes"` (plain strings, same as name).

In `normalize_vcenter`, after reading `url`:

```python
    description = str(raw.get("description") or "").strip()
    vm_notes = str(raw.get("vm_notes") or "").strip()
```

Include them on the returned dict: `"description": description`, `"vm_notes": vm_notes`.

Do not change `health_server.py`. `vpxclient_argv` keeps using `VPXCLIENT_PATH`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_vcenters_directory.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add launchpad/vcenters_directory.py tests/test_vcenters_directory.py
git commit -m "Add vCenter description, VM notes, search matcher, and VpxClient path."
```

---

### Task 2: Page Description, VM names, and Directory search

**Files:**
- Modify: `launchpad/vcenters.py`
- Modify: `tests/test_vcenters_page.py`

**Interfaces:**
- Consumes: GET `/api/vcenters` rows that include `description` and `vm_notes` (Task 1)
- Produces: page contains `id="vcenter-search"`, placeholder `Search name, IP, or VM`, `id="description"`, `id="vm_notes"`, `id="d-description"`, `<details`, `<summary>VM names</summary`, and JS `rowMatchesQuery`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_vcenters_page.py`:

```python
def test_vcenters_page_has_description_vm_notes_and_search():
    assert 'id="vcenter-search"' in VCENTERS_HTML
    assert 'placeholder="Search name, IP, or VM"' in VCENTERS_HTML
    assert 'id="description"' in VCENTERS_HTML
    assert "<strong>Description</strong>" in VCENTERS_HTML
    assert 'id="vm_notes"' in VCENTERS_HTML
    assert "<textarea" in VCENTERS_HTML
    assert 'id="d-description"' in VCENTERS_HTML
    assert "<details" in VCENTERS_HTML
    assert "<summary>VM names</summary>" in VCENTERS_HTML
    assert 'id="d-vm-notes"' in VCENTERS_HTML
    assert "function rowMatchesQuery" in VCENTERS_HTML
    assert "No matching vCenters" in VCENTERS_HTML
    assert "<th>Name</th><th>Location</th><th>Address</th><th>Link</th>" in VCENTERS_HTML
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_vcenters_page.py::test_vcenters_page_has_description_vm_notes_and_search -v`

Expected: FAIL (missing `id="vcenter-search"`)

- [ ] **Step 3: Update the page**

In `<style>`, add:

```css
    textarea { width:100%; min-height:88px; padding:9px 10px; color:var(--text); background:var(--panel-alt); border:1px solid var(--border); border-radius:8px; font:inherit; resize:vertical; }
    #vcenter-search { width:auto; min-width:220px; flex:1; max-width:360px; padding:9px 10px; color:var(--text); background:var(--panel-alt); border:1px solid var(--border); border-radius:8px; font:inherit; }
    details.notes { margin:12px 0 0; }
    details.notes summary { cursor:pointer; font-weight:700; }
    #d-vm-notes { white-space:pre-wrap; margin:8px 0 0; color:var(--muted); }
```

In `#list-section`, change the actions row to:

```html
      <div class="actions">
        <button id="add-btn" type="button">Add</button>
        <input id="vcenter-search" type="search" placeholder="Search name, IP, or VM" aria-label="Search name, IP, or VM">
      </div>
```

In `#detail-section`, after the Link paragraph (`id="d-link"`), insert:

```html
      <p><strong>Description</strong><br><span id="d-description"></span></p>
```

After `#d-user-wrap` and before `.actions`, insert this closed details block (do not set `open`):

```html
      <details id="d-vm-notes-wrap" class="notes">
        <summary>VM names</summary>
        <p id="d-vm-notes"></p>
      </details>
```

Do not duplicate `#d-user-wrap`. Do not add a list column. Keep the existing Link, Username, and launch button.

After URL override in the form, add:

```html
        <label class="wide" style="grid-column:1 / -1;">Description<input id="description" name="description"></label>
        <label class="wide" style="grid-column:1 / -1;">VM names<textarea id="vm_notes" name="vm_notes" rows="5"></textarea></label>
```

In JS, after `effectiveUrl`, add:

```javascript
    function rowMatchesQuery(row, query) {
      const needle = String(query || "").trim().toLowerCase();
      if (!needle) return true;
      const hay = [row.name, row.address, row.vm_notes].map((value) => String(value || "").toLowerCase());
      return hay.some((part) => part.includes(needle));
    }
```

Replace `renderTable` so it filters, and uses `No matching vCenters` when `rows.length` is non-zero but the filter is empty:

```javascript
    function renderTable() {
      const query = document.getElementById("vcenter-search").value;
      const visible = rows.filter((row) => rowMatchesQuery(row, query));
      if (!rows.length) {
        listWrap.innerHTML = '<p class="empty">No vCenters yet</p>';
        return;
      }
      if (!visible.length) {
        listWrap.innerHTML = '<p class="empty">No matching vCenters</p>';
        return;
      }
      const body = visible.map((row) => {
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
```

In `showDetail`, after setting the web link:

```javascript
      document.getElementById("d-description").textContent = row.description || "—";
      const vmWrap = document.getElementById("d-vm-notes-wrap");
      vmWrap.open = false;
      document.getElementById("d-vm-notes").textContent = row.vm_notes || "";
```

Keep the existing username / launchBtn lines.

In `showForm`, after filling `url`:

```javascript
      document.getElementById("description").value = row ? (row.description || "") : "";
      document.getElementById("vm_notes").value = row ? (row.vm_notes || "") : "";
```

Add to the save payload:

```javascript
        description: document.getElementById("description").value,
        vm_notes: document.getElementById("vm_notes").value,
```

After `addBtn` listener (or with other listeners), add:

```javascript
    document.getElementById("vcenter-search").addEventListener("input", renderTable);
```

Do not bump APP_VERSION. Do not change `health_server.py`. Keep **Open vSphere Client** and the web Link.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_vcenters_page.py tests/test_vcenters_directory.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add launchpad/vcenters.py tests/test_vcenters_page.py
git commit -m "Add vCenters description, VM names, and directory search on the page."
```

---

### Task 3: Bump APP_VERSION to 1.6.188

**Files:**
- Modify: `launchpad/config.py`
- Modify: `tests/test_capacity_unit_js.py`
- Modify: `tests/test_hadoop_sudo_wire.py`
- Modify: `tests/test_system_connectivity_version.py`

**Interfaces:**
- Consumes: none
- Produces: `APP_VERSION = "1.6.188"`

- [ ] **Step 1: Write the failing pin updates**

Set the three version assertions to `"1.6.188"` (they currently expect `1.6.187`). Do not change `config.py` yet.

- [ ] **Step 2: Run pins to verify they fail**

Run: `python -m pytest tests/test_capacity_unit_js.py::test_app_version_153 tests/test_hadoop_sudo_wire.py::test_version_174 tests/test_system_connectivity_version.py -v`

Expected: FAIL (`1.6.187` != `1.6.188`)

- [ ] **Step 3: Bump config**

In `launchpad/config.py`: `APP_VERSION = "1.6.188"`

- [ ] **Step 4: Run pins to verify they pass**

Run: `python -m pytest tests/test_capacity_unit_js.py::test_app_version_153 tests/test_hadoop_sudo_wire.py::test_version_174 tests/test_system_connectivity_version.py tests/test_vcenters_directory.py tests/test_vcenters_page.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add launchpad/config.py tests/test_capacity_unit_js.py tests/test_hadoop_sudo_wire.py tests/test_system_connectivity_version.py
git commit -m "Bump version to 1.6.188 for vCenters description, VM search, and client path."
```

---

## Spec coverage

| Spec item | Task |
|-----------|------|
| Description one-line on Add/Edit; detail only | 2 |
| Empty Description shows `—` | 2 |
| VM names textarea; detail `<details>` starts closed | 2 |
| Empty VM names still show collapsed header | 2 |
| Search box; filter name / address / vm_notes | 1 (helper), 2 (page) |
| Description not searched | 1 |
| No new list columns | 2 |
| `VPXCLIENT_PATH` Virtual Infrastructure Client `VpxClient.exe` | 1 |
| Start in launcher folder (`exe.parent`) | 1 (`vpxclient_argv` / existing launch cwd) |
| Old rows default empty strings | 1 |
| APP_VERSION 1.6.188 | 3 |
