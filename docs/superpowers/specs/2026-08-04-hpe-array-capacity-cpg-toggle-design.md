# HPE Array Capacity + CPG Toggle — Design

**Date:** 2026-08-04  
**Status:** Superseded by `docs/superpowers/specs/2026-08-05-capacity-layers-array-pools-raw-design.md` (adds IBM pools + Raw layer; HPE array/CPG rules below remain authoritative within that doc)  
**App version target:** 1.6.108+ (see superseding doc for current target)  
**Depends on:**
- Capacity Report (`launchpad/capacity_report.py`) — existing **Show pool storage** toggle / `localStorage`
- HPE capacity commands (`showsys -d`, `showcpg`) via `ensure_hpe_capacity_commands` / interactive shell
- `analyze_health` / `parse_capacity_summary` / `capacity_summary_from_pools`
- Capacity focus refresh (`filter_capacity_focus_commands`) and Excel export (`capacity_export.py`)
- Dashboard capacity alerts (array + pool/CPG issues)

## Problem

For HPE 3PAR/Primera, Capacity Report / Excel often show **CPG fill** (e.g. “All CPGs: 97.5% used”) while SSMC **Capacity** shows **array allocated** (e.g. 27% Allocated of total physical). Operators treat the report as wrong because the site-level number does not match SSMC. CPG detail is still useful and must remain switchable — including skipping live `showcpg` when off for faster refresh.

## Goals

- Site-level capacity uses **array** metrics from `showsys -d` (Allocated / Total ≈ SSMC Total Capacity “Allocated %”).
- **Include CPG capacity** control on Capacity Report:
  - **On:** show CPG/pool detail; live Refresh / capacity focus includes `showcpg`.
  - **Off:** hide CPG/pool UI; live Refresh / capacity focus **skips** `showcpg` (still runs `showsys -d`).
- Persist the preference in `localStorage` (same pattern as today’s pool toggle).
- Excel respects the same include-CPG flag (omit pool/CPG detail when off).
- Capacity **alerts** still evaluate **both** array and CPG whenever CPG data is present; after a refresh with CPG off, only array alerts apply until CPG is collected again.

## Non-goals (v1)

- Changing IBM FlashSystem / SVC pool math or labels.
- Removing CPG/pool alerts permanently or changing ≥80 / ≥90 thresholds.
- SSMC historical capacity charts or Device Type breakdown cards.
- Forcing a re-fetch of CPG when toggling UI on without Refresh.

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Site-level metric | **A** — array capacity from `showsys -d` (match SSMC Allocated %) |
| CPG on/off | **C** — UI hide/show **and** skip `showcpg` on live refresh when off |
| Alerts | **C** — always alert on both array and CPG when CPG data exists |
| Approach | **1** — Capacity Report toggle + live focus filter |
| Default | **On** (include CPG) |
| Persist | `localStorage` |

## Behavior

### Site-level capacity (HPE)

1. Parse `showsys -d` (or labeled Capacity - System) into `capacity_summary` with used = **allocated** when allocated + total are present (existing `parse_capacity_summary` behavior).
2. Prefer this system summary for:
   - Capacity Report site capacity text / primary bar
   - Excel **Storage Capacity** / inventory capacity column
   - “Running at X% capacity” fleet/site alerts from system %
3. Do **not** replace a valid system summary with `capacity_summary_from_pools` (“All CPGs”) when pools exist.
4. Fallback to pool rollup only when system capacity is missing/unparseable.

### Include CPG capacity toggle

- Rename or retitle the existing **Show pool storage** control to **Include CPG capacity** (or keep the checkbox id and update the visible label + tooltip) so one control covers display + live collect.
- Default **checked** (on).
- `localStorage` key: reuse `launchpad.capacityReport.showPools` **or** introduce `launchpad.capacityReport.includeCpg` with migration from the old key if renamed.
- When **off:**
  - CSS/hide CPG/pool blocks on Capacity Report (same as today’s `hide-pool-storage`).
  - Pass `include_cpg=0` (or equivalent) on Refresh On Sites / per-site capacity refresh and on Excel export.
  - Server-side capacity focus / command list **drops** `showcpg` (and HPE CPG-only capacity labels); keeps `showsys -d` / system capacity commands.
- When **on:** current behavior for collecting and showing CPG/pool rows.

### Live Refresh (“Refresh On Sites”)

- Already capacity-focused for HPE; extend filtering so `include_cpg=0` excludes `showcpg`.
- Unlock + Monitor rules unchanged.

### Excel

- When `include_cpg=0`: omit Pool Capacity detail rows / pool stats text derived from CPG; site capacity column still filled from array summary when available.
- When `include_cpg=1`: unchanged pool sheet + pool stats lines.

### Alerts

- Unchanged thresholds (≥80 warn, ≥90 critical).
- Emit array (“Running at …”) from system summary when ≥80.
- Emit per-CPG (“Pool … is …% full”) when CPG rows are present and ≥80.
- If CPG was skipped on the latest refresh, do not invent CPG alerts from stale UI-only state; use whatever is in the latest `command_results` / analysis payload (stale cached CPG output may still alert until overwritten — acceptable v1; optional follow-up: clear CPG results when skipped).

## Architecture

| Piece | Responsibility |
|-------|----------------|
| `analyze_health` / capacity fill helpers | Prefer `showsys` system summary over All-CPGs rollup for `capacity_summary` |
| `format_capacity_text` / report HTML | Site text from system summary; pools only in pool section |
| `filter_capacity_focus_commands` (+ API query) | Optional exclude `showcpg` when `include_cpg=0` |
| `capacity_report.py` | Toggle label, persist, pass `include_cpg` on refresh/export |
| `capacity_export.py` / `/api/capacity-export` | Honor `include_cpg` for pool sheet / pool stats |
| Tests | System preferred over CPG rollup; focus filter drops showcpg; page marker for toggle |

## Error / edge handling (v1)

| Case | Result |
|------|--------|
| `showsys -d` missing / unparseable | Fall back to CPG/pool rollup for site summary (today’s behavior) with clear label if from pools |
| CPG off + no system capacity | Empty/error site capacity; no CPG rows |
| IBM / non-HPE | Unchanged; pool toggle still hides pool UI only |
| Toggle on without Refresh | Show last collected CPG if present; no automatic SSH |

## Testing

- Unit: with both `showsys -d` (~27% allocated) and `showcpg` (~97% CPG), `capacity_summary.used_pct` matches system allocated %, not All CPGs.
- Unit: `filter_capacity_focus_commands(..., include_cpg=False)` keeps `showsys`, drops `showcpg`.
- Page: Include CPG capacity control present; off hides pool blocks; refresh/export URLs include the flag.
- Excel: `include_cpg=0` omits pool detail rows.
- Alerts: system ≥80 and CPG ≥80 both still produce issues when both datasets present.
- `APP_VERSION` bump on ship task.

## Out of scope follow-ups

- Clearing cached `showcpg` output immediately when toggle turns off.
- Per-card CPG include override.
- Matching SSMC “Device Type” / historical charts.
- Snapcopy outdated CG filter (separate plan; version after this ship).
