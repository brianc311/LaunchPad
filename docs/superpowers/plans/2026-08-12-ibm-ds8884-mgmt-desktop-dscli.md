# IBM DS8884 Management-Desktop SSH + DSCLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `ibm_ds8884` cards work via SSH to a management desktop running DSCLI CLI, with optional DSCLI path + HMC host wrapping (v**1.6.163**).

**Architecture:** New `wrap_dscli_command` rewrites `dscli …` strings with optional executable path, `-hmc1`, and `-user`/`-passwd`. Card columns `dscli_path` / `dscli_hmc` feed Admin UX and `resolve_card_commands` / inventory / system-connectivity DS8884 command lists. SSH stays password + keyboard-interactive.

**Tech Stack:** Python, Paramiko, CustomTkinter Admin, pytest, SQLite card columns.

**Spec:** `docs/superpowers/specs/2026-08-12-ibm-ds8884-mgmt-desktop-dscli-design.md`

## Global Constraints

- APP_VERSION is currently `1.6.162`; bump to `1.6.163` only in the final version task.
- Host = management desktop; do not add local DSCLI-to-HMC protocol or RDP/GUI automation.
- Optional fields: `dscli_path`, `dscli_hmc` (empty string default).
- Wrapper applies only to commands whose first token is `dscli` (case-insensitive) or whose first token ends with `dscli` / `dscli.bat` / `dscli.exe`.
- When `dscli_hmc` set and password non-empty: inject `-hmc1`, `-user`, `-passwd` after the executable. Never print passwords in test assertions beyond checking the flag is present with a fixture secret.
- When path and HMC empty: commands unchanged.
- Windows PowerShell commits; TDD; no `.superpowers/sdd*` or install zips in commits.

## File structure

| File | Responsibility |
|------|----------------|
| `launchpad/dscli_wrap.py` | `wrap_dscli_command`, `wrap_dscli_command_list` |
| `tests/test_dscli_wrap.py` | Wrapper unit tests |
| `launchpad/database.py` | Columns + Card fields + CRUD |
| `launchpad/ui/admin_view.py` | DS8884-only path/HMC fields + hint |
| `launchpad/command_format.py` | Apply wrap in `resolve_card_commands` |
| `launchpad/storage_inventory.py` | Wrap DS8884 topic cmds |
| `launchpad/system_connectivity.py` | Wrap DS8884 topic cmds |
| `launchpad/health_server.py` / `dashboard_view.py` | Pass path/hmc/user/password into resolve |
| `launchpad/config.py` + version pin tests | `1.6.163` |

---

### Task 1: DSCLI command wrapper

**Files:**
- Create: `launchpad/dscli_wrap.py`
- Create: `tests/test_dscli_wrap.py`

**Interfaces:**
- Produces:
  - `wrap_dscli_command(command: str, *, dscli_path: str = "", hmc_host: str = "", username: str = "", password: str = "") -> str`
  - `wrap_dscli_command_list(commands: list[str], *, dscli_path: str = "", hmc_host: str = "", username: str = "", password: str = "") -> list[str]`
  - `wrap_dscli_labeled_commands(commands: list[tuple[str, str]], *, ...) -> list[tuple[str, str]]` (label unchanged; command wrapped)

- [ ] **Step 1: Write failing tests**

Create `tests/test_dscli_wrap.py`:

