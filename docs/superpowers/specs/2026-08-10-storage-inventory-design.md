# Storage Inventory Report (Word-style fleet Excel)

**Date:** 2026-08-10  
**Status:** Approved for implementation  
**App version target:** 1.6.147  
**Depends on:** HealthServer card list, unlock + live SSH, System Connectivity collectors (Call Home / DNS / NTP), Health Active Issues, Connection Dashboard buttons, `SVC_PROFILES` / `HPE_SHELL_PROFILES` / `ibm_ds8884`  
**Approach:** Dedicated browser page + Excel mirroring System Connectivity (Approach 1)  
**Reference:** Operator Word inventory `Storage_Inventory_1.docx` (Site / Host / IP / Model / Serial / Location / Phone Home / Data Protection / SMTP / Issues; red issue rows; totals; Issues Summary)  
**Base branch:** `main` (tip at 1.6.146)

## Problem

Operators maintain a Word/Excel-style **Storage Device Inventory** that shows every array’s identity, Phone Home, Data Protection, SMTP, and Issues, with red rows for devices that need attention plus totals and an Issues Summary. LaunchPad already has System Connectivity (Call Home / DNS / SNMP / NTP / …) and Health Active Issues, but nothing produces this combined fleet inventory report.

## Goals

- Dedicated page **Storage Inventory** at `/storage-inventory`.
- Connection Dashboard button **Storage Inventory**.
- Controls: **Site** filter (**None** = all), **Refresh live**, **Export Excel**.
- Eligibility: **monitor-on** SSH cards only; unlock required for live Refresh.
- Platforms: same as System Connectivity — FlashSystem (`SVC_PROFILES`), HPE 3PAR/Primera (`HPE_SHELL_PROFILES`), DS8884.
- One inventory table on the page; totals + Issues Summary panel.
- Excel: Inventory sheet (red highlight on issue rows) + Issues Summary sheet; meta header (generated time, total devices, devices with issues).
- Columns aligned to the Word report (see Behavior).
- Data: live scan reusing System Connectivity Call Home / DNS / NTP where applicable; **new** SMTP and Data Protection collectors; merge Health Active Issues into Issues / Notes.
- Read-only (collect, display, export).
- Bump `APP_VERSION` to **1.6.147**.

## Non-goals (v1)

- Configuring Phone Home, SMTP, Data Protection, DNS, or NTP from LaunchPad.
- Monitor-off cards; non-SSH or other vendors (XIV, NetApp, Dell, …).
- HPE Phone Home via Service Processor / SPOCC (array SSH remains `n/a` as in System Connectivity).
- CSV export (Excel only).
- Replacing System Connectivity or Health Dashboard Active Issues UI.
- Perfect one-to-one wording with every historical Word cell when collectors differ.

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Delivery | Dedicated Storage Inventory Excel (not only extend SysConn/Health Excel) |
| Data | Live System Connectivity-style scan + Health Active Issues |
| Entry point | New **Storage Inventory** button on Connection Dashboard |
| Columns | Match Word doc closely (Phone Home, Data Protection, SMTP, Issues; totals; Issues Summary; red highlight) |
| Devices | All **monitored** SSH storage cards (SysConn platform set) |
| Implementation | Approach 1 — dedicated page + Excel |

## Behavior

### Eligibility

SSH card, monitoring on, and `device_profile` in:

- `SVC_PROFILES`, or
- `HPE_SHELL_PROFILES`, or
- `ibm_ds8884`

### Page

- Path: `/storage-inventory`
- Title: **Storage Inventory**
- Blurb: live fleet inventory (Phone Home / Data Protection / SMTP / Issues) for monitored FlashSystem, HPE, and DS8884 arrays
- Controls: Site (None = all), Refresh live, Export Excel
- Main table: one row per eligible card (after site filter)
- Summary: **Total Devices**, **Devices with Issues**, and an **Issues Summary** list/table (rows where Issues / Notes is non-empty)
- Cache: last successful scan payload; page loads from cache; Export uses cache
- Unlock: required for Refresh live; not required to view/export cached results

### Columns

