# Call Home CLI — SMTP in place, email users, Cloud on/off

**Date:** 2026-08-18  
**Status:** Approved for implementation (pending user review of this file)  
**App version target:** 1.6.180  
**Extends:** `docs/superpowers/specs/2026-08-18-call-home-cli-design.md`  
**Depends on:** Call Home CLI page (`/call-home-cli`, IBM `SVC_PROFILES` SSH cards)  
**Approach:** Same page. Five independent Preview/Run kinds so contact, SMTP, users, Cloud, and SMTP wipe cannot mix.

## Problem

v1 can set shared contact, per-array location, add SMTP only when none exists, and wipe the whole SMTP stack. Operators still cannot:

- Change an existing email server (Anderson already has `172.29.62.98:25`).
- Add or remove individual Call Home email users (`support` vs `local`).
- Enable or disable Cloud Call Home.

v1 **Apply** also refused all writes on an array that already had an email server if SMTP add fields were filled.

## Goals

- Per-array SMTP edit in place (`chemailserver`); `mkemailserver` only when that array has no server.
- Per-array email users: remove checked existing rows; add address + type (`support` or `local`).
- Per-array Cloud Call Home enable/disable.
- Five Preview/Run pairs; each Run unlocked only by its own `preview_hash`.
- SMTP password still never stored in LaunchPad DB; masked in preview, confirm modal, and logs.
- Stop **that array** on first real CLI error; continue the next; no rollback.
- Load current must not put cluster status (`running` / `stopped`) into the location **state** box.
- Bump `APP_VERSION` to **1.6.180**.

## Non-goals

- Storage Insights URL, proxy, Test Notification.
- `inventory` email-user type.
- Blanking contact/location (`-nocontact` and similar).
- Choosing among two or more email servers (that array is not runnable for SMTP).
- HPE / Dell / DS8884.
- Automatic rollback.
- Persisting SMTP password or last-used users in the LaunchPad DB.

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| SMTP / users scope | Per array (each site card) |
| Cloud | Enable / disable only; still show live status |
| Existing SMTP | Edit in place (`chemailserver`) |
| New users | Address + type `support` or `local`; remove via checkbox |
| Layout | Same page; five separate Preview/Run pairs |
| SMTP password | Typed on the array card; never in DB; masked in preview/logs |
| Errors | Stop that array; continue next; no rollback |
| `startemail` | After Users Apply, if any `mkemailuser` ran and live email was stopped |

## Page

- Path stays `/call-home-cli`.
- IBM `SVC_PROFILES` with a non-empty host only.
- Array IP remains an `https://` link **outside** the checkbox label.
- Fetch `try/catch` on Load / Preview / Run.

**Layout**

1. Shared **contact** (top): name, reply, primary, alternate. Used **only** by Contact/location Apply.
2. Remove the shared **SMTP add** block. SMTP lives on each array card.
3. Per array:
   - Checkbox, name, IP link, live Cloud status text.
   - Cloud control: Enable / Disable (pre-filled from load: configured `yes` → Enable, `no` → Disable).
   - SMTP fields: IP or hostname, port, username, password (password empty unless the operator is changing it).
   - Users: existing rows (address, type, remove checkbox); one or more add rows (address + type).
   - Location: company, street, city, state, postal, country, comment.
   - Read-only SMTP summary line (live load), same as v1.
4. Actions: Select all / none, **Load current**, then:

| Preview | Run (disabled until matching Preview) |
|---------|----------------------------------------|
| Preview Contact | Run Contact |
| Preview SMTP | Run SMTP |
| Preview Users | Run Users |
| Preview Cloud | Run Cloud |
| Preview Remove SMTP | Run Remove SMTP |

Load current fills contact from the first successfully loaded **checked** array (or first success if none checked), same as v1. Location, Cloud control, SMTP fields (not password), and user list always come from **that** array. Password fields stay empty after load.

**State sanitizer:** if loaded `state` is `running` or `stopped` (any case), store it as empty. Location state keys stay `email_state` / `email_machine_state` only — never generic `state` / `status`.

## APIs

Keep v1 cards + state. Replace the two Apply routes with Contact-only. Add SMTP / Users / Cloud pairs. Keep Remove.

| Method | Path | Kind |
|--------|------|------|
| GET | `/api/call-home/cards` | Unchanged |
| POST | `/api/call-home/state` | Unchanged (must return `servers`, `users`, `cloud_configured`, `cloud_status`) |
| POST | `/api/call-home/preview-apply` | Contact + location only (no `mkemailserver`) |
| POST | `/api/call-home/run-apply` | Contact + location only |
| POST | `/api/call-home/preview-smtp` | SMTP in place / add |
| POST | `/api/call-home/run-smtp` | SMTP in place / add |
| POST | `/api/call-home/preview-users` | User add/remove + optional `startemail` |
| POST | `/api/call-home/run-users` | User add/remove + optional `startemail` |
| POST | `/api/call-home/preview-cloud` | Cloud enable/disable |
| POST | `/api/call-home/run-cloud` | Cloud enable/disable |
| POST | `/api/call-home/preview-remove` | Unchanged wipe |
| POST | `/api/call-home/run-remove` | Unchanged wipe |

