# Capacity Report — per-vendor pool visibility toggles

**Date:** 2026-08-06  
**Status:** Approved (operator); awaiting written-spec review  
**App version target:** next patch after tip (1.6.126+)  
**Depends on:** Capacity Report page (`launchpad/capacity_report.py`); capacity refresh/export `include_pools`; existing pool HTML (`.capacity-pools-wrap`)  
**Approach:** Replace the single “Include CPG / pools” View option with three display-only vendor checkboxes; always collect/export pools

## Problem

Operators want to show pool / CPG capacity on the Capacity Report for only the vendors they care about (IBM, HPE, and/or Dell). Today there is one global **Include CPG / pools** toggle that shows or hides pools for every site and also gates SSH refresh and Excel / Dell Report pool collection. That forces an all-or-nothing choice and couples display preference to data collection.

## Goals

- View options: three independent checkboxes — **Show IBM pools**, **Show HPE CPGs / pools**, **Show Dell pools**.
- Defaults: all three **off** (pools stay in the product for later; operators turn on what they want to see).
- Visibility applies to the Capacity Report page and print/PDF of that page.
- Refresh, Excel Capacity export, and Dell Report **always** include pool collection (`include_pools=1`); no per-vendor filter on SSH or workbooks.
- Pool HTML remains in the DOM when hidden so toggling a checkbox is instant (CSS), without a re-fetch.
- Persist each vendor preference in `localStorage`.

## Non-goals (v1)

- Per-vendor control of SSH pool commands or Excel / Dell Report pool sheets.
- A fourth “Other” / unknown-vendor pool toggle.
- Changing how pools are parsed or rolled into system capacity summaries.
- Site Lookup or Health Dashboard pool UI changes.

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Scope of vendor checkboxes | **Display / print only** |
| Master “Include CPG / pools” | **Remove** (replaced by three vendor toggles) |
| Refresh / Excel / Dell Report pools | **Always on** (`include_pools=1`) |
| Defaults | All three vendor checkboxes **off** |
| Implementation style | CSS visibility by `data-pool-family` + body classes (Approach 1) |

## Behavior

### View options

- Remove checkbox **Include CPG / pools** and its `launchpad.capacityReport.showPools` preference (migrate: ignore old key; do not auto-enable vendor toggles from it).
- Add:
  - `Show IBM pools` → `launchpad.capacityReport.showPoolsIbm`
  - `Show HPE CPGs / pools` → `launchpad.capacityReport.showPoolsHpe`
  - `Show Dell pools` → `launchpad.capacityReport.showPoolsDell`
- Values `"1"` / `"0"`; missing key ⇒ off.
- View options button badge count includes these toggles when on (same pattern as other options).

### Page / print visibility

- Each `.site-block` gets `data-pool-family="ibm" | "hpe" | "dell" | ""`.
- Body classes (names illustrative): `show-pools-ibm`, `show-pools-hpe`, `show-pools-dell` when the matching checkbox is on.
- CSS: hide `.capacity-pools-wrap` inside a site unless the site’s family matches an enabled body class.
- Sites with empty / unknown family: pool blocks stay hidden (no misc toggle in v1).
- Print uses the same visibility (do not mark pool wraps `no-print` solely because of vendor preference).

### Refresh and exports

- Capacity Report refresh-all, per-site refresh, Excel export, and Dell Report export always pass `include_pools=1` (or omit the param and rely on server default true).
- Do not reintroduce a UI path that sets `include_pools=0` from Capacity Report View options.
- Server API may still accept `include_pools=0` for other clients / tests; Capacity Report UI simply always requests pools on.

### Vendor mapping (`data-pool-family`)

Reuse existing profile markers where possible (align with Dell Report family helpers):

| Family | Mapping |
|--------|---------|
| `ibm` | IBM / FlashSystem / Storwize / SVC / XIV / DS8-style profiles (same markers as Dell Report `ibm`) |
| `hpe` | HPE / 3PAR / Primera / `hp_*` (Dell Report `hp` → label **HPE** in UI) |
| `dell` | `device_profile` starting with `dell_` (PowerMax, Unity, PowerStore, etc.) |
| `""` | Everything else |

Prefer `device_profile` on the card; optional manufacturer / name fallback only if already used by sibling Capacity Report helpers for Dell Report family detection.

## Components

| Piece | Change |
|-------|--------|
| `launchpad/capacity_report.py` | View options HTML/JS/CSS; site `data-pool-family`; drop master pool toggle; always `include_pools=1` |
| Tests (`test_capacity_layers_ui.py` and related) | Assert three toggles, defaults off, always-on `include_pools` in refresh/export URLs |
| `launchpad/config.py` | Bump `APP_VERSION` when implementing |

Optional small shared helper (only if it avoids duplicating markers): map profile → `ibm` / `hpe` / `dell` for the report page. Prefer reusing `dell_report_family` for ibm/hpe and adding `dell_` detection in one place rather than copying marker lists into JS and Python separately — e.g. expose `pool_family` (or equivalent) on the card JSON from the server so the page does not re-implement classification.

## Error handling

- Unclassified sites: no pool display even if pool HTML exists; data still collected for Excel.
- Missing `localStorage`: treat vendor toggles as off.
- Checkbox change failures: N/A (client-only prefs).

## Testing

- UI contains the three new toggles; master “Include CPG / pools” absent.
- Defaults / init leave pools hidden until a vendor box is checked.
- Enabling IBM shows pools only on ibm-tagged sites (and likewise for hpe/dell).
- Refresh and export URL builders always use `include_pools=1` (or equivalent).
- Existing capacity-layer / export tests that assumed a UI master toggle are updated.

## Out of scope reminders

Pool parsing, thresholds, Excel “Pool Capacity” sheet shape, and Dell Report layout stay as today — only Capacity Report **display** of pool blocks is gated per vendor.
