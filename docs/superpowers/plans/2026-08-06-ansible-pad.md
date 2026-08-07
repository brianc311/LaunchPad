# Ansible Pad Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Ansible Pad so operators can download/sync Ansible packages from LaunchPad data and run `ansible-playbook` on control host `plp5-dz5-nw`, while keeping native Contingency / FlashCopy CG SSH as Path A.

**Architecture:** Pure export builders create inventory + stub playbooks + ZIP. Remote helpers SCP and execute over Paramiko to the Ansible control host only. HealthServer exposes settings + export + sync-run + run-existing APIs; a new `/ansible-pad` page and dashboard button drive the UI. Mutating runs require `confirm: true`; `--check` is first-class.

**Tech Stack:** Python, Paramiko (existing), zipfile, HealthServer HTML/JS pages, pytest with mocked SSH.

**Spec:** `docs/superpowers/specs/2026-08-06-ansible-pad-design.md`

## Global Constraints

- APP_VERSION is currently `1.6.130`; bump to `1.6.131` when shipping Ansible Pad.
- Default control host: `plp5-dz5-nw` (configurable via settings).
- Do not embed private keys or array passwords in exported YAML.
- Path A (Contingency / FlashCopy CG native Run) must remain unchanged.
- Non-check mutating API calls require `confirm: true` or return 400.
- Windows PowerShell commits (here-string), no bash heredoc.
- Commit at each task’s commit step.

## File structure

| File | Responsibility |
|------|----------------|
| `launchpad/ansible_pad_settings.py` | Setting key constants + normalize settings dict |
| `launchpad/ansible_pad_export.py` | Inventory/vars/playbook file map + ZIP bytes |
| `launchpad/ansible_pad_remote.py` | SCP sync + remote `ansible-playbook` command runner (injectable SSH) |
| `launchpad/ansible_pad.py` | `ANSIBLE_PAD_PATH`, `ANSIBLE_PAD_HTML` |
| `launchpad/health_server.py` | Routes + settings get/set + orchestration |
| `launchpad/ui/dashboard_view.py` | Dashboard **Ansible Pad** button |
| `launchpad/config.py` | `APP_VERSION` → `1.6.131` |
| `tests/test_ansible_pad_export.py` | Package/ZIP tests |
| `tests/test_ansible_pad_remote.py` | Command construction + confirm gating helpers |
| `tests/test_ansible_pad_api.py` | HTTP/API tests with mocks |
| `tests/test_ansible_pad_page.py` | HTML markers / dashboard wiring smoke |

---

### Task 1: Settings + export package (ZIP)

**Files:**
- Create: `launchpad/ansible_pad_settings.py`
- Create: `launchpad/ansible_pad_export.py`
- Create: `tests/test_ansible_pad_export.py`

**Interfaces:**
- Produces:
  - `ANSIBLE_PAD_HOST = "ansible_pad_host"` (and keys for user, key_path, key_passphrase, password, remote_dir, default_playbook)
  - `DEFAULT_ANSIBLE_PAD_HOST = "plp5-dz5-nw"`
  - `normalize_ansible_pad_settings(raw: dict) -> dict`
  - `build_ansible_pad_files(*, cards: list[dict], contingency_groups: list[dict], control_host: str = DEFAULT_ANSIBLE_PAD_HOST) -> dict[str, str]`  
    Keys at least: `README.md`, `inventory/hosts.yml`, `playbooks/start_fc_consistgrp.yml`, `playbooks/snap_copy_stub.yml`
  - `build_ansible_pad_zip_bytes(...) -> bytes` (ZIP of that file map)

- [ ] **Step 1: Write failing tests**

