# Capacity Layers — Array, Pools/CPGs, Raw — Design

**Date:** 2026-08-05  
**Status:** Approved  
**App version target:** 1.6.114+  
**Supersedes / extends:** `docs/superpowers/specs/2026-08-04-hpe-array-capacity-cpg-toggle-design.md` (HPE array + CPG only; that doc’s locked HPE site-summary rules remain in force and are absorbed here)  
**Depends on:**
- Capacity Report (`launchpad/capacity_report.py`) — **Show pool storage** toggle / `localStorage`
- HPE: `showsys -d`, `showcpg`
- IBM FlashSystem/SVC: `lssystem` / Capacity - System, `lsmdiskgrp` / Capacity - Pools
- `analyze_health` / `parse_capacity_summary` / `capacity_summary_from_pools` / pool parsers
- Capacity-focus refresh (`filter_capacity_focus_commands`) and Excel (`capacity_export.py`)
- Dashboard capacity alerts

## Problem

Operators need three distinct capacity views that today are easy to conflate:

1. **Normal (array) capacity** — allocated/usable vs system total (matches SSMC Allocated % on HPE; IBM system usable summary). This should be the default site-level number.
2. **Pools / CPGs** — HPE CPG fill (`showcpg`) and IBM pool fill (`lsmdiskgrp`). Useful, but can read “full” while array allocated is low.
3. **Raw / physical capacity** — hardware footprint from system output (HPE raw/physical fields on `showsys -d`; IBM `physical_capacity` / related `lssystem` fields). Not the same as allocated %.

Today’s **Show pool storage** is largely a display toggle. Site totals sometimes still prefer CPG rollups over array. There is no Raw layer, and IBM pools are not first-class in the HPE-only CPG design.

## Goals

- **Always** collect and show **normal array capacity** as the primary site metric (live from the array on capacity refresh).
- Two Capacity Report toggles:
  - **Include CPG / pools** — HPE `showcpg` + IBM `lsmdiskgrp` (display + optional skip on live refresh when off).
  - **Show raw capacity** — parse/show raw/physical summary when available (display; collect from the same system command as array when off still runs system capacity).
- Persist both preferences in `localStorage`.
- Excel and capacity-focus refresh honor the flags.
- Alerts continue on array + pool/CPG when that data exists; **no raw-based alerts** in v1.
- Use clear labels: IBM **Pools** (not FlashCopy “CG”).

## Non-goals (v1)

- FlashCopy consistency-group capacity (separate feature).
- Raw-based CRIT/WARN alerts.
- Per-card overrides for the toggles.
- SSMC Device Type / historical charts.
- Changing ≥80 / ≥90 alert thresholds.
- Auto SSH on toggle without Refresh (show last collected when turning on).

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Layers | Normal array **always**; toggles for **CPG/pools** and **Raw** |
| Site-level primary | Array / normal capacity (HPE `showsys -d` allocated%; IBM system summary) |
| CPG/pools toggle | UI hide/show **and** skip pool/CPG commands on capacity refresh when off |
| Raw toggle | UI hide/show; raw parsed from system capacity output (no extra SSH when system cmd already runs) |
| IBM pool label | **Pools** (not “CG”) |
| CPG/pools default | **On** (migrate from today’s Show pool storage) |
| Raw default | **Off** |
| Persist | `localStorage` |
| Alerts | Array + pool/CPG when data present; not raw |
| Approach | Capacity Report toggles + focus filter + Excel flags |

## Command / data map

| Layer | HPE | IBM FlashSystem / SVC |
|-------|-----|------------------------|
| Normal (array) | `showsys -d` → allocated / total (existing parse preference) | Capacity - System / `lssystem` → usable used/total summary |
| Pools / CPGs | `showcpg` | `lsmdiskgrp` (Capacity - Pools) |
| Raw / physical | Raw/physical fields from `showsys -d` when present (e.g. raw capacity keys in KV output) | `physical_capacity` / `physical_free_capacity` (and related) from `lssystem` |

When a field is missing for a platform/firmware, that layer’s section is empty or omitted — do not invent values.

## Behavior

### 1) Normal array capacity (always)

1. Prefer system/array summary for site primary bar, Capacity Report site text, Excel Storage Capacity column, and fleet “Running at X%” alerts.
2. HPE: do **not** replace a valid `showsys` summary with “All CPGs” rollup.
3. IBM: keep system summary as primary; do not replace with sum of `lsmdiskgrp` when system summary exists.
4. Fallback to pool/CPG rollup only when system capacity is missing/unparseable (label clearly if from pools).

### 2) Include CPG / pools toggle

