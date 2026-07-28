# FlashCopy CG summary — policy, maps, size, snaps/week (both pages)

**Date:** 2026-07-28  
**Status:** Approved for implementation  
**App version target:** 1.6.69  
**Depends on:** FlashCopy CGs inventory (`fc_consistgrp_ops`), member map source sizes, Snapshot Schedule frequency helpers, Contingency Groups page + storage hint / Sync  
**Approach:** Shared CG summary builder; thin summary on FlashCopy CGs table + Contingency read-only section (Approach 1)  
**Base branch:** `feature/contingency-groups` (tip at 1.6.68)

## Problem

Operators know there are FlashCopy Consistency Groups on arrays, but LaunchPad does not give a single at-a-glance view of **policy**, **what is mapped** (FC maps + host maps), **size**, and **snapshots per week**. FlashCopy CGs already shows member maps and source sizes; Contingency Groups often looks empty for card-stub sites and does not surface live CG summaries. Snapshot Schedule already encodes site snap frequency but is a separate page.

## Goals

- Build a **shared CG summary** per array FlashCopy CG:
  - Policy (array fields when present)
  - FC member map count
  - Host map count (targets of that CG)
  - Total size (sum of member source sizes)
  - Snaps/week (array if available, else Snapshot Schedule)
- Show that summary on **FlashCopy CGs** (table columns) and on **Contingency Groups** (read-only section for the site’s resolved card).
- v1 is a **thin vertical slice**: counts/totals/labels, not full host-map tables on Contingency.
- Bump `APP_VERSION` to **1.6.69**.

## Non-goals (v1)

- Full host↔LUN mapping tables on Contingency (follow-up).
- Creating/editing array FlashCopy policies from LaunchPad.
- Auto-creating or running snapshots.
- HPE / non–Spectrum Virtualize CG inventory.
- Merging Contingency Source planning rows with live CG membership automatically.
- Changing CG create / assign / remove / start / delete behavior beyond displaying summary fields.

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Home | **C** — both: FlashCopy CGs source of truth; Contingency read-only summary |
| Policies | **C** — array CG policy fields **and** LaunchPad Snapshot Schedule frequency |
| Snaps/week | **B** — array if available; else Snapshot Schedule |
| What’s mapped | **C** — FC member maps **and** host maps (v1 = counts; full host tables later) |
| v1 shape | **C** — thin summary on both pages |
| Implementation | **1** — shared summary builder |

## Behavior

### Shared summary record

For each FlashCopy CG on a card:

| Field | Meaning | Source |
|-------|---------|--------|
| `name` | CG name | `lsfcconsistgrp` |
| `status` | CG status | `lsfcconsistgrp` |
| `policy` | Human-readable policy snippet | Extra `lsfcconsistgrp` columns when present (copy rate / relationship / autodelete-style fields if in the delimited table); otherwise `""` / display `—` |
| `fc_map_count` | Member FlashCopy maps | Existing membership count |
| `host_map_count` | Host maps to CG **target** volumes | `lshostvdiskmap` filtered to targets of this CG’s member maps |
| `total_size` / `total_size_bytes` | Sum of member **source** sizes | Existing size enrichment |
| `snaps_per_week` | Approximate weekly snap rate | Prefer array-provided field if discovered in inventory; else derive from Snapshot Schedule interval for the card: `7 / days` (e.g. 7 days → `1`, 14 → `0.5`); held / no capacity → display schedule label (`HOLD`, `NO CAPACITY DATA`) instead of a number |
| `snaps_source` | `array` \| `schedule` \| `none` | Provenance for UI hint |

### FlashCopy CGs page

- Extend the Consistency Groups table with columns: **Policy**, **Host maps**, **Size**, **Snaps/week** (Maps column remains).
- On Refresh / inventory load: collect CGs + maps + sizes (existing) plus host maps; attach schedule frequency for the selected card.
- Member maps panel unchanged (still lists maps with per-row Size).
- Optional one-line hint under the table: snaps/week provenance when from schedule.

### Contingency Groups page

- Add read-only section **Array FlashCopy CG summary** (near Source or after metadata).
- Resolve card via `storage_hint` / group name (same as Sync).
- **Refresh CG summary** control (and refresh after successful Sync when practical).
- List one row per CG on that array using the shared summary fields.
- Empty Contingency Source volumes does **not** block this section — stubs can still show live CG summaries once SSH inventory succeeds.
- Link to FlashCopy CGs for management; Contingency does not mutate CGs here.

### Snapshot Schedule integration

- Reuse the same capacity→interval logic Snapshot Schedule uses for the card (or a small shared helper), without requiring the Snapshot Schedule page to be open.
- Do not invent a second scheduling system.

## Architecture

```
FlashCopy CGs Refresh ──┐
                        ├──▶ shared build_cg_summaries(card inventory + schedule)
Contingency summary ────┘              │
                                       ▼
                         FC CG table columns / Contingency summary table
```

### Modules (proposed)

| Module | Responsibility |
|--------|----------------|
| `launchpad/fc_cg_summary.py` (new) or extend `fc_consistgrp_ops.py` | Build summary records; host-map counts; snaps/week derivation |
| `launchpad/fc_consistgrp.py` | Table columns + JS render |
| `launchpad/contingency_groups.py` | Read-only summary section + refresh |
| `launchpad/health_server.py` | Inventory enrichment; Contingency summary API if needed |
| Snapshot schedule helpers | Interval/frequency for card (extract/reuse) |

## Testing

- Unit: summary with known maps/hosts/sizes; host_map_count only for CG targets; snaps/week from schedule days; missing policy → empty/`—`.
- Unit/API: FC inventory response includes new summary fields; Contingency summary endpoint or embedded payload for a card.
- Page contracts: FlashCopy CGs HTML contains new column headers; Contingency HTML contains summary section + Refresh.
- No live array required in CI.

## Success criteria

1. FlashCopy CGs CG table shows Policy, Maps, Host maps, Size, Snaps/week for each CG after Refresh.
2. Contingency Groups shows the same summary for the site’s resolved card without requiring Source volumes to be filled.
3. Snaps/week prefers array data when present; otherwise matches Snapshot Schedule frequency for that card.
4. Version **1.6.69**.

## Out of scope follow-ups

- Contingency full host-map / member-map detail tables.
- Editing policies or snap cadence from these summaries.
- Persisting summaries into Contingency JSON for offline stale views.
- Per-CG Snapshot Schedule rows (schedule remains site/card scoped unless product changes later).
