# Firmware Catalog Recommended Seed (IBM screenshots + HPE CSV)

**Date:** 2026-07-29  
**Status:** Approved for implementation  
**App version target:** 1.6.75  
**Depends on:** Firmware catalog + auto-grow (1.6.73–1.6.74), `SVC_PROFILES`, `HPE_SHELL_PROFILES`  
**Approach:** Built-in seed module + Admin “Load recommended catalog seed” merge button (Approach 1)  
**Base branch:** `feature/contingency-groups`

## Problem

Operators must hand-enter IBM Available Update Versions and HPE Storage OS levels into per-profile catalogs. Estate screenshots and an HPE inventory CSV already list the versions needed for Latest / Versions behind.

## Goals

- Ship a **built-in recommended seed** derived from the Jul 2026 IBM Update System screenshots (15 sites) and the HPE `hw-systems` CSV.
- Admin button **Load recommended catalog seed** version-sort–merges seed into existing DB catalogs (insert missing only; never delete operator entries).
- Apply the same FlashSystem union to every `SVC_PROFILES` key; apply normalized HPE base to every `HPE_SHELL_PROFILES` key.
- Normalize live HPE Current the same way as the seed (`strip +P…` patches) before catalog match / auto-grow insert.
- Bump `APP_VERSION` to **1.6.75**.

## Non-goals (this pass)

- IBM support URL on the Firmware tab (follow-up).
- License Key tab / collectors (follow-up).
- Per-site / per-card catalogs (remain per `device_profile`).
- DS8884 seed (no source data in this pass).
- Auto-download from IBM/HPE portals.
- Replacing or re-sorting the entire catalog on seed load (merge-insert only).

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Catalog key | Shared per device profile (not per site) |
| Delivery | Built-in seed + Admin merge button |
| FlashSystem contents | Full union: Currents + Latest PTF + Available Updates + older tracks |
| HPE contents | Normalized base `3.3.1.648 (MU5)` (strip `+P…`) |
| HPE live match | Same normalization on Current |
| Implementation | Approach 1 — static seed module + Admin button |

## Seed contents

### FlashSystem / SVC (same list for every profile in `SVC_PROFILES`)

Version-sorted union from operator screenshots (normalized release strings, no build suffix):

```
7.8.1.8
7.8.1.16
8.2.1.11
8.4.0.20
8.6.0.2
8.6.0.7
8.6.0.9
8.6.0.11
8.6.1.0
8.6.2.1
8.6.3.0
8.7.0.3
8.7.0.13
```

Source notes (for maintainers): Available Updates commonly `8.6.1.0`, `8.6.2.1`, `8.6.3.0`, `8.7.0.13`; Latest PTF `8.6.0.11`; Currents included `8.6.0.2`–`8.6.0.9`, `8.7.0.3`; older tracks `7.8.1.8`→`7.8.1.16`, `8.2.1.11`→`8.4.0.20`.

### HPE 3PAR / Primera (same base for every profile in `HPE_SHELL_PROFILES`)

From CSV `HPE Storage OS` column, normalized:

```
3.3.1.648 (MU5)
```

Normalization rule: take the substring before `+` (patch list); trim; keep ` (MU5)` when present. Example: `3.3.1.648 (MU5)+P126,P132,...` → `3.3.1.648 (MU5)`.

## Behavior

### Admin — Load recommended catalog seed

1. Load current catalog from DB.
2. Build seed via `recommended_firmware_seed()` (dict profile → version list).
3. For each seed profile/version: `insert_version_sorted` into that profile’s list (reuse auto-grow helper).
4. If any inserts → `save_firmware_catalog`.
5. Status: `Seed merged: N new version(s).` or `Seed already up to date.` when N=0.
6. Refresh on-screen profile list from saved catalog.

Hint under button: *Merges built-in IBM/HPE release lists into each profile; does not remove your entries.*

### Live HPE Current normalization

When collecting/enriching HPE firmware Current (and when auto-grow inserts HPE Current), apply the same `normalize_hpe_firmware_version` rule so catalog match works against the seeded base.

FlashSystem Current continues to use existing SVC build-suffix normalization.

## Architecture

```
firmware_catalog_seed.py ──▶ recommended_firmware_seed()
                                    │
Admin button ──▶ merge_seed_into_catalog(db_catalog, seed)
                                    │
                                    ▼
                         save_firmware_catalog (if N>0)
```

### Modules (proposed)

| Unit | Responsibility |
|------|----------------|
| `launchpad/firmware_catalog_seed.py` | Static lists; `recommended_firmware_seed()` |
| `launchpad/firmware_catalog.py` | `normalize_hpe_firmware_version`; `merge_seed_into_catalog` |
| `launchpad/system_connectivity.py` / scan path | Apply HPE normalize on Current |
| `launchpad/ui/admin_view.py` | Seed button + status |
| `launchpad/config.py` | **1.6.75** |
| Tests | Seed membership, merge, HPE normalize, Admin strings, version |

## Testing

- Seed maps every `SVC_PROFILES` / `HPE_SHELL_PROFILES` key; FlashSystem list contains the documented union; HPE is `3.3.1.648 (MU5)`.
- Merge inserts missing only; second merge N=0; never drops existing unrelated versions.
- `normalize_hpe_firmware_version` strips `+P…`.
- Admin source asserts button label + hint.
- Version **1.6.75**.

## Delivery

- Branch off `feature/contingency-groups`
- Bump to **1.6.75**
- Prefer Subagent-Driven after plan approval
- Merge back to install tip after PR

## Success criteria

1. Admin **Load recommended catalog seed** merges the built-in IBM/HPE lists without removing existing entries.
2. FlashSystem profiles share the documented union; HPE profiles share `3.3.1.648 (MU5)`.
3. HPE live Current normalized the same way matches the seed for Versions behind when appropriate.
4. Version shows **1.6.75** after rebuild.
5. IBM link and License Key remain deferred.