```python
from launchpad.dscli_wrap import (
    wrap_dscli_command,
    wrap_dscli_command_list,
    wrap_dscli_labeled_commands,
)


def test_wrap_empty_options_unchanged():
    assert wrap_dscli_command("dscli lssi") == "dscli lssi"


def test_wrap_path_only_quotes_executable():
    out = wrap_dscli_command(
        "dscli lssi",
        dscli_path=r"C:\Program Files\IBM\dscli\dscli.bat",
    )
    assert out.startswith('"C:\\Program Files\\IBM\\dscli\\dscli.bat"')
    assert out.endswith(" lssi")
    assert " -hmc1 " not in out


def test_wrap_hmc_and_auth_flags():
    out = wrap_dscli_command(
        "dscli lssi",
        dscli_path="dscli.bat",
        hmc_host="10.1.2.3",
        username="admin",
        password="s3cret",
    )
    assert out.startswith('"dscli.bat"') or out.startswith("dscli.bat")
    assert " -hmc1 10.1.2.3 " in f" {out} " or " -hmc1 10.1.2.3" in out
    assert " -user admin " in f" {out} " or out.find("-user admin") >= 0
    assert " -passwd s3cret " in f" {out} " or out.find("-passwd s3cret") >= 0
    assert out.rstrip().endswith("lssi")


def test_wrap_hmc_without_password_skips_auth_flags():
    out = wrap_dscli_command("dscli lssi", hmc_host="10.1.2.3", username="admin")
    assert "-hmc1 10.1.2.3" in out
    assert "-passwd" not in out
    assert "-user" not in out


def test_wrap_non_dscli_unchanged():
    assert wrap_dscli_command("lssystem") == "lssystem"


def test_wrap_list_and_labeled():
    assert wrap_dscli_command_list(
        ["dscli showsp", "shownet"],
        hmc_host="1.2.3.4",
    ) == [
        wrap_dscli_command("dscli showsp", hmc_host="1.2.3.4"),
        "shownet",
    ]
    labeled = wrap_dscli_labeled_commands(
        [("Health", "dscli lssi")],
        dscli_path="dscli.bat",
    )
    assert labeled[0][0] == "Health"
    assert "dscli.bat" in labeled[0][1]
```

- [ ] **Step 2: Run tests — expect FAIL**

```powershell
python -m pytest tests/test_dscli_wrap.py -v
```

- [ ] **Step 3: Implement `launchpad/dscli_wrap.py`**

```python
"""Rewrite DSCLI command strings for remote SSH execution."""

from __future__ import annotations

import shlex


def _is_dscli_invocation(command: str) -> bool:
    parts = command.strip().split(None, 1)
    if not parts:
        return False
    token = parts[0].strip('"').lower().replace("\\", "/")
    base = token.rsplit("/", 1)[-1]
    return base in {"dscli", "dscli.bat", "dscli.exe"} or base.endswith("/dscli")


def _quote_exe(path: str) -> str:
    path = path.strip()
    if not path:
        return "dscli"
    if path.startswith('"') and path.endswith('"'):
        return path
    if any(ch in path for ch in (" ", "\t")):
        return f'"{path}"'
    return path


def wrap_dscli_command(
    command: str,
    *,
    dscli_path: str = "",
    hmc_host: str = "",
    username: str = "",
    password: str = "",
) -> str:
    raw = (command or "").strip()
    if not raw or not _is_dscli_invocation(raw):
        return raw
    parts = raw.split(None, 1)
    rest = parts[1] if len(parts) > 1 else ""
    exe = _quote_exe(dscli_path) if dscli_path.strip() else parts[0]
    flags: list[str] = []
    hmc = (hmc_host or "").strip()
    if hmc:
        flags.extend(["-hmc1", hmc])
        user = (username or "").strip()
        pwd = password or ""
        if pwd:
            if user:
                flags.extend(["-user", user])
            flags.extend(["-passwd", pwd])
    mid = " ".join(flags)
    if mid and rest:
        return f"{exe} {mid} {rest}"
    if mid:
        return f"{exe} {mid}"
    if rest:
        return f"{exe} {rest}"
    return exe


def wrap_dscli_command_list(
    commands: list[str],
    *,
    dscli_path: str = "",
    hmc_host: str = "",
    username: str = "",
    password: str = "",
) -> list[str]:
    return [
        wrap_dscli_command(
            cmd,
            dscli_path=dscli_path,
            hmc_host=hmc_host,
            username=username,
            password=password,
        )
        for cmd in commands
    ]


def wrap_dscli_labeled_commands(
    commands: list[tuple[str, str]],
    *,
    dscli_path: str = "",
    hmc_host: str = "",
    username: str = "",
    password: str = "",
) -> list[tuple[str, str]]:
    return [
        (
            label,
            wrap_dscli_command(
                cmd,
                dscli_path=dscli_path,
                hmc_host=hmc_host,
                username=username,
                password=password,
            ),
        )
        for label, cmd in commands
    ]
```

(Adjust quoting/`-hmc1` spacing so the Task 1 tests pass exactly.)

- [ ] **Step 4: Run tests — expect PASS**

```powershell
python -m pytest tests/test_dscli_wrap.py -v
```

- [ ] **Step 5: Commit**

