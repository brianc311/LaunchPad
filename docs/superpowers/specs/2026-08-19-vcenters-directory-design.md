# vCenters directory

**Date:** 2026-08-19  
**Status:** Approved for implementation (pending user review of this file)  
**App version target:** 1.6.186  
**Depends on:** Health Server browser pages, `db.get_setting` / `set_setting`, dashboard `_open_sync_browser_report`  
**Approach:** Settings-backed JSON directory. Dashboard **vCenters** button opens a Health Server page. Operators add/edit/delete rows there. Each row has a vSphere web-client link.

## Problem

Operators need a single place for vCenter names, locations, and addresses, plus one click into the vSphere web client. LaunchPad has no vCenter directory today. These are not SSH connection cards; the list is maintained by hand.

## Goals

- Connection dashboard has a **vCenters** button in the tools row, next to Ansible Pad.
- Button opens a Health Server page (`/vcenters`) in the browser.
- The page is a directory the operator adds to: name, location, IP or hostname, optional URL override.
- Each row has a clickable vSphere link (`target="_blank"`). Default URL is `https://{address}/ui`.
- Clicking a row name opens a LaunchPad detail card on the same page (name, location, address, link, Edit, Delete).
- Add / Edit / Delete live on that page. List survives LaunchPad restart.
- View and click links without Unlock. Mutations require Unlock.
- Empty default. No seed data.
- Bump `APP_VERSION` to **1.6.186**.

## Non-goals

- Live vCenter API, VM/host/datastore inventory, or credentials for vCenter.
- A new Admin card type or SQLite table.
- SSH/RDP to vCenter.
- Notes field (deferred).
- Editing the list from LaunchPad Admin.
- Changing Ansible Pad, Site Lookup, Storage Inventory, or Monitor SSH.

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Click a vCenter | LaunchPad detail card **and** a vSphere web-client link |
| Detail content | Name, location, address, link only |
| Maintain list | On the vCenters page (Add / Edit / Delete) |
| Link storage | Address required; URL optional override; default `https://{address}/ui` |
| Persistence | One JSON setting via `get_setting` / `set_setting` |
| Storage | Settings-backed directory, not a DB table or Admin cards |
| Button label | **vCenters** |
| Version | **1.6.186** |

## Behavior

Persisted key: `vcenters_directory`. Value is a JSON list of records. Missing, empty, or corrupt → `[]` (page still loads).

Each record:

| Field | Required | Rules |
|-------|----------|--------|
| `id` | yes (server-assigned if omitted on create) | Stable string; unique in the list |
| `name` | yes | Trimmed; non-empty |
| `location` | no | Trimmed; may be `""` |
| `address` | yes | Trimmed IP or hostname; no `://` |
| `url` | no | Empty → default link. If set, must start with `http://` or `https://` |

Effective link: stored `url` if non-empty after normalize, else `https://{address}/ui`.

Sort the list by `name` case-insensitive.

**List view:** columns Name, Location, Address, Link. Empty state: “No vCenters yet” plus **Add**. Name is the detail control. Link is `<a href="..." target="_blank" rel="noopener">`.

**Detail view:** same page, selected by `?id=`. Shows the four fields, **Edit**, **Delete** (confirm), **Back** to the list.

**Add / Edit form:** Name, Location, Address, URL (optional). Save upserts. Validation errors stay on the form; nothing is written.

**Unlock:** GET list is allowed while locked. POST create/update/delete fails with the same unlock error pattern as other Health Server writes. Page disables those controls and shows the usual unlock hint.

**Dashboard open:** `_open_vcenters` uses `_open_sync_browser_report` like Storage Inventory. Does **not** require SSH cards with credentials (unlike Ansible Pad).

## APIs

- `GET /vcenters` — HTML page.
- `GET /api/vcenters` — `{ "vcenters": [ ... ] }` (normalized, sorted).
- `POST /api/vcenters` — upsert one record. Body is one object. Missing `id` → assign. Returns `{ "vcenters": [ ... ] }`. Unlock required.
- `POST /api/vcenters/delete` — `{ "id": "..." }`. Unknown id is a no-op success. Returns `{ "vcenters": [ ... ] }`. Unlock required.

## Files (expected)

| File | Change |
|------|--------|
| `launchpad/vcenters_directory.py` | Setting key, normalize, default URL, upsert/delete helpers |
| `launchpad/vcenters.py` | `/vcenters` HTML/JS |
| `launchpad/health_server.py` | Route, GET/POST APIs, `open_vcenters()` |
| `launchpad/ui/dashboard_view.py` | **vCenters** button next to Ansible Pad; `_open_vcenters` |
| `launchpad/config.py` | `APP_VERSION` **1.6.186** |
| Tests | Helper, API (save + locked), page contracts, dashboard button, version pins |

## Test plan

- Fresh / missing setting: empty list, no crash.
- Add a row with address only: link is `https://{address}/ui`.
- Add a row with URL override: link uses that URL.
- Reject missing name or address; reject address that contains `://`; reject URL override without `http://` or `https://`.
- Restart LaunchPad: list still there.
- Locked: list and links work; save/delete fail; controls disabled.
- Unlocked: edit and delete update the list.
- Dashboard **vCenters** opens `/vcenters` with no SSH cards required.
- Login screen shows **v1.6.186**.
