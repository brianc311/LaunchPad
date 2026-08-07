# Hadoop Sudo Password Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let operators store an encrypted sudo password on `hadoop_linux` cards and have LaunchPad run sudo-bearing commands via `sudo -S` with that password on stdin for health refresh and Host Power.

**Architecture:** Pure helpers rewrite/detect sudo commands. Paramiko/`run_remote_ssh_command` gain an optional `sudo_password` and feed stdin when needed. Card DB + Admin store `encrypted_sudo_password`. HealthCard registration, refresh suite, and Host Power runners pass the decrypted sudo password only for `hadoop_linux`.

**Tech Stack:** Python, SQLite card schema, Paramiko `exec_command` + stdin, CustomTkinter Admin, pytest.

**Spec:** `docs/superpowers/specs/2026-08-07-hadoop-sudo-password-design.md`

## Global Constraints

- APP_VERSION is currently `1.6.132`; bump to `1.6.133` when shipping the wiring/UI task.
- Scope is **`hadoop_linux` only** — never apply sudo password to other profiles.
- Separate encrypted field `encrypted_sudo_password` — do **not** reuse SSH login password.
- Supply password only for commands whose text matches the sudo command word (`\bsudo\b`).
- Mechanism: normalize to `sudo -S` and write `password + "\n"` to stdin; no PTY prompt scraping.
- Missing sudo password + sudo command → clear failure (`Sudo password required for this Hadoop command`); do not hang.
- Non-sudo commands unchanged (no stdin password).
- On Admin load/save: decrypt into field when set; empty on save clears stored value.
- Windows PowerShell commits (`git commit -m "..."`); commit at each task’s commit step.
- Prefer TDD: failing test → implement → pass → commit.

## File structure

| File | Responsibility |
|------|----------------|
| `launchpad/hadoop_sudo.py` | Detect sudo, normalize `-S`, prepare command or raise missing-password |
| `launchpad/ssh_paramiko.py` | Optional stdin feed on `exec_command` paths used for Hadoop |
| `launchpad/ssh_commands.py` | Thread `sudo_password` through `run_remote_ssh_command` / `run_remote_command_suite` |
| `launchpad/database.py` | `Card.encrypted_sudo_password` + schema migrate + CRUD |
| `launchpad/ui/admin_view.py` | Sudo password field; show for `hadoop_linux` |
| `launchpad/ssh_utils.py` | Decrypt sudo password helper (or extend auth) |
| `launchpad/health_server.py` | `HealthCard.sudo_password`; register/refresh/Host Power runners |
| `launchpad/monitor.py` | Pass sudo password when registering dashboard entries |
| `launchpad/config.py` | `APP_VERSION` → `1.6.133` |
| `tests/test_hadoop_sudo.py` | Helper + stdin/normalize unit tests |
| `tests/test_hadoop_sudo_wire.py` | Suite/runner/DB/Admin marker tests as needed |

---

### Task 1: Sudo command helpers

**Files:**
- Create: `launchpad/hadoop_sudo.py`
- Create: `tests/test_hadoop_sudo.py`

**Interfaces:**
- Produces:
  - `SUDO_PASSWORD_REQUIRED = "Sudo password required for this Hadoop command"`
  - `command_needs_sudo(command: str) -> bool` — True when `\bsudo\b` matches
  - `ensure_sudo_dash_s(command: str) -> str` — if needs sudo and `-S` not already among sudo’s options before the utility, insert `-S` after `sudo`
  - `prepare_hadoop_sudo_command(command: str, *, sudo_password: str) -> tuple[str, str | None]`  
    Returns `(remote_command, stdin_payload)` where `stdin_payload` is `password + "\n"` when sudo is needed, else `(command, None)`.  
    If needs sudo and `sudo_password` is empty/whitespace → raise `ValueError(SUDO_PASSWORD_REQUIRED)`.

- [ ] **Step 1: Write the failing tests**