```python
from launchpad.ansible_pad_export import build_ansible_pad_files, build_ansible_pad_zip_bytes
from launchpad.ansible_pad_settings import DEFAULT_ANSIBLE_PAD_HOST, normalize_ansible_pad_settings
import zipfile, io

def test_default_host():
    s = normalize_ansible_pad_settings({})
    assert s["host"] == "plp5-dz5-nw"

def test_package_contains_inventory_playbooks_readme():
    files = build_ansible_pad_files(
        cards=[{"id": 1, "name": "site-a", "host": "10.0.0.1", "username": "user", "device_profile": "flashsystem_5200"}],
        contingency_groups=[],
    )
    assert "inventory/hosts.yml" in files
    assert "10.0.0.1" in files["inventory/hosts.yml"]
    assert "playbooks/start_fc_consistgrp.yml" in files
    assert "prestartfcconsistgrp" in files["playbooks/start_fc_consistgrp.yml"]
    assert "startfcconsistgrp" in files["playbooks/start_fc_consistgrp.yml"]
    assert "plp5-dz5-nw" in files["README.md"]
    assert "BEGIN RSA PRIVATE KEY" not in "\n".join(files.values())

def test_zip_bytes_roundtrip():
    raw = build_ansible_pad_zip_bytes(cards=[], contingency_groups=[])
    zf = zipfile.ZipFile(io.BytesIO(raw))
    names = zf.namelist()
    assert "README.md" in names
    assert any(n.startswith("playbooks/") for n in names)
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `python -m pytest tests/test_ansible_pad_export.py -v`

- [ ] **Step 3: Implement settings + export**

`ansible_pad_settings.py`: constants + `normalize_ansible_pad_settings` returning keys `host`, `user`, `key_path`, `key_passphrase`, `password`, `remote_dir`, `default_playbook` with host default `plp5-dz5-nw`.

`ansible_pad_export.py`:
- Build YAML inventory listing card hosts (name-safe inventory hostname from card name/id).
- Include username as `ansible_user` when present; never write key material.
- Stub `playbooks/start_fc_consistgrp.yml` with vars `cg_name` and shell tasks for `svctask prestartfcconsistgrp` / `startfcconsistgrp` (document that array SSH is via Ansible inventory on the control host).
- Stub `playbooks/snap_copy_stub.yml` with placeholder tasks / comments pointing operators to Contingency Preview steps; include at least one `svctask` example pattern and `when: not ansible_check_mode` or a `perform_changes` var gate.
- README mentions dual path and `plp5-dz5-nw`.
- ZIP via `zipfile`.

- [ ] **Step 4: Run tests — expect PASS**

- [ ] **Step 5: Commit**

```powershell
git add launchpad/ansible_pad_settings.py launchpad/ansible_pad_export.py tests/test_ansible_pad_export.py
git commit -m @"
Add Ansible Pad export package builder and settings defaults.
"@
```

---

### Task 2: Remote SCP + ansible-playbook helpers

**Files:**
- Create: `launchpad/ansible_pad_remote.py`
- Create: `tests/test_ansible_pad_remote.py`

**Interfaces:**
- Consumes: settings dict from Task 1
- Produces:
  - `build_ansible_playbook_argv(*, playbook: str, inventory: str | None, check: bool) -> list[str]`
  - `require_confirm_for_mutate(*, check: bool, confirm: bool) -> None` raises `ValueError` if mutate without confirm
  - `sync_files_via_sftp(sftp, remote_dir: str, files: dict[str, str]) -> None` (injectable sftp-like)
  - `run_remote_argv(exec_fn, argv: list[str], *, cwd: str | None = None) -> dict` with `returncode`, `stdout`, `stderr`

- [ ] **Step 1: Write failing tests**

```python
from launchpad.ansible_pad_remote import (
    build_ansible_playbook_argv,
    require_confirm_for_mutate,
)

def test_check_mode_argv():
    argv = build_ansible_playbook_argv(
        playbook="playbooks/start_fc_consistgrp.yml",
        inventory="inventory/hosts.yml",
        check=True,
    )
    assert argv[0] == "ansible-playbook"
    assert "--check" in argv

def test_mutate_requires_confirm():
    try:
        require_confirm_for_mutate(check=False, confirm=False)
        assert False, "expected ValueError"
    except ValueError:
        pass
    require_confirm_for_mutate(check=True, confirm=False)
    require_confirm_for_mutate(check=False, confirm=True)
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement remote helpers** (no live SSH in unit tests; keep Paramiko connection factory optional/late for Task 3)

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit**

```powershell
git add launchpad/ansible_pad_remote.py tests/test_ansible_pad_remote.py
git commit -m @"
Add Ansible Pad remote playbook argv helpers and confirm gate.
"@
```

---

### Task 3: HealthServer APIs (settings, export, sync-run, run-existing)

**Files:**
- Modify: `launchpad/health_server.py`
- Create: `tests/test_ansible_pad_api.py`

**Interfaces:**
- Produces routes:
  - `GET /ansible-pad` → HTML
  - `GET /api/ansible-pad/settings` → normalized settings (no secrets echoed if empty; password may be masked as `***` when set)
  - `POST /api/ansible-pad/settings` → save settings
  - `GET /api/ansible-pad/export.zip` → ZIP download
  - `POST /api/ansible-pad/sync-run` body: `{ "playbook": "...", "check": true/false, "confirm": true/false, "extra_vars": {} }`
  - `POST /api/ansible-pad/run-existing` body: `{ "playbook": "/remote/path.yml", "check": ..., "confirm": ... }`
