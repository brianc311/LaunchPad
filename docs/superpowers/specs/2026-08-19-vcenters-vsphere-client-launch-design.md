# vCenters — vSphere Client launch

**Date:** 2026-08-19  
**Status:** Approved for implementation (pending user review of this file)  
**App version target:** 1.6.187  
**Depends on:** vCenters directory (`vcenters_directory`, `/vcenters`, Health Server unlock + `crypto_key`)  
**Approach:** Per-row checkbox. Checked sites keep the web link and gain **Open vSphere Client**, which starts the local `vpxclient.exe` with optional stored username/password.

## Problem

Some vCenters (starting with `remvcenter101`) must be opened in the desktop VMware vSphere Client, not only the web UI. Operators want a checkbox they can turn on per site, stored credentials, and a one-click launch from the existing vCenters page.

## Goals

- Add / Edit form has **vSphere Client** checkbox (default off), **Username**, and **Password**.
- Detail card keeps the web Link. When the checkbox is on, also show username (not password) and **Open vSphere Client**.
- Username and password persist with the row, encrypted with the LaunchPad crypto key. GET never returns plaintext (`""` or `"***"`).
- Launch runs  
  `C:\Program Files (x86)\VMware\Infrastructure\Client\Launcher\vpxclient.exe`  
  with `-s {address}` and `-u` / `-p` only when those values are set.
- Unlock required to save secrets and to launch. Web links still work without Unlock.
- Existing rows without the new fields behave as checkbox off.
- Bump `APP_VERSION` to **1.6.187**.

## Non-goals

- Creating Desktop `.lnk` shortcuts.
- Guessing alternate `vpxclient.exe` paths if the spec path is missing.
- Changing the web-link URL rules.
- Live vCenter API, inventory, or notes.
- Showing passwords in the browser after save.
- Changing Ansible Pad, SSH cards, or other dashboard tools.

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Action | Launch `vpxclient.exe` (the vSphere Client login window) |
| Credentials | Saved encrypted per site, like SSH cards |
| Web link | Stays; **Open vSphere Client** is extra |
| Scope | Per-vCenter checkbox; others stay web-only until checked |
| Exe path | `C:\Program Files (x86)\VMware\Infrastructure\Client\Launcher\vpxclient.exe` |
| Missing exe | Error message; do not search other folders |
| Version | **1.6.187** |

## Behavior

New record fields (in the same `vcenters_directory` JSON list):

| Field | Required | Rules |
|-------|----------|--------|
| `use_vsphere_client` | no | Bool; missing → `false` |
| `username` | no | Trimmed |
| `password_encrypted` | no | `encrypt_text(crypto_key, plaintext)`; empty plaintext → `""` |

**Save password:**

- New non-empty password (not `***`) → encrypt and store.
- `***` or omitted password on update → keep existing `password_encrypted`.
- Explicit empty password while unlocked → clear stored secret.

**GET `/api/vcenters`:** each row includes `use_vsphere_client`, `username`, and `password` as `""` or `"***"` (never ciphertext, never plaintext).

**POST `/api/vcenters/launch`:** body `{ "id": "..." }`.

- Locked (`_set_setting` / crypto key missing) → **503** unlock error.
- Unknown id → **400**.
- `use_vsphere_client` is false → **400**.
- Exe missing → **400**, message includes the expected path.
- Else `Popen` the exe with cwd = launcher folder; argv `vpxclient.exe`, `-s`, address; if username: `-u`, username; if decrypted password: `-p`, password. Return `{ "ok": true }`. Do not wait for the client to exit.

**Page:** checkbox label **vSphere Client**. Launch button label **Open vSphere Client**. Launch errors show on the detail card.

## Files (expected)

| File | Change |
|------|--------|
| `launchpad/vcenters_directory.py` | New fields, password keep/clear, public vs stored shape |
| `launchpad/vcenters.py` | Checkbox, user/password, launch button, POST launch |
| `launchpad/health_server.py` | Encrypt on save, `POST /api/vcenters/launch` |
| `launchpad/config.py` | **1.6.187** |
| Tests | Helper encrypt/keep-`***`; launch 503/400; page markers; version pins |

## Test plan

- Old row without new fields: checkbox off; no launch button.
- Check the box, save user/password, reload: password field is `***`; username still shown.
- Save again with `***`: password unchanged; launch still works.
- Unchecked site: launch API returns 400; detail has no **Open vSphere Client**.
- Locked: launch 503; web link still present.
- Missing `vpxclient.exe`: 400 naming that path.
- Login screen shows **v1.6.187**.
