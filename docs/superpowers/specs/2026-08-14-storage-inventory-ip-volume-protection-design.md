# Storage Inventory IP links, All Arrays, toggle highlight, Volume Protection

**Date:** 2026-08-14  
**Status:** Approved for implementation  
**App version target:** 1.6.170  
**Depends on:** Storage Inventory progress and Recent / Older / All (1.6.169)  
**Approach:** Parse Volume Protection from existing `lssystem` output (no extra SSH); keep Data Protection as Remote Copy; page IP `https://` links; Site **All Arrays**; fix Recent / Older / All selected-button CSS  
**Base branch:** `main` (1.6.169)

## Problem

Storage Inventory Issues / Notes can show empty Host and IP columns while the device row has both. IPs are not GUI links. The Recent / Older / All control does not show which button is selected (`button.btn.secondary` overrides `.si-age-btn.is-on`). The Site dropdown empty choice says **None** instead of **All Arrays**. The **Data Protection** column is Remote Copy (`lsrcrelationship` / `showrcopy`) and shows **unknown** on IBM arrays that have **Volume Protection** enabled on `lssystem`. Operators need both columns.

## Goals

- Clickable `https://{ip}` links for IPv4 addresses on every site (device table and nested Issues / Notes). Nested Host and IP cells stay visible.
- Selected Recent / Older / All button is orange (same accent as Refresh live).
- Site empty choice label **All Arrays** (still shows every site).
- Keep **Data Protection** as Remote Copy. Add **Volume Protection** as the next column (page and Excel).
- IBM: parse Volume Protection from the `lssystem` output already collected for identity. HPE and DS8884: **n/a**.
- Volume Protection off → **Volume Protection not configured** in Issues / Notes (Recent, like other config gaps) and can turn the site red.
- Exact **unknown** on Volume Protection participates in site orange (same as Phone Home / Data Protection / SMTP).
- Bump `APP_VERSION` to **1.6.170**.

## Non-goals

- Extra SSH for Volume Protection or per-volume exceptions.
- Changing Remote Copy collectors or the `lsrcrelationship` / `showrcopy` parsers.
- Changing Phone Home / SMTP / DNS / NTP collectors.
- Changing Admin Branding, Health Dashboard, eligibility, or site-card collapse CSS.
- Persist Site filter or age toggle across reload.
- Linking non-IPv4 hostnames; a separate GUI-URL field.

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Data Protection vs Volume Protection | Both columns. Data Protection stays Remote Copy. |
| Column headers | **Data Protection** then **Volume Protection** |
| Volume Protection source | Existing IBM `lssystem` output (Approach 1) |
| Volume Protection off | Issues / Notes line; can make site red |
| HPE / DS8884 Volume Protection | `n/a` (not an issue, not orange) |
| Site empty label | **All Arrays** |
| IP links | `https://{row.ip}` in device rows and nested Issues / Notes |
| Toggle highlight | Orange selected button |

## Behavior

### Site filter and age toggle

- HTML and JS rebuild of `#siteFilter` use `<option value="">All Arrays</option>`. Empty value still means all sites.
- `.si-age-btn.is-on` must win over `button.btn.secondary` (higher specificity, e.g. `button.btn.secondary.si-age-btn.is-on`). Selected = accent background and dark text. Unselected stay secondary.

### IP links and nested Issues / Notes

Reuse the Snapcopy / Volume Find pattern:

- If `row.ip` matches IPv4, render `<a href="https://{ip}" target="_blank" rel="noopener">` with escaped text. Otherwise plain escaped text (or empty).
- Apply in `renderDeviceRows` (IP Address column) and `renderIssuesBlock` (Host + IP + notes). Host and IP come from the same inventory row as the device table.
- Nested Issues table Host and IP columns have a min-width so long notes cannot collapse them to empty-looking cells.
- Quote JS HTML with single-quoted `class="..."`.

### Volume Protection column

Device table order:

Host, IP Address, Model, Serial Number (SN), Location, Phone Home, Data Protection, **Volume Protection**, SMTP IP(s)

Display (same Yes/No helper style as other config cells):

| Collector result | Cell |
|------------------|------|
| on / enabled / yes | **Yes** |
| off / disabled / no | **No — Not configured** |
| n/a (HPE, DS8884) | **n/a** |
| missing field (old cache) or unreadable | **unknown** |

### IBM parse

From cached `lssystem -delim :` identity output, read the `volume_protection` key (case-insensitive). No extra command. Identity / NTP continue to share that output.

- `enabled`, `on`, `yes`, `true` → configured yes
- `disabled`, `off`, `no`, `false` → configured no
- key missing or other value → unknown

### Issues / Notes and site color

- When Volume Protection configured is **no**, append **Volume Protection not configured** with the other config notes (Phone Home / Data Protection / SMTP / DNS / NTP). It is a live config gap: it stays on **Recent**.
- **n/a** and **unknown** do not add that note.
- Python `site_status` and page `rowHasUnknown` include `volume_protection` next to `phone_home`, `data_protection`, `smtp`. Exact case-insensitive `unknown` → orange if the site is not already red. `n/a` does not.

### Excel

Add **Volume Protection** immediately after **Data Protection**. Red-row fill still keys on full `issues` (including the new note). Other columns unchanged.

### Live scan

SVC/FlashSystem: pass Volume Protection from the identity `lssystem` parse into `build_inventory_row`. Failure path rows: unknown Volume Protection unless the profile is HPE/DS8884 (`n/a`). Do not bump scan command count.

## Files (expected)

| File | Responsibility |
|------|----------------|
| `launchpad/storage_inventory.py` | Parse helper; row field; issues note; unknown-fields; Excel columns |
| `launchpad/health_server.py` | Wire parse into SVC scan; n/a on HPE/DS paths |
| `launchpad/storage_inventory_page.py` | All Arrays; toggle CSS; IP links; Volume Protection column; unknown check |
| Tests for the above + version pins | |
| `launchpad/config.py` | `1.6.170` |

## Testing

- Parse: on, off, missing key, HPE/DS n/a.
- Off → issues text contains **Volume Protection not configured**; n/a does not.
- Page markers: All Arrays, `https://` IP helper, Volume Protection header, toggle CSS that beats `.secondary`.
- Nested Issues block still emits Host and IP cells.
- Excel headers include Volume Protection after Data Protection.
- Version pins `1.6.170`.
