# Mouse Jiggler + Health/Capacity Site Dropdown + Health Excel

**Date:** 2026-07-24  
**Status:** Approved for implementation  
**App version target:** 1.6.65  
**Depends on:** Health Dashboard HTML/JS, Capacity Report page/export, desktop `dashboard_view` settings persistence, FlashCopy CGs Array `<select>` pattern  
**Approach:** Shared Site dropdown (None = all) on Health + Capacity; Health Export Excel (summary sheet); desktop mouse jiggler default Off + Health indicator (Approach 1)  
**Base branch:** `feature/contingency-groups` (tip at 1.6.64)

## Problem

1. Operators leave LaunchPad open for long refreshes; Windows idle policies can sleep the session. They want an optional **mouse jiggler**, **off by default**, visible on desktop and Health.
2. **Health Dashboard** has PDF search/checkboxes but no Array-style **site dropdown**, so picking one site to view/print is awkward; there is also **no Excel export**.
3. **Capacity Report** can print/Excel all (or monitoring-filtered) sites but has no **Site / Array** dropdown to focus one site or **None** (all).

## Goals

- Desktop **Mouse jiggler** toggle, **default Off**, persisted; when On, nudge the cursor slightly on an interval while LaunchPad is running.
- Health Dashboard shows jiggler **On/Off** indicator (synced with desktop setting).
- Health: **Site** dropdown (first option **None** = show all), styled like FlashCopy CGs **Array** box; filters visible cards; **Print / Save PDF** and new **Export Excel** follow that scope.
- Health Excel: one **Summary** sheet (card name, host/IP, profile/model, healthy vs issues summary, monitor on/off).
- Capacity: same **Site** dropdown (**None** = all); filters visible sites; **Print / Save PDF** and **Export Excel** follow that scope; coexist with existing “Include monitoring-off” and display checkboxes.
- Bump `APP_VERSION` to **1.6.65**.

## Non-goals

- Jiggler as a Windows service / when LaunchPad is fully quit.
- Preventing sleep via other APIs only (no SetThreadExecutionState-only substitute unless jiggle is blocked — jiggle is the primary mechanism).
- Health Excel capacity/pool sheets (Capacity Report owns that).
- Replacing Capacity WAG/group filters if any (Capacity site dropdown is per-card filter only).
- Changing FC WWPN / Host-Volume Find / FlashCopy CGs site pickers beyond reuse of the visual pattern.
- Auto-selecting every PDF checkbox when Site = None (Print/Excel use dropdown scope as source of truth).

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Jiggler UI | **C** — desktop toggle + Health indicator; default **Off** |
| Health export | **B** — Site dropdown + Print PDF + Export Excel |
| Health Excel content | **A** — Summary sheet only |
| Site picker UX | FlashCopy CGs–style `<select>`; **None** = all |
| Implementation | **1** — shared pattern; three coordinated deliverables |

## Behavior

### Mouse jiggler

- **Desktop:** Checkbox or switch labeled **Mouse jiggler** near header/actions (or Settings-adjacent control on main dashboard). Default **unchecked / Off**.
- **Persist:** Store in LaunchPad settings/DB (same family as other app prefs). Survive restart; still default Off for new installs / missing key.
- **When On:** While the desktop app process is running, on a fixed interval (e.g. every 45–60 seconds), move the cursor by ~1px and back (or equivalent tiny offset) so the OS sees input activity. Must not steal focus or open menus.
- **When Off:** No timer / no movement.
- **Health indicator:** Read-only (or mirrored toggle if settings API already allows browser→desktop prefs; otherwise read-only status). Text like `Mouse jiggler: Off` / `On`. Refresh via existing health sync or a small settings GET. Prefer: Health can toggle if `/api/settings` (or equivalent) already supports unlock-gated writes; if not, desktop-only toggle + Health status from poll. **Minimum:** Health always shows current state; desktop is authoritative for On/Off.
- **Locked app:** Reading status always OK. Changing jiggler from Health (if writable) requires unlock, same as other settings.

### Site dropdown (shared UX)