Each Preview returns `preview_hash`. Run requires `confirm: true` and that kind’s hash. A Contact hash must not unlock Run SMTP (and so on). `preview_hash` includes `kind` plus the payload for that kind. SMTP hash includes `sha256(password)` per array (empty string when omitted), never the raw password in JSON responses.

## CLI quoting

Same as v1: IBM double-quoted argument; reject `"`, CR, LF, or NUL. `cli_token` when it already matches. Password appears on the real SSH command; all logs/preview/modal use `mask_password_in_cmd`.

## Contact / location (Preview Contact → Run Contact)

Same `svctask chemail` as v1: shared contact flags then per-array location flags; skip empty groups; no `chsystem`. **Do not** send `mkemailserver` / `chemailserver` on this kind.

Nothing to apply → that array is not runnable.

## SMTP (Preview SMTP → Run SMTP)

Per selected array, live `lsemailserver` at Preview and again at Run before mutate.

- SMTP fields all empty → not runnable.
- Any field filled → IP (or hostname) and port `1–65535` required. Username optional. Password required when username is set **and** (there is no existing server, **or** username is changing / password field is non-empty). Changing only IP/port on an existing server does not require password.
- **0 servers:** `svctask mkemailserver -ip {ip} -port {port} [-username] [-password]`. Omit `-ssl`. No `-name`.
- **1 server:** `svctask chemailserver {id}` with only the flags that have values (`-ip` `-port` `-username` `-password`). Use id preferred.
- **2+ servers:** not runnable. Warning: more than one email server (no silent pick).
- Run re-reads `lsemailserver` first. If server count no longer matches Preview’s 0-vs-1 assumption, skip **all** SMTP commands on that array.

## Users (Preview Users → Run Users)

Does not use contact, location, SMTP, or Cloud form values except the per-array user list.

1. `svctask rmemailuser {id}` for each **checked** existing user (id preferred; name if no id).
2. `svctask mkemailuser -address {email} -usertype {support|local}` for each add row with a non-empty address. Type required; reject any other type.
3. If any `mkemailuser` is in the step list, append `svctask startemail`. Treat already-started as success (case-insensitive substring `already started`, plus any CMMVC text tests pin). Any other non-zero is a real error.

No removes and no adds → that array is not runnable. Duplicate add address vs an existing user that is not being removed → that array not runnable (warning). Empty address rows are ignored.

## Cloud (Preview Cloud → Run Cloud)

Per selected array:

- Control is Enable or Disable.
- Load maps `cloud_configured == "yes"` → Enable, else Disable.
- If the control still matches the loaded configured flag, that array is not runnable.
- Enable → `svctask chcloudcallhome -enable yes`
- Disable → `svctask chcloudcallhome -enable no`

Run re-reads `lscloudcallhome` first; if configured already matches the requested state, skip that array (success, no command). Do not send Insights/proxy flags.

## Remove SMTP (unchanged)

`stopemail` (already-stopped = success) → each `rmemailuser` → each `rmemailserver`. Leaves Cloud Call Home, contact, and location.

## Run order and errors

Selected arrays in page order. On first real CLI error, stop **that array**; continue the next. Commands already sent on that array stay (no rollback). Mixed success: page shows finished with errors and per-array log, same as Call Home CLI v1 Run modal.

Confirm copy must name the kind (contact/location vs SMTP vs users vs Cloud vs remove).

## Architecture

| Unit | Role |
|------|------|
| `launchpad/call_home_cli.py` | Page: per-array SMTP/users/cloud; five Preview/Run pairs |
| `launchpad/call_home_cli_ops.py` | Parsers, sanitizer, step builders per kind, hashes, already-started |
| `launchpad/health_server.py` | New preview/run routes; Contact Apply no longer adds SMTP |
| `launchpad/config.py` | **1.6.180** |
| Tests | Ops per kind; hash isolation; state sanitizer; version pins |

Reuse `SnapStep` + `run_snap_steps`. New step kinds: `chemailserver`, `mkemailuser`, `rmemailuser` (already used on remove), `startemail`, `chcloudcallhome`. Existing: `chemail`, `mkemailserver`, `stopemail`, `rmemailserver`.

## Testing

- Contact Apply steps contain no `mkemailserver` / `chemailserver`.
- SMTP: 0 servers → `mkemailserver`; 1 server → `chemailserver`; 2+ → not runnable.
- Users: `rmemailuser` then `mkemailuser -usertype support|local`; `startemail` only when an add exists; already-started = success.
- Cloud: command only when Enable/Disable differs from load; skip if already matched at Run.
- Preview hash for kind A does not unlock Run kind B.
- Password masked; raw secret not in preview JSON.
- Load `state` of `running`/`stopped` becomes empty.
- Version pins **1.6.180**.
- IBM `SVC_PROFILES` only; HPE omitted.

## Out of scope follow-ups

- Insights URL / proxy / test notification.
- `chemailserver` picker when multiple servers exist.
- `inventory` user type.
- Country dropdown / phone-format validation.
