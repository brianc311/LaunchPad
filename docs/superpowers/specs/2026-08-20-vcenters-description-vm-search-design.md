# vCenters — Description, VM names, search, and client path

**Date:** 2026-08-20  
**Status:** Approved for implementation (pending user review of this file)  
**App version target:** 1.6.188  
**Depends on:** vCenters directory and vSphere Client launch (1.6.186–1.6.187)  
**Approach:** Two optional text fields on the existing JSON row (`description`, `vm_notes`); client-side Directory search; point `VpxClient.exe` at the working shortcut path.

## Problem

Operators need a purpose line and a paste-in list of VM names on each vCenter so they can tell sites apart and find the right VM. The Directory has no search. **Open vSphere Client** looks in `...\Infrastructure\Client\Launcher\vpxclient.exe`, which is not installed; the working shortcut is under `Virtual Infrastructure Client`.

## Goals

- Add / Edit form has **Description** (one line, optional) and **VM names** (multi-line comment, optional).
- Detail card shows Description (always) and a **VM names** section that starts **closed**.
- Directory list is unchanged (no new columns). A search box filters rows as you type.
- Search matches (case-insensitive substring) vCenter **name**, **address** (IP/hostname), and **VM names** text. It does not match Description, Location, URL, or username.
- **Open vSphere Client** starts  
  `C:\Program Files (x86)\VMware\Infrastructure\Virtual Infrastructure Client\Launcher\VpxClient.exe`  
  with Start in that Launcher folder.
- Old rows without the new fields behave as empty strings.
- Bump `APP_VERSION` to **1.6.188**.

## Non-goals

- Extra Directory columns.
- Structured VM rows (name+IP fields per VM).
- Searching Description, Location, URL, or username.
- Guessing other `VpxClient.exe` / `vpxclient.exe` folders.
- Desktop `.lnk` files.
- Encrypting Description or VM names.
- Live vCenter inventory API.
- Dashboard nav changes.

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| First field | **Description** / purpose, one line |
| Description after save | Detail card only |
| VM names | Multi-line comment, typed on Add/Edit |
| VM names on detail | Closed by default; click to expand |
| Search | Directory box; filter rows as you type |
| Search fields | Name, address/IP, VM names text |
| Exe path | `C:\Program Files (x86)\VMware\Infrastructure\Virtual Infrastructure Client\Launcher\VpxClient.exe` |
| Start in | That same Launcher folder (`exe.parent`) |
| Missing exe | Error naming that path; do not search other folders |
| Version | **1.6.188** |

## Behavior

New record fields (same `vcenters_directory` JSON list):

| Field | Required | Rules |
|-------|----------|--------|
| `description` | no | Trimmed one line; missing → `""` |
| `vm_notes` | no | Multi-line; trim ends only; keep inner newlines; missing → `""` |

`public_vcenter` includes both as plain text. They are not secrets. Unlock is still required to save; GET, search, and viewing work while locked. Web Link and launch checkbox/credentials are unchanged except the exe path.

**Search:** query is trimmed. Empty query shows all rows. A row matches if the query (casefold) is a substring of `name`, `address`, or `vm_notes`. Matching is a helper (`vcenter_matches_query(row, query) -> bool`) used by the page so tests can cover it without a browser.

**Page copy (exact):**

- Search placeholder: `Search name, IP, or VM`
- Form/detail label **Description**
- Form/detail label **VM names**
- Empty Description on detail: `—`
- Empty VM names: still show the collapsed header (no names inside)

Use a closed `<details>` / `<summary>VM names</summary>` on the detail card. Expanding does not save; content comes from the last saved `vm_notes`.

**Launch:** replace `VPXCLIENT_PATH` with the path above (`VpxClient.exe`). `cwd` remains `VPXCLIENT_PATH.parent`. Argv still `-s` address, plus `-u` / `-p` when set. Locked launch → **503**. Unknown id, checkbox off, or missing exe → **400** (message includes the expected path).

## Files (expected)

| File | Change |
|------|--------|
| `launchpad/vcenters_directory.py` | `description`, `vm_notes`, `vcenter_matches_query`, new `VPXCLIENT_PATH` |
| `launchpad/vcenters.py` | Form fields, detail Description + collapsed VM names, Directory search |
| `launchpad/health_server.py` | Launch uses updated `VPXCLIENT_PATH` (imported name); GET already returns `public_vcenters` |
| `launchpad/config.py` | **1.6.188** |
| Tests | Defaults, match helper, page markers, path string, version pins |

## Test plan

- Old row: Description and VM names empty; detail Description is `—`; VM names header present and closed.
- Save Description and a multi-line VM list; GET returns them; Edit shows them.
- Search `HPEW101` matches that name; search an IP fragment matches `address`; search a VM token in `vm_notes` shows that row; a Description-only token does not match.
- Empty search shows all rows.
- Launch path string is the `Virtual Infrastructure Client\...\VpxClient.exe` value; missing exe 400 names that path.
- Login screen shows **v1.6.188**.