| Column | Meaning |
|--------|---------|
| Site | Card site label |
| Host | Array display / SSH card name |
| IP Address | SSH host/IP |
| Model | Product / model string from live identity when available; else profile-derived label |
| Serial Number (SN) | Live serial when available; else card metadata if already stored |
| Location | Card location (or site label if location empty) |
| Phone Home | Call Home summary (Yes/No + short detail), reuse System Connectivity Call Home |
| Data Protection | Yes / No / unknown / n/a + short detail |
| SMTP IP(s) | Configured SMTP/email server IP(s), or “No IP — Not configured” / unknown / n/a |
| Issues / Notes | Semicolon-joined operator-facing notes (connectivity gaps + Health Active Issues + scan errors); no secrets |

### Issue row / red highlight rule

A row **has issues** (counts toward Devices with Issues; red background in Excel and highlighted on page) **if and only if** Issues / Notes is non-empty after aggregation.

### Issues / Notes aggregation

Build Issues / Notes from (order stable; skip blanks; semicolon-separated):

1. Phone Home clearly bad or not configured (when not `n/a`)
2. Data Protection clearly not configured / No (when not `n/a` / unknown-without-error)
3. SMTP not configured / email server failures (when detectable)
4. DNS / NTP gaps from the same live scan (reuse SysConn parsers; surface short notes like the Word report)
5. Health Active Issues text for that card
6. Per-card or per-topic scan/parse errors (human-readable; no passwords)

Do not invent issues for `n/a` platform topics.

### Collectors (read-only)

| Topic | FlashSystem / SVC | HPE 3PAR / Primera | DS8884 |
|-------|-------------------|--------------------|--------|
| **Identity** (model/serial) | Existing `lssystem` / inventory path used elsewhere | `showsys` / equivalent already used in estate scans | DSCLI identity best-effort |
| **Phone Home** | Reuse System Connectivity Call Home (`lscloudcallhome`) | **`n/a`** (SPOCC / SP — same as SysConn) | Best-effort / `n/a` as SysConn |
| **DNS / NTP** | Reuse SysConn collectors (for Issues text only; not separate columns) | Same | Same |
| **SMTP** | Email/SMTP server list via SVC email-server CLI (e.g. `lsemailserver` family); IPs joined or “No IP — Not configured” | Best-effort CLI if present; else `unknown` / `n/a` | Best-effort / `n/a` |
| **Data Protection** | Best-effort presence of remote-copy / Metro / volume-group protection from read-only CLI; **Yes** if configured relationships/groups found, **No — Not configured** if command succeeds and none found, else `unknown` | Best-effort replication/protection summary; else `unknown` / `n/a` | Best-effort / `n/a` |

Prefer `unknown` over a false Yes/No when output is missing or unparseable. Exact CLI command strings are fixed in the implementation plan from platform docs / existing helpers; parsers stay unit-tested.

### Excel

- Sheet **Inventory**: all columns above; header/meta row or freeze pane note with Generated timestamp, Total Devices, Devices with Issues; red fill on issue rows; alternating normal rows optional.
- Sheet **Issues Summary**: subset of inventory columns for issue rows only (at least Site, Host, IP, Model, Serial, Issues / Notes).
- No secrets (no passwords, SNMP communities, API keys).

### Error handling

- Per-card SSH/scan failure → still emit a row from card config identity; put error into Issues / Notes; continue other cards.
- Per-topic failure → that column `unknown` (or `n/a` if platform topic is unsupported); append a short note to Issues / Notes when useful; do not abort the estate scan.

## Architecture

| Unit | Responsibility |
|------|----------------|
| `launchpad/storage_inventory.py` | Eligibility helpers, row shape, SMTP / Data Protection parsers, issue aggregation, Excel builder, totals |
| `launchpad/storage_inventory_page.py` | HTML/JS page (table, site filter, refresh, export, summary) |
| `launchpad/health_server.py` | Routes (`/storage-inventory`, refresh API, export), live scan orchestration, cache, unlock gate |
| Connection Dashboard | **Storage Inventory** button → open page |
| Reuse | System Connectivity Call Home / DNS / NTP parsers and command maps; Health Active Issues lookup by card |

Do not duplicate Call Home/DNS/NTP parsing logic — import/reuse from `system_connectivity` (or shared helpers already used there).

## Testing

- Unit: SMTP / Data Protection parsers; issue aggregation; red-row / totals / Issues Summary Excel contents.
- Page: HTML contains title/controls; Dashboard button present.
- Integration (mocked SSH): scan builds rows for mixed platforms; card failure still yields a row; export from cache works without unlock.

## Version

Bump `APP_VERSION` to **1.6.147** when the feature ships.
