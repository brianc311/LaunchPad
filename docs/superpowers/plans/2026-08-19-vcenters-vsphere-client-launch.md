# vCenters vSphere Client Launch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a per-vCenter **vSphere Client** checkbox, encrypted username/password, and **Open vSphere Client** that starts `vpxclient.exe`, shipping as **1.6.187**.

**Architecture:** Extend the existing `vcenters_directory` JSON records. GET returns a public shape (`password` is `""` or `"***"`). Health Server encrypts on save and `Popen`s the desktop client on `POST /api/vcenters/launch`. The web Link is unchanged.

**Tech Stack:** Python, Health Server, `launchpad.crypto.encrypt_text` / `decrypt_text`, `subprocess.Popen`, pytest.

**Spec:** `docs/superpowers/specs/2026-08-19-vcenters-vsphere-client-launch-design.md`

## Global Constraints

- APP_VERSION bump to **1.6.187** only in the final version task. Do not bump in Tasks 1–3.
- Checkbox label exactly **vSphere Client**. Launch button exactly **Open vSphere Client**.
- Exe path exactly `C:\Program Files (x86)\VMware\Infrastructure\Client\Launcher\vpxclient.exe`. Do not search other folders.
- Argv: `vpxclient.exe -s {address}` plus `-u` / `-p` only when username / decrypted password are non-empty.
- GET never returns plaintext or ciphertext; `password` is `""` or `"***"`.
- `***` or omitted password on update keeps the stored secret. Explicit empty password clears it.
- Unlock required to save secrets and to launch (503). Web links still work without Unlock.
- Missing exe or checkbox off or unknown id → **400**. Locked launch → **503**.
- No Desktop `.lnk` files. No live vCenter API. No peer-page nav changes.
- Place imports at the top of modules (no inline imports).
- Windows PowerShell commits (`git commit -m "..."`); commit at each task commit step.
- Prefer TDD: failing test → implement → pass → commit.
- Do not commit `.superpowers/sdd*` scratch, `LaunchPad-Install/`, or install zips.
- Work on branch `feature/vcenters-vsphere-client-launch`.

## File structure

| File | Responsibility |
|------|----------------|
| `launchpad/vcenters_directory.py` | New fields, public shape, password keep/clear, exe path, argv |
| `tests/test_vcenters_directory.py` | Helper tests |
| `launchpad/vcenters.py` | Checkbox, username/password, launch button + fetch |
| `tests/test_vcenters_page.py` | Page markers |
| `launchpad/health_server.py` | Encrypt on upsert, public GET, `POST /api/vcenters/launch` |
| `tests/test_vcenters_api.py` | Save `***`, launch 503/400/ok |
| `launchpad/config.py` + version pins | **1.6.187** (Task 4 only) |

---

### Task 1: Directory fields, public password, argv helper

**Files:**
- Modify: `launchpad/vcenters_directory.py`
- Modify: `tests/test_vcenters_directory.py`

**Interfaces:**
- Consumes: `encrypt_text` from `launchpad.crypto` (password helper only)
- Produces:
  - `VCENTER_PASSWORD_PLACEHOLDER = "***"`
  - `VPXCLIENT_PATH = Path(r"C:\Program Files (x86)\VMware\Infrastructure\Client\Launcher\vpxclient.exe")`
  - `use_vsphere_client_enabled(value: object) -> bool`
  - `public_vcenter(record: dict) -> dict` — `password` is `""` or `"***"`; no `password_encrypted`
  - `public_vcenters(store: list[dict]) -> list[dict]`
  - `resolve_password_encrypted(incoming: dict, existing_encrypted: str, crypto_key: bytes) -> str`
  - `vpxclient_argv(address: str, username: str = "", password: str = "") -> list[str]`
  - `normalize_vcenter` stored shape also includes `use_vsphere_client: bool`, `username: str`, `password_encrypted: str` (missing → false / `""` / `""`)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_vcenters_directory.py` (keep existing tests; add imports):

```python
from cryptography.fernet import Fernet

from launchpad.crypto import decrypt_text, encrypt_text
from launchpad.vcenters_directory import (
    VCENTER_PASSWORD_PLACEHOLDER,
    VPXCLIENT_PATH,
    public_vcenter,
    resolve_password_encrypted,
    use_vsphere_client_enabled,
    vpxclient_argv,
)


