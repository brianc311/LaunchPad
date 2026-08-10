# FC WWPN Port Labels (fc0 / fc1 / …)

**Date:** 2026-08-10  
**Status:** Approved for implementation  
**App version target:** 1.6.150  
**Depends on:** FC WWPN Report (`/fc-wwpn`), `parse_fc_ports` / `lsportfc`, FC WWPN Excel export  
**Approach:** Shared display helper for Port column on page + Excel (Approach 1)  
**Base branch:** `main` (tip at 1.6.149)

## Problem

Operators identify FlashSystem FC ports as **fc0**, **fc1**, **fc2**, **fc3**. The FC WWPN report Port column shows the raw `lsportfc` id (often `0`, `1`, `2`, `3`), which is harder to match to switch/zoning language.

## Goals

- Display Port as **`fcN`** when the underlying id is numeric (or already `fcN`).
- Apply on the **FC WWPN page** and **Excel** Port column.
- Keep raw `port_id` / `fc_io_port_id` unchanged for fabric matching and APIs.
- Bump `APP_VERSION` to **1.6.150**.

## Non-goals (v1)

- Changing parser storage or `lsfabric` matching keys.
- Renaming other columns (WWPN, status, etc.).
- HPE / non-SVC port naming schemes beyond the shared helper rules.
- New Port columns or dual id/label columns.

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Label style | Prefix existing id as `fc0` / `fc1` / … (display-only) |
| Surfaces | Page + Excel |
| Implementation | Shared `format_fc_port_label` helper |

## Behavior

### `format_fc_port_label(raw) -> str`

| Input | Output |
|-------|--------|
| empty / None | `""` |
| digits only (`0`, `1`, `12`) | `fc0`, `fc1`, `fc12` |
| already `fc` + digits (`fc0`, `FC1`) | `fc0`, `fc1` (lowercase `fc`, no double prefix) |
| any other non-empty string | unchanged |

### Source for the Port cell

Same as today: `port_id` if present, else `fc_io_port_id`. Format that string with the helper for display/export only.

### UI

In `fc_wwpn_report.py` port tables (flat and per-node), Port `<td>` shows `format_fc_port_label(...)`. Prefer exposing the helper to JS via a small mirrored JS function with the **same rules**, or format server-side before render if ports are already JSON — matching rules in page JS is acceptable if kept next to the Python helper tests (document both). Preferred: **Python helper for Excel**; **identical JS helper in the page** (or format in Python when building card payload — only if that does not mutate stored `port_id`). Do **not** overwrite `port_id` on the card payload.

### Excel

In `fc_wwpn_export.py`, the Port column value uses `format_fc_port_label(port_id or fc_io_port_id)`.

## Architecture

| Unit | Change |
|------|--------|
| `launchpad/flashsystem_fc.py` | Add `format_fc_port_label` |
| `launchpad/fc_wwpn_export.py` | Use helper for Port column |
| `launchpad/fc_wwpn_report.py` | Port column display uses same label rules |
| `tests/test_flashsystem_fc.py` (or dedicated) | Unit tests for helper |
| Page/export tests | Assert `fc0`-style Port where fixtures use id `0` |
| `launchpad/config.py` | `APP_VERSION` → `1.6.150` |

## Testing

- Unit: empty, numeric, already-prefixed, mixed-case `FC1`, non-numeric passthrough.
- Export: Port cell is `fc0` when fixture port id is `0`.
- Page: HTML/JS contains formatting for Port (marker or rendered fixture if applicable).

## Version

Bump `APP_VERSION` to **1.6.150** when the feature ships.
