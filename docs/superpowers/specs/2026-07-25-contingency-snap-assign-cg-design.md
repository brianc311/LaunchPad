# Contingency Run Create — optional assign to FlashCopy CG

**Date:** 2026-07-25  
**Status:** Approved for implementation  
**App version target:** 1.6.67  
**Depends on:** Contingency Groups `_snap` Preview/Run (`contingency_snap_create`), FlashCopy CG ops (`fc_consistgrp_ops` create/assign), Contingency Groups browser UI  
**Approach:** Extend Contingency Preview/Run with optional CG create-if-missing + assign steps (Approach 1)  
**Base branch:** `feature/contingency-groups` (tip at 1.6.66)

## Problem

Operators plan source → `_snap` pairs on **Consistency Groups** (Contingency), then **Run Create** to create volumes and FlashCopy maps on the array. Those maps land as **stand-alone**. Putting them into an array FlashCopy Consistency Group requires a manual second pass on **FlashCopy CGs** (Assign). That handoff is easy to miss and feels like a gap when building the “correct” CG membership.

## Goals

- On Contingency **Create & Map**, add an **optional** control: assign this run’s new FlashCopy maps into a named array CG.
- **Off by default**; operator opts in with checkbox + CG name.
- During Preview: if CG **exists**, warn *already exists — will assign into it*; if **missing**, plan *create CG, then assign*.
- Persist the **CG name** on the Contingency group (editable anytime); checkbox preference may also be saved so the group remembers intent, but assign only runs when checkbox is on for that Preview/Run.
- Only assign maps that this **Run Create** creates or starts (not every historical `_snap` on the group).
- Keep FlashCopy CGs as the place for later add/remove membership.
- Bump `APP_VERSION` to **1.6.67**.

## Non-goals

- Creating FlashCopy maps from the FlashCopy CGs page.
- Auto-assign with no opt-in (always-on).
- Blocking when CG name already exists (reuse with Preview warning instead).
- Assigning maps that already existed and were fully skipped this run (no create/start step executed for that map).
- Multi-CG assign in one Run (one CG name per run).
- Changing Remove-from-CG / stand-alone assign UX on FlashCopy CGs beyond cross-links/copy if useful.

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| When to assign | **A** — Optional checkbox + CG name; off by default |
| Missing CG | **A1** — Create if missing; if exists, Preview warns and assign into it |
| Which maps | **A** — Only maps created or started in **this** Run Create |
| Implementation | **1** — Extend Contingency Preview/Run step list |
| Persist | **A** — Save CG name on Contingency group (pre-fill; operator can change before run) |

## Behavior

### UI (Contingency Groups → step 3 Create & Map)

- Near Preview / Run Create:
  - Checkbox: **Assign new FlashCopy maps to CG** (unchecked by default for new sessions unless group saved with it on — prefer: **persist CG name always; persist checkbox state with the group** so Windsor can remember “usually assign to WIN_ESX_snap”, but first-time groups start unchecked).
  - Text field: **CG name** (e.g. `WIN_ESX_snap`), enabled when checkbox is on; required when checkbox is on.
- Changing the name and **Save** updates the group’s stored default; next open pre-fills that name. Operator may type a different name for one run without saving, or save to update the default.
- Unchecking skips all CG create/assign steps for that Preview/Run.

### Preview / Run pipeline

When checkbox is on and CG name is non-empty (validated safe CLI token):

1. Existing Contingency `_snap` steps run as today (mkvdisk / mkfcmap / startfcmap / host map, with skip-if-exists).
2. Collect map names for which this run has a **non-skipped** `mkfcmap` and/or `startfcmap` step (maps “created or started this run”). If none, Preview warns that assign has nothing to do; do not fail the whole snap create unless product prefers soft-skip assign only.
3. Inventory `lsfcconsistgrp`:
   - If CG name **missing** → step `mkfcconsistgrp -name <name>`.
   - If CG name **present** → skip create; add Preview warning: `CG "<name>" already exists — will assign maps into it.`
4. For each map from step 2 that is still stand-alone (or not yet in this CG): step `chfcmap -consistgrp <name> <map>`. Skip if already in that CG. If map is in a **different** non-empty CG, Preview **warning** and skip that map (do not silently steal); list which maps were skipped. (Hard-fail optional later; v1 = warn + skip.)
5. Single confirm → Run executes the combined step list; log includes CG create/assign outcomes.

### Persistence

- Contingency group JSON gains fields, e.g.:
  - `snap_assign_cg_name: string` (default `""`)
  - `snap_assign_cg_enabled: bool` (default `false`)
- Loaded into UI on group select; written on Save / Save as new with the rest of the group.

### FlashCopy CGs

- Unchanged for membership editing (Assign / Remove).
- Optional: short hint on Contingency page linking to FlashCopy CGs for fine-grained membership changes.

## Architecture

```
Contingency Create & Map
  checkbox + CG name (saved on group)
           │
           ▼
preview_contingency_snaps / create_contingency_snaps
  existing snap steps
  + optional mkfcconsistgrp (skip if exists)
  + optional chfcmap assign (maps from this run only)
           │
           ▼
FlashCopy CGs page (still used for add/remove later)
```

Reuse `fc_consistgrp_ops` helpers where practical (`build_fc_consistgrp_steps` / inventory parsers) rather than duplicating CLI string logic.

## Testing

- Unit: when assign off → no CG steps.
- Unit: CG missing → mkfcconsistgrp + chfcmap for maps with non-skipped mkfcmap/startfcmap this run.
- Unit: CG exists → no mkfcconsistgrp; warning present; chfcmap for eligible maps.
- Unit: skipped-only maps (already existed) → not assigned.
- Unit: map already in target CG → skip assign; map in other CG → warn + skip.
- API/UI: group save/load of `snap_assign_cg_name` / `snap_assign_cg_enabled`; checkbox gates Preview payload.
- No live array required in CI.

## Success criteria

1. With checkbox off, Run Create behavior unchanged from today.
2. With checkbox on + new CG name, Preview shows create CG + assign; after Run, FlashCopy CGs shows maps under that CG (not only stand-alone).
3. With checkbox on + existing CG name, Preview warns reuse; Run assigns this run’s new maps into it.
4. Operator can change CG name on the group and Save; next open shows the new default.
5. Version **1.6.67**.

## Out of scope follow-ups

- “Assign all planned `_snap` maps for this group” mode.
- Steal maps from another CG (force reassign).
- Multi-select CG targets in one run.
- Auto-start CG after assign.
