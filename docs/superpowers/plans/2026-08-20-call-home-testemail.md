# Call Home Test Email Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add **Preview Test Email** / **Run Test Email** that SSHs `svctask testemail` to one loaded user on each checked array, using SMTP already on the array, shipping as **1.6.189**.

**Architecture:** Sixth Call Home kind (`testemail`). Ops builds a single `SnapStep`. Health Server preview/run reuse `_call_home_preview_rows` / `_call_home_run_rows`. Page adds buttons after Run SMTP and a per-array **Test user** select filled by Load current. No SMTP write.

**Tech Stack:** Python, Health Server, existing Call Home CLI page, pytest.

**Spec:** `docs/superpowers/specs/2026-08-20-call-home-testemail-design.md`

## Global Constraints

- APP_VERSION bump to **1.6.189** only in the final version task. Do not bump in Tasks 1–3.
- Button labels exactly **Preview Test Email** and **Run Test Email**.
- Command exactly `svctask testemail {quoted token}` where token is user **id**, else **address**.
- No `chemailserver`, `mkemailserver`, `startemail`, `rmemailuser`, or other writes on this kind.
- Card Username/Password unused; password never in the testemail payload or hash.
- `preview_hash` kind is `testemail`. A SMTP hash must not unlock Run Test Email.
- Empty Test user → that array not runnable (`ERROR: select a test user`).
- Unlock required (existing Call Home run path). First CLI error stops that array; continue next; no rollback.
- Place imports at the top of modules (no inline imports).
- Windows PowerShell commits (`git commit -m "..."`); commit at each task commit step.
- Prefer TDD: failing test → implement → pass → commit.
- Do not commit `.superpowers/sdd*` scratch, `LaunchPad-Install/`, or install zips.
- Work on branch `feature/call-home-testemail`.

## File structure

| File | Responsibility |
|------|----------------|
| `launchpad/call_home_cli_ops.py` | `build_testemail_array_steps`, hash kind `testemail` |
| `tests/test_call_home_cli_ops.py` | Steps + hash isolation |
| `launchpad/call_home_cli.py` | Buttons, Test user select, kind wiring |
| `tests/test_call_home_cli_page.py` | Page markers |
| `launchpad/health_server.py` | Preview/run routes |
| `tests/test_health_server_call_home_cli.py` | Preview steps; SMTP hash cannot run testemail |
| `launchpad/config.py` + version pins | **1.6.189** (Task 4 only) |

---

### Task 1: Ops builder and hash kind

**Files:**
- Modify: `launchpad/call_home_cli_ops.py`
- Modify: `tests/test_call_home_cli_ops.py`

**Interfaces:**
- Consumes: `quote_cli_arg`, `SnapStep`, existing `preview_hash`
- Produces:
  - `build_testemail_array_steps(*, user_id: str = "", address: str = "") -> tuple[list[SnapStep], list[str], bool]`
  - `preview_hash("testemail", payload)` blob `{"kind":"testemail","arrays":[{"card_id":N,"user_id":"...","address":"..."}, ...]}`

- [ ] **Step 1: Write the failing tests**

Add `build_testemail_array_steps` to the import list in `tests/test_call_home_cli_ops.py`.

Append:

```python
def test_testemail_uses_id_then_address_and_rejects_empty():
    steps, warnings, ok = build_testemail_array_steps(user_id="1", address="a@b.com")
    assert ok is True
    assert warnings == []
    assert steps[0].kind == "testemail"
    assert steps[0].cmd == "svctask testemail 1"
    assert "chemailserver" not in steps[0].cmd
    assert "mkemailserver" not in steps[0].cmd
    by_addr, _, ok2 = build_testemail_array_steps(user_id="", address="a@b.com")
    assert ok2 is True
    assert by_addr[0].cmd == 'svctask testemail "a@b.com"'
    empty, errs, ok3 = build_testemail_array_steps(user_id="", address="")
    assert ok3 is False
    assert empty == []
    assert any("select a test user" in item for item in errs)
```

In `test_preview_hash_isolates_kinds_and_hides_password`, after the existing kind asserts, add:

