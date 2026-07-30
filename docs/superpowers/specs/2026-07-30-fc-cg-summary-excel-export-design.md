# Array FlashCopy CG Summary — Excel Export

**Date:** 2026-07-30  
**Status:** Approved for implementation  
**App version target:** 1.6.81  
**Depends on:** Contingency Groups page Array FlashCopy CG summary (`contingency_fc_cg_summary`), unlock/live SSH  
**Approach:** Dedicated export endpoint (Approach A) — refresh-on-export  
**Base branch:** `feature/contingency-groups`

## Problem

Operators use **Array FlashCopy CG summary** on Contingency Groups to see live Name / Status / Maps / Host maps / Size / Policy / Snaps/week for the linked array, but there is no Excel export of that table. They want a one-click download that always uses fresh array data.

## Goals

- Add **Export Excel** beside **Refresh CG summary** on Contingency Groups.
- Export always **live-collects** (refresh-on-export), then downloads `.xlsx` for the current contingency group’s linked card.
- Columns match the on-page table.
- Bump `APP_VERSION` to **1.6.81**.

## Non-goals

- CSV export in v1.
- Changing the existing Contingency Groups workbook (`/api/contingency-groups-export`).
- Multi-site / Status-mode export (covered by FlashCopy CGs Status).
- New columns beyond the current summary table.
- Single-SSH-collect combined JSON+file API (v1 accepts two collects: refresh then export).

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| When to collect | **Refresh-on-export** (always live; not last-cached-only) |
| Button placement | Beside **Refresh CG summary** |
| Architecture | Dedicated endpoint (Approach A) |
| File format | `.xlsx` only |
| Scope | Current contingency group’s linked array only |

## Behavior

### UI

- Button label: **Export Excel** next to **Refresh CG summary**.
- Requires a selected contingency group; otherwise show a status hint to select a group.
- Requires LaunchPad unlock (same as Refresh).
- Recommended JS flow:
  1. Call existing Refresh (`/api/contingency-groups/fc-cg-summary?group_id=…`) to update the table.
  2. If ok, navigate/download `GET /api/contingency-groups/fc-cg-summary/export?group_id=…&format=xlsx&open=1`.
- Export endpoint **also** live-collects (two SSH collects per Export is acceptable for this infrequent action).
- On collect failure: show error; do not download an empty workbook.

### Workbook

| Item | Value |
|------|--------|
| Sheet name | `FC CG Summary` |
| Columns | Name, Status, Maps, Host maps, Size, Policy, Snaps/week |
| Row source | `summaries` from `contingency_fc_cg_summary` (same fields as the UI table) |
| Filename | e.g. `FC_CG_Summary_<card>_<YYYYMMDD_HHMM>.xlsx` |
| Open after | `open=1` uses existing TEMP_DIR + `open_exported_workbook` pattern |

### API

- `GET /api/contingency-groups/fc-cg-summary/export?group_id=<id>&format=xlsx&open=1`
- Reuse `contingency_fc_cg_summary(group_id)` for live collect.
- `format` must be `xlsx` (400 otherwise).
- Unlock / unknown group / no matching card / collect failure → appropriate JSON error status (403/404/400/500) consistent with sibling APIs; no empty xlsx on failure.

## Architecture

| File | Responsibility |
|------|----------------|
| `launchpad/fc_cg_summary_export.py` (new) | `export_fc_cg_summary_xlsx(rows) -> bytes`; styled headers like other exports |
| `launchpad/health_server.py` | Export route + thin wrapper that collects then exports |
| `launchpad/contingency_groups.py` | Export button + JS wire-up |
| `launchpad/config.py` | `APP_VERSION = "1.6.81"` |
| Tests | Helper unit; API; page markers; version |

## Tests

- Export helper: sheet name, headers, row values.
- API: unlock/group required; happy path with mocked summary/inventory; xlsx content-type.
- Page: Export Excel control and export path string present.
- Version assert `1.6.81`.

## Follow-up (out of scope)

1. CSV zip option.
2. One-collect export that also returns JSON for the table.
3. Adding the same Export control on FlashCopy CGs Manage inventory (separate from Status export).