def test_vsphere_client_fields_default_off_and_public_hides_secret():
    row = normalize_vcenter(
        {"name": "VC1", "address": "10.0.0.1"}, assign_id=True
    )
    assert row["use_vsphere_client"] is False
    assert row["username"] == ""
    assert row["password_encrypted"] == ""
    pub = public_vcenter(row)
    assert "password_encrypted" not in pub
    assert pub["password"] == ""
    assert pub["use_vsphere_client"] is False


def test_resolve_password_keeps_placeholder_and_clears_empty():
    key = Fernet.generate_key()
    stored = encrypt_text(key, "secret")
    assert (
        resolve_password_encrypted(
            {"password": VCENTER_PASSWORD_PLACEHOLDER}, stored, key
        )
        == stored
    )
    assert resolve_password_encrypted({}, stored, key) == stored
    assert resolve_password_encrypted({"password": ""}, stored, key) == ""
    fresh = resolve_password_encrypted({"password": "n3w"}, stored, key)
    assert decrypt_text(key, fresh) == "n3w"


def test_vpxclient_argv_and_path():
    assert str(VPXCLIENT_PATH) == (
        r"C:\Program Files (x86)\VMware\Infrastructure\Client\Launcher\vpxclient.exe"
    )
    assert vpxclient_argv("10.1.2.3") == [str(VPXCLIENT_PATH), "-s", "10.1.2.3"]
    assert vpxclient_argv("10.1.2.3", "admin", "pw") == [
        str(VPXCLIENT_PATH),
        "-s",
        "10.1.2.3",
        "-u",
        "admin",
        "-p",
        "pw",
    ]
    assert use_vsphere_client_enabled(True) is True
    assert use_vsphere_client_enabled("true") is True
    assert use_vsphere_client_enabled(None) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_vcenters_directory.py::test_vsphere_client_fields_default_off_and_public_hides_secret tests/test_vcenters_directory.py::test_resolve_password_keeps_placeholder_and_clears_empty tests/test_vcenters_directory.py::test_vpxclient_argv_and_path -v`

Expected: FAIL (import error — new names missing)

- [ ] **Step 3: Write minimal implementation**

In `launchpad/vcenters_directory.py`, add `from pathlib import Path` and `from launchpad.crypto import encrypt_text` at the top (no inline imports).

After `SETTING_VCENTERS_DIRECTORY`:

```python
VCENTER_PASSWORD_PLACEHOLDER = "***"
VPXCLIENT_PATH = Path(
    r"C:\Program Files (x86)\VMware\Infrastructure\Client\Launcher\vpxclient.exe"
)


def use_vsphere_client_enabled(value: object) -> bool:
    if value is True:
        return True
    text = str(value or "").strip().lower()
    return text in {"true", "1", "on", "yes"}


def public_vcenter(record: dict) -> dict:
    encrypted = str(record.get("password_encrypted") or "").strip()
    return {
        "id": str(record.get("id") or ""),
        "name": str(record.get("name") or ""),
        "location": str(record.get("location") or ""),
        "address": str(record.get("address") or ""),
        "url": str(record.get("url") or ""),
        "use_vsphere_client": use_vsphere_client_enabled(
            record.get("use_vsphere_client")
        ),
        "username": str(record.get("username") or ""),
        "password": VCENTER_PASSWORD_PLACEHOLDER if encrypted else "",
    }


def public_vcenters(store: list[dict]) -> list[dict]:
    return [public_vcenter(row) for row in store]


def resolve_password_encrypted(
    incoming: dict, existing_encrypted: str, crypto_key: bytes
) -> str:
    if "password" not in incoming:
        return str(existing_encrypted or "")
    text = incoming.get("password")
    if text is None:
        return str(existing_encrypted or "")
    raw = str(text)
    if raw == VCENTER_PASSWORD_PLACEHOLDER:
        return str(existing_encrypted or "")
    if not raw.strip():
        return ""
    return encrypt_text(crypto_key, raw)


def vpxclient_argv(address: str, username: str = "", password: str = "") -> list[str]:
    cmd = [str(VPXCLIENT_PATH), "-s", str(address)]
    user = str(username or "").strip()
    secret = str(password or "")
    if user:
        cmd.extend(["-u", user])
    if secret:
        cmd.extend(["-p", secret])
    return cmd
