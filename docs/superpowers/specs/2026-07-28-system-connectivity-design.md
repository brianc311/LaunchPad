# System Connectivity Report — Call Home / DNS / SNMP / NTP

**Date:** 2026-07-28  
**Status:** Approved for implementation  
**App version target:** 1.6.70  
**Depends on:** HealthServer card list, unlock + live SSH, Hosts & Volumes page/export patterns, `SVC_PROFILES` / `HPE_SHELL_PROFILES` / `ibm_ds8884`  
**Approach:** Dedicated browser page mirroring Hosts & Volumes (Approach 1)  
**Base branch:** `feature/contingency-groups` (tip at 1.6.69)

## Problem

Operators need a live, estate-wide view of **Call Home**, **DNS**, **SNMP**, and **NTP** per site/array for FlashSystem, HPE 3PAR/Primera, and DS8884, with Excel and CSV export. LaunchPad has no collectors for these topics today.

## Goals

- Dedicated page **System Connectivity** at `/system-connectivity` with **four tabs**: Call Home | DNS | SNMP | NTP.
- **Site** dropdown (**None** = all), **Refresh live**, **Export Excel**, **Export CSV**.
- Eligibility: **monitor-on** SSH cards only; unlock required for live Refresh.
- Platforms: IBM FlashSystem family (`SVC_PROFILES`), HPE 3PAR/Primera (`HPE_SHELL_PROFILES`), **DS8884**.
- Excel: one sheet per topic; CSV ZIP mirrors sheet names.
- Nav: Connection Dashboard button + Health Dashboard link.
- **Read-only** (collect, display, export).
- Bump `APP_VERSION` to **1.6.70**.

## Non-goals (v1)

- Configuring or enabling Call Home, DNS, SNMP, or NTP from LaunchPad.
- Cards with Monitor off; non-SSH or other vendors (XIV, NetApp, Dell, …).
- HPE Call Home via Service Processor / SPOCC (not array InServ SSH).
- Full HMC-only DS8884 Call Home / NTP when not exposed via DSCLI.
- Replacing Health Dashboard Active Issues panels.
- Exporting SNMP communities, passwords, or other secrets.

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Platforms | FlashSystem + HPE + DS8884 |
| Exports | Excel + CSV |
| Site filter | All or one (None = all) |
| Report home | Dedicated page + Dashboard button + Health link |
| Eligibility | Monitor-on SSH only |
| Excel layout | One sheet per topic |
| Scope | Read-only |
| Page UI | Four tabs matching Excel sheets |
| Implementation | Approach 1 — mirror Hosts & Volumes |

## Behavior

### Eligibility

SSH card, monitoring on, and `device_profile` in:

- `SVC_PROFILES` (FlashSystem 5200/7200/7300/9500 and related), or
- `HPE_SHELL_PROFILES` (3PAR / Primera), or
- `ibm_ds8884`

### Common row shape (every tab / sheet)

| Column | Meaning |
|--------|---------|
| Site | Card site label |
| Card | Array display name |
| Host | SSH host/IP |
| Vendor | IBM / HPE |
| Profile | Device profile key |
| Configured | `yes` / `no` / `unknown` / `n/a` |
| Status | Short state (enabled, disabled, empty, error, …) |
| Details | Human summary (servers, mode — no secrets) |
| Error | Per-topic SSH/parse error if any |

One row per eligible card per topic (including Configured=`no`). Card-level failures still produce rows with Error filled. Per-card topic errors must not abort the rest of the estate scan.

### Configured rules

| Value | When |
|-------|------|
| `yes` | At least one usable setting present (server IP, enabled flag, managers, …) |
| `no` | Command succeeded; nothing configured / feature off |
| `unknown` | Command failed or output unparseable |
| `n/a` | Topic not readable via this card’s SSH path (see platform table) |

### Platform collectors (read-only)

| Topic | FlashSystem / SVC | HPE 3PAR / Primera | DS8884 |
|-------|-------------------|--------------------|--------|
| **Call Home** | `lscloudcallhome -delim :` | **`n/a`** — Call Home lives on Service Processor / SPOCC, not array InServ SSH | Best-effort `showsp` / remote-support attrs if present; else `n/a` (often HMC) |
| **DNS** | `lsdnsserver -delim :` | Parse DNS from `shownet` | `lsnetworkport` → Primary/Secondary DNS |
| **SNMP** | `lssnmpserver -delim :` | `showsnmpmgr` (managers only; never communities/passwords) | Best-effort SNMP show if available; else `unknown` / `n/a` |
| **NTP** | `lssystem -delim :` → `cluster_ntp_IP_address` | Parse NTP from `shownet` | Best-effort; if not in DSCLI → `n/a` (often HMC) |