```python
    h_test = preview_hash(
        "testemail",
        {"arrays": [{"card_id": 1, "user_id": "1", "address": "a@b.com"}]},
    )
    assert h_test != h_smtp
    assert preview_hash(
        "testemail",
        {"arrays": [{"card_id": 1, "user_id": "2", "address": "a@b.com"}]},
    ) != h_test
    assert "s3cret" not in h_test
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_call_home_cli_ops.py::test_testemail_uses_id_then_address_and_rejects_empty tests/test_call_home_cli_ops.py::test_preview_hash_isolates_kinds_and_hides_password -v`

Expected: FAIL (`build_testemail_array_steps` missing and/or testemail hashed as remove)

- [ ] **Step 3: Implement**

After `build_cloud_array_steps`, add:

```python
def build_testemail_array_steps(
    *,
    user_id: str = "",
    address: str = "",
) -> tuple[list[SnapStep], list[str], bool]:
    token = str(user_id or "").strip() or str(address or "").strip()
    if not token:
        return [], ["ERROR: select a test user"], False
    try:
        quoted = quote_cli_arg(token)
    except ValueError as exc:
        return [], [f"ERROR: {exc}"], False
    return (
        [
            SnapStep(
                kind="testemail",
                purpose=f"test email to {token}",
                cmd=f"svctask testemail {quoted}",
            )
        ],
        [],
        True,
    )
```

In `preview_hash`, **before** the final `else` (remove), insert:

```python
    elif kind == "testemail":
        def test_row(item: dict) -> dict:
            return {
                "user_id": str(item.get("user_id") or item.get("id") or "").strip(),
                "address": str(item.get("address") or "").strip(),
            }
        blob = {"kind": "testemail", "arrays": card_ids(test_row)}
```

Do not let `testemail` fall through to `kind: remove`. Do not change SMTP builders.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_call_home_cli_ops.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add launchpad/call_home_cli_ops.py tests/test_call_home_cli_ops.py
git commit -m "Add Call Home testemail step builder and isolated preview hash."
```

---

### Task 2: Page buttons and Test user select

**Files:**
- Modify: `launchpad/call_home_cli.py`
- Modify: `tests/test_call_home_cli_page.py`

**Interfaces:**
- Consumes: API path strings `/api/call-home/preview-testemail` and `/api/call-home/run-testemail`
- Produces: page contains **Preview Test Email**, **Run Test Email**, `id="preview-testemail-btn"`, `id="run-testemail-btn"`, `test-user-`, kind `testemail` in KINDS, confirm copy naming test email

- [ ] **Step 1: Write the failing tests**

Update `tests/test_call_home_cli_page.py`:

In `test_path_title_and_actions`, after `Run SMTP` asserts, add:

```python
    assert "Preview Test Email" in html
    assert "Run Test Email" in html
```

In `test_api_paths_and_payload_fields`, add to the path tuple:

```python
        "/api/call-home/preview-testemail",
        "/api/call-home/run-testemail",
```

Also assert:

```python
    assert "test-user-" in html or 'id="test-user-' in html
    assert "user_id" in html
```

Rename/extend `test_five_run_kinds_invalidate_and_catch`: keep the function name **or** change it to `test_six_run_kinds_invalidate_and_catch` and update the `for key in` tuple to include `"testemail"`. Assert:

```python
    assert "This sends a test email through the SMTP already on the selected arrays" in html
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_call_home_cli_page.py -v`

Expected: FAIL (missing Preview Test Email)

- [ ] **Step 3: Update the page**

After the Run SMTP button (`id="run-smtp-btn"`), insert:

```html
        <button type="button" class="secondary" id="preview-testemail-btn">Preview Test Email</button>
        <button type="button" class="danger" id="run-testemail-btn" disabled>Run Test Email</button>