```

In `normalize_vcenter`, after building `url` and before the `id` checks, keep validation as today. Add to the returned dict:

```python
        "use_vsphere_client": use_vsphere_client_enabled(
            raw.get("use_vsphere_client")
        ),
        "username": str(raw.get("username") or "").strip(),
        "password_encrypted": str(raw.get("password_encrypted") or "").strip(),
```

Do not read plaintext `password` inside `normalize_vcenter`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_vcenters_directory.py -q`

Expected: PASS (including the original four tests)

- [ ] **Step 5: Commit**

```powershell
git add launchpad/vcenters_directory.py tests/test_vcenters_directory.py
git commit -m "Add vSphere Client fields and hidden-password helpers for vCenters."
```

---

### Task 2: Page checkbox, credentials, launch button

**Files:**
- Modify: `launchpad/vcenters.py`
- Modify: `tests/test_vcenters_page.py`

**Interfaces:**
- Consumes: API paths `/api/vcenters` and `/api/vcenters/launch` as strings
- Produces: page contains checkbox `id="use_vsphere_client"` text **vSphere Client**, `id="username"`, `id="password"`, button **Open vSphere Client**, and `fetch("/api/vcenters/launch"`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_vcenters_page.py`:

```python
def test_vcenters_page_has_vsphere_client_controls():
    assert 'id="use_vsphere_client"' in VCENTERS_HTML
    assert "vSphere Client" in VCENTERS_HTML
    assert 'id="username"' in VCENTERS_HTML
    assert 'id="password"' in VCENTERS_HTML
    assert "Open vSphere Client" in VCENTERS_HTML
    assert "/api/vcenters/launch" in VCENTERS_HTML
    assert 'id="d-username"' in VCENTERS_HTML
    assert 'id="launch-btn"' in VCENTERS_HTML
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_vcenters_page.py::test_vcenters_page_has_vsphere_client_controls -v`

Expected: FAIL (missing `id="use_vsphere_client"`)

- [ ] **Step 3: Update the page**

In the `<style>` block of `VCENTERS_HTML`, add:

```css
    .checks { display:flex; flex-wrap:wrap; align-items:center; gap:10px; margin-top:8px; }
    .checks label { flex-direction:row; align-items:center; cursor:pointer; font-weight:600; }
    .checks input { width:auto; accent-color:var(--accent); }
```

In the detail section, after the Link paragraph and before `.actions`, add:

```html
      <p id="d-user-wrap" hidden><strong>Username</strong><br><span id="d-username"></span></p>
```

In the detail `.actions` div, add the launch button as the first button:

```html
        <button id="launch-btn" type="button" hidden>Open vSphere Client</button>
```

After the URL override label in the form, add:

```html
        <label class="wide checks" style="grid-column:1 / -1;flex-direction:row;">
          <input id="use_vsphere_client" name="use_vsphere_client" type="checkbox"> vSphere Client
        </label>
        <label>Username<input id="username" name="username" autocomplete="username"></label>
        <label>Password<input id="password" name="password" type="password" autocomplete="new-password"></label>
```

In JS, next to `saveBtn`:

```javascript
    const launchBtn = document.getElementById("launch-btn");
```

In `setMutationsEnabled`, also set `launchBtn.disabled = !on`.

In `showDetail`, after setting the web link:

```javascript
      const useClient = row.use_vsphere_client === true;
      document.getElementById("d-user-wrap").hidden = !useClient;
      document.getElementById("d-username").textContent = row.username || "—";
      launchBtn.hidden = !useClient;
```

In `showForm`, after filling `url`:

```javascript
      document.getElementById("use_vsphere_client").checked = !!(row && row.use_vsphere_client);
      document.getElementById("username").value = row ? (row.username || "") : "";
      document.getElementById("password").value = row ? (row.password || "") : "";
```

Add to the save payload:

```javascript
        use_vsphere_client: document.getElementById("use_vsphere_client").checked,
        username: document.getElementById("username").value,
        password: document.getElementById("password").value,
```

After the save click handler, add:

```javascript
    launchBtn.addEventListener("click", async () => {
      if (!selectedId) return;
      const res = await fetch("/api/vcenters/launch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: selectedId }),
      });
      const data = await res.json();
      const statusEl = document.getElementById("list-status");
      if (!res.ok) {
        statusEl.textContent = data.error || "Launch failed.";
        detailSection.appendChild(statusEl);
        return;
      }
      statusEl.textContent = "vSphere Client started.";
    });
