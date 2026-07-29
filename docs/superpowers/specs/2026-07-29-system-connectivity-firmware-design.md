# System Connectivity Firmware Tab + Admin Catalog

**Date:** 2026-07-29  
**Status:** Approved for implementation  
**App version target:** 1.6.73  
**Depends on:** System Connectivity report (1.6.70+), Admin tabs, HealthServer live SSH unlock gate, `SVC_PROFILES` / `HPE_SHELL_PROFILES` / `ibm_ds8884`  
**Approach:** Extend System Connectivity with a fifth Firmware tab; Admin-maintained per-profile catalog (Approach 1)  
**Base branch:** `feature/contingency-groups`

## Problem

Operators can see Call Home / DNS / SNMP / NTP on System Connectivity, but not each array’s **current firmware** or how many **catalog releases** they are behind. Firmware tracks differ by device profile, so a shared global list would mislead.

## Goals

- Fifth System Connectivity tab **Firmware** (after NTP), with matching Excel sheet and CSV member.
- Show **Current**, **Latest**, and **Versions behind** per eligible monitor-on card.
- **Admin → Firmware catalog**: ordered oldest→newest release list **per `device_profile`**.
- Platforms: FlashSystem / SVC, HPE 3PAR/Primera, DS8884 (same eligibility as System Connectivity).
- Read-only collection (no upgrades from LaunchPad).
- Bump `APP_VERSION` to **1.6.73**.

## Non-goals (v1)

- Auto-fetching release lists from IBM / HPE / Lenovo portals.
- Installing or recommending upgrade packages from LaunchPad.
- Semver auto-sort of catalog entries (operator order is authoritative).
- A separate Firmware Dashboard button or standalone report page.
- Auto-inserting live Current into the catalog.
- Cards with Monitor off; vendors outside System Connectivity eligibility.

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Placement | Fifth tab on System Connectivity (+ Excel/CSV) |
| Catalog source | Admin UI, persisted in LaunchPad DB |
| Catalog key | One ordered list per `device_profile` |
| Platforms | FlashSystem + HPE + DS8884 |
| Current not in catalog | Versions behind = `unknown` |
| Catalog empty / collect fail | Versions behind = `unknown` |
| Version string match | Exact string match to array-reported Current |

## Behavior

### Firmware tab / sheet columns

Identity columns match other System Connectivity topics (Site, Card, Host, Vendor, Profile), plus:

| Column | Meaning |
|--------|---------|
| Current | Live firmware / code level from the array |
| Latest | Newest entry in that card’s device_profile catalog (blank if catalog empty) |
| Versions behind | Count of catalog entries **strictly after** Current through Latest; or `unknown` |
| Configured | `yes` if Current collected; `no` / `unknown` / `n/a` per existing topic rules |
| Status | Short state (current, behind, unknown, error, …) |
| Details | Human summary (e.g. current → latest) |
| Error | Per-card collect/parse error if any |

One row per eligible card. Sort: card name A–Z. Site filter and unlock rules unchanged.

### Versions behind rules

Catalog for a profile is an ordered list **oldest → newest**.

| Situation | Versions behind |
|-----------|-----------------|
| Current found in catalog | Number of entries after Current (0 if Current is last / equals Latest) |
| Current missing from catalog | `unknown` (still show Current and Latest when known) |
| Catalog empty | `unknown` (Latest blank) |
| Collect/parse failed | `unknown` (Current blank/unknown; Error set) |

Example: catalog `[8.5.0, 8.6.0, 8.6.1, 8.6.2]`, Current `8.6.0` → Latest `8.6.2`, Versions behind `2`.

### Collectors (read-only)

| Family | Source of Current |
|--------|-------------------|
| FlashSystem / SVC | `lssystem -delim :` → `code_level` (normalize build suffix consistently for display; match catalog on the string used as Current) |
| HPE 3PAR / Primera | Show-version / equivalent InServ output field used as firmware level |
| DS8884 | Best-effort DSCLI version field; else Configured/`n/a` or `unknown` with clear Details/Error |

### Live Refresh + cache + export

- Extend cache payload with `firmware` list alongside `call_home`, `dns`, `snmp`, `ntp`.
- Excel: fifth sheet **Firmware**; CSV ZIP: `firmware.csv` (or equivalent clear name).
- Export scope = current Site filter on last successful cache (unchanged).

### UI page updates

- Tab button **Firmware** after **NTP**.
- Hero blurb mentions firmware.
- Hint on Firmware panel: *Versions behind uses the Admin Firmware catalog for this device profile. If Current is not in the catalog, behind shows unknown.*
- Footer still shows `APP_VERSION`.

## Admin — Firmware catalog

- New Admin tab: **Firmware catalog**.
- Profile dropdown: System Connectivity–eligible device profiles.
- Listbox/table of versions for the selected profile (oldest at top → newest at bottom).
- Actions: **Add version**, **Remove**, **Move up**, **Move down**, **Save**.
- Persistence: DB-backed per-profile ordered string lists (settings JSON or equivalent small store).
- No SSH from Admin; manual entry only.
- Duplicate version strings within a profile should be rejected or ignored on save (exact-match catalog must be unambiguous).

## Architecture

```
Admin Firmware catalog ──▶ DB (per device_profile ordered list)
                                    │
Dashboard / Health ──▶ /system-connectivity
                              │
                   Refresh ───┼──▶ live SSH Current firmware
                              │         │
                              ▼         ▼
                         join catalog ──▶ firmware rows (Current, Latest, Behind)
                              │
                   Export ────┴──▶ Firmware sheet / firmware.csv
```

### Modules (proposed)

| Unit | Responsibility |
|------|----------------|
| `launchpad/firmware_catalog.py` (or equivalent) | Load/save catalog; compute Latest + Versions behind |
| `launchpad/system_connectivity.py` | Firmware collectors/parsers; row normalize |
| `launchpad/system_connectivity_page.py` | Fifth tab + columns |
| `launchpad/system_connectivity_export.py` | Fifth sheet / CSV member |
| `launchpad/health_server.py` | Cache key + live/export include firmware |
| `launchpad/ui/admin_view.py` | Firmware catalog tab |
| Tests | Behind math, catalog CRUD, parsers, page/export chrome, version |

## Testing

- Unit: behind-count 0 / N / `unknown` (missing current, empty catalog).
- Catalog save/load per profile; move up/down order preserved; duplicate rejection.
- Parsers: FlashSystem `code_level`, HPE version sample, DS gap/`n/a` path.
- Export: five sheets / five CSV members including Firmware columns.
- Page: Firmware tab present after NTP; hint text; version **1.6.73**.

## Delivery

- Branch off `feature/contingency-groups` (include header-wrap tip if already on branch).
- Bump to **1.6.73**.
- Prefer Subagent-Driven after plan approval.
- Merge back to install tip after PR.

## Success criteria

1. Refresh live fills Firmware tab for monitor-on FlashSystem, HPE, and DS8884 cards with Current when SSH can read it.
2. Admin catalog per profile drives Latest and Versions behind; missing Current → `unknown` behind.
3. Excel/CSV include Firmware; Site filter and unlock behavior unchanged.
4. Version shows **1.6.73** after rebuild.
5. No upgrade/mutation commands; catalog order remains operator-defined.
