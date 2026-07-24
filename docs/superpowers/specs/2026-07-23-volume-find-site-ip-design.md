# Volume Find — Site IP column + editable host

**Date:** 2026-07-23  
**Status:** Approved for implementation  
**App version target:** 1.6.59  
**Depends on:** Volume Find page/API (1.6.57+), Health Cards DB (`update_card`), unlock/settings backend  
**Approach:** Results `host` + Site IP column + `POST` host update + one-time Anderson rename (Approach 1)  
**Base branch:** `feature/contingency-groups` (tip at 1.6.58)

## Problem

Volume Find shows which card owns a volume, but operators also need the site’s management IP as a clickable `https://…` link (matching their site list). Wrong or outdated hosts should be fixable without leaving Volume Find. The card still named **WILLIAMSTON (ANDERSON) SC** should become **Anderson, SC**.

## Goals

- Add a **Site IP** column on Volume Find results from each Health Card’s **host**.
- Show host as a clickable `https://{host}` link.
- Allow **inline edit** of host on the results table; Save persists to the LaunchPad card DB (same store as Admin).
- One-time rename: `WILLIAMSTON (ANDERSON) SC` → `Anderson, SC` (idempotent).
- Bump version to **1.6.59**.

## Non-goals

- Separate “GUI URL” field distinct from SSH host.
- Editing card name from Volume Find except the Anderson one-time rename.
- Bulk import of the full site IP spreadsheet.
- Changing Volume Find match/eligibility/live SSH behavior.

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Site IP source | Health Card **host** (Approach A) |
| Edit UX | Inline in results table (Approach A) |
| Anderson rename | Yes, as part of this change |
| Implementation | Approach 1 — column + save API + rename |

## Behavior

### UI

- Path remains `/volume-find`.
- Results table columns: **Card**, **Site IP**, Vendor, Volume, Pool / CPG, Source.
- Site IP:
  - If host non-empty: render `<a href="https://{host}" target="_blank" rel="noopener">https://{host}</a>` (or equivalent).
  - If host empty: show `—`.
- Inline edit:
  - Activate edit on the Site IP cell (click link area / edit affordance).
  - Input shows raw host (IP or hostname); operators may paste `https://…/` — normalize before save.
  - **Save** / **Cancel**.
  - On success, update all visible rows for that `card_id`.
  - If LaunchPad is locked: show unlock message; do not call save.

### API

**Find responses** (`GET /api/volume-find`): each match includes existing fields plus:

- `host`: string (card host at search time; may be empty)

**Save host**

- `POST /api/volume-find/card-host`
- Body: `{ "card_id": <int>, "host": "<string>" }`
- Requires unlock (same gate as other persist ops). Locked → `403` with clear error.
- Normalize host: strip whitespace; strip leading `http://` / `https://`; strip trailing `/`.
- Reject empty host after normalize (`400`).
- Persist host on that card in the desktop DB without changing other card fields (name, credentials, profile, monitor, etc.).
- Refresh HealthServer in-memory card host (and name if rename ran) so subsequent Find sees the update.
- Response: `{ "ok": true, "card_id": …, "host": "<normalized>", "name": "<current name>" }` (or equivalent).

Wire a HealthServer callback (pattern like `set_settings_backend` / sync provider) so the desktop app can apply `db.update_card` / partial host update when unlocked. Do not invent a second card store.

### Anderson rename

- When unlocked and Volume Find (or host-save / sync) runs a rename check:
  - Find card whose name matches `WILLIAMSTON (ANDERSON) SC` allowing flexible whitespace.
  - If found and no other card is already named `Anderson, SC`, rename to `Anderson, SC`.
  - Leave host unchanged if set; if host is empty, set `10.244.25.158`.
- Idempotent: no-op if already renamed or no matching card.
- Do not rename other sites.

## Testing

- Find matches include `host`; page shows Site IP link or `—`.
- Save when unlocked updates host; locked returns unlock error.
- Pasted `https://10.1.2.3/` saves as `10.1.2.3`.
- Anderson rename: matching name → `Anderson, SC`; second run no-op; conflict if `Anderson, SC` already exists → skip rename (keep original name; do not overwrite other card).

## Out of scope reminders

- No live SSH changes for Site IP (host is card metadata).
- No Capacity / FC WWPN Site IP columns in this change (Volume Find only).