```

Do **not** move `list-status` out of the list section. Show launch errors on the detail card by adding `<p id="detail-status" class="status" role="status"></p>` at the bottom of `#detail-section` (after `.actions`) and write launch errors there instead of `list-status`.

Launch handler (use this, not the `list-status` version):

```javascript
    launchBtn.addEventListener("click", async () => {
      if (!selectedId) return;
      const statusEl = document.getElementById("detail-status");
      statusEl.textContent = "";
      const res = await fetch("/api/vcenters/launch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: selectedId }),
      });
      const data = await res.json();
      statusEl.textContent = res.ok
        ? "vSphere Client started."
        : (data.error || "Launch failed.");
    });
```

Keep the existing web Link. Do not add a list column.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_vcenters_page.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add launchpad/vcenters.py tests/test_vcenters_page.py
git commit -m "Add vSphere Client checkbox and launch controls to vCenters page."
```

---

### Task 3: Encrypt on save and launch API

**Files:**
- Modify: `launchpad/health_server.py`
- Modify: `tests/test_vcenters_api.py`

**Interfaces:**
- Consumes: `public_vcenters`, `resolve_password_encrypted`, `VPXCLIENT_PATH`, `decrypt_text`
- Produces:
  - `GET /api/vcenters` returns `public_vcenters(...)` (no `password_encrypted`)
  - `upsert_vcenter_record` encrypts password, returns public list
  - `delete_vcenter_record` returns public list
  - `HealthServer.launch_vcenter_client(vcenter_id: str) -> dict`
  - `POST /api/vcenters/launch`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_vcenters_api.py`:

```python
from cryptography.fernet import Fernet

from launchpad.crypto import decrypt_text
from launchpad.vcenters_directory import (
    SETTING_VCENTERS_DIRECTORY,
    VCENTER_PASSWORD_PLACEHOLDER,
    VPXCLIENT_PATH,
)


def test_vcenter_get_hides_password_and_keeps_placeholder(monkeypatch):
    server = HealthServer()
    settings, getter, setter = _settings_backend()
    key = Fernet.generate_key()
    server.set_settings_backend(getter, setter, crypto_key=key)
    saved = _post(
        "/api/vcenters",
        {
            "name": "remvcenter101",
            "address": "172.31.198.193",
            "use_vsphere_client": True,
            "username": "admin",
            "password": "s3cret",
        },
        monkeypatch,
        server,
    )
    row = saved["payload"]["vcenters"][0]
    assert row["password"] == VCENTER_PASSWORD_PLACEHOLDER
    assert "password_encrypted" not in row
    stored = json.loads(settings[SETTING_VCENTERS_DIRECTORY])[0]
    assert decrypt_text(key, stored["password_encrypted"]) == "s3cret"
    again = _post(
        "/api/vcenters",
        {
            "id": row["id"],
            "name": "remvcenter101",
            "address": "172.31.198.193",
            "use_vsphere_client": True,
            "username": "admin",
            "password": VCENTER_PASSWORD_PLACEHOLDER,
        },
        monkeypatch,
        server,
    )
    stored2 = json.loads(settings[SETTING_VCENTERS_DIRECTORY])[0]
    assert stored2["password_encrypted"] == stored["password_encrypted"]
    got = _get("/api/vcenters", monkeypatch, server)
    assert got["json"]["vcenters"][0]["password"] == VCENTER_PASSWORD_PLACEHOLDER


def test_launch_vcenter_client_requires_unlock_and_checkbox(monkeypatch):
    locked = _post("/api/vcenters/launch", {"id": "x"}, monkeypatch, HealthServer())
    assert locked["status"] == 503
    server = HealthServer()
    _settings, getter, setter = _settings_backend()
    key = Fernet.generate_key()
    server.set_settings_backend(getter, setter, crypto_key=key)
    created = _post(
        "/api/vcenters",
        {"name": "WebOnly", "address": "10.0.0.1", "use_vsphere_client": False},
        monkeypatch,
        server,
    )
    vid = created["payload"]["vcenters"][0]["id"]
    denied = _post("/api/vcenters/launch", {"id": vid}, monkeypatch, server)
    assert denied["status"] == 400
    missing = _post("/api/vcenters/launch", {"id": "nope"}, monkeypatch, server)
    assert missing["status"] == 400


def test_launch_vcenter_client_starts_process(monkeypatch, tmp_path):
    server = HealthServer()
    _settings, getter, setter = _settings_backend()
    key = Fernet.generate_key()
    server.set_settings_backend(getter, setter, crypto_key=key)
    created = _post(
        "/api/vcenters",
        {
            "name": "remvcenter101",
            "address": "172.31.198.193",
            "use_vsphere_client": True,
            "username": "admin",
            "password": "s3cret",
        },
        monkeypatch,
        server,
    )
    vid = created["payload"]["vcenters"][0]["id"]
    fake_exe = tmp_path / "vpxclient.exe"
    fake_exe.write_text("stub")
    monkeypatch.setattr(
        "launchpad.health_server.VPXCLIENT_PATH", fake_exe
    )
    monkeypatch.setattr(
        "launchpad.vcenters_directory.VPXCLIENT_PATH", fake_exe
    )
    started = []

    def fake_popen(cmd, **kwargs):
        started.append((cmd, kwargs))
        return object()

    monkeypatch.setattr("launchpad.health_server.subprocess.Popen", fake_popen)
    result = _post("/api/vcenters/launch", {"id": vid}, monkeypatch, server)
    assert result["status"] == 200
    assert result["payload"]["ok"] is True
    cmd, kwargs = started[0]
    assert cmd[0] == str(fake_exe)
    assert cmd[1:5] == ["-s", "172.31.198.193", "-u", "admin"]
    assert "-p" in cmd and "s3cret" in cmd
    assert kwargs.get("cwd") == str(fake_exe.parent)
```

