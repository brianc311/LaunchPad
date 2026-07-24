# Host / Volume Find — Host search on Volume Find page

**Date:** 2026-07-24  
**Status:** Approved for implementation (pending user review of this spec)  
**App version target:** 1.6.64  
**Depends on:** Volume Find page/API (1.6.57+), Site IP edit (1.6.59+), IBM `lshost` / FC inventory, HPE presets  
**Approach:** Same page + Volume | Host toggle (Approach 1); Host results = name + card/site + WWPNs when known (operator choice A)  
**Base branch:** `feature/contingency-groups` (tip at 1.6.63)

## Problem

Operators already use **Volume Find** to answer “which array owns this volume?” They also need “where is this **host** defined?” across the same monitor-on IBM FlashSystem / Storwize / SVC and HPE 3PAR / Primera cards. FC WWPN search is IBM/FC-centric and does not present a simple host-name → site table with Site IP.

## Goals

- Rename the page UI to **Host / Volume Find** (display title and nav labels).
- Keep path **`/volume-find`** (bookmarks and existing links continue to work). Optional redirect alias `/host-volume-find` → same page is nice-to-have, not required.
- Add a **Volume | Host** type toggle (Volume remains default).
- **Host** mode: hybrid **Find** (cache) + **Search live** (SSH), same eligibility and unlock rules as Volume Find.
- Host results: **Card**, **Site IP** (existing edit behavior), **Vendor**, **Host**, **WWPNs** (when known), **Source** (`cache` | `live`).
- Case-insensitive substring match on host name.
- Add HPE host inventory command to 3PAR/Primera presets (e.g. `showhost`) so cache/live can see HPE hosts after refresh (mirror `showvv` for volumes).
- Bump `APP_VERSION` to **1.6.64**.

## Non-goals

- Host ↔ volume LUN maps (operator choice B — out of scope).
- Combined “search both types in one shot” results mix (Approach 2).
- Separate Host Find route/page (Approach 3).
- DS8884 / XIV / NetApp / Dell host find.
- Creating, renaming, or deleting hosts on the array.
- Changing Volume Find match/eligibility behavior (except shared UI chrome rename).

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Result shape | **A** — host name + card/site + WWPNs when known |
| UI / API home | **1** — same page, Volume \| Host toggle |
| Path | Keep `/volume-find` |
| Card scope | Same as Volume Find: monitor-on SSH IBM SVC-family + HPE shell profiles |
| Query path | Hybrid cache then live (same Find / Search live buttons) |

## Behavior

### UI

- Title: **Host / Volume Find**.
- Blurb: mention both volume and host search; Find = cache; Search live = SSH when unlocked.
- Controls: type toggle **Volume** | **Host**; search input; **Find**; **Search live**; existing nav links.
- Placeholder switches with type (e.g. `Search volume name…` / `Search host name…`).
- Results table:
  - **Volume:** Card | Site IP | Vendor | Volume | Pool / CPG | Source (unchanged).
  - **Host:** Card | Site IP | Vendor | Host | WWPNs | Source.
- Empty query: prompt; do not SSH.
- Cache miss: status guides operator to **Search live**.
- Site IP edit / Anderson rename behavior unchanged (applies to both modes’ rows by `card_id`).

### Eligibility

Unchanged from Volume Find:

- `card_type` is SSH  
- Monitoring enabled  
- Profile is IBM FlashSystem / Storwize / SVC family **or** HPE 3PAR / Primera  

### Match (Host)

- Case-insensitive **substring** on host name.
- Multiple hosts / cards: return all hits, sorted by card name A–Z, then host name A–Z.

### Cache Find (Host)

- No SSH.
- IBM: host list from last FC / health command results (`lshost` / `fc_hosts` when present). WWPNs from enriched FC inventory when available (same source FC WWPN report uses — fabric-derived when present); otherwise empty string.
- HPE: parse host inventory from cached `showhost` (or agreed label) output when present after preset + refresh.

### Live Find (Host)

- Unlock required (same gate as Volume live).
- IBM: SSH `svcinfo lshost -delim :` (align with preset). WWPNs best-effort: include if live/cached fabric enrichment is already available without a second heavy pass; otherwise leave WWPNs blank rather than failing the search. Do **not** require full FC inventory for a successful host-name match.
- HPE: SSH `showhost` (or agreed equivalent on Primera).
- Per-card errors → `errors[]`; continue other cards.

### API

Extend existing find endpoint (preferred) or add a thin sibling — implementation may choose either as long as the page uses one clear contract:

**Preferred:** `GET /api/volume-find?q=<query>&mode=cache|live&type=volume|host`

- Default `type=volume` preserves current clients.
- `type=host` returns host-shaped matches.

Host match object (conceptual):

```json
{
  "card_id": 1,
  "card_name": "Woodland Hills, CA",
  "host": "10.244.66.227",
  "profile": "flashsystem_9500",
  "vendor": "ibm",
  "host_name": "woo_esx_cluster",
  "wwpns": "100000…; 100000…",
  "source": "cache"
}
```

(`host` = Site IP / card SSH host; `host_name` = array host object name.)

Volume mode response shape unchanged.

`POST /api/volume-find/card-host` unchanged.

### Presets

- Add HPE host list command to 3PAR/Primera command lists (e.g. `("Hosts - host list", "showhost")`), analogous to `showvv`.
- Existing IBM `lshost` preset remains the IBM source.

### Nav / labels

- Health Dashboard button and cross-page links that say **Volume Find** → **Host / Volume Find** (or keep short **Volume Find** only where space is tight — prefer full name on the page title and primary dashboard control).

## Architecture

| Unit | Responsibility |
|------|----------------|
| `volume_find_page` | Toggle, dual column render, Find/live wiring |
| `volume_find` helpers | Host match, IBM/HPE host parse, shared eligibility |
| `health_server` | `type=` on find API; live host SSH |
| `storage_presets` | HPE `showhost` (or equivalent) |
| `flashsystem_fc` | Reuse `parse_fc_hosts` / inventory where practical |
| Dashboard / nav | Label updates |

## Testing

- Unit: host substring match; IBM `lshost` parse; HPE `showhost` parse (fixture); eligibility unchanged.
- API: `type=volume` regression; `type=host` cache no SSH; live host matches + per-card errors.
- Page: title, toggle, host columns, placeholder switch.

## Delivery

- Branch off `feature/contingency-groups`
- Bump to **1.6.64**
- Merge back to install tip after PR

## Success criteria

1. Toggle to Host; cache Find returns matching hosts from refreshed monitor-on IBM (and HPE after refresh with new command).
2. Search live finds hosts by name and shows card + Site IP; WWPNs when known.
3. Volume mode behavior unchanged.
4. Version shows **1.6.64** after rebuild.
