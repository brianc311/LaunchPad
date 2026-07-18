# Contingency Groups — Design

**Date:** 2026-07-17  
**Status:** Implemented  
**App version target:** next bump after current (e.g. 1.6.19)

## Problem

Operators need a reusable library of site contingency host/volume/map sets (Houston, Hartford, Windsor, then more) that they can select to prefill a detail view, edit (including WWPNs and volume UIDs), export, and use as a filter on the FC WWPN report — without changing the storage array.

## Goals

- New **Contingency Groups** browser page with group picker + editable detail.
- Seed **Houston, TX**, **Hartford, CT**, and **Windsor** from operator screenshots.
- Persist groups in LaunchPad DB when unlocked; local cache when locked.
- **Save** updates in place; **Save as new** grows the library.
- FC WWPN page: select a contingency group to filter hosts/volumes/maps (and WWPN matches when present).
- Fields for host **WWPNs** and volume **UIDs** are always editable (may be empty).
- Export Excel for current or all groups.

## Non-goals

- Creating/changing hosts, volumes, or maps on the FlashSystem.
- Automatic discovery from SSH for v1 seeds (live capture from FC UI is a same-release stretch if straightforward; manual edit is required).
- Multi-user realtime collaboration beyond single LaunchPad DB.

## Data model

Setting key: `contingency_groups`  
Value: JSON array of group objects.

```json
{
  "id": "houston-tx",
  "name": "Houston, TX",
  "location": "Houston, TX",
  "storage_hint": "V5kHOU-g3v1",
  "notes": "",
  "updated_at": "2026-07-17T00:00:00Z",
  "hosts": [
    {
      "name": "pen-houesx-vm03",
      "status": "Online",
      "host_type": "Generic",
      "port_count": 2,
      "protocol": "SCSI",
      "wwpns": []
    }
  ],
  "volumes": [
    {
      "name": "HOUSTON_ESX1_DATASTORE_1",
      "capacity": "4.00 TiB",
      "pool": "",
      "uid": "",
      "protocol": "SCSI"
    }
  ],
  "maps": [
    { "volume": "HOUSTON_ESX1_DATASTORE_1", "host": "pen-houesx-vm03", "scsi_id": "0" }
  ]
}
```

| Field | Notes |
|-------|--------|
| `id` | Stable slug; unique |
| `wwpns` | List of WWPN strings; editable; empty OK |
| `uid` | Volume UID string; editable; empty OK |
| `storage_hint` | Optional LaunchPad card / array name for operator context |

### Seed groups (shipped defaults)

On first unlock with empty `contingency_groups`, seed these three (then treat as user data):

#### 1. Hartford, CT (`hartford-ct`)

- **storage_hint:** (empty or operator-filled; not in inventory by HRDC name)
- **Hosts:** `pen_hrdcesx_vm01`, `pen_hrdcesx_vm02`, `pen_hrdcesx_vm03` — Online, Generic, 2 ports, SCSI; `wwpns: []`
- **Volumes:** `HRDC_ESXI_DS01`, `HRDC_ESXI_DS02`, `HRDC_ESXI_DS03` — 4.00 TiB, pool `Hart_Pool1`, `uid: ""`
- **Maps:** each DS → all three hosts; SCSI IDs 0 / 1 / 2 respectively

#### 2. Houston, TX (`houston-tx`)

- **storage_hint:** `V5kHOU-g3v1` (from capacity inventory)
- **Hosts:** `pen-houesx-vm03`, `pen-houesx-vm04` — Online, Generic, 2 ports, SCSI; `wwpns: []`
- **Volumes:** `HOUSTON_ESX1_DATASTORE_1` … `_4` — capacity/pool blank unless known; `uid: ""`
- **Maps:** each datastore → both hosts; SCSI IDs 0 / 1 / 2 / 3 respectively

#### 3. Windsor (`windsor`)

- **storage_hint:** `v5kwin-g3v1`
- **Hosts:** `PEN_WINESX_VM01`, `PEN_WINESX_VM02`, `PEN_WINESX_VM03` — Online, Generic, 4 ports, SCSI
- **WWPNs** (from operator screenshots; editable):

| Host | WWPNs |
|------|--------|
| PEN_WINESX_VM01 | `51402EC012CFD072`, `51402EC012CFD073`, `51402EC012CFD2BE`, `51402EC012CFD2BF` |
| PEN_WINESX_VM02 | `51402EC012CFD090`, `51402EC012CFD091`, `51402EC012CFD2C4`, `51402EC012CFD2C5` |
| PEN_WINESX_VM03 | `51402EC012C90280`, `51402EC012C90281`, `51402EC012C904A4`, `51402EC012C904A5` |

- **Volumes:** `WIN_ESX_DataStore_1`–`3` — 4.00 TiB, pool `Windsor_G3_Pool0`
- **UIDs** (from screenshots; pad/store as shown):  
  `60050768128000A75800000000000000`, `…0001`, `…0002` (exact strings from GUI)
- **Maps:** each datastore → all three hosts; SCSI 0 / 1 / 2

## UI

### Contingency Groups page (`/contingency-groups`)

- Group dropdown + **New group**
- Summary fields: name, location, storage hint, notes
- Editable tables: Hosts (incl. WWPN add/remove), Volumes (incl. UID), Maps
- Actions: **Save**, **Save as new**, **Delete**, **Export Excel**, **Open in FC WWPN**
- Dashboard button + link from FC WWPN header

### FC WWPN page

- Dropdown: **Contingency group:** None | …saved groups…
- Filter: case-insensitive host name and volume/vdisk name; if WWPNs present, also match those strings in host/remote WWPN fields
- Optional stretch: **Save selection as Contingency group…** from visible/selected FC hosts + related maps

## APIs

| Method | Path | Behavior |
|--------|------|----------|
| GET | `/api/contingency-groups` | `{ groups, persisted }` |
| POST | `/api/contingency-groups` | `{ groups }` replace-all; or `{ group }` upsert; or `{ delete_id }` |
| GET | `/api/contingency-groups-export?id=` | XLSX (omit `id` = all groups) |

Seed merge: if backend available and stored value empty/missing, write seeds once.

## Excel

Workbook sheets: **Summary**, **Hosts**, **Volumes**, **Maps** (WWPNs as semicolon-separated column; UID column on Volumes).

## Edge cases

- Locked LaunchPad: localStorage cache; unlock merges/saves like snapshot overrides.
- Empty WWPN/UID allowed.
- Duplicate display names OK; `id` must be unique (Save as new generates new id).
- Footer/docs: reference library only — LaunchPad does not modify the array.
- Version bump on ship.

## Files to touch (implementation)

- `launchpad/contingency_groups.py` — page HTML + seeds helpers (or split seeds module)
- `launchpad/contingency_groups_export.py` — Excel
- `launchpad/health_server.py` — routes + settings CRUD
- `launchpad/fc_wwpn_report.py` — group filter dropdown
- `launchpad/ui/dashboard_view.py` — open Contingency Groups
- `launchpad/config.py` — version bump
- Tests for normalize/seed/filter helpers

## Manual test plan

1. Unlock → open Contingency Groups → see Houston, Hartford, Windsor.
2. Edit a WWPN/UID → Save → reload → persists.
3. Save as new → new group appears in picker and FC filter.
4. FC WWPN: select Houston → only matching hosts/volumes/maps (when live data present).
5. Export Excel opens with four sheets.
6. Locked edits stay local; unlock persists.

## Out of scope / later

- Click-calendar style capture from IBM GUI screenshots.
- Auto-link to SSH refresh of a specific card.
- Host cluster ID/name fields (empty in source GUI).
