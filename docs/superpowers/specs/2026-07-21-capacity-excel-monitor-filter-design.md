# Capacity Report Excel export + monitoring-off filter

**Date:** 2026-07-21  
**Status:** Approved for implementation  
**App version target:** Next patch on the implementation branch  
**Depends on:** Health server Capacity Report page; `launchpad/capacity_export.py`; `/api/monitor` state

## Problem

Operators use the browser **Capacity Report** (`/capacity`) for review and PDF, but that page has no **Export Excel** control. Capacity Excel already exists on the desktop Dashboard (**Export Excel ▾ → Capacity**) via `export_storage_capacity_excel`, producing Storage Capacity + Pool Capacity sheets. Operators expect the same export from the browser page.

Separately, sites with **Monitor / SSH off** still appear on the Capacity Report (dimmed) and in Excel (often as auth/capacity errors). Operators want those left off by default, with an explicit checkbox when they need them included.

## Goals

- Add **Export Excel** to the Capacity Report browser toolbar (same pattern as FC WWPN / Snapshot Schedule).
- Reuse `export_storage_capacity_excel` (or a thin wrapper) so the workbook matches the existing desktop export look and sheets.
- Add checkbox **Include monitoring-off sites** (unchecked by default).
- When unchecked: hide Monitor-off cards on the HTML report **and** exclude them from Excel (no SSH refresh for those cards).
- When checked: restore current all-sites behavior on both surfaces.

## Non-goals

- Changing desktop Dashboard **Export Excel ▾ → Capacity** behavior (still all sites unless extended later).
- Changing Print/PDF beyond whatever cards are currently rendered.
- Redesigning inventory template rows or Excel styling beyond filtering who is included.
- New monitor persistence beyond existing `/api/monitor` state.

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Excel placement | Capacity Report browser button + `/api/capacity-export` |
| Filter applies to | HTML Capacity Report **and** Excel (same checkbox) |
| Default | Monitoring-off sites **excluded** |
| Checkbox label | Include monitoring-off sites |
| Desktop Dashboard Excel menu | Out of scope for this change |

## Behavior

### HTML Capacity Report

- After cards load, apply filter using `/api/monitor` states (same source as existing Monitor toggles).
- Default: only render site blocks where monitor is on.
- When **Include monitoring-off sites** is checked: render all sites (current behavior, including dimmed monitor-off blocks).
- Site count / status text should reflect what is shown.
- Changing the checkbox re-renders without requiring a full SSH refresh.

### Excel export

- New button **Export Excel** next to Print / Refresh on `/capacity`.
- `GET` (or `POST`) `/api/capacity-export?include_off=0|1` (query mirrors checkbox).
- Server builds workbook using existing capacity export logic.
- When `include_off=0` (default):
  - Only consider cards with monitor enabled.
  - Skip SSH capacity refresh for monitor-off cards.
  - Drop inventory template rows that do not match an included card.
  - Drop unmatched “extra” card rows that are monitor-off.
- When `include_off=1`: current export behavior (all entries / inventory rows).
- Response: download `.xlsx`; open-in-Excel when supported (same as FC WWPN `?open=1` if already used elsewhere).

## Architecture

```
Capacity Report UI
  ├─ checkbox: include monitoring-off sites (default off)
  ├─ filter cards for render via /api/monitor
  └─ Export Excel → /api/capacity-export?include_off=…
        └─ capacity_export.export_storage_capacity_excel(..., include_monitor_off=bool)
              └─ uses HealthServer.is_monitor_enabled / monitor state map
```

## Files (expected)

| File | Role |
|------|------|
| `launchpad/capacity_report.py` | Export button, checkbox, JS filter + download |
| `launchpad/capacity_export.py` | `include_monitor_off` (or equivalent) filter parameter |
| `launchpad/health_server.py` | `/api/capacity-export` route; pass monitor states into exporter |
| `tests/` | Filter + API coverage for include_off on/off |

## Testing

- Unit: exporter with mock cards/monitor map — off cards omitted when `include_monitor_off=False`; present when `True`.
- API/page: Capacity HTML contains Export Excel + Include monitoring-off sites; export endpoint returns xlsx.
- Manual: Monitor-off site hidden on page; check box shows it; Excel row counts match visible set.

## Version

Bump `APP_VERSION` by one patch on the implementation branch after feature work lands.