- Methods on `HealthServer`: `get_ansible_pad_settings`, `set_ansible_pad_settings`, `export_ansible_pad_zip_bytes`, `ansible_pad_sync_run`, `ansible_pad_run_existing`
- `open_ansible_pad()` opens browser like other report pages

- [ ] **Step 1: API tests with FakeServer / monkeypatched remote**
  - export ZIP 200 + zip magic
  - sync-run check=true succeeds without confirm
  - sync-run check=false without confirm → 400
  - run-existing uses remote path

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Wire routes + settings persistence** via `_get_setting` / `_set_setting` JSON blob or individual keys under `ansible_pad_*`

For sync-run: build files → mockable `connect`/`sftp`/`exec` injected on HealthServer for tests; default implementation uses Paramiko to settings host.

- [ ] **Step 4: Run focused API tests — PASS**

- [ ] **Step 5: Commit**

```powershell
git add launchpad/health_server.py tests/test_ansible_pad_api.py
git commit -m @"
Expose Ansible Pad export and remote run APIs on HealthServer.
"@
```

---

### Task 4: Ansible Pad page + dashboard button + version

**Files:**
- Create: `launchpad/ansible_pad.py`
- Modify: `launchpad/ui/dashboard_view.py` (add tool button + open helper mirroring Site Lookup)
- Modify: `launchpad/monitor.py` if other pages register open helpers there
- Modify: `launchpad/config.py` → `1.6.131`
- Create: `tests/test_ansible_pad_page.py`
- Optionally modify: `launchpad/health_server.py` nav links on sibling pages (only if pattern is “add link everywhere”; prefer dashboard + page self-nav)

**Interfaces:**
- `ANSIBLE_PAD_PATH = "/ansible-pad"`
- Page controls: settings fields, Download ZIP, Sync & Run (check checkbox default on), Run existing, confirm checkbox for mutate, log `<pre>`

- [ ] **Step 1: Page marker tests**

```python
from launchpad.ansible_pad import ANSIBLE_PAD_HTML, ANSIBLE_PAD_PATH

def test_ansible_pad_markers():
    assert ANSIBLE_PAD_PATH == "/ansible-pad"
    assert "Ansible Pad" in ANSIBLE_PAD_HTML
    assert "/api/ansible-pad/export.zip" in ANSIBLE_PAD_HTML
    assert "/api/ansible-pad/sync-run" in ANSIBLE_PAD_HTML
    assert "/api/ansible-pad/run-existing" in ANSIBLE_PAD_HTML
    assert "plp5-dz5-nw" in ANSIBLE_PAD_HTML
```

Also assert dashboard tool list contains `"Ansible Pad"` string in `dashboard_view.py` (import/source read or smoke via attribute if easier).

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement page + dashboard open** (register cards if needed like other tools; open `server.open_ansible_pad()`)

- [ ] **Step 4: Bump `APP_VERSION` to `1.6.131`**

- [ ] **Step 5: Run**

```powershell
python -m pytest tests/test_ansible_pad_export.py tests/test_ansible_pad_remote.py tests/test_ansible_pad_api.py tests/test_ansible_pad_page.py -q
```

Expected: PASS

- [ ] **Step 6: Commit**

```powershell
git add launchpad/ansible_pad.py launchpad/ui/dashboard_view.py launchpad/monitor.py launchpad/config.py launchpad/health_server.py tests/test_ansible_pad_page.py
git commit -m @"
Add Ansible Pad UI and dashboard entry (1.6.131).
"@
```

---

## Spec coverage (self-review)

| Spec requirement | Task |
|------------------|------|
| Path A unchanged | — (no Contingency/FC CG edits) |
| `/ansible-pad` page + dashboard | 4 |
| Generate package + ZIP | 1, 3 |
| Settings default `plp5-dz5-nw` | 1, 3 |
| Sync & Run SCP + playbook | 2, 3 |
| Run existing | 2, 3 |
| Confirm for mutate; check mode | 2, 3, 4 |
| No keys in ZIP | 1 |
| README / dual-path | 1, 4 |
| Version bump | 4 |

**Placeholder scan:** none intentional.  
**Type consistency:** settings dict keys `host`/`user`/`key_path`/`key_passphrase`/`password`/`remote_dir`/`default_playbook` used across tasks.
