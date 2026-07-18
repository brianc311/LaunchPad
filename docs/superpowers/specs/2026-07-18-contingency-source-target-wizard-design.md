# Contingency Groups Source → Target Wizard — Design

**Date:** 2026-07-18  
**Status:** Implemented  
**App version target:** 1.6.21  
**Depends on:**
- Contingency Groups library (`2026-07-17-contingency-groups-design.md`)
- Contingency `_snap` create (`2026-07-18-contingency-snap-copies-design.md`)

## Problem

Contingency Groups already store sources, `_snap` targets, and can Preview/Run Create on IBM FlashSystem. The current page is table-heavy and does not clearly teach operators the Source → Target → Create & Map flow used when setting up contingency copies on the array.

## Goals

- Guided **3-step wizard** on the Contingency Groups page:
  1. **Source** — storage card + source volumes (pool/size) + source host maps
  2. **Target** — generated/editable `*_snap` targets side-by-side with sources
  3. **Create & Map** — plain-language plan, Preview/Dry-run, confirmed Run Create
- Keep an **Advanced edit** path for raw hosts/volumes/maps tables.
- Reuse existing snap generate / preview / create APIs and safety rules.
- Make the default path easy: defaults for names, pool/size, host/SCSI; validate before Next/Run.

## Non-goals

- Waiting for FlashCopy completion.
- Creating hosts on the array.
- Auto-selecting pools.
- Redesigning FC WWPN or Snapshot Schedule pages.

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Approach | Three-step guided wizard (Approach 1) |
| Step order | Source → Target → Create & Map |
| Advanced tables | Remain available (toggle/collapse) |
| Wizard step persistence | Client-only (no DB `wizard_step` field for v1) |
| Create engine | Existing `_snap` Preview + Run Create |

## UX

### Entry

- Group picker unchanged.
- Primary view: wizard with progress `1 Source · 2 Target · 3 Create & Map`.
- Controls: **Back**, **Next**, **Save**.
- Link/toggle: **Advanced edit** shows existing tables (hosts / all volumes / maps).

### Step 1 — Source

- Set/confirm **Storage hint** (LaunchPad SSH card name) — required before Step 3 create.
- Table of **source volumes only** (`role != snap`): name, pool, capacity.
- Source host maps (host + SCSI) shown for those volumes.
- Validation to leave Step 1:
  - At least one source volume
  - Each source has non-empty name; pool and capacity required when planning create (same blocking rules as snap create)
- Optional stretch: **Refresh from array** via light `lsvdisk` on the resolved card to fill pool/size.

### Step 2 — Target

- On enter (or via button): ensure `_snap` rows via existing generate logic.
- Side-by-side: Source | Target (`*_snap`) | Pool | Size | Planned/Exists.
- Targets editable; default naming remains `SourceName_snap`.
- Validation: every source has a matching target row before Next.

### Step 3 — Create & Map

- Plain-language checklist:
  - Create target volumes
  - Create FlashCopy (source → target)
  - Start FlashCopy
  - Map targets to hosts (same SCSI as source)
- Pair summary table: Source → Target → Hosts/SCSI → Action (create / skip if exists).
- **Preview / Dry-run** and **Run Create** (confirm; gated on successful preview this session).
- Result log modal (existing snap modal; must remain hidden when closed — CSS `[hidden]` fix).

### Make it easy

- Defaults do naming, pool/size copy, and host/SCSI mirroring.
- Inline blocking messages before Next/Run.
- One linear path for operators; Advanced edit for power users.

## Data / APIs

**No new persistence schema required** beyond existing contingency group + snap fields (`role`, `source_volume`).

**Reuse:**
- `POST /api/contingency-groups/generate-snaps`
- `POST /api/contingency-groups/snap-preview` (returns resolved `card`)
- `POST /api/contingency-groups/snap-create` (`confirm: true`)
- Existing save/upsert group APIs
- Save-before-snap-ops behavior remains

**Optional v1 stretch:**
- `POST /api/contingency-groups/refresh-sources` — `{ group_id }` runs `lsvdisk` and returns suggested pool/capacity updates for source volumes (does not auto-write unless user accepts).

## Edge cases

- Empty/unknown `storage_hint`: Steps 1–2 editable; Step 3 Preview/Run blocked with clear error.
- Missing pool/size: block leaving Step 1 or block create in Step 3 (same warnings as snap engine).
- Existing target/FC map/host map: Step 3 shows Skip; create engine skip-if-exists.
- Unsafe CLI tokens: existing `cli_token` validation remains.
- Generate does **not** require a live card; Preview/Create do.

## Files to touch (implementation)

- `launchpad/contingency_groups.py` — wizard UI (steps, validation, advanced toggle)
- Possibly light helpers in `contingency_groups_data.py` (source-only / pair views)
- Optional refresh-sources route in `health_server.py` + `contingency_snap_create.py`
- `tests/test_contingency_groups_page.py` — wizard contract strings
- `launchpad/config.py` — version bump

## Manual test plan

1. Open Contingency Groups → Hartford → wizard Step 1 shows sources only.
2. Next → Step 2 shows `*_snap` targets paired to sources.
3. Next → Step 3 checklist + Preview (with valid storage_hint/card).
4. Run Create on lab array only; log shows steps; Close dismisses modal.
5. Advanced edit still works for raw table edits.
6. Missing pool on a source blocks Next or Preview with a clear message.

## Out of scope / later

- Resume wizard step from DB after reload.
- Drag-and-drop multi-select from live IBM volume browser as the only Step 1 path.
- Consistency/incremental FC policy UI.
