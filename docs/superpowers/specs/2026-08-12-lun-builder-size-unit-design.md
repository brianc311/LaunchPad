# LUN Builder Size unit selector (GB / TB)

**Date:** 2026-08-12  
**Status:** Approved for implementation  
**App version target:** 1.6.157  
**Depends on:** LUN Builder size CLI bare→GB behavior (1.6.154) — `_size_gb` / `_format_size_gb_cli` in `lun_builder_create.py`  
**Approach:** UI-only split of the Size cell; keep one stored `size` string  
**Base branch:** `main` (tip at 1.6.156)

## Problem

Operators enter Size as free text. Bare `100` already means 100 GB on create (1.6.154), but the Size column does not show a unit, so it is easy to wonder whether Run Create needs `GB` or `TB` typed in. Templates already use strings like `100GB` / `1TB`.

## Goals

- In each LUN spec **Size** cell, show a numeric input plus a **GB | TB** dropdown.
- Default unit: **GB**.
- Keep a single stored `size` string (`"100GB"`, `"1TB"`) for plan, export, templates, and create.
- Preserve existing create behavior: FlashSystem CLI still uses `-size N -unit gb` after converting TB→GB via current parser math.
- Bump `APP_VERSION` to **1.6.157**.

## Non-goals

- GiB / TiB labels or a four-way unit menu.
- Decimal (1000-based) vs binary marketing math beyond what `parse_capacity_to_gb` already does for GB/TB.
- Changing Contingency snap capacity parsing.
- Changing FlashSystem `-unit` away from `gb`.
- A page-wide defaults-only unit control.

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Units | **GB** and **TB** only |
| Default | **GB** |
| Layout | Number + unit dropdown **in the Size cell** |
| Storage | One `size` string (e.g. `"100GB"`); dropdown is an editor aid |

## Behavior

### Size cell UI

1. Render Size as: `[ number ] [ GB ▼ ]` (options: `GB`, `TB`).
2. New rows and missing/unknown unit → unit = **GB**.
3. Changing number or unit updates the underlying `lun.size` to `{number}{UNIT}` with no space (e.g. `100GB`, `1.5TB`).
4. On load / re-render, parse `lun.size`:
   - Bare number → amount as-is, unit **GB**, normalize stored value to `{n}GB` when the row is edited (optional normalize-on-load is allowed if it keeps the plan consistent).
   - Suffix `GB` / `TB` (case-insensitive) → split amount + unit.
   - Any other suffix (e.g. `MB`): show the numeric amount with unit **GB** in the controls, but rewrite `size` to `{amount}GB` only when the operator edits number or unit (do not silently rewrite on load alone).
5. If the operator pastes a unit into the number field (e.g. `500GB`), on change/blur strip the unit into the dropdown and set `size` to `"500GB"`.

### Create / plan / export

- No new JSON keys. Export columns unchanged (`size` only).
- Templates keep embedding units in `size` (e.g. `"50GB"`).
- `lun_builder_create._size_gb` unchanged in contract: bare → GB; `1TB` → 1024 GB (existing `parse_capacity_to_gb`); CLI `-unit gb`.
- Validation: size required; parsed amount must be > 0.

## Architecture

| Unit | Responsibility |
|------|----------------|
| LUN Builder HTML/JS (`lun_builder.py` embedded UI) | Size cell: number + GB/TB select; sync to `lun.size` |
| Optional small pure helper (JS and/or Python test double) | `split_size_for_ui(size) → {amount, unit}` / `join_size(amount, unit)` |
| `lun_builder_create.py` | Unchanged create math unless a tiny shared join helper is reused |
| `config.APP_VERSION` | `1.6.157` |

## Testing

- UI/contract: Size cell markup includes a unit `<select>` with `GB` and `TB`; default selected **GB** for bare sizes.
- Round-trip: `100` + GB → stored `"100GB"`; `1` + TB → `"1TB"`.
- Load: `"100GB"` → amount `100`, unit `GB`; `"1TB"` → amount `1`, unit `TB`; bare `"100"` → amount `100`, unit `GB`.
- Paste normalize: number field `500GB` → amount `500`, unit `GB`, store `"500GB"`.
- Create still formats FlashSystem size without scientific notation for integer GB.
- Version pins expect `1.6.157`.

## Out of scope follow-ups

- GiB/TiB labels.
- Decimal SI units.
- Per-profile unit hints (HPE vs IBM).
