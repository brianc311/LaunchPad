# Health Dashboard — Per-card Active Issues panel

**Date:** 2026-07-23  
**Status:** Approved for implementation  
**App version target:** 1.6.61  
**Depends on:** Health Dashboard (`/`), `analyze_health` → `health_issues` on card API  
**Approach:** Render existing per-card `health_issues` in an Active Issues panel on each server card (Approach 1)  
**Base branch:** `feature/contingency-groups` (tip at 1.6.60)

## Problem

Operators see array problems in the IBM GUI “Active Issues” style (e.g. Tempe) and want the same **per-site** visibility in LaunchPad. The Health Dashboard already computes `health_issues` per card and shows a **fleet** issues panel, but individual cards do not surface that site’s issues in an Active Issues box.

## Goals

- Add an **Active Issues** panel on each Health Dashboard server card.
- Populate from existing `card.health_issues` (no new CLI suite).
- Style similarly to the Tempe GUI panel (orange title / bordered box; severity-colored rows).
- Hide the panel when Monitor is off.
- Keep the existing top fleet issues panel unchanged.
- Bump version to **1.6.61**.

## Non-goals

- New IBM GUI–parity checks (software upgrade status, DNS config, support assistance, detailed per-port matrices) beyond what `analyze_health` already produces.
- Site Lookup Active Issues panel.
- Changing how issues are detected or scored.
- Desktop Tk dashboard cards (browser Health Dashboard only).

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Surface | Health Dashboard per-card panel |
| Data source | Existing `health_issues` from Refresh / `analyze_health` |
| Layout | Always-visible Active Issues box on the card (Approach 1) |
| Monitor off | Hide panel |

## Behavior

### Card panel

- Location: under card metrics (before/near updated timestamp), inside each `.server` card.
- Title: **Active Issues** (accent/orange styling; bordered container).
- Content:
  - If Monitor off: do not render the panel.
  - If Monitor on and `health_issues` empty: show “No active issues.”
  - If Monitor on and issues present: list each issue with severity class (`critical` / `warn`), category, and message. Sort critical first, then warn (same ranking as fleet panel).
- Do not repeat the card name inside each row (the card header already identifies the site).

### Fleet panel

- Unchanged: continue aggregating monitor-on cards’ issues at the top of the page.

### Data

- No new API fields required (`health_issues` already on card JSON from `to_api` / `analyze_health`).
- No new presets or SSH commands in this change.

## Testing

- HTML/JS contracts: Active Issues markup/strings in Health Dashboard HTML; render uses `health_issues`.
- Monitor-off path omits panel; empty list shows “No active issues.”; non-empty lists show severity + message.

## Version

`APP_VERSION = "1.6.61"`