```python
import pytest
from launchpad.hadoop_sudo import (
    SUDO_PASSWORD_REQUIRED,
    command_needs_sudo,
    ensure_sudo_dash_s,
    prepare_hadoop_sudo_command,
)


def test_command_needs_sudo_token():
    assert command_needs_sudo("sudo shutdown -h now")
    assert command_needs_sudo("sudo -n true")
    assert not command_needs_sudo("uptime")
    assert not command_needs_sudo("echo sudoish")


def test_ensure_sudo_dash_s():
    assert ensure_sudo_dash_s("sudo shutdown -h now") == "sudo -S shutdown -h now"
    assert ensure_sudo_dash_s("sudo -S shutdown -h now") == "sudo -S shutdown -h now"
    assert ensure_sudo_dash_s("uptime") == "uptime"


def test_prepare_feeds_stdin_or_errors():
    cmd, payload = prepare_hadoop_sudo_command("sudo shutdown -h now", sudo_password="secret")
    assert cmd == "sudo -S shutdown -h now"
    assert payload == "secret\n"
    cmd2, payload2 = prepare_hadoop_sudo_command("uptime", sudo_password="secret")
    assert cmd2 == "uptime"
    assert payload2 is None
    with pytest.raises(ValueError, match=SUDO_PASSWORD_REQUIRED):
        prepare_hadoop_sudo_command("sudo true", sudo_password="")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_hadoop_sudo.py -v`

Expected: FAIL (module missing)

- [ ] **Step 3: Write minimal implementation**

Create `launchpad/hadoop_sudo.py` using `re.search(r"\bsudo\b", command)` for detection. For `ensure_sudo_dash_s`, if the command already has `sudo` followed by options including `-S` (e.g. `sudo -S`, `sudo -nS`, or separate `-S`), leave as-is; otherwise replace the first `sudo` token with `sudo -S`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_hadoop_sudo.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add launchpad/hadoop_sudo.py tests/test_hadoop_sudo.py
git commit -m "Add Hadoop sudo -S command helpers."
```

---

### Task 2: Paramiko / remote SSH stdin support

**Files:**
- Modify: `launchpad/ssh_paramiko.py` (`run_ssh_command`, `run_ssh_auth_command`, and any helper used for single-command exec)
- Modify: `launchpad/ssh_commands.py` (`run_remote_ssh_command`, `run_remote_command_suite`)
- Modify: `tests/test_hadoop_sudo.py` (add runner tests with mocks)

**Interfaces:**
- Consumes: `prepare_hadoop_sudo_command`
- Produces:
  - `run_ssh_command(..., stdin_data: str | None = None)` — if `stdin_data` set, write to channel stdin and shut it down before reading output
  - `run_ssh_auth_command(..., stdin_data: str | None = None)` — same
  - `run_remote_ssh_command(..., sudo_password: str = "")` — when `sudo_password` non-empty **or** command needs sudo: call `prepare_hadoop_sudo_command`; on missing password raise; pass `stdin_data` into Paramiko path. For OpenSSH key CLI fallback path: if sudo stdin is required, raise a clear `ValueError` that password-auth or Paramiko key path is required for sudo (do not try to pipe via system ssh unless already supported — keep YAGNI: prefer forcing Paramiko via existing password/key helpers).  
    Practical rule: when prepared command needs stdin, always use Paramiko (`run_ssh_command` or `run_ssh_auth_command`), not the system `ssh` subprocess branch.
  - `run_remote_command_suite(..., sudo_password: str = "")` — when `sudo_password` is non-empty, **do not** use the batch `run_ssh_commands` password path; run each command via `run_remote_ssh_command(..., sudo_password=sudo_password)` so stdin can differ per command. When `sudo_password` empty, preserve existing behavior (including missing-password errors only when a sudo command is hit via prepare inside `run_remote_ssh_command` if you pass empty and command needs sudo — for health refresh without sudo password, sudo commands must fail clearly per command in the suite).

**Important:** For `hadoop_linux` health refresh without a sudo password, non-sudo commands still succeed; sudo commands record per-command errors. Implement suite so a prepare/`ValueError` on one command does not abort the whole suite (match existing per-command try/except on the key path).

- [ ] **Step 1: Write failing tests**

Add to `tests/test_hadoop_sudo.py` (mock Paramiko client or patch `run_ssh_command`):

```python
from unittest.mock import MagicMock, patch
from launchpad.ssh_commands import run_remote_ssh_command


