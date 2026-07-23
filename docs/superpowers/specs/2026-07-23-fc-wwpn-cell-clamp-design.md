# FC WWPN Report — Collapse Multi-line Cells + Find Expand

**Date:** 2026-07-23  
**Status:** Approved for implementation  
**App version target:** 1.6.56  
**Depends on:** FC WWPN Find search (Site picker + client/server find)  
**Approach:** CSS clamp + class toggles (Approach 1)  
**Base branch:** `feature/contingency-groups` (tip at 1.6.55)

## Problem

Port tables (and other FC WWPN tables) show Remote WWPNs and other multi-line cells fully expanded. Long `;`-separated WWPN lists make rows very tall and hide neighboring columns/data. Operators still need one-line scanning, plus the ability to open a cell when Find locates a WWPN inside it.

## Goals

- Collapse **all multi-line cells** on the FC WWPN Inventory report to **one visible line** (+ ellipsis) by default.
- **Click** a clamped cell to toggle expand/collapse.
- **Find** (existing search) auto-expands every multi-line cell on the selected site whose full text matches the query.
- **Clear Find** (empty query) collapses **all** multi-line cells (including ones opened by click).
- Print/PDF shows full cell text; Excel export unchanged.

## Non-goals (v1)

- Collapsing cells on LUN Builder, Consistency Groups, or Capacity Report.
- Changing Find match rules (still WWPN / remote WWPN / host / volume as today).
- Highlighting the matched substring inside the expanded cell (nice-to-have later).
- Changing modal mappings export or WAG filters.

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Manual open | **C** — click toggle anytime; Find also auto-expands |
| Clear Find | **C** — collapse all multi-line cells |
| Implementation | **1** — CSS clamp + `is-expanded` class toggles |

## Behavior

### Collapse rules

- Apply to FC WWPN report tables only (ports by node, hosts, mappings, fabric, and any other table cells rendered on that page).
- A cell is multi-line when its text contains a newline **or** would otherwise display as more than one line (e.g. long Remote WWPNs with `;` separators that currently wrap/stack).
- Clamped cells: one line, ellipsis overflow, pointer cursor, accessible hint (e.g. `title` / `aria-expanded`).
- Single-line cells: no clamp, no toggle.

### Click

- Click on a clamped cell toggles `is-expanded`.
- Expanded cells show full text (wrap allowed).

### Find integration

- Keep existing Find flow (client match → set Site; else `/api/fc-wwpn-find`; miss status unchanged).
- After a successful Find that shows a site, expand every multi-line cell on that site whose **full text** matches the query using the same match semantics as card search (normalized WWPN substring; host/volume text).
- Prefer scrolling the first expanded matching cell into view when practical.
- Empty Find query / clear: remove expand from **all** multi-line cells.
- Find miss: do not leave search-driven expands; cells remain collapsed (or reset to collapsed).

### Print / Excel

- Print / Save PDF: disable clamp so full text prints.
- Excel / CSV exports: unchanged full values.

## Architecture

- CSS in `fc_wwpn_report.py`: `.cell-clamp` (line-clamp 1) and `.cell-clamp.is-expanded` (no clamp).
- After table render, mark multi-line `td` elements and wire click delegation.
- Extend `runFcSearch` (or post-render hook) to expand matching clamped cells on the visible card(s); clear expands on empty query.
- No new APIs.

## Testing

- Page/HTML contract: `cell-clamp`, expand/collapse wiring, Find clears expands.
- Smoke: multi-line Remote WWPNs clamp; click toggles; Find expands match; clear Find collapses all.

## Delivery

- Branch off `feature/contingency-groups`.
- Bump `APP_VERSION` to **1.6.56**.
- Merge back to install tip after PR.

## Success criteria

1. Remote WWPNs (and other multi-line cells) show one line by default.
2. Click expands/collapses; Find opens matching cells; clear Find collapses all.
3. Print shows full text; Excel unchanged.
4. Version shows **1.6.56** after rebuild.