- Replace/retitle **Show pool storage** → **Include CPG / pools** (tooltip: HPE CPGs and IBM pools).
- Default **on**; migrate `launchpad.capacityReport.showPools` → `launchpad.capacityReport.includePools` (or keep old key with new label).
- **Off:**
  - Hide pool/CPG blocks on Capacity Report.
  - Pass `include_pools=0` (name TBD in plan; alias `include_cpg` acceptable) on Refresh / Excel / Dell if applicable.
  - Capacity focus **drops** `showcpg` and IBM pool commands (`lsmdiskgrp` / Capacity - Pools); keeps system capacity commands.
- **On:** collect and show pool/CPG rows as today.
- Toggle on without Refresh: show last collected rows if present; no automatic SSH.

### 3) Show raw capacity toggle

- New checkbox **Show raw capacity**, default **off**.
- `localStorage`: `launchpad.capacityReport.showRaw`.
- **On:** show a Raw / physical subsection (or columns) under the site when `raw_capacity_summary` (or equivalent) is present.
- **Off:** hide Raw UI; Excel omits raw columns/section.
- Collection: raw is derived from the **same** system capacity command already required for normal capacity — no extra command when pools are off. Do not skip `showsys` / `lssystem` when raw is off.
- Parsing: expose a dedicated summary object (e.g. `raw_capacity_summary` with total/used/free/used_pct when computable) alongside normal `capacity_summary`, so UI can show both without overwriting allocated %.

### 4) Live Refresh

- Capacity focus remains the path for Capacity Report Refresh / Export Excel / Dell Report.
- Filter pool/CPG commands when `include_pools=0`.
- Unlock + Monitor rules unchanged.

### 5) Excel

| Flag | Effect |
|------|--------|
| `include_pools=0` | Omit Pool Capacity sheet rows / pool stats text |
| `include_pools=1` | Current pool detail behavior |
| `show_raw=0` | Omit raw columns/section |
| `show_raw=1` | Include raw GiB / % when parsed |
| (always) | Site Storage Capacity from normal array summary |

### 6) Alerts

- Unchanged ≥80 / ≥90 bands.
- Array alerts from normal `capacity_summary`.
- Pool/CPG alerts when those rows exist in the latest analysis payload.
- No alerts from raw summary in v1.

## UI (Capacity Report)

Checkbox row (near existing pool control):

1. **Include CPG / pools** (default checked)  
2. **Show raw capacity** (default unchecked)  

Optional short helper text: “Site % uses array capacity. CPG/pools and raw are optional.”

## Architecture

| Piece | Responsibility |
|-------|----------------|
| `parse_capacity_summary` / new raw helper | Split or annotate normal vs raw from system output without conflating % |
| `analyze_health` | Prefer system for `capacity_summary`; attach `raw_capacity_summary` when available; pools list unchanged |
| `filter_capacity_focus_commands` | Drop pool/CPG cmds when `include_pools=0` |
| `capacity_report.py` | Two toggles, persist, pass flags on refresh/export; CSS hide sections |
| `capacity_export.py` / APIs | Honor `include_pools` + `show_raw` |
| Tests | Prefer system over pool rollup; filter drops pool cmds; raw parse fixture; page markers |

## Error / edge cases

| Case | Result |
|------|--------|
| System capacity missing | Fallback to pool rollup for site % if pools collected; else empty |
| Pools off + no system | Empty site capacity; no pool rows |
| Raw fields absent | Hide raw section even if toggle on |
| Non-HPE/non-IBM | Best-effort: pools toggle hides pool UI; raw only if parser finds physical fields |
| Stale pool data after pools off | Acceptable until next refresh overwrites (optional follow-up: clear pool results when skipped) |

## Testing

- HPE fixture: `showsys` ~27% allocated + `showcpg` ~97% → site `used_pct` ≈ 27%, not All CPGs.
- IBM fixture: system summary preferred over `lsmdiskgrp` sum when both present.
- `include_pools=False` keeps system cmds, drops `showcpg` / `lsmdiskgrp`.
- Raw parse: when physical fields exist, `raw_capacity_summary` populated; normal summary unchanged.
- Page: both toggle ids/labels; refresh/export query params include flags.
- Excel: pools/raw omitted when flags off.
- Alerts: array + pool when both present; no raw alert issues.
- Version bump on ship task (**1.6.114**).

## Out of scope follow-ups

- Clear cached pool/CPG command results when toggle turns off.
- Raw alerts.
- Per-card toggle overrides.
- Snapcopy outdated CG filter (separate workstream).
- Health Excel command-block tabs (separate workstream).
