# Volume Find — Cross-Array Volume Search (IBM + HPE)

**Date:** 2026-07-23  
**Status:** Approved for implementation  
**App version target:** 1.6.57  
**Depends on:** Health Cards (SSH, monitor), storage presets, existing `lsvdisk` parsing  
**Approach:** Dedicated Volume Find page + hybrid cache-then-live API (Approach 1)  
**Base branch:** `feature/contingency-groups` (tip at 1.6.56)

## Problem

Operators need to answer “which array is this volume on?” across registered IBM FlashSystem / Storwize / SVC and HPE 3PAR / Primera systems. LUN Builder Find only searches planning builds. FC WWPN Find is IBM/FC-centric and does not cover HPE volume inventory. HPE presets today do not include a volume list command, so cached Health Card data often has no 3PAR volume names.

## Goals

- New **Volume Find** browser page (`/volume-find`) to search volume names across **monitor-enabled** SSH storage cards.
- **Hybrid find:** search **cache first**; **Search live** (or after cache miss guidance) SSHs eligible IBM and HPE cards.
- Results show **card/site**, **vendor/profile**, **volume name**, **pool/CPG** (when known), and **source** (`cache` | `live`).
- Add HPE volume inventory command (e.g. `showvv`) to 3PAR/Primera presets so cache and live can see HPE volumes after refresh.
- Nav links from Health Dashboard and related browser pages.

## Non-goals (v1)

- Searching LUN Builder templates/builds or Consistency Groups planning rows (existing Find stays separate).
- DS8884 / XIV volume find.
- Creating, mapping, or deleting volumes.
- Full HPE host/VV set maps beyond name + pool/CPG columns available from the inventory command.
- Parallel “search everything including monitoring-off cards.”

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Query path | **C** — hybrid: cache first, then live SSH / explicit Search live |
| UI home | **A** — dedicated Volume Find page |
| Card scope | **A** — monitor-enabled SSH cards only (IBM + HPE profiles) |
| Implementation | **1** — page + hybrid API; add HPE `showvv` (or equivalent) to presets |

## Behavior

### UI

- Path: `/volume-find`
- Search input (placeholder e.g. `Search volume name…`), **Find**, **Search live**, status (`aria-live`)
- Results table columns: Card / site, Vendor / profile, Volume, Pool / CPG, Source
- Empty query: prompt to enter a name; do not SSH
- Cache miss: status guides operator to **Search live**
- Live: show progress/status while cards are queried; list per-card errors without aborting the whole search

### Eligibility

Include a card when all are true:

- `card_type` is SSH
- Monitoring is enabled
- Device profile is IBM FlashSystem / Storwize / SVC family **or** HPE 3PAR / Primera

### Match

- Case-insensitive **substring** on volume name
- Multiple volumes / cards: return all hits, sorted by card name A–Z, then volume name A–Z

### Cache Find

- Read last known command results / parsed volume lists on eligible cards
- IBM: `lsvdisk` (and FC mapping volume names if already available on the card)
- HPE: volume inventory output when present (after preset + refresh)
- No SSH on Find

### Live Find

- SSH each eligible card:
  - IBM: `svcinfo lsvdisk -delim :` (align with existing inventory/sync command)
  - HPE: `showvv` (or agreed equivalent on Primera)
- Parse volume name and pool/CPG when columns exist
- Unlock required for live SSH (same gate as other SSH-mutating/read-live ops that require unlock)
- Card failures → `errors[]` entry; continue other cards

### API

`GET /api/volume-find?q=<query>&mode=cache|live`

Response shape (conceptual):

```json
{
  "matches": [
    {
      "card_id": 1,
      "card_name": "Hartford, CT",
      "profile": "flashsystem_7200",
      "vendor": "ibm",
      "volume": "pconsps_archvg_1",
      "pool_or_cpg": "…",
      "source": "cache"
    }
  ],
  "errors": [
    { "card_id": 2, "card_name": "…", "error": "SSH timeout" }
  ]
}
```

## Architecture

| Unit | Responsibility |
|------|----------------|
| `volume_find` page HTML/JS | UI, Find vs Search live, render results |
| `volume_find` helpers | Match, eligibility, parse IBM/HPE volume rows from text |
| `health_server` | Route page + `GET /api/volume-find`; live SSH orchestration |
| `storage_presets` | Add HPE volume inventory command to 3PAR/Primera lists |
| Dashboard / nav | Open Volume Find URL |

## Testing

- Unit: eligibility, substring match, IBM `lsvdisk` name parse, HPE `showvv` parse (fixture text)
- API: cache mode no SSH; live mode collects matches + per-card errors
- Page: path, Find / Search live controls, result columns

## Delivery

- Branch off `feature/contingency-groups`
- Bump `APP_VERSION` to **1.6.57**
- Merge back to install tip after PR

## Success criteria

1. From Volume Find, cache Find returns volumes from refreshed monitor-on IBM (and HPE after refresh with new command).
2. Search live queries eligible IBM + HPE cards and reports which card owns matching volumes.
3. Monitoring-off and non-storage cards are skipped.
4. Version shows **1.6.57** after rebuild.