def test_run_remote_feeds_stdin_for_sudo(monkeypatch):
    seen = {}

    def fake_run_ssh_command(host, port, username, password, command, *, timeout=45, stdin_data=None):
        seen["command"] = command
        seen["stdin_data"] = stdin_data
        return "ok"

    monkeypatch.setattr("launchpad.ssh_commands.run_ssh_command", fake_run_ssh_command)
    out = run_remote_ssh_command(
        "10.0.0.1", 22, "user", "sudo shutdown -h now",
        password="ssh-pass", sudo_password="sudo-pass",
    )
    assert out == "ok"
    assert seen["command"] == "sudo -S shutdown -h now"
    assert seen["stdin_data"] == "sudo-pass\n"


def test_run_remote_errors_without_sudo_password():
    with pytest.raises(ValueError, match="Sudo password required"):
        run_remote_ssh_command(
            "10.0.0.1", 22, "user", "sudo true",
            password="ssh-pass", sudo_password="",
        )
```

Adjust patch targets to match real import paths inside `ssh_commands.py`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_hadoop_sudo.py -v`

Expected: FAIL on missing `sudo_password` / `stdin_data` kwargs

- [ ] **Step 3: Implement stdin wiring**

In `ssh_paramiko.py`, after `exec_command`:

```python
stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
if stdin_data:
    stdin.write(stdin_data)
    stdin.flush()
    stdin.channel.shutdown_write()
```

Update all three single-command helpers that health uses. Extend `run_remote_ssh_command` to prepare sudo and prefer Paramiko when stdin is needed. Update `run_remote_command_suite` to accept `sudo_password` and use per-command execution when it is non-empty; also when `sudo_password` is empty, still call `run_remote_ssh_command` per command on password-auth path if any command needs sudo (or always per-command for simplicity when `device_profile == "hadoop_linux"` — acceptable and clearer). Prefer: if `sudo_password` or `device_profile == "hadoop_linux"`, use the per-command loop (both password and key).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_hadoop_sudo.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add launchpad/ssh_paramiko.py launchpad/ssh_commands.py tests/test_hadoop_sudo.py
git commit -m "Feed sudo -S password on stdin for remote SSH commands."
```

---

### Task 3: Persist sudo password + Admin UI

**Files:**
- Modify: `launchpad/database.py`
- Modify: `launchpad/ui/admin_view.py`
- Modify: `launchpad/ssh_utils.py` (add `resolve_sudo_password(card, crypto_key) -> str`)
- Create or extend: `tests/test_hadoop_sudo_wire.py` (DB round-trip + Admin markers)

**Interfaces:**
- Produces:
  - `Card.encrypted_sudo_password: str`
  - Schema: `ALTER TABLE cards ADD COLUMN encrypted_sudo_password TEXT DEFAULT ''` (same migrate pattern as other columns)
  - Insert/update/select/`_row_to_card` / export-import include the field
  - Admin: masked **Sudo password** entry; in `_SECRET_ENTRY_KEYS`; visible when `_selected_device_profile_key() == "hadoop_linux"` (toggle in `_on_device_profile_change` / load card)
  - `resolve_sudo_password(card, crypto_key) -> str` — decrypt or `""` on failure/empty; callers only use for `hadoop_linux`

- [ ] **Step 1: Write failing tests**

```python
from launchpad.crypto import encrypt_text, decrypt_text
# use temp DB path pattern from existing DB tests if any


def test_card_persists_encrypted_sudo_password(tmp_path, crypto_helper_if_available):
    ...


def test_admin_has_sudo_password_field_marker():
    from pathlib import Path
    text = Path("launchpad/ui/admin_view.py").read_text(encoding="utf-8")
    assert "sudo_password" in text
    assert "Sudo password" in text
```

If no shared crypto fixture exists, unit-test encrypt/decrypt of a string into a temp Database card CRUD.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_hadoop_sudo_wire.py -v`

Expected: FAIL

- [ ] **Step 3: Implement DB + Admin**