Details examples: DNS IPs joined; SNMP manager IPs/ports; NTP IP; Call Home enabled/mode/proxy summary. Never SNMP communities, passwords, or API keys.

### UI page

- Path: `/system-connectivity`
- Title: **System Connectivity**
- Short blurb: live Call Home / DNS / SNMP / NTP on monitored FlashSystem, HPE, and DS8884 arrays
- Controls: Site (None = all), Refresh live, Export Excel, Export CSV
- Four tabs with tables matching Section columns above
- Empty state after refresh when no eligible cards / Site filter empty
- Call Home tab hint: *HPE Call Home requires Service Processor access — not collected from array SSH in v1. DS8884 Call Home/NTP may require HMC.*
- Footer includes `APP_VERSION`
- Peer nav links (Health, Capacity, Hosts & Volumes, etc.) as on sibling report pages

### Live Refresh

- Unlock required; if locked, return clear 403/message.
- For each eligible card (optionally Site-filtered): run family-specific topic commands; normalize into four lists.
- Cache payload: `call_home`, `dns`, `snmp`, `ntp`, `errors` (plus metadata as needed).
- Sort: card name A–Z within each topic.

### Export

- Scope = current Site filter applied to **last successful cache** (None = all rows from last refresh).
- **Excel:** sheets named `Call Home`, `DNS`, `SNMP`, `NTP` (same columns as tables).
- **CSV:** ZIP with `call_home.csv`, `dns.csv`, `snmp.csv`, `ntp.csv` (or equivalent clear names).
- Optional open-after-save like other exports.

### Nav wiring

- Connection Dashboard: button **System Connectivity**
- Health Dashboard: hero/actions link to `/system-connectivity`

## Architecture

```
Dashboard / Health link ──▶ /system-connectivity page
                                    │
                         Refresh ───┼──▶ live SSH per eligible card
                                    │         │
                                    │         ▼
                                    │   system_connectivity adapters
                                    │         │
                                    ▼         ▼
                              cache  ◀── normalized topic rows
                                    │
                         Export ────┴──▶ xlsx / csv zip
```

### Modules (proposed)

| Unit | Responsibility |
|------|----------------|
| `launchpad/system_connectivity.py` | Eligibility, platform adapters, Configured rules, row normalize |
| `launchpad/system_connectivity_page.py` | HTML/JS (tabs, Site, Refresh, export) |
| `launchpad/system_connectivity_export.py` | openpyxl + CSV ZIP |
| `launchpad/health_server.py` | Serve page; live scan; cache; export endpoints |
| `launchpad/ui/dashboard_view.py` | Opener button |
| Tests | Parsers, Configured/`n/a`, export sheets, unlock, page chrome |

### APIs

| Endpoint | Role |
|----------|------|
| `GET /system-connectivity` | HTML page |
| `GET` or `POST /api/system-connectivity/live` | Live scan; optional `site` / `card_id`; unlock gate |
| `GET /api/system-connectivity/export?format=xlsx\|csv` | Excel or CSV ZIP; optional Site scope |

Exact query param names follow Hosts & Volumes conventions where practical.

## Testing

- Unit: fixtures for SVC / HPE / DS sample outputs → Configured, Status, Details.
- Explicit `n/a` for HPE Call Home; DS gap paths when commands unavailable.
- Export: four sheets / four CSV members; fixtures contain no secrets.
- API: unlock gate for live; Site None vs one site scopes rows.
- Page: path, four tabs, Site None, Export buttons, Health/dashboard links, version string.

## Delivery

- Branch off `feature/contingency-groups`
- Bump to **1.6.70**
- Prefer Subagent-Driven after plan approval
- Merge back to install tip after PR

## Success criteria

1. Refresh live fills four tabs for monitor-on FlashSystem, HPE, and DS8884 cards (with honest `n/a` where SSH cannot read the topic).
2. Site filter All vs one site works; Excel (4 sheets) and CSV ZIP export match tables.
3. Dashboard button and Health link open the page; unlock required for live Refresh.
4. Version shows **1.6.70** after rebuild.
5. No secrets (communities, passwords) appear in UI or exports.
