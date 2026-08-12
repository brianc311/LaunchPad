# Dell HPE Report Display Capacity — Design

**Date:** 2026-08-12  
**Status:** Approved  
**App version target:** 1.6.161  
**Extends:** `docs/superpowers/specs/2026-08-11-dell-array-snapshots-forecast-design.md`  
**Related:** `docs/superpowers/specs/2026-08-05-dell-report-raw-facility-wkly-design.md`

## Problem

After **1.6.152** (array-only weekly snapshots), Dell Report **HP Report**, **HP Forecast**, and **HP Report - Wkly** / forecast-wkly sheets show headers but **no HPE data rows**.

Operators confirm:

- HPE dashboard cards are online and **show usable/used (or raw) capacity** after refresh.
- IBM Dell sheets still populate.
- HP Excel sheets are empty under the blue headers.

**Root cause:** `collect_dell_report_rows` uses only `select_dell_array_snapshot_summary` (non-rollup system `capacity_summary`). HPE Primera/3PAR often has **raw** (`showsys -space`) and/or **All CPGs** pool rollup without a usable non-rollup system summary, so sites are skipped. IBM usually has system capacity, so IBM sheets still work.

Online/SSH health is not the failure mode.

## Goals

- Restore **HP Report**, **HP Forecast**, and **HP Wkly / Forecast-Wkly** rows whenever display capacity exists (same collect pipeline feeds all of these sheets).
- Keep weekly snapshot upserts **system-layer only** so mixed raw/pool weeks do not poison Weekly Growth % / forecast projections.
- Preserve forced-include blank identity rows and IBM system-path behavior.

## Non-goals

- Changing Capacity Report page totals or CPG/raw toggle UI.
- Fixing HPE SSH/parse (capacity already appears on the card).
- Reverting the 1.6.152 growth layer gate.
- Writing raw or pool bytes into the Dell weekly snapshot store.
- LED band changes, logos, or non-IBM/HPE vendor sheets.

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Approach | **1** — display via full capacity selector; snapshots stay system-only |
| Sheets restored | HP Report, HP Forecast, HP Report - Wkly, HP Forecast - Wkly (shared rows) |
| Snapshot policy | Never upsert raw / All CPGs / pool rollup |
| Display when no system | Emit row from display summary; prior/growth blank or existing no-prior rules |

## Behavior

### Dual selection in collect

For each IBM/HPE site in `collect_dell_report_rows`:

1. **Display summary** — `select_dell_capacity_summary(capacity_summary=..., raw_capacity_summary=..., pools=..., include_pools=...)` using the export’s CPG/pools flag.
2. **Snapshot summary** — `select_dell_array_snapshot_summary(capacity_summary=...)` only.

### Row emission

| Case | Emit row? | Upsert snapshot? | Current week GiB/util | Prior / growth |
|------|-----------|------------------|------------------------|----------------|
| System summary usable | Yes | Yes (`layer=system`) | From store after upsert | From store; growth gated system↔system |
| No system; display usable (raw and/or pools per toggle) | Yes | **No** | From **display** summary | Blank / no-prior behavior |
| No display capacity; card in include set | Yes (blank capacity) | No | Blank | Blank |
| No display capacity; not included | Skip | No | — | — |

Identity (`facility`, `array_name`, `model`) uses existing `resolve_dell_identity` with the display (or blank) summary name.

### Forecast and Wkly

No separate HPE collector. Workbook builders already consume `hp_rows` / `ibm_rows` from collect. Restoring collect emission restores:

- HP Report / IBM Report  
- HP Forecast / IBM Forecast  
- HP Report - Wkly / Forecast - Wkly (and IBM counterparts)

Forecast projection rules from 1.6.152 stay as-is: growth/projection only when snapshot layers allow; display-only weeks still show current util on Report and flat Date util on Forecast when the row exists.

### `maybe_upsert_dell_snapshot_for_card`

Unchanged: system-only upsert when the current ISO week is missing. Does not write raw/pool.

## Components

| Area | Change |
|------|--------|
| `launchpad/dell_report_export.py` | Dual select in `collect_dell_report_rows`; helper to build a current-week row from display bytes when store has no system upsert |
| `launchpad/dell_report_capacity.py` | No API change |
| `launchpad/dell_report_snapshots.py` | No behavior change |
| `launchpad/config.py` | `APP_VERSION` → `1.6.161` |
| Tests | Update collect expectations for raw-only / All-CPGs+raw |

## Error handling

- Empty IBM **and** HP after collect → existing `DellReportEmptyError` / UI message.
- Display-only HPE sites must count as non-empty HP rows (so export succeeds when only HPE raw capacity exists).
- No new user-facing errors for “raw used for display, not snapshotted.”

## Testing

- Only raw, `include_pools=False` → HP row with raw GiB/util; **store empty**.
- All CPGs + raw, CPG off → row from raw; no snapshot.
- System + raw → snapshot and current week from **system** (unchanged).
- Forced-include, no capacity → blank identity row (unchanged).
- Untagged / non-system prior still blanks growth (unchanged).
- Version pin tests for 1.6.161.

## Success criteria

- [ ] Dell export with monitored HPE cards that show capacity on the dashboard fills **HP Report**, **HP Forecast**, and HP Wkly sheets with data rows.
- [ ] Raw/pool-only HPE weeks do not create `layer=system` snapshot entries.
- [ ] IBM system path and growth gating remain correct.
- [ ] Focused Dell collect/capacity tests pass.
