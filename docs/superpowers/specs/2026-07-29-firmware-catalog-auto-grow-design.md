# Firmware Catalog Auto-Grow from Live Scans

**Date:** 2026-07-29  
**Status:** Approved for implementation  
**App version target:** 1.6.74  
**Depends on:** System Connectivity Firmware tab + Admin catalog (1.6.73)  
**Approach:** Opt-in auto-insert of unseen Current into per-profile catalog during Refresh live, with version-sort placement (Approach 1)  
**Base branch:** `feature/contingency-groups`

## Problem

Versions behind only works when Current is already in the Admin catalog. Operators must hand-type every release they’ve seen on arrays. Live Refresh already collects Current; that signal is unused for catalog maintenance.

## Goals

- Admin opt-in setting **Auto-add firmware from live scans** (default **off**).
- When on, System Connectivity **Refresh live** inserts each new non-empty Current into that card’s `device_profile` catalog using **version-sort** placement, then saves and computes Latest / Versions behind as today.
- Manual catalog Add / Remove / Move up / Move down / Save unchanged.
- Status feedback when Refresh added versions (`Catalog updated: N new version(s).` when N > 0).
- Bump `APP_VERSION` to **1.6.74**.

## Non-goals

- Auto-download of IBM/HPE/Lenovo release lists or Fix Central scrape.
- Auto-defining a vendor “recommended latest” beyond versions observed on the estate.
- Re-sorting the entire catalog on every scan (only insert missing Currents).
- Changing Firmware tab columns or export sheet shape (beyond reflecting updated catalog values).
- Growing the catalog when the setting is off.

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Capability | Auto-grow from live scans (not vendor download) |
| Insert position | Version-sort among existing entries |
| When it runs | During Refresh live, only if Admin setting is on |
| Setting default | Off |
| Implementation | Approach 1 — grow during Refresh when enabled |

## Behavior

### Admin setting

- Location: **Admin → Firmware catalog** tab.
- Control: checkbox **Auto-add firmware from live scans**.
- Hint: *When on, Refresh live inserts unseen Current versions into this profile’s list by version order.*
- Persisted in LaunchPad DB (dedicated setting key, boolean).
- Default: off (missing/empty setting → off).

### Refresh live (setting on)

1. Collect Current per eligible card as today (normalized SVC code level, etc.).
2. Load firmware catalog + auto-add setting once.
3. For each row with non-empty Current and a profile key:
   - If Current already in that profile’s list → no-op.
   - Else insert Current into the list at the **version-sort** position; do not delete or shuffle other entries beyond that insertion.
4. If any inserts occurred → `save_firmware_catalog` once (batch).
5. Enrich firmware rows (Latest / Versions behind) using the updated catalog.
6. If insert count N > 0 → include a clear status/note: `Catalog updated: N new version(s).`

### Refresh live (setting off)

- No catalog writes from Refresh.
- Missing Current → Versions behind `unknown` (unchanged).

### Version-sort rules

- Compare dotted/numeric segments (semver-ish): split on `.` and non-digit boundaries; compare numeric parts as integers where both sides are numeric; otherwise lexicographic.
- Place the new version so the list remains ascending oldest → newest under that ordering.
- Equal sort key: stable append after existing equals (or after last equal) — must be deterministic and tested.
- Blank Current never inserted; duplicates never inserted.

### Manual catalog

- Add / Remove / Move up / Move down / Save continue to work.
- Operator can still remove a bad auto-added build.
- Move up/down after auto-insert remains authoritative until the next insert of a *different* missing version (inserts only affect placement of the new string).

## UI

### Admin

- Checkbox + hint on Firmware catalog tab (alongside existing profile list controls).
- Opening the tab loads current setting and catalog as today.

### System Connectivity

- No new tab.
- After Refresh, show catalog-update status line when N > 0 (in existing status/errors area is fine).
- Firmware table columns unchanged.

## Architecture

```
Admin toggle (default off) ──▶ DB setting
                                    │
Refresh live ──▶ Currents ──▶ if on: version-sort insert missing ──▶ save catalog
                                    │
                                    └──▶ enrich Latest / Versions behind (existing)
```

### Modules (proposed)

| Unit | Responsibility |
|------|----------------|
| `launchpad/firmware_catalog.py` | Auto-add setting load/save; `insert_version_sorted`; maybe `grow_catalog_from_currents` |
| `launchpad/health_server.py` | Call grow during `scan_system_connectivity_live` when enabled; status N |
| `launchpad/ui/admin_view.py` | Checkbox + hint on Firmware catalog tab |
| Tests | Sort insert, duplicate no-op, setting off, N status |
| `launchpad/config.py` | **1.6.74** |

## Testing

- Version-sort: insert middle / start / end; duplicate no-op; blank skipped.
- Setting off: catalog unchanged after simulated grow path.
- Setting on: missing Currents added; save called; behind count uses updated list.
- Admin source/UI: checkbox label and setting key wired.
- Version assert **1.6.74**.

## Delivery

- Branch off `feature/contingency-groups`
- Bump to **1.6.74**
- Prefer Subagent-Driven after plan approval
- Merge back to install tip after PR

## Success criteria

1. With setting off, Refresh never mutates the catalog.
2. With setting on, unseen Currents appear in the profile catalog in version order after Refresh; Latest/behind update accordingly.
3. Admin checkbox persists across restarts; default off.
4. Status reports N when catalog grew.
5. Version shows **1.6.74** after rebuild.
