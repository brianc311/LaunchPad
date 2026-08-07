# Hadoop SSH sudo password — Design

**Date:** 2026-08-07  
**Status:** Approved  
**App version target:** next patch after tip (1.6.132+)  
**Depends on:** SSH card Admin secrets (`encrypted_password`); Paramiko `exec_command`; `hadoop_linux` profile / Host Power runners  
**Approach:** Approach A — separate encrypted **Sudo password** on Hadoop cards; for commands containing `sudo`, run as `sudo -S` and write the password to stdin. Hadoop-only.

## Problem

Hadoop Linux hosts often require a sudo password for `sudo systemctl …` / `sudo shutdown …`. LaunchPad today only stores the SSH login password/key and runs non-interactive `exec_command`, so sudo prompts hang or fail. Operators need a way to store a sudo password and have health refresh + Host Power supply it for sudo commands — without changing non-Hadoop cards.

## Goals

- Add a per-card encrypted **Sudo password** field in Admin for `hadoop_linux` cards.
- When running a command on a `hadoop_linux` card whose command text includes `sudo`:
  - Normalize to `sudo -S …` if `-S` is not already present.
  - Feed the stored sudo password on stdin (newline-terminated) via Paramiko.
- Apply to **health refresh and Host Power** (any sudo-bearing command on that profile).
- Clear failure if a sudo command runs but no sudo password is configured (no hang on interactive prompt).
- Leave non-`hadoop_linux` cards and non-sudo commands unchanged.

## Non-goals (v1)

- Passwordless-sudo detection or “test sudo” wizard.
- Applying sudo password to IBM/HPE/other storage profiles.
- Interactive Connect-terminal sudo typing.
- Reusing SSH login password as sudo password (separate field only).
- Wrapping every Hadoop command in sudo (only commands that already include `sudo`).

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Scope | `hadoop_linux` only |
| Storage | Separate encrypted Admin field (not SSH password) |
| When to supply | Any command text that includes `sudo` (health + Host Power) |
| Mechanism | `sudo -S` + stdin password (Approach A) |

## Behavior

### Admin

- For SSH cards with device profile **Hadoop / Linux SSH**, show **Sudo password** entry (masked), same vault encryption pattern as SSH password.
- On load: decrypt into the field when set (same pattern as SSH password). On save: encrypt the current field value; empty clears the stored sudo password.
- Persisted as encrypted blob on the card (`encrypted_sudo_password`); DB migration as needed.

### Runtime

- Resolve sudo password only for `device_profile == hadoop_linux`.
- If command contains `sudo` (case-sensitive token match on `sudo` as a command word is preferred; simple substring `sudo` is acceptable if documented):
  - Ensure `-S` is passed to sudo (rewrite leading `sudo` → `sudo -S` when missing).
  - Require non-empty decrypted sudo password; else fail with a clear message such as `Sudo password required for this Hadoop command`.
  - `exec_command(command)`; write `password + "\n"` to stdin; close stdin; read stdout/stderr as today.
- If command does not include `sudo`, run unchanged (no stdin password).

### Host Power

- Uses the same Hadoop SSH runner path so `Power -` steps that use `sudo` automatically get `-S` + stdin.
- Existing abort-on-failure / confirm gates remain unchanged.

### Errors

- Missing sudo password for a sudo command → fail that step/command with a clear error (Host Power aborts remaining steps for that host).
- Wrong password → remote failure output; treat as command failure.
- Decrypt failure → surface like other vault decrypt errors in Admin / run path.

## Architecture

| Piece | Role |
|-------|------|
| `database.py` / `Card` | Store `encrypted_sudo_password` |
| `admin_view.py` | Sudo password UI for `hadoop_linux` |
| `ssh_utils` / auth resolve | Decrypt sudo password into auth/context for Hadoop |
| `ssh_paramiko` or small helper | `ensure_sudo_stdin(command) -> (command, needs_stdin)`; exec with stdin feed |
| Health monitor / Host Power runner | Pass sudo password into runner for `hadoop_linux` only |

## Testing

- Command rewrite: `sudo shutdown -h now` → `sudo -S shutdown -h now`; already `-S` unchanged; non-sudo unchanged.
- Runner feeds stdin only when Hadoop + sudo password + sudo command.
- Missing password → explicit error, no hang.
- Non-hadoop profile ignores sudo password field even if somehow set.
- Admin encrypt/decrypt round-trip for the new field (unit test with crypto helpers).

## Out of scope follow-ups

- Optional “use SSH password for sudo” checkbox.
- `sudo -n` (non-interactive fail-fast) probe before runs.
- Connect-session automated sudo.
