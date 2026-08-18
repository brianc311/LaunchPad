# Call Home CLI (contact, location, SMTP add/remove)

**Date:** 2026-08-18  
**Status:** Approved for implementation (pending user review of this file)  
**App version target:** 1.6.178  
**Depends on:** none (new HealthServer page; IBM SSH cards only)  
**Approach:** One HealthServer page, ESX-snap Policy pattern: Preview then Run. Two Run kinds so apply and SMTP cleanup cannot mix.

## Problem

Call Home fields in the IBM GUI (Support → Call Home) are CLI objects. LaunchPad already **reads** `lscloudcallhome` and `lsemailserver` (Storage Inventory / System Connectivity). It does **not** write them. Operators need a page to set shared contact, per-array location, optionally add an SMTP server, and remove leftover SMTP stacks — without storing an SMTP password in the LaunchPad database.

Houston (V5kHOU-g3v1) example: Cloud Call Home Active; SMTP `172.29.62.98:25` user `avijaytc` Failed Temporary; they are **not using SMTP** but still need add and remove for old data.

## Goals

- Dashboard button opens a Call Home CLI page for IBM `SVC_PROFILES` SSH cards (one or many).
- Load live cloud status, contact, location, and SMTP summary; edit in place; Preview then Run.
- **Apply fields:** shared contact, per-array location, optional `mkemailserver`.
- **Remove SMTP:** `stopemail` → `rmemailuser` each → `rmemailserver` each. Leave cloud Call Home, contact, and location.
- SMTP password typed at Preview/Run only; never stored in LaunchPad DB; masked in Preview text and logs.
- Stop **that array** on the first real CLI error; continue the next array; no rollback.
- Bump `APP_VERSION` to **1.6.178**.

## Non-goals

- Cloud Call Home enable/disable (`chcloudcallhome` / `cfgcloudcallhome`).
- Storage Insights URL, proxy, Test Notification.
- Creating or deleting support/local email users on Apply (add is server-only).
- Blanking fields (`-nocontact` and similar). Apply only sets non-empty flags.
- Silent overwrite of an existing email server (`chemailserver`).
- Automatic rollback.
- HPE / Dell / DS8884.

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Arrays | One or many IBM SSH cards |
| Modes | Apply fields **and** live-edit on one page |
| Shape | HealthServer page; Preview then Run; two Run kinds |
| Cleanup v1 | SMTP stack only: servers, email users, `stopemail` |
| Apply-to-many | Shared contact/SMTP add; location per array |
| Cloud Call Home | Status only |
| SMTP add | `mkemailserver` only (IP/port/user/password) |
| Set fields v1 | Shared contact + per-array location |
| Password | Typed at Preview/Run; never in DB; masked in Preview/logs |
| Errors | Stop that array; continue next; no rollback |
| Existing SMTP on Apply | That array errors (no silent overwrite). Skip SMTP add if those fields are empty |

## Page

- Path: `/call-home-cli`
- Title: **Call Home CLI**
- Dashboard button **Call Home CLI** next to **System Connectivity**
- Open via `_open_sync_browser_report` (same as ESX-snap Policy)
- IBM `SVC_PROFILES` with a non-empty host only
- Array IP is `https://{host}` **outside** the checkbox `<label>` (`target="_blank"` `rel="noopener"`), same as ESX-snap Policy
- Fetch `try/catch` so Load / Preview / Run never sit on a spinner forever

**Layout**

1. Shared **contact:** name, reply email, primary phone, alternate phone
2. Optional SMTP **add:** IP or hostname, port, username, password. Leave all four empty to skip SMTP add. If any is filled, IP and port (`1–65535`) are required; username is optional; password is required when username is set.
3. Per array: checkbox, name, IP link, cloud Call Home status (read-only), location fields (company, street, city, state, postal, country, comment), live SMTP summary (server IP:port, user, user list or “none”)
4. Actions: Select all / none, **Load current**, **Preview Apply**, **Run Apply** (disabled until a matching Apply Preview), **Preview Remove SMTP**, **Run Remove SMTP** (disabled until a matching Remove Preview)

Load current fills contact, location, cloud status, and SMTP summary from the array. If shared contact fields are empty, fill them from the first successfully loaded **checked** array (or the first success if none are checked). Location always comes from **that** array.

## APIs

| Method | Path | Role |
|--------|------|------|
| GET | `/api/call-home/cards` | IBM eligible cards (id, name, host, profile) |
| POST | `/api/call-home/state` | Live load for one `{card_id}` (page loops per card; one failure does not block others) |
| POST | `/api/call-home/preview-apply` | Build Apply steps; return `preview_hash` |
| POST | `/api/call-home/run-apply` | Mutate; requires `confirm: true` and Apply `preview_hash` |
| POST | `/api/call-home/preview-remove` | Build Remove steps; return `preview_hash` |
| POST | `/api/call-home/run-remove` | Mutate; requires `confirm: true` and Remove `preview_hash` |

Apply Preview hash must not unlock Run Remove, and vice versa.

## Live load (bounded SSH)

Per array, **four** commands only (no loops over objects):

1. `svcinfo lscloudcallhome -delim :` (fallback without `-delim`)
2. `svcinfo lsemailserver -delim :`
3. `svcinfo lsemailuser -delim :`
4. `svcinfo lssystem` (key:value object detail for contact/location)

Cloud status reuses `parse_svc_call_home`. SMTP summary lists each server’s IP, port, username (no password). Email users list name/address and `user_type`. Contact/location parsed from `lssystem` with key aliases; missing keys are empty strings.