Also add `import subprocess` only if the test file needs it (it does not if Popen is patched on `health_server`).

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_vcenters_api.py::test_vcenter_get_hides_password_and_keeps_placeholder tests/test_vcenters_api.py::test_launch_vcenter_client_requires_unlock_and_checkbox tests/test_vcenters_api.py::test_launch_vcenter_client_starts_process -v`

Expected: FAIL (`/api/vcenters/launch` 404 or password visible in GET)

- [ ] **Step 3: Wire Health Server**

At the top of `launchpad/health_server.py`, add `import subprocess` next to the other stdlib imports.

Extend the existing vcenters_directory import to include:

```python
from launchpad.vcenters_directory import (
    SETTING_VCENTERS_DIRECTORY,
    VPXCLIENT_PATH,
    delete_vcenter,
    parse_vcenters_setting,
    public_vcenters,
    resolve_password_encrypted,
    upsert_vcenter,
)
```

`decrypt_text` is already imported from `launchpad.crypto`.

Replace `get_vcenters` so the list is public:

```python
        return {
            "vcenters": public_vcenters(parse_vcenters_setting(raw)),
            "unlocked": unlocked,
        }
```

Replace `upsert_vcenter_record` body after the setter check:

```python
        with self._lock:
            getter = self._get_setting
            setter = self._set_setting
            crypto_key = self._crypto_key
        if not setter:
            raise RuntimeError("LaunchPad must be unlocked to save vCenters.")
        if crypto_key is None:
            raise RuntimeError("LaunchPad must be unlocked to save vCenters.")
        raw = (getter(SETTING_VCENTERS_DIRECTORY, "[]") or "[]") if getter else "[]"
        store = parse_vcenters_setting(raw)
        incoming_id = str(payload.get("id") or "").strip()
        existing = next((row for row in store if row["id"] == incoming_id), {})
        stored_payload = dict(payload)
        stored_payload["password_encrypted"] = resolve_password_encrypted(
            payload, str(existing.get("password_encrypted") or ""), crypto_key
        )
        stored_payload.pop("password", None)
        cleaned = upsert_vcenter(store, stored_payload)
        setter(SETTING_VCENTERS_DIRECTORY, json.dumps(cleaned))
        return {"vcenters": public_vcenters(cleaned), "unlocked": True}
