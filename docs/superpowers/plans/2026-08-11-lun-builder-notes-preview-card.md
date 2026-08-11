# LUN Builder Notes, Preview Gate, and Card Hint Dropdown Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist LUN Builder notes across redraws, stop Run Create from demanding a new Preview after a timestamp/notes save, and make Build-details Card hint a dropdown of SSH Health Cards (v**1.6.153**).

**Architecture:** `_lun_build_content_hash` hashes the normalized build minus metadata (`updated_at`, `notes`, `plan_done`, `command_done`, `name`, `location`). The page writes Name/Location/Notes onto the in-memory build on `input`, and calls `readSummary` before `render()` in mutation handlers (not inside `render()`, which would wipe on first load and on picker change). `#default-card-hint` becomes a `<select>` rebuilt in `render()` from `/api/cards` plus an unmatched saved hint option.

**Tech Stack:** Python, HealthServer, embedded LUN Builder HTML/JS, pytest.

**Spec:** `docs/superpowers/specs/2026-08-11-lun-builder-notes-preview-card-design.md`

## Global Constraints

- APP_VERSION is currently `1.6.152`; bump to `1.6.153` in the Card-hint/version task (Task 3). Do not bump earlier.
- Hash omits: `updated_at`, `notes`, `plan_done`, `command_done`, `name`, `location`. Hosts, luns, id, is_template, default_storage_profile, default_pool_or_cpg, default_card_hint still count.
- Do not call `readSummary()` at the start of `render()` (first paint and picker-change would copy empty/old DOM onto the active build). Write-through on input; `readSummary(activeBuild())` immediately before `render()` in add/remove/plan-done handlers.
- Card list: all SSH Health Cards from `/api/cards` (`card_type === "ssh"` or missing type). Unmatched saved hint stays an extra `<option>` until a listed card is chosen. No auto-select of partial matches.
- Keep `id="default-card-hint"`. Per-row LUN `card_hint` stays a text input. Hint copy unchanged. Preview expiry 300s and `find_card_by_hint` unchanged. Still persist on Run Create.
- Windows PowerShell commits (`git commit -m "..."`); commit at each task’s commit step.
- Prefer TDD: failing test → implement → pass → commit.
- Do not commit `.superpowers/sdd*` scratch or install zips.

## File structure

| File | Responsibility |
|------|----------------|
| `launchpad/health_server.py` | `_lun_build_content_hash` omits metadata keys |
| `tests/test_health_server_lun_builder.py` | Preview then metadata save still creates; size change still blocked |
| `launchpad/lun_builder.py` | Notes write-through; Card hint `<select>` |
| `tests/test_lun_builder_page.py` | Page contracts for notes + select |
| `launchpad/config.py` | `APP_VERSION` → `1.6.153` |
| `tests/test_system_connectivity_version.py` | Version pin → `1.6.153` |
| `tests/test_hadoop_sudo_wire.py` | Version pin → `1.6.153` |
| `tests/test_capacity_unit_js.py` | Version pin → `1.6.153` |

---

### Task 1: Preview hash ignores metadata

**Files:**
- Modify: `launchpad/health_server.py` (`_lun_build_content_hash`)
- Modify: `tests/test_health_server_lun_builder.py`

**Interfaces:**
- Consumes: `normalize_build`, existing `_lun_preview_session` rules
- Produces: `_lun_build_content_hash(build)` stable across notes/timestamp/name/completion changes

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_health_server_lun_builder.py` (reuse the Primera + monkeypatch pattern from `test_create_lun_build_rejects_build_changed_after_preview`):

```python
def _runnable_primera_server(monkeypatch):
    _settings, getter, setter = _settings_backend()
    server = HealthServer()
    server.set_settings_backend(getter, setter)
    build = {
        "id": "first",
        "name": "First",
        "hosts": [],
        "luns": [
            {
                "purpose": "vol",
                "count": 1,
                "size": "10GB",
                "pool_or_cpg": "Pool0",
                "storage_profile": "hpe_primera_600",
                "card_hint": "cardA",
            }
        ],
    }
    server.set_lun_builds([build])
    server.register_card(
        1,
        "cardA",
        "array.example",
        22,
        "operator",
        "",
        device_profile="hpe_primera_600",
    )
    monkeypatch.setattr(
        server,
        "_lun_run_command",
        lambda _card: lambda _command: "created",
    )
    return server, build


def test_create_lun_build_allows_metadata_changes_after_preview(monkeypatch):
    server, build = _runnable_primera_server(monkeypatch)
    assert server.preview_lun_build("first")["ok"] is True
    build["updated_at"] = "2026-08-11T18:00:00+00:00"
    build["notes"] = "operator comment"
    build["name"] = "Renamed"
    build["plan_done"] = {"vol": True}
    build["command_done"] = {"vol\\ncmd": True}
    server.set_lun_builds([build])

    result = server.create_lun_build("first", confirm=True)

    assert result["ok"] is True