| Form field | `lssystem` keys (first hit wins) |
|------------|----------------------------------|
| Contact name | `email_contact`, `contact` |
| Reply | `email_reply`, `reply` |
| Primary phone | `email_contact_primary`, `email_primary` |
| Alternate phone | `email_contact_alternate`, `email_alternate` |
| Company | `email_organization`, `organization` |
| Street | `email_street`, `email_address`, `email_machine_address` |
| City | `email_city`, `email_machine_city` |
| State | `email_state`, `email_machine_state` |
| Postal | `email_zip`, `email_machine_zip` |
| Country | `email_country`, `email_machine_country` |
| Comment | `email_contact_location`, `email_location`, `location` |

Failed load shows the error on **that** card; other arrays continue.

## CLI quoting

Contact, location, email, and password values are **not** `cli_token` (they contain `@`, spaces, digits). Helper: IBM double-quoted argument; reject `"`, CR, LF, or NUL in a value. Tokens that already match `cli_token` (IPv4, hostname, numeric port, username without `@`) may stay unquoted.

Password appears in the real SSH command. Preview text, page confirm modal, and LaunchPad logs substitute `********`. `preview_hash` includes `sha256(password)` (empty string when omitted), never the raw password in JSON responses.

## Apply (per selected array)

**Skip empty groups.** Send only non-empty flags. v1 does not clear fields.

1. If any shared contact field is non-empty:  
   `svctask chemail` with `-contact` `-reply` `-primary` `-alternate` as present.
2. If any of **that** array’s location fields is non-empty:  
   `svctask chemail` with `-organization` `-address` `-city` `-state` `-zip` `-country` `-location` (comment → `-location`) as present.  
   Do **not** call `chsystem` in v1.
3. If SMTP add fields are all empty: skip.  
   If any SMTP add field is filled, require IP or hostname and port (`1–65535`); username optional; if username is set, password is required. Then always pass `-ip` and `-port`:  
   `svctask mkemailserver -ip {ip} -port {port} [-username {user}] [-password {password}]`  
   Omit `-ssl` (IBM default). Do not pass `-name`; IBM assigns `emailserverN`.

**Existing server:** if SMTP add is requested and live `lsemailserver` has **any** row, that array is **not runnable**. Preview warning: email server already exists (no silent overwrite). Run re-reads `lsemailserver` **before** any mutate on that array; if a server exists, skip **all** Apply commands for that array (do not write contact then fail SMTP).

**Nothing to apply:** no contact flags, no location flags, no SMTP add → that array is not runnable.

**Run order:** selected arrays in page order. On first real CLI error, stop **that** array; continue the next. Contact/location already sent on that array stay (no rollback).

Confirm copy: this writes Call Home contact/location and optional SMTP add on the selected arrays; first CLI error stops that array; no rollback.

## Remove SMTP (per selected array)

Does **not** use contact, location, or SMTP-add form values. Uses live `lsemailuser` / `lsemailserver`.

1. `svctask stopemail`. Treat already-stopped as success (`is_email_already_stopped`: case-insensitive substring `already stopped`, plus any CMMVC text the tests pin). Any other non-zero is a real error.
2. `svctask rmemailuser {id_or_name}` for each user from `lsemailuser` (id preferred).
3. `svctask rmemailserver {id_or_name}` for each server from `lsemailserver` (id preferred).

No users/servers: those steps are omitted (not errors). `stopemail` still runs.

Confirm copy: this stops email sending and deletes email users and email servers on the selected arrays; cloud Call Home, contact, and location are not changed.

## Architecture

| Unit | Role |
|------|------|
| `launchpad/call_home_cli.py` | Page HTML/JS (`CALL_HOME_CLI_PATH`, `CALL_HOME_CLI_HTML`) |
| `launchpad/call_home_cli_ops.py` | Parse live state, quote args, mask password, build Apply/Remove `SnapStep`s, `preview_hash`, `is_email_already_stopped` |
| `launchpad/health_server.py` | Routes, eligible cards, SSH via existing `_snap_run_command`, Preview/Run, `open_call_home_cli` |
| `launchpad/ui/dashboard_view.py` | Dashboard button |
| `launchpad/config.py` | **1.6.178** |
| Tests | Ops (quote, mask, skip-empty, existing-server block, remove order, already-stopped); page source (IP link outside label, two Run kinds); version pins |

Reuse `SnapStep` + `run_snap_steps`. Step kinds: `chemail`, `mkemailserver`, `stopemail`, `rmemailuser`, `rmemailserver`. Any log or preview string that would include `-password` must run through a mask helper first (HealthServer must not log the raw `SnapStep.cmd` for `mkemailserver`).

Health dashboard HTML adds a secondary link to `/call-home-cli` next to other tool links (same as ESX-snap Policy).

## Testing

- Eligible cards are `SVC_PROFILES` with a host; HPE cards omitted.
- Apply steps: contact `chemail` then location `chemail` then `mkemailserver` when SMTP filled; no `mkemailuser` / `startemail` / `chcloudcallhome`.
- Empty SMTP fields omit `mkemailserver`.
- Existing email server + SMTP add → not runnable; Run does not send `chemail` on that array.
- Password masked in preview/log strings; raw password not in API JSON besides the request body the browser posts.
- Remove order: `stopemail`, then each `rmemailuser`, then each `rmemailserver`.
- `stopemail` already-stopped counts as success.
- IP link markup is outside the checkbox label.
- Version pins **1.6.178**.

## Out of scope follow-ups

- Cloud Call Home on/off and Insights URL.
- `chemailserver` to change an existing server in place.
- Apply creating support/local email users and `startemail`.
- Country dropdown / phone-format validation beyond non-empty and quote-safety.
- Persisting last-used contact in the LaunchPad DB.
