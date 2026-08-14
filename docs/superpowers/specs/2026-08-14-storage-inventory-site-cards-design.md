# Storage Inventory site cards (collapse + color)

**Date:** 2026-08-14  
**Status:** Approved for implementation  
**App version target:** 1.6.168  
**Depends on:** Storage Inventory page (`/storage-inventory`), `storage_inventory.py` row shape and `row_has_issues`  
**Approach:** Accordion site cards on the existing page; Excel unchanged  
**Base branch:** `main`

## Problem

Storage Inventory is one long table. Operators cannot scan sites at a glance, Issues / Notes stretches every row, and there is no site-level red / orange / green.

## Goals

- Group inventory rows into **one collapsible card per site**.
- Sites start **collapsed**.
- Inside an open site, **Issues / Notes** is a nested block, **collapsed by default**, so device rows stay compact.
- Color each site header **red / orange / green** from that site’s devices.
- Keep Site filter, Refresh live, Export Excel, and page totals.
- Bump `APP_VERSION` to **1.6.168**.

## Non-goals

- Changing Excel layout, columns, or red-row fill.
- Changing collectors, issue aggregation text, or which devices are eligible.
- Persist expand/collapse across refresh or reload.
- Expand-all / collapse-all controls.
- Left-rail master-detail layout.
- Coloring individual device rows (site header only).
- Treating expected `n/a` as incomplete.

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Layout | Site accordion cards (not grouped table rows, not split pane) |
| Sites on load | All collapsed |
| Issues / Notes | One nested block per site, collapsed; hidden when the site has no notes |
| Site color | Worst-of: red if any Issues / Notes; else orange if any **unknown**; else green |
| `n/a` | Does not make a site orange |
| Scan errors | Already in Issues / Notes → red |
| Page Issues Summary table | Remove (duplicated by per-site Issues / Notes) |
| Excel | Unchanged |

## Behavior

### Page

Hero, Site filter (**None** = all sites), Refresh live, Export Excel, and **Total Devices** / **Devices with Issues** stay.

Replace the flat Inventory table and the page-level **Issues Summary** table with a list of site cards, sorted by site name (case-insensitive). Blank site labels group as `(no site)`.

Site filter: selected site shows only that card; **None** shows every site that has at least one inventory row in the current payload.

Refresh live and filter re-render cards; all sites and all Issues / Notes blocks start collapsed again.

### Site header (always visible)

Click the header to expand or collapse the site body. Header shows:

- Site name
- Device count
- Count of devices with Issues / Notes when that count is greater than zero
- Color: left bar + light background tint (`site-red` / `site-orange` / `site-green`)

### Site body (expanded)

Compact device table columns:

Host, IP Address, Model, Serial Number (SN), Location, Phone Home, Data Protection, SMTP IP(s)

No Site column (redundant). No Issues / Notes column.

### Issues / Notes block

Rendered under the device table only when at least one device on that site has non-empty Issues / Notes.

Closed label: `Issues / Notes (N)` where N is the number of devices with notes.

Open content: one compact row per such device — Host, IP Address, Issues / Notes text.

Does not open when the site opens.

### Site color

Compute from the devices on that site only. Red wins over orange.

| Status | When |
|--------|------|
| **red** | Any device has non-empty Issues / Notes (`row_has_issues`) |
| **orange** | Not red, and at least one device has a **unknown** display value in Phone Home, Data Protection, or SMTP (case-insensitive exact `unknown`) |
| **green** | Not red and not orange |

`n/a` is ignored. Topic columns that are Yes / No / configured IPs do not create orange.

Scan errors are appended into Issues / Notes today, so those sites are red.

Empty site (no devices) is not rendered.

### Excel

No change: Inventory sheet with Issues / Notes column and red issue rows; Issues Summary sheet; existing totals meta.

## Architecture

| Unit | Responsibility |
|------|----------------|
| `launchpad/storage_inventory.py` | Add `site_status(rows) -> "red" \| "orange" \| "green"` (and grouping helper if it keeps tests small). Reuse `row_has_issues`. Do not change Excel or collectors. |
| `launchpad/storage_inventory_page.py` | Replace flat tables with site cards, nested Issues / Notes `<details>`, color classes, JS render grouped by site. Keep cache / refresh / export / site filter wiring. |
| Tests | Color helper unit tests; page markup/JS markers for cards, collapsed default, nested issues, no page-level Issues Summary. |
| Version pins | `APP_VERSION` **1.6.168** and the three existing pin tests. |

Page JS mirrors `site_status` using the same rules on already-formatted row fields (`issues`, `phone_home`, `data_protection`, `smtp`). No new API payload fields required.

Prefer `<details>` / `<summary>` for site cards and the nested Issues / Notes block so collapse works without extra widget code. Quote JS HTML strings so `class="..."` cannot break the script (same class of bug as the 1.6.166 inventory `row-issue` fix).

## Testing

- `site_status`: red when any issues; orange when only `unknown` topic cells; green when clean including `n/a`; red wins over `unknown`; empty issues + no unknown → green.
- Page HTML/JS: site card container; sites rendered collapsed; Issues / Notes nested and collapsed; `site-red` / `site-orange` / `site-green`; no page-level Issues Summary heading/table; inventory device table inside a site has no Issues / Notes column.
- Existing cache / refresh / export / site-from-cards tests still pass.
- Version pin **1.6.168**.

## Version

Bump `APP_VERSION` to **1.6.168** when this ships.