def test_create_lun_build_still_rejects_lun_size_change_after_preview(monkeypatch):
    server, build = _runnable_primera_server(monkeypatch)
    assert server.preview_lun_build("first")["ok"] is True
    build["luns"][0]["size"] = "20GB"
    server.set_lun_builds([build])

    result = server.create_lun_build("first", confirm=True)

    assert result["ok"] is False
    assert "Preview must be run again" in result["warnings"][0]
```

Keep `test_create_lun_build_rejects_build_changed_after_preview` as-is (size change + session clear).

- [ ] **Step 2: Run tests to confirm they fail**

```powershell
python -m pytest tests/test_health_server_lun_builder.py::test_create_lun_build_allows_metadata_changes_after_preview tests/test_health_server_lun_builder.py::test_create_lun_build_still_rejects_lun_size_change_after_preview -q
```

Expected: metadata test fails (`ok` is False) because `updated_at`/`notes` are in the hash.

- [ ] **Step 3: Implement**

In `launchpad/health_server.py`, near `_lun_build_content_hash`, add:

```python
_LUN_PREVIEW_HASH_OMIT = frozenset(
    {
        "updated_at",
        "notes",
        "plan_done",
        "command_done",
        "name",
        "location",
    }
)
```

Replace `_lun_build_content_hash`:

```python
@staticmethod
def _lun_build_content_hash(build: dict[str, Any]) -> str:
    normalized = normalize_build(build)
    if normalized is None:
        raise ValueError("Invalid LUN build")
    content = {
        key: value
        for key, value in normalized.items()
        if key not in _LUN_PREVIEW_HASH_OMIT
    }
    payload = json.dumps(content, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
```

If `_LUN_PREVIEW_HASH_OMIT` cannot sit inside the class without a decorator issue, define it as a module-level constant above `HealthServer`.

- [ ] **Step 4: Run tests to confirm they pass**

```powershell
python -m pytest tests/test_health_server_lun_builder.py -q
```

Expected: pass (including the two new tests and the existing size-change rejection).

- [ ] **Step 5: Commit**

```powershell
git add launchpad/health_server.py tests/test_health_server_lun_builder.py
git commit -m "Ignore LUN metadata in Preview/Run content hash."
```

---

### Task 2: Notes survive redraws

**Files:**
- Modify: `launchpad/lun_builder.py`
- Modify: `tests/test_lun_builder_page.py`

**Interfaces:**
- Consumes: existing `readSummary(build)`, `activeBuild()`, `render()`
- Produces: input on `#build-name` / `#build-location` / `#build-notes` writes `build.name` / `build.location` / `build.notes`; add/remove/plan-done call `readSummary` before `render`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_lun_builder_page.py`:

```python
def test_lun_builder_summary_input_writes_through_to_build():
    handler = LUN_BUILDER_HTML.split(
        '["build-name", "build-location", "build-notes"].forEach',
        1,
    )[1].split("document.getElementById(\"default-storage-profile\")", 1)[0]
    assert "readSummary" in handler or "build.notes" in handler
    assert "activeBuild()" in handler


def test_lun_builder_add_row_reads_summary_before_render():
    add_row = LUN_BUILDER_HTML.split("function addRow(kind)", 1)[1].split(
        "function updateField", 1
    )[0]
    assert "readSummary(activeBuild())" in add_row
    assert add_row.index("readSummary(activeBuild())") < add_row.index("render()")
```

The input handler today only calls `invalidatePreview()` — first test must fail.

- [ ] **Step 2: Run tests to confirm they fail**

```powershell
python -m pytest tests/test_lun_builder_page.py::test_lun_builder_summary_input_writes_through_to_build tests/test_lun_builder_page.py::test_lun_builder_add_row_reads_summary_before_render -q
```

Expected: fail (handler has no `activeBuild()` / `readSummary`).

- [ ] **Step 3: Implement**

Replace the summary `input` listener in `launchpad/lun_builder.py`:

```javascript
    ["build-name", "build-location", "build-notes"].forEach((id) => document.getElementById(id).addEventListener("input", () => {
      const build = activeBuild();
      readSummary(build);
      invalidatePreview();
      document.getElementById("run-btn").disabled = true;
    }));
```

In `addRow`, immediately before `invalidatePreview(); render();`:

```javascript
      readSummary(activeBuild());
      invalidatePreview();
      render();
```

In the remove-row click handler, immediately before `invalidatePreview(); render();`:

```javascript
      readSummary(activeBuild());
      invalidatePreview(); render();
```

In the plan-body `change` handler, immediately before `render(); persistCompletionState();`:

```javascript
      readSummary(activeBuild());
      render();
      persistCompletionState();
```

Do **not** call `readSummary` at the top of `render()`.

- [ ] **Step 4: Run tests to confirm they pass**

```powershell
python -m pytest tests/test_lun_builder_page.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```powershell
git add launchpad/lun_builder.py tests/test_lun_builder_page.py
git commit -m "Keep LUN Builder notes across table redraws."
```

---

### Task 3: Card hint dropdown + version

**Files:**
- Modify: `launchpad/lun_builder.py`
- Modify: `tests/test_lun_builder_page.py`
- Modify: `launchpad/config.py`
- Modify: `tests/test_system_connectivity_version.py`
- Modify: `tests/test_hadoop_sudo_wire.py`
- Modify: `tests/test_capacity_unit_js.py`

**Interfaces:**
- Consumes: `healthCards` from `loadHealthCards()` (`/api/cards`)
- Produces: `<select id="default-card-hint">` rebuilt in `render()`; `APP_VERSION = "1.6.153"`

- [ ] **Step 1: Write the failing tests**

In `tests/test_lun_builder_page.py`, add:

```python
def test_lun_builder_card_hint_is_a_select():
    assert '<select id="default-card-hint"' in LUN_BUILDER_HTML
    assert '<input id="default-card-hint"' not in LUN_BUILDER_HTML
    assert "Select Health Card" in LUN_BUILDER_HTML
    assert "fillCardHintOptions" in LUN_BUILDER_HTML
```

Bump version pins to `"1.6.153"` in:

- `tests/test_system_connectivity_version.py`
- `tests/test_hadoop_sudo_wire.py`
- `tests/test_capacity_unit_js.py`

- [ ] **Step 2: Run tests to confirm they fail**

```powershell
python -m pytest tests/test_lun_builder_page.py::test_lun_builder_card_hint_is_a_select tests/test_system_connectivity_version.py tests/test_hadoop_sudo_wire.py tests/test_capacity_unit_js.py -q
```

Expected: select test fails; version still `1.6.152`.

- [ ] **Step 3: Implement**

Replace the Card hint control in `launchpad/lun_builder.py`:

```html
        <label>Card hint <select id="default-card-hint" title="LaunchPad SSH Health Card name used for Preview/Run"><option value="">Select Health Card</option></select></label>
```

Add this function near `loadHealthCards`:

```javascript
    function sshCardNames() {
      return Object.values(healthCards)
        .filter((card) => !card.card_type || card.card_type === "ssh")
        .map((card) => String(card.name || "").trim())
        .filter(Boolean)
        .sort((a, b) => a.localeCompare(b, undefined, { sensitivity: "base" }));
    }
    function fillCardHintOptions(selectedHint) {
      const select = document.getElementById("default-card-hint");
      if (!select) return;
      const current = String(selectedHint || "").trim();
      const names = sshCardNames();
      const extras = current && !names.includes(current) ? [current] : [];
      const values = ["", ...extras, ...names];
      select.innerHTML = values.map((name) => {
        const label = name || "Select Health Card";
        return `<option value="${esc(name)}">${esc(label)}</option>`;
      }).join("");
      select.value = current;
    }
```

In `render()`, in the non-inventory branch, replace

```javascript
      document.getElementById("default-card-hint").value = build.default_card_hint || "";
```

with:

```javascript
      fillCardHintOptions(build.default_card_hint || "");
```

Keep `document.getElementById("default-card-hint").addEventListener("change", onBuildDefaultsChanged);`

Set `APP_VERSION = "1.6.153"` in `launchpad/config.py`.

- [ ] **Step 4: Run tests to confirm they pass**

```powershell
python -m pytest tests/test_lun_builder_page.py tests/test_health_server_lun_builder.py tests/test_system_connectivity_version.py tests/test_hadoop_sudo_wire.py tests/test_capacity_unit_js.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```powershell
git add launchpad/lun_builder.py launchpad/config.py tests/test_lun_builder_page.py tests/test_system_connectivity_version.py tests/test_hadoop_sudo_wire.py tests/test_capacity_unit_js.py
git commit -m "Add LUN Builder Health Card dropdown and bump to 1.6.153."
```

---

## Self-review

| Spec item | Task |
|-----------|------|
| Notes write-through on input | Task 2 |
| Notes survive Add host / remove / Done redraw | Task 2 (`readSummary` before `render`) |
| Do not wipe on first load / picker change | Task 2 (no `readSummary` inside `render`) |
| Hash omits updated_at/notes/plan_done/command_done/name/location | Task 1 |
| Size/host/profile/pool/card still require Preview | Task 1 |
| Card hint `<select>` of SSH cards + unmatched extra option | Task 3 |
| Per-row card_hint stays text | Task 3 (untouched table input) |
| `id="default-card-hint"` kept | Task 3 |
| APP_VERSION 1.6.153 | Task 3 |

**Placeholder scan:** none. Commands are PowerShell `python -m pytest` / `git commit -m`.

**Type consistency:** `_LUN_PREVIEW_HASH_OMIT`, `fillCardHintOptions(selectedHint)`, `sshCardNames()`.