```

Keep the original `if not setter` check; add the `crypto_key is None` check so password encrypt cannot run locked. Merge those two into one unlock RuntimeError as shown.

Change `delete_vcenter_record` return to `{"vcenters": public_vcenters(cleaned), "unlocked": True}`.

Add `launch_vcenter_client` immediately after `delete_vcenter_record`:

```python
    def launch_vcenter_client(self, vcenter_id: str) -> dict:
        with self._lock:
            getter = self._get_setting
            setter = self._set_setting
            crypto_key = self._crypto_key
        if not setter or crypto_key is None:
            raise RuntimeError("LaunchPad must be unlocked to launch vSphere Client.")
        raw = (getter(SETTING_VCENTERS_DIRECTORY, "[]") or "[]") if getter else "[]"
        store = parse_vcenters_setting(raw)
        target = str(vcenter_id or "").strip()
        row = next((item for item in store if item["id"] == target), None)
        if row is None:
            raise ValueError("Unknown vCenter.")
        if not row.get("use_vsphere_client"):
            raise ValueError("vSphere Client is not enabled for this vCenter.")
        if not VPXCLIENT_PATH.is_file():
            raise ValueError(f"vSphere Client not found: {VPXCLIENT_PATH}")
        password = decrypt_text(crypto_key, str(row.get("password_encrypted") or ""))
        cmd = [str(VPXCLIENT_PATH), "-s", str(row.get("address") or "")]
        user = str(row.get("username") or "").strip()
        if user:
            cmd.extend(["-u", user])
        if password:
            cmd.extend(["-p", password])
        subprocess.Popen(cmd, cwd=str(VPXCLIENT_PATH.parent), close_fds=False)
        return {"ok": True}
```

Build argv from `health_server.VPXCLIENT_PATH` so tests can monkeypatch that name. `vpxclient_argv` remains for Task 1 unit tests.

In `do_POST`, immediately after the `/api/vcenters/delete` block, add:

```python
        if path == "/api/vcenters/launch":
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
                    server.launch_vcenter_client(str(payload.get("id") or ""))
                )
            except RuntimeError as exc:
                self._send_json({"error": str(exc)}, status=503)
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=400)
            return
```

Existing tests that only assert `rows[0]["name"]` still pass. `json.loads(settings[SETTING_VCENTERS_DIRECTORY])` still truthy.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_vcenters_api.py tests/test_vcenters_directory.py tests/test_vcenters_page.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add launchpad/health_server.py tests/test_vcenters_api.py
git commit -m "Launch vSphere Client from vCenters with encrypted per-site credentials."
```

---

### Task 4: Bump APP_VERSION to 1.6.187

**Files:**
- Modify: `launchpad/config.py`
- Modify: `tests/test_capacity_unit_js.py`
- Modify: `tests/test_hadoop_sudo_wire.py`
- Modify: `tests/test_system_connectivity_version.py`

**Interfaces:**
- Consumes: none
- Produces: `APP_VERSION = "1.6.187"`

- [ ] **Step 1: Write the failing pin updates**

Set the three version assertions to `"1.6.187"` (they currently expect `1.6.186`). Do not change `config.py` yet.

- [ ] **Step 2: Run pins to verify they fail**

Run: `python -m pytest tests/test_capacity_unit_js.py::test_app_version_153 tests/test_hadoop_sudo_wire.py::test_version_174 tests/test_system_connectivity_version.py -v`

Expected: FAIL (`1.6.186` != `1.6.187`)

- [ ] **Step 3: Bump config**

In `launchpad/config.py`: `APP_VERSION = "1.6.187"`

- [ ] **Step 4: Run pins to verify they pass**

Run: `python -m pytest tests/test_capacity_unit_js.py::test_app_version_153 tests/test_hadoop_sudo_wire.py::test_version_174 tests/test_system_connectivity_version.py tests/test_vcenters_directory.py tests/test_vcenters_page.py tests/test_vcenters_api.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add launchpad/config.py tests/test_capacity_unit_js.py tests/test_hadoop_sudo_wire.py tests/test_system_connectivity_version.py
git commit -m "Bump version to 1.6.187 for vCenters vSphere Client launch."
```

---

## Spec coverage

| Spec item | Task |
|-----------|------|
| Checkbox **vSphere Client**, username, password on form | 2 |
| Detail keeps web link; **Open vSphere Client** when checked | 2 |
| Encrypted password; GET `""` / `"***"` | 1, 3 |
| Keep on `***`; clear on empty | 1, 3 |
| Launch exe path + `-s` / `-u` / `-p` | 1, 3 |
| Missing exe / checkbox off / unknown id → 400 | 3 |
| Locked launch → 503 | 3 |
| Old rows default checkbox off | 1 |
| No `.lnk`, no other-path search | (omitted) |
| APP_VERSION 1.6.187 | 4 |