1. Add column migrate in `_init_schema`.
2. Extend `Card`, INSERT, UPDATE, `_row_to_card`, backup/restore dicts.
3. Admin: add entry after Password; show/hide based on profile; load/save encrypt like password (`encrypt_text(self.crypto_key, value)`); empty clears.
4. `resolve_sudo_password` in `ssh_utils.py`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_hadoop_sudo_wire.py tests/test_hadoop_sudo.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add launchpad/database.py launchpad/ui/admin_view.py launchpad/ssh_utils.py tests/test_hadoop_sudo_wire.py
git commit -m "Persist Hadoop sudo password in Admin and card database."
```

---

### Task 4: Wire health refresh + Host Power + version

**Files:**
- Modify: `launchpad/health_server.py` — `HealthCard.sudo_password`; `register_card(... sudo_password="")`; `refresh_card` → `run_remote_command_suite(..., sudo_password=...)` when `device_profile == "hadoop_linux"`; `_snap_run_command` / Host Power runner pass `sudo_password` for Hadoop cards
- Modify: `launchpad/monitor.py` — `HealthDashboardEntry.sudo_password`; resolve via `resolve_sudo_password` when registering; pass into `register_card`
- Modify: `launchpad/ui/dashboard_view.py` — any place that builds `HealthDashboardEntry` / `register_card` for health (match Ansible/Host Power open helpers) must pass sudo password for Hadoop
- Modify: `launchpad/config.py` — `APP_VERSION = "1.6.133"`
- Modify: version-pin tests if any assert `1.6.132`
- Extend: `tests/test_hadoop_sudo_wire.py` / Host Power tests — mock runner receives sudo password for hadoop card

**Interfaces:**
- Consumes: `resolve_sudo_password`, `run_remote_command_suite(..., sudo_password=)`, `run_remote_ssh_command(..., sudo_password=)`
- Non-hadoop: always pass `sudo_password=""`

- [ ] **Step 1: Write failing wiring tests**

```python
def test_host_power_runner_passes_sudo_password(monkeypatch):
    # Build a HealthServer with a hadoop_linux HealthCard including sudo_password
    # Monkeypatch run_remote_ssh_command to capture kwargs
    # Invoke _snap_run_command or host_power path with a sudo command
    ...


def test_version_133():
    from launchpad.config import APP_VERSION
    assert APP_VERSION == "1.6.133"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_hadoop_sudo_wire.py -v`

Expected: FAIL on version / missing kwarg

- [ ] **Step 3: Wire registration and runners**

1. Add `sudo_password: str = ""` to `HealthCard` and `register_card`.
2. In `build_health_dashboard_entries` / `_register_entry`, set `sudo_password=resolve_sudo_password(card, crypto_key)` only when `device_profile == "hadoop_linux"`.
3. `refresh_card`: pass `sudo_password=card.sudo_password` into suite when profile is hadoop (or always pass card.sudo_password which is empty for others).
4. `_snap_run_command` / Host Power:  
   `run_remote_ssh_command(..., password=card.password, ..., sudo_password=card.sudo_password if card.device_profile == "hadoop_linux" else "")`
5. Grep for other `HealthDashboardEntry(` / `register_card(` call sites in `dashboard_view.py` and update.
6. Bump version to `1.6.133`.

- [ ] **Step 4: Run focused tests**

```powershell
python -m pytest tests/test_hadoop_sudo.py tests/test_hadoop_sudo_wire.py tests/test_host_power_ops.py tests/test_host_power_api.py tests/test_hadoop_presets.py -q
```

Expected: all PASS

- [ ] **Step 5: Commit**

```powershell
git add launchpad/health_server.py launchpad/monitor.py launchpad/ui/dashboard_view.py launchpad/config.py tests
git commit -m "Wire Hadoop sudo password into health refresh and Host Power (1.6.133)."
```

---

## Spec coverage checklist

| Spec requirement | Task |
|------------------|------|
| Detect sudo / `sudo -S` normalize | 1 |
| Missing password clear error | 1, 2 |
| Stdin feed via Paramiko | 2 |
| Per-command suite (not batch) when sudo in play | 2 |
| `encrypted_sudo_password` DB | 3 |
| Admin field show for `hadoop_linux` | 3 |
| Load decrypt / empty clears | 3 |
| Health refresh uses sudo password | 4 |
| Host Power uses same path | 4 |
| Non-hadoop unchanged | 2, 4 |
| Version bump | 4 → 1.6.133 |

## Placeholder / consistency self-review

- Error string locked: `Sudo password required for this Hadoop command`
- Field name locked: `encrypted_sudo_password` / Admin key `sudo_password`
- Profile gate locked: `hadoop_linux`
- No TBD left in steps
