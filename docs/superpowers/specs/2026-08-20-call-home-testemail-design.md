# Call Home CLI — Test Email (saved SMTP)

**Date:** 2026-08-20  
**Status:** Approved for implementation (pending user review of this file)  
**App version target:** 1.6.189  
**Extends:** `docs/superpowers/specs/2026-08-18-call-home-cli-smtp-users-cloud-design.md`  
**Depends on:** Call Home CLI page (`/call-home-cli`, IBM `SVC_PROFILES` SSH cards, Load current users)  
**Approach:** Sixth independent Preview/Run kind. SSH `svctask testemail` to one loaded user per checked array. Uses SMTP already on the array. Does not write SMTP or contact.

## Problem

Operators want to prove the array can send mail **before** changing SMTP. IBM has no CLI that tries a typed username/password without `mkemailserver` / `chemailserver`. The array command is `testemail`, which uses the **saved** email server and **sends a real message** to a configured user.

## Goals

- Per-array **Test user** dropdown filled from **Load current** (existing email users).
- **Preview Test Email** then **Run Test Email** (own `preview_hash`; other kinds cannot unlock it).
- Command: `svctask testemail {id}` (address if no id).
- No `chemailserver`, `mkemailserver`, `startemail`, `rmemailuser`, or other writes.
- Card Username/Password fields are ignored for this kind; password never in the payload.
- Unlock required. First real CLI error stops **that** array; others continue; no rollback.
- Bump `APP_VERSION` to **1.6.189**.

## Non-goals

- Testing unsaved form SMTP credentials.
- `testemail -all`.
- Auto `startemail` if email is stopped.
- Insights URL, proxy, HPE / Dell / DS8884.
- Persisting the last Test user in the LaunchPad DB.

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Where | From the **array** over SSH |
| IBM command | `svctask testemail` to one existing user |
| Recipient | Operator picks from that card’s loaded users |
| SMTP write | None |
| Form username/password | Unused for this kind |
| UI | Sixth Preview/Run pair after **Run SMTP** |
| Version | **1.6.189** |

## Page

Keep path `/call-home-cli` and the five existing pairs. After **Run SMTP** add:

| Preview | Run (disabled until matching Preview) |
|---------|----------------------------------------|
| Preview Test Email | Run Test Email |

Per array card, after the user list: **Test user** `<select>` of loaded rows, label `address (type)`, value = user `id` (fallback `address`). Empty until Load current. Changing the select invalidates preview (same as other fields).

Confirm modal names this kind (test email). Select all / none still select arrays.

## APIs

| Method | Path | Kind |
|--------|------|------|
| POST | `/api/call-home/preview-testemail` | `testemail` |
| POST | `/api/call-home/run-testemail` | `testemail` |

Payload per array: `card_id` plus chosen user `id` and/or `address` (same shape as loaded users). `preview_hash` is `kind` + those ids. Run requires `confirm: true` and this kind’s hash.

Not runnable: no checked arrays; empty Test user.

CLI error text is shown per array (including stopped email, no server, or unknown user). Do not treat those as success. Do not cache Load current users on the server; the page sends the selected id/address.

## CLI quoting

Same as other Call Home kinds: IBM double-quoted argument; reject `"`, CR, LF, or NUL. Use `cli_token` when it already matches. Preview/logs show the full `svctask testemail …` command (no password).

## Files (expected)

| File | Change |
|------|--------|
| `launchpad/call_home_cli.py` | Buttons, Test user select, kind `testemail` |
| `launchpad/call_home_cli_ops.py` | Step builder `svctask testemail`; hash kind `testemail` |
| `launchpad/health_server.py` | Preview/run routes |
| `launchpad/config.py` | **1.6.189** |
| Tests | Ops steps; hash isolation; page markers; version pins |

## Test plan

- Preview lists `svctask testemail` with the selected user id; no `chemailserver` / `mkemailserver`.
- SMTP `preview_hash` does not unlock Run Test Email.
- Empty Test user → that array not runnable.
- Login screen shows **v1.6.189**.
