# FlashCopy CGs Connect + Offline/Degraded Hosts & Volumes Report

**Date:** 2026-07-25  
**Status:** Approved for implementation (pending user review of this spec)  
**App version target:** 1.6.66  
**Depends on:** FlashCopy CGs page, HealthServer card list, dashboard `launch_card` / SSH connect, Volume Find eligibility (IBM + HPE monitor-on), openpyxl/CSV export patterns  
**Approach:** Two coordinated features — FC Connect/Open GUI + dedicated Hosts & Volumes Health report page (Approach 1)  
**Base branch:** `feature/contingency-groups` (tip at 1.6.65)

## Problem

1. On **FlashCopy Consistency Groups**, operators pick an Array but must leave the page to Connect from the Connection Dashboard when they want to log in and inspect the array.
2. Operators need a **live** view of **offline / degraded hosts and volumes** across monitored IBM and HPE arrays, with **Excel and CSV** export, reachable like other reports from the Connection Dashboard (and from Health).

## Goals

- FlashCopy CGs: **Connect** and **Open GUI** controls next to Array / Refresh for the selected array.
  - **Connect** = same interactive SSH session as the card’s orange Connect on the Connection Dashboard.
  - **Open GUI** = open the card’s stored **URL** (web/GUI) when present; hide or disable when empty.
- New browser report page for offline/degraded **hosts** and **volumes**.
- Live SSH pull on Refresh (unlock required), eligibility same as Volume Find: monitor-on SSH IBM FlashSystem/Storwize/SVC **or** HPE 3PAR/Primera.
- Export **Excel** (Hosts + Volumes sheets) and **CSV** (two files or ZIP).
- Nav: new Connection Dashboard button; Health Dashboard link; peer links on related pages as appropriate.
- Site dropdown (**None** = all) on the report page, matching recent Health/Capacity pattern.
- Bump `APP_VERSION` to **1.6.66**.

## Non-goals

- Creating/fixing hosts or volumes from the report.
- DS8884 / XIV / NetApp / Dell offline inventory in v1.
- Cache-only degraded report without a live Refresh path (cache-assisted preview is optional, not a substitute for live).
- Replacing Health Dashboard Active Issues panels.
- Changing FlashCopy CG create/start/delete workflows beyond Connect/Open GUI.

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| FC Connect action | **C** — SSH Connect + Open GUI when URL available |
| Report card scope | **A** — monitor-on IBM + HPE (Volume Find–like) |
| Report home | **C** — dedicated browser page + Health link + Connection Dashboard button |
| Implementation | **1** — two coordinated features |

## Behavior

### FlashCopy CGs — Connect / Open GUI

- Place **Connect** and **Open GUI** beside **Refresh** (Array must be selected).
- **Connect:** `POST` (or equivalent) to HealthServer that invokes the same desktop `launch_card` path used by dashboard Connect for that `card_id` (SSH interactive). Requires LaunchPad unlocked so credentials can be used; if locked, return clear 403/message.
- **Open GUI:** Open `card.url` in the default browser when non-empty (normalize: if URL lacks scheme, prepend `https://`). If `url` empty, button disabled/hidden with tooltip “No GUI URL on this card — set URL in Admin.”
- Status text: success/failure next to buttons (e.g. “SSH session started”, “Opened GUI”, errors).

### Hosts & Volumes Health report (name TBD; prefer **Hosts & Volumes Health** or **Offline / Degraded**)

#### UI

- Path: e.g. `/host-volume-health` (exact path locked in plan).
- Title + short blurb: live offline/degraded hosts and volumes on monitored IBM/HPE arrays.
- Controls: **Site** dropdown (None = all), **Refresh live**, **Export Excel**, **Export CSV**, nav links (Health, Capacity, FC WWPN, Volume Find, FlashCopy CGs, etc.).
- Two tables (or tabbed sections): **Hosts**, **Volumes**.
- Columns (minimum):
  - Hosts: Card, Site IP/host, Vendor, Host name, Status, (optional WWPNs if cheap)
  - Volumes: Card, Site IP/host, Vendor, Volume name, Pool/CPG, Status
- Empty state when no problems found after refresh.
- Per-card errors listed without aborting the whole refresh.

#### Eligibility

Same as Volume Find:

- SSH card, monitoring on, IBM SVC-family **or** HPE shell profiles.

#### Live Refresh

- Unlock required.
- Per eligible card (or Site-filtered card):
  - **IBM:** `svcinfo lshost -delim :` and `svcinfo lsvdisk -delim :` (or existing parsers).
  - **HPE:** host list + VV list commands already in presets (`showhost`, `showvv`).
- Keep rows where status matches offline/degraded rules (case-insensitive substring on status/state fields):
  - Include at least: `offline`, `degraded`.
  - Also include common IBM variants if present in status text: `offline_unconfigured` only if it contains `offline`; do **not** include healthy/`online`/`active` unless also marked degraded.
- Sort: card name A–Z, then object name A–Z.

#### Export

- **Excel:** workbook with sheets `Hosts` and `Volumes` (same columns as tables). Scope = current Site filter (None = all matches from last refresh).
- **CSV:** `hosts.csv` + `volumes.csv` in a ZIP (preferred) or sequential downloads.
- Optional open-after-save like other exports.

#### Nav

- Connection Dashboard: button e.g. **Hosts & Volumes** or **Offline / Degraded**.
- Health Dashboard: link in hero actions.
- Report page footer/version string includes `APP_VERSION`.

## API / desktop wiring

| Surface | Change |
|---------|--------|
| HealthServer | FC page buttons → connect/open-gui endpoints calling desktop callbacks |
| Desktop app | `set_connect_provider` / reuse launch path for `card_id`; open URL helper |
| HealthServer | Serve report HTML; `GET/POST` live scan; Excel/CSV export endpoints |
| Helpers | Parse/filter offline-degraded hosts & volumes (IBM + HPE) |
| Dashboard | New opener button |

## Architecture

| Unit | Responsibility |
|------|----------------|
| `fc_consistgrp` page JS/HTML | Connect + Open GUI buttons |
| `health_server` + app callbacks | Bridge browser → `launch_card` / webbrowser |
| `host_volume_health` page + helpers | Live scan, tables, exports |
| `dashboard_view` | Nav button |
| Tests | Connect API contracts; filter rules; export sheets; page chrome |

## Testing

- Unit: status filter rules; IBM/HPE row extraction fixtures.
- API: unlock gate for live/connect; empty URL disables GUI path.
- Page: FC buttons present; report path, Site None, Export buttons, Health/dashboard links.

## Delivery

- Branch off `feature/contingency-groups`
- Bump to **1.6.66**
- Prefer Subagent-Driven after plan approval
- Merge back to install tip after PR

## Success criteria

1. On FlashCopy CGs, with an array selected, Connect opens SSH; Open GUI opens card URL when set.
2. New report Refresh live lists offline/degraded hosts and volumes for monitor-on IBM+HPE; Excel/CSV export works.
3. Dashboard button and Health link open the report.
4. Version shows **1.6.66** after rebuild.
