# Capacity unit toggle (GiB/TiB ↔ GB/TB)

**Date:** 2026-08-11  
**Status:** Approved for implementation  
**App version target:** 1.6.151  
**Depends on:** Connection Dashboard settings (`db.get_setting` / `set_setting`), `_format_bytes` / `_parse_size_bytes`, Dell Report export, HealthServer page JS `formatBytes`  
**Approach:** One persisted unit mode + shared formatters (Approach 1)  
**Base branch:** `main` (tip at 1.6.150)

## Problem

LaunchPad stores capacity as **bytes** (correct) but **labels** those 1024-based values as GB/TB. Dell Report already uses GiB headers and `1024³`. Operators need honest IEC labels by default, a way to switch to real decimal GB/TB (numbers change), and Dell headings/values that follow that same switch.

## Goals

- Default display is **GiB / TiB / PiB** (1024).
- A **global** Connection Dashboard header switch selects IEC vs SI. The last choice is persisted.
- SI mode uses **1000** divisors and **GB / TB / PB** labels. Same bytes → different numbers.
- Dell Report usable/used **headers and cell values** follow the mode (`(GiB)` vs `(GB)`).
- All capacity **display** surfaces share the same formatter/mode (UI, HealthServer pages, Excel, Dell).
- IBM/HPE CLI **parse** stays 1024 → bytes. No extra SSH on toggle.
- Bump `APP_VERSION` to **1.6.151**.

## Non-goals (v1)

- Changing LUN Builder / Contingency create CLI (`-unit gb`, `parse_capacity_to_gb`). Those are array command sizes, not display labels.
- Per-report or export-time unit pickers.
- Auto-scaling Dell columns to TiB/TB. Dell stays a **fixed** GiB or GB column (as today is always GiB).
- Recollecting SSH data when the toggle flips.
- A second toggle in Admin (dashboard header only).
- Relabeling non-capacity fields (WWPN, counts, percents).

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Dell headings | Follow the toggle: `(GiB)` in IEC, `(GB)` in SI. Values use matching divisor. |
| Math | Real units: IEC = 1024, SI = 1000. Numbers change when flipped. |
| Scope | One global mode for UI, reports, Dell, Excel, HealthServer. |
| Default | `iec` (GiB/TiB) when the setting is missing. |
| Control | Connection Dashboard header switch (same row as Light mode / Admin / Lock). |
| Persistence | Remember last choice via settings DB. |

## Setting

Key: `capacity_unit_mode`  
Values: `iec` | `si`  
Default: `iec`  
API: `db.get_setting("capacity_unit_mode", "iec")` / `db.set_setting(...)` (same as `theme` / `cards_compact`).

Unknown or empty stored values treat as `iec`.

## Behavior

### Parse (unchanged)

`_parse_size_bytes` keeps 1024 multipliers. CLI `TiB` still aliases to the TB multiplier. CLI `1TB` / `1GB` remain `1024⁴` / `1024³` bytes. Source of truth in snapshots stays `*_bytes`.

### Shared display formatter

`_format_bytes(num_bytes)` (and JS `formatBytes` clones) use the **current** mode:

| Mode | Divisors | Labels | Example `1024³` bytes | Example `1024⁴` bytes |
|------|----------|--------|----------------------|----------------------|
| `iec` | 1024³ / 1024⁴ / 1024⁵ | GiB / TiB / PiB | `1.0 GiB` | `1.0 TiB` |
| `si` | 1000³ / 1000⁴ / 1000⁵ | GB / TB / PB | `1.1 GB` | `1.1 TB` |

Keep today’s shape: start at the giga unit (no B/KiB/MiB), one decimal, space before the unit, `<= 0` → `0 GiB` or `0 GB`.

`health_format._gb` must use the same mode and unit names (call `_format_bytes` or an equivalent shared helper). Do not leave a second 1024-labeled-as-GB path.

### Dell Report

- Four usable/used headers: `Useable Capacity (GiB)` / `Used Capacity (GiB)` in IEC; `(GB)` in SI.
- Cell values: `num_bytes / 1024³` (IEC) or `num_bytes / 1000³` (SI). Prefer a `bytes_to_capacity_unit` helper; `bytes_to_gib` may wrap IEC or be replaced at call sites.
- Convert at **Excel write** from byte fields (or from stored IEC GiB history). Do not bake SI/IEC into the snapshot store. Existing weekly `*_gib` points stay 1024-based GiB on disk; SI display is `stored_gib * 1024³ / 1000³`.
- Utilization % and weekly growth unchanged.
- Forecast sheets that do not print GiB/GB capacity headers are unchanged.

### Dashboard toggle

`CTkSwitch` on the header row with Light mode / Admin / Lock.

- Switch off → `iec`. Switch on → `si`.
- Label shows the **active** mode: `GiB/TiB` or `GB/TB` (same pattern as the theme switch label).
- On change: persist setting, then re-format dashboard card capacity text from existing byte snapshots. Reload or re-render LaunchPad-owned HealthServer views that are already open. Browser tabs the operator opened separately pick up the mode on next page load.
- Excel / Dell / other exports read the mode when the file is built.

### HealthServer / page JS

Inject `capacity_unit_mode` into served pages (constant or small API read at request time). Every `formatBytes` (health dashboard, site lookup, snapshot schedule, FC consistgrp, capacity report JS, and host RAM/disk in `health_server.py`) must use the same divisor/label table as Python.

## Architecture

| Unit | Change |
|------|--------|
| Settings | `capacity_unit_mode` (`iec` default) |
| `launchpad/capacity_units.py` (new) | Mode get/set in memory, `format_bytes`, `bytes_to_capacity_unit`, header unit label (`GiB`/`GB`). Load from DB at app start and on toggle. |
| `launchpad/flashsystem_parse.py` | `_format_bytes` delegates to `capacity_units.format_bytes`. Parse unchanged. |
| `launchpad/health_format.py` | `_gb` / disk labels use shared formatter |
| `launchpad/dell_report_export.py` | Mode-aware headers + `bytes_to_capacity_unit` at write time |
| `launchpad/ui/dashboard_view.py` | Header switch, persist, set in-memory mode, refresh cards |
| HealthServer + page JS | Inject mode; align `formatBytes` |
| Exports that call `_format_bytes` | Inherit automatically (`capacity_export`, snapshot schedule Excel, FC CG totals, etc.) |
| `launchpad/config.py` | `APP_VERSION` → `1.6.151` |

Tests may call `set_capacity_unit_mode` directly. Formatters do not query the DB on every call.

## Testing

- `_format_bytes(1024**3)` → `1.0 GiB` (iec) and `1.1 GB` (si).
- `_format_bytes(1024**4)` → `1.0 TiB` (iec) vs matching TB in si.
- `_format_bytes(0)` → `0 GiB` / `0 GB`.
- `_parse_size_bytes("1TB")` still `1024**4` regardless of mode.
- Dell: headers contain `(GiB)` or `(GB)` from mode; `bytes_to_capacity_unit(1024**3)` is `1.0` (iec) and `1.073741824` (si).
- Missing setting → `iec`.
- JS helpers: same examples as Python (unit test or string-marker in page source).

## Version

Bump `APP_VERSION` to **1.6.151** when the feature ships.