- Label: **Site** (or **Array** on Capacity if it reads clearer next to storage cards — prefer **Site** on both for consistency).
- Options: `<option value="">None</option>` then each card `Name (host)` sorted A–Z by name (same spirit as FC Consistgrp Array list).
- **None:** show all sites that the page would otherwise show (Health: all loaded cards subject to existing alert UI; Capacity: subject to “Include monitoring-off” and capacity-data rules).
- **One site:** show only that card’s section; hide others in the DOM (or equivalent filter).
- Changing Site updates the visible list immediately (no full page reload required).

### Health Dashboard

- Add Site dropdown near the existing filter/PDF bar (alongside Find sites for PDF).
- **Print / Save PDF:** Scope to Site selection:
  - One site → print that card only.
  - None → print all currently visible cards (or all cards when None — define as **all cards matching current non-site filters**, i.e. the full dashboard list under None). Prefer: under None, keep today’s behavior of PDF checkboxes if any are checked; if none checked, print **all** sites (or prompt). **Locked rule:** With a specific Site selected, Print that site only (ignore other PDF checks). With None, if any PDF boxes checked, print those; if none checked, print all.
- **Export Excel:** New button. Builds workbook with sheet **Summary**:

  | Column | Source |
  |--------|--------|
  | Card | card name |
  | Host / Site IP | card host |
  | Profile / Model | device_profile / model |
  | Monitor | on/off |
  | Status | healthy / has issues / monitoring off (derive from existing health fields) |
  | Issue count | len(health_issues) or similar |

  Rows = Site scope (one card or all under None). Open-after-download optional, matching Capacity Excel pattern if easy.
- PDF search / Select matches can remain for multi-select print when Site is None.

### Capacity Report

- Add Site dropdown in hero actions (near Print / Export Excel).
- Filter `#sites` (or equivalent) to one card or all.
- **Print / Save PDF** and **Export Excel** use the same Site scope (pass `card_id` when one selected; omit for all). Existing `include_off` and display toggles still apply to the “all” set before site filter, or: site filter applies to the already-filtered list. **Locked:** Apply monitoring-off / display filters first, then Site (None = that set; one id = that card if still in set, else empty + status message).

## API / desktop wiring

| Surface | Change |
|---------|--------|
| Settings / DB | `mouse_jiggler_enabled: bool` default `false` |
| Desktop | Timer + Win32 cursor nudge when enabled; toggle in UI |
| HealthServer | Expose jiggler state to Health page (GET); optional POST when unlocked |
| Health | `GET`/`POST` or reuse settings endpoints for jiggler; new `GET /api/health-export?card_id=` (optional) for Excel |
| Capacity export | Accept optional `card_id` query param |

Exact endpoint names may follow existing settings patterns in-repo.

## Architecture

| Unit | Responsibility |
|------|----------------|
| `launchpad/mouse_jiggler.py` (or small helper) | Start/stop timer; nudge cursor (Windows) |
| Desktop dashboard / settings | Toggle + persist |
| `health_server.py` Health HTML/JS | Site dropdown, print scope, Excel button, jiggler indicator |
| Health Excel builder | Summary workbook bytes |
| `capacity_report.py` + capacity export | Site dropdown + `card_id` filter |
| Tests | Jiggler setting default; export row shape; capacity card_id filter; page contracts for Site/None |

## Testing

- Unit: default jiggler false; enable/disable persistence; health summary rows for one vs all cards; capacity export respects `card_id`.
- Page contracts: Health/Capacity HTML contain Site select + None option; Health Excel button; jiggler status text.
- Manual: toggle jiggler on desktop → Health shows On; Site filter on Health/Capacity; Print/Excel one site vs None.

## Delivery

- Branch off `feature/contingency-groups`
- Bump to **1.6.65**
- Prefer Subagent-Driven after plan approval
- Merge back to install tip after PR

## Success criteria

1. Fresh install: jiggler Off; desktop can turn On; Health shows matching indicator.
2. Health Site None shows all; pick one shows one; Print and Excel follow scope; Excel is Summary-only.
3. Capacity Site None / one site filters view and Print/Excel accordingly.
4. Version **1.6.65** after rebuild.