```

In JS:

- `KINDS` becomes `["apply","smtp","testemail","users","cloud","remove"]`
- Add PREVIEW_URL / RUN_URL / PREVIEW_TITLE / RUN_TITLE / STATUS_KIND entries for `testemail`
- CONFIRMS.testemail: `This sends a test email through the SMTP already on the selected arrays. It does not change SMTP, users, contact, or Cloud Call Home. The first CLI error stops that array; other arrays continue. No rollback.`
- `window.__testemailOk` / `window.__testemailHash` next to the other hash vars

In `fillUsers`, after the Add address block, append a Test user select (preserve existing add rows). Use:

```javascript
      const selected = (document.getElementById("test-user-"+id)||{}).value || "";
      const opts = ['<option value="">Select user</option>'].concat((users || []).map((u) => {
        const uid = String(u.id || u.name || "").replace(/"/g, "");
        const addr = String(u.address || "").replace(/"/g, "");
        const typ = String(u.user_type || "").replace(/"/g, "");
        const sel = uid === selected ? " selected" : "";
        return '<option value="'+uid+'" data-address="'+addr+'"'+sel+'>'+addr+' ('+typ+')</option>';
      }));
      const testSel = '<label>Test user <select id="test-user-'+id+'">'+opts.join("")+'</select></label>';
      el.innerHTML = rows + add + testSel;
```

Keep the existing invalidate listeners on the rebuilt nodes.

Add:

```javascript
    function testemailKindPayload() {
      return {
        arrays: selectedIds().map((id) => {
          const sel = document.getElementById("test-user-" + id);
          const opt = sel && sel.selectedOptions && sel.selectedOptions[0];
          return {
            card_id: id,
            user_id: sel ? (sel.value || "") : "",
            address: opt ? (opt.getAttribute("data-address") || "") : ""
          };
        })
      };
    }
```

In `kindPayload`, handle `testemail` before the remove default:

```javascript
      if (kind === "testemail") return testemailKindPayload();
```

Wire:

```javascript
    document.getElementById("preview-testemail-btn").onclick = () => doPreview("testemail");
```

`KINDS.forEach` already binds Run. Do not bump APP_VERSION. Do not change ops in this task.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_call_home_cli_page.py tests/test_call_home_cli_ops.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add launchpad/call_home_cli.py tests/test_call_home_cli_page.py
git commit -m "Add Call Home Preview Test Email and per-array Test user select."
```

---

### Task 3: Health Server preview and run routes

**Files:**
- Modify: `launchpad/health_server.py`
- Modify: `tests/test_health_server_call_home_cli.py`

**Interfaces:**
- Consumes: `build_testemail_array_steps`, `preview_hash("testemail", …)`
- Produces: `preview_call_home_testemail`, `run_call_home_testemail`; POST `/api/call-home/preview-testemail` and `/api/call-home/run-testemail`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_health_server_call_home_cli.py` (reuse `_server`, `_bind`, `SERVERS`, `USERS`, `LSYS`, `CLOUD`):

```python
def test_preview_testemail_and_smtp_hash_cannot_run_it(monkeypatch):
    server = _server()
    _bind(monkeypatch, [
        ("lscloudcallhome", CLOUD),
        ("lsemailserver", SERVERS),
        ("lsemailuser", USERS),
        ("lssystem", LSYS),
    ])
    payload = {"arrays": [{"card_id": 1, "user_id": "1", "address": "EISSAN-Alerts@walgreens.com"}]}
    preview = server.preview_call_home_testemail(payload)
    assert preview["ok"] is True
    cmd = preview["arrays"][0]["steps"][0]["cmd"]
    assert cmd.startswith("svctask testemail")
    assert "chemailserver" not in cmd
    smtp_hash = preview_hash(
        "smtp",
        {"arrays": [{"card_id": 1, "smtp": {"ip": "1.2.3.4", "port": "25", "username": "u", "password": "x"}}]},
    )
    denied = server.run_call_home_testemail(
        {**payload, "confirm": True, "preview_hash": smtp_hash}
    )
    assert denied["ok"] is False
    empty = server.preview_call_home_testemail({"arrays": [{"card_id": 1, "user_id": "", "address": ""}]})
    assert empty["ok"] is False
```

`_bind` takes `(monkeypatch, mapping)` only — same as `test_smtp_chemailserver_in_place`.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_health_server_call_home_cli.py::test_preview_testemail_and_smtp_hash_cannot_run_it -v`

Expected: FAIL (`preview_call_home_testemail` missing)

- [ ] **Step 3: Wire Health Server**

At the top of `health_server.py`, add `build_testemail_array_steps` to the `call_home_cli_ops` import.

In the call-home `path in { ... }` set and `handlers` dict, add:

```python
            "/api/call-home/preview-testemail",
            "/api/call-home/run-testemail",
```

```python
                "/api/call-home/preview-testemail": lambda: server.preview_call_home_testemail(payload),
                "/api/call-home/run-testemail": lambda: server.run_call_home_testemail(payload, confirm=payload.get("confirm") is True),
```

After `run_call_home_smtp`, add:

```python
    def preview_call_home_testemail(self, payload: dict) -> dict[str, Any]:
        def builder(item, state):
            return build_testemail_array_steps(
                user_id=str(item.get("user_id") or item.get("id") or ""),
                address=str(item.get("address") or ""),
            )
        return self._call_home_preview_rows(payload, "testemail", builder)

    def run_call_home_testemail(self, payload: dict, *, confirm: bool) -> dict[str, Any]:
        def builder(item, state):
            return build_testemail_array_steps(
                user_id=str(item.get("user_id") or item.get("id") or ""),
                address=str(item.get("address") or ""),
            )
        return self._call_home_run_rows(
            payload,
            kind="testemail",
            confirm=confirm,
            confirm_warning="confirm must be true before sending a test email",
            hash_warning="Preview must be run again before sending a test email.",
            preview_fn=self.preview_call_home_testemail,
            builder=builder,
        )
```

`builder` may ignore `state`. Do not bump APP_VERSION.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_health_server_call_home_cli.py tests/test_call_home_cli_ops.py tests/test_call_home_cli_page.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add launchpad/health_server.py tests/test_health_server_call_home_cli.py
git commit -m "Wire Call Home testemail preview and run APIs."
```

---

### Task 4: Bump APP_VERSION to 1.6.189

**Files:**
- Modify: `launchpad/config.py`
- Modify: `tests/test_capacity_unit_js.py`
- Modify: `tests/test_hadoop_sudo_wire.py`
- Modify: `tests/test_system_connectivity_version.py`

**Interfaces:**
- Consumes: none
- Produces: `APP_VERSION = "1.6.189"`

- [ ] **Step 1: Write the failing pin updates**

Set the three version assertions to `"1.6.189"` (they currently expect `1.6.188`). Do not change `config.py` yet.

- [ ] **Step 2: Run pins to verify they fail**

Run: `python -m pytest tests/test_capacity_unit_js.py::test_app_version_153 tests/test_hadoop_sudo_wire.py::test_version_174 tests/test_system_connectivity_version.py -v`

Expected: FAIL (`1.6.188` != `1.6.189`)

- [ ] **Step 3: Bump config**

In `launchpad/config.py`: `APP_VERSION = "1.6.189"`

- [ ] **Step 4: Run pins to verify they pass**

Run: `python -m pytest tests/test_capacity_unit_js.py::test_app_version_153 tests/test_hadoop_sudo_wire.py::test_version_174 tests/test_system_connectivity_version.py tests/test_call_home_cli_ops.py tests/test_call_home_cli_page.py tests/test_health_server_call_home_cli.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add launchpad/config.py tests/test_capacity_unit_js.py tests/test_hadoop_sudo_wire.py tests/test_system_connectivity_version.py
git commit -m "Bump version to 1.6.189 for Call Home Test Email."
```

---

## Spec coverage

| Spec item | Task |
|-----------|------|
| `svctask testemail` id then address | 1 |
| Hash kind `testemail`; SMTP hash cannot unlock | 1, 3 |
| Empty Test user not runnable | 1, 3 |
| Preview/Run buttons after Run SMTP | 2 |
| Test user dropdown from Load current | 2 |
| No SMTP writes | 1, 3 |
| Routes preview-testemail / run-testemail | 2, 3 |
| APP_VERSION 1.6.189 | 4 |