```powershell
git add launchpad/dscli_wrap.py tests/test_dscli_wrap.py
git commit -m "Add DSCLI command wrapper for path and HMC flags."
```

---

### Task 2: Persist dscli_path / dscli_hmc + Admin UX

**Files:**
- Modify: `launchpad/database.py`
- Modify: `launchpad/ui/admin_view.py`
- Create or modify: `tests/test_dscli_card_fields.py` (or extend an existing admin/database card test if one fits)

**Interfaces:**
- Consumes: Card CRUD patterns in `database.py`
- Produces: `Card.dscli_path: str`, `Card.dscli_hmc: str`; Admin entries visible only for `ibm_ds8884`

- [ ] **Step 1: Failing test — round-trip columns**

```python
from launchpad.database import Database


def test_card_persists_dscli_path_and_hmc(tmp_path):
    db = Database(tmp_path / "t.db")
    cid = db.add_card(
        {
            "name": "DS1",
            "card_type": "ssh",
            "host": "10.0.0.5",
            "device_profile": "ibm_ds8884",
            "dscli_path": r"C:\dscli\dscli.bat",
            "dscli_hmc": "10.0.0.9",
            "encrypted_password": "",
            "encrypted_sudo_password": "",
            "encrypted_key_passphrase": "",
            "encrypted_key": "",
        }
    )
    card = db.get_card(cid)
    assert card.dscli_path == r"C:\dscli\dscli.bat"
    assert card.dscli_hmc == "10.0.0.9"
    db.update_card(
        cid,
        {
            "name": "DS1",
            "card_type": "ssh",
            "host": "10.0.0.5",
            "device_profile": "ibm_ds8884",
            "dscli_path": "",
            "dscli_hmc": "10.0.0.8",
            "encrypted_password": "",
            "encrypted_sudo_password": "",
            "encrypted_key_passphrase": "",
            "encrypted_key": "",
            "username": "",
            "url": "",
            "icon": "default",
            "category": "General",
            "sort_order": 0,
            "glow_color": "#FF6B00",
            "key_file_path": "",
            "custom_commands": "",
            "serial_number": "",
            "port": None,
        },
    )
    card2 = db.get_card(cid)
    assert card2.dscli_path == ""
    assert card2.dscli_hmc == "10.0.0.8"
```

(Match `add_card`/`update_card` required keys to whatever the file already requires — mirror an existing database card test if present.)

- [ ] **Step 2: Run test — expect FAIL**

```powershell
python -m pytest tests/test_dscli_card_fields.py -v
```

- [ ] **Step 3: Schema + Card fields**

In `database.py`:
- Add `dscli_path: str = ""` and `dscli_hmc: str = ""` to `Card`.
- `ALTER TABLE cards ADD COLUMN dscli_path TEXT DEFAULT ''` and `dscli_hmc` (same try/except pattern as other columns).
- Include both in INSERT/UPDATE/SELECT mapping/`export_cards_raw`/`_row_to_card`.

- [ ] **Step 4: Admin UI**

In `admin_view.py`:
- Add entries `dscli_path` and `dscli_hmc` after device profile (or near Host).
- Hint label (wraplength ~420):  
  `DS8884: Host is the management desktop (OpenSSH). Optional DSCLI path if not on PATH; optional HMC host for -hmc1.`
- Show path/HMC/hint only when profile is `ibm_ds8884` (toggle on profile change + load card); grid_remove otherwise.
- Load/save via `_populate` / `_collect` / save payload including `dscli_path` / `dscli_hmc`.

- [ ] **Step 5: Tests PASS + commit**

```powershell
python -m pytest tests/test_dscli_card_fields.py -v
git add launchpad/database.py launchpad/ui/admin_view.py tests/test_dscli_card_fields.py
git commit -m "Persist DS8884 DSCLI path and HMC host on cards."
```

---

### Task 3: Wire wrapper into resolve + inventory + connectivity

**Files:**
- Modify: `launchpad/command_format.py`
- Modify: `launchpad/health_server.py` (call sites of `resolve_card_commands`)
- Modify: `launchpad/ui/dashboard_view.py` (call sites)
- Modify: `launchpad/storage_inventory.py`
- Modify: `launchpad/system_connectivity.py`
- Modify: `tests/test_dscli_wrap.py` or add `tests/test_dscli_resolve.py`

