# Dashboard Capacity Alerts — Design

**Date:** 2026-08-03  
**Status:** Approved  
**App version target:** 1.6.101+  
**Depends on:**
- Capacity issue detection in `launchpad/flashsystem_health.py` (`analyze_health`)
- Health Server in-memory cards (`/api/cards`) with `health_issues`
- Capacity Report banners (`launchpad/capacity_report.py`) — already show CRITICAL/WARNING after SSH refresh
- Main Connection Dashboard (`launchpad/ui/dashboard_view.py`, `launchpad/ui/card_widget.py`)

## Problem

Capacity Report and Health Dashboard can show pool utilization and (after 1.6.100) CRITICAL/WARNING banners when pools hit thresholds. Operators often stay on the **main LaunchPad Connection Dashboard** and never open those pages, so high capacity (e.g. 82% warn / 98% critical) is easy to miss.

`Warn%` from HPE `showcpg` is an array-side CPG allocation threshold and is unrelated to LaunchPad alerts; empty/`-` is expected when unset.

## Goals

- Surface capacity alerts on the **main Connection Dashboard** so operators notice without opening Capacity Report first.
- Show both:
  1. A **top alert strip** summarizing fleet critical/warn capacity counts
  2. A **per SSH card badge** (`CRIT` / `WARN`) for affected monitored sites
- Clicking the strip opens **Capacity Report** so the operator can inspect the issue.
- Reuse **last Health Server SSH snapshot** (`health_issues`) — no extra background SSH from the desktop app.
- Keep thresholds: **≥80% warn**, **≥90% critical** (82% stays warn, not critical).

## Non-goals (v1)

- Separate background `showcpg` / capacity SSH from the desktop app.
- Email / toast / sound notifications.
- Changing Warn% display semantics on HPE detail tables beyond existing hide-when-`-` behavior.
- Promoting ≥80% to Critical.
- Badges for non-capacity health issues (nodes, alerts, CPU) on the main dashboard in v1.

## Operator decisions (locked)

- Placement: **both** top strip and per-card badges (option C).
- Data source: **Approach 1** — poll Health Server last snapshot / `health_issues`.
- Strip click target: **Capacity Report**.
- Thresholds unchanged: warn ≥80%, critical ≥90%.

## Behavior

### Alert source

- Use capacity-category (and equivalent capacity message) entries already produced by `analyze_health`.
- Only **Monitor-on** SSH cards with refreshed card data participate.
- If Health Server is down or a card has never been refreshed, show **no** badge/strip entry for that card (do not invent stale SSH probes).

### Top alert strip (Connection Dashboard)

- Visible near Health Dashboard / Capacity Report actions when any monitored capacity warn/critical exists.
- Example copy: `CRITICAL capacity: 2 site(s) · WARNING: 1 site(s)`.
- Critical count takes visual priority (red); warn uses amber when no criticals, or both counts shown together.
- Click (or primary button on the strip) opens Capacity Report for the current SSH inventory (same path as existing Capacity Report action).
- Hidden when counts are zero.

### Per-card badge

- On SSH GlowCards only, when that card has ≥1 capacity issue and Monitor is on.
- `CRIT` (red) if any capacity issue is critical; else `WARN` (amber).
- Tooltip lists capacity issue message(s) for that site.
- Hidden when Monitor off, no issues, or no refreshed health data.

### Freshness

- After Capacity Report / Health Dashboard refresh completes, desktop strip and badges update from Health Server cards.
- While Health Server is reachable, light periodic poll (reuse existing dashboard timer patterns where practical) so badges stay in sync without opening the browser page.
- No new interactive HPE SSH sessions from the desktop UI for this feature.

## UI / UX notes

- Match existing LaunchPad dark theme and accent colors; use red/amber consistent with Capacity Report banners and Health issue styling.
- Do not replace the SSH connectivity LED; capacity badge is a separate signal.
- Keep the strip compact so it does not dominate the first viewport when idle (hidden with zero alerts).

## Testing

- Unit/helper tests: derive strip counts and per-card severity from sample `health_issues` lists (critical wins over warn; monitor-off ignored).
- UI wiring smoke: strip HTML/text present when issues exist; badge labels CRIT/WARN; strip opens Capacity Report path.
- Regression: pools at 82% → warn only; pools at ≥90% → critical; empty issues → no strip/badge.

## Out of scope follow-ups

- Desktop notifications when LaunchPad is minimized.
- Filtering the strip to capacity-only vs all health issues.
- Auto-open Capacity Report on first critical detection.