**Interfaces:**
- Extends `resolve_card_commands(..., *, dscli_path: str = "", dscli_hmc: str = "", username: str = "", password: str = "")`
- After existing ensures, if profile is `ibm_ds8884` (casefold), run `wrap_dscli_labeled_commands`
- `inventory_commands_for_profile` / `topic_commands_for_profile` stay raw presets; wrapping happens at scan call sites that have card credentials — **or** add optional kwargs to those helpers. Prefer: wrap at the health_server DS8884 scan paths and in `resolve_card_commands` for refresh.

- [ ] **Step 1: Failing test**

```python
from launchpad.command_format import resolve_card_commands


def test_resolve_ds8884_applies_hmc_wrap():
    cmds = resolve_card_commands(
        "ibm_ds8884",
        "",
        dscli_path="dscli.bat",
        dscli_hmc="10.9.9.9",
        username="admin",
        password="pw",
    )
    assert cmds
    joined = " ".join(c for _, c in cmds)
    assert "10.9.9.9" in joined
    assert "dscli.bat" in joined or '"dscli.bat"' in joined
```

- [ ] **Step 2: Implement resolve + pass-through**

Update `resolve_card_commands` signature and end with:

```python
    from launchpad.dscli_wrap import wrap_dscli_labeled_commands

    commands = apply_command_placeholders(commands, instance_id=instance_id)
    if device_profile.strip().lower() == "ibm_ds8884":
        commands = wrap_dscli_labeled_commands(
            commands,
            dscli_path=dscli_path,
            hmc_host=dscli_hmc,
            username=username,
            password=password,
        )
    return commands
```

At every `resolve_card_commands(...)` call site that has a card object, pass:

```python
dscli_path=getattr(card, "dscli_path", "") or "",
dscli_hmc=getattr(card, "dscli_hmc", "") or "",
username=str(getattr(card, "username", "") or ""),
password=<decrypted password already used for SSH at that site>,
```

If a call site has no decrypted password yet, pass `password=""` (HMC auth flags omitted; path/HMC still apply).

For DS8884 inventory/system-connectivity command lists in `health_server.py` (`_scan_*_ds_card`), wrap the command strings with `wrap_dscli_command_list` using the card’s path/hmc/user/password before SSH exec.

- [ ] **Step 3: Run tests**

```powershell
python -m pytest tests/test_dscli_wrap.py tests/test_dscli_resolve.py tests/test_hpe_capacity_commands.py tests/test_storage_presets_drives.py -v
```

- [ ] **Step 4: Commit**

```powershell
git add launchpad/command_format.py launchpad/health_server.py launchpad/ui/dashboard_view.py launchpad/storage_inventory.py launchpad/system_connectivity.py tests/test_dscli_resolve.py
git commit -m "Wire DSCLI wrap into DS8884 refresh and scans."
```

---

### Task 4: Auth error clarity + version 1.6.163

**Files:**
- Modify: `launchpad/ssh_paramiko.py` and/or `launchpad/ssh_interactive.py` (message only if needed)
- Modify: `launchpad/config.py`
- Modify: `tests/test_system_connectivity_version.py`, `tests/test_hadoop_sudo_wire.py`, `tests/test_capacity_unit_js.py`

- [ ] **Step 1:** Ensure auth failure text mentions checking Host (management desktop), username/password, and OpenSSH (extend existing `AuthenticationException` message in `authenticate_with_password` / interactive shell print). Keep existing KI tests passing.

- [ ] **Step 2:** Set `APP_VERSION = "1.6.163"` and pin tests.

- [ ] **Step 3:**

```powershell
python -m pytest tests/test_dscli_wrap.py tests/test_dscli_card_fields.py tests/test_dscli_resolve.py tests/test_ssh_keyboard_interactive.py tests/test_system_connectivity_version.py -v
```

- [ ] **Step 4: Commit**

```powershell
git commit -m "Bump version to 1.6.163 for DS8884 management-desktop DSCLI."
```

---

## Spec coverage (self-review)

| Spec item | Task |
|-----------|------|
| wrap path + HMC + user/passwd | Task 1 |
| Card fields + Admin UX/hint | Task 2 |
| resolve + inventory/connectivity | Task 3 |
| Clearer SSH auth errors | Task 4 |
| Version 1.6.163 | Task 4 |
| No local DSCLI / no RDP | All (out of scope) |
