# LUN Builder + Consistency Groups — Find Search + UI Rename

**Date:** 2026-07-23  
**Status:** Approved for implementation  
**App version target:** 1.6.54  
**Depends on:** LUN Builder page; Contingency Groups page (planning library)  
**Approach:** Client-only Find + row filter; cross-build/group switch on miss (Approach 1)  
**Base branch:** `feature/contingency-groups` (tip at 1.6.53)

## Problem

Operators need to locate hosts, volumes, and purposes inside large LUN Builder builds, and locate groups / hosts / volumes inside the Contingency Groups planning library, without scrolling every table. The library page is also labeled **Contingency Groups**, which operators want shown as **Consistency Groups** (UI only — IBM FlashCopy “consistency group” remains a different concept).

## Goals

- **LUN Builder Find:** search box for volume names, purpose, and host names; filter matching rows in the open build; if none, switch to another loaded build that matches.
- **Consistency Groups Find:** search box for group / host / volume names; prefer group-name match, else search inside groups and switch + filter.
- **UI rename:** operator-visible **Contingency Groups → Consistency Groups** (titles, headings, nav, aria-labels, footer, status copy).
- Keep URLs, APIs, Python modules, and persisted IDs as `contingency-groups` / contingency_* so existing bookmarks and data stay valid.

## Non-goals (v1)

- Renaming FlashCopy consistency-group features or IBM `consistgrp` objects.
- New find APIs (pages already load full catalogs client-side).
- Fixing bad LUN volume names (e.g. spaced tokens); Preview warnings remain correct.
- Changing Save / Preview / Run Create / Sync behavior beyond status text for Find.

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Rename | **A** — UI label **Consistency Groups**; paths stay `contingency-groups` |
| LUN Builder Find | **C** — filter current Hosts/LUNs; if none, offer/switch to another build |
| Consistency Groups Find | **C** — group name first; else search inside groups and switch + filter |
| Implementation | **1** — client-only (no new find API) |

## Behavior

### UI rename (Consistency Groups)

Update operator-visible strings only, including at least:

- Page `<title>`, `<h1>`, lede (wording may keep “contingency” in descriptive prose only where it means disaster-recovery planning — prefer “planning” / “site library” if rewriting the lede).
- Nav / cross-links from Health Dashboard, FC WWPN, LUN Builder, etc. that say “Contingency Groups”.
- `aria-label` on the group picker and related controls.
- Footer version line.

Do **not** change:

- Route `/contingency-groups`
- API `/api/contingency-groups*`
- Module/file names (`contingency_groups.py`, `contingency_groups_data.py`, …)
- Seed / persisted group ids (`hartford-ct`, etc.)

### LUN Builder Find

**UI:** Search input + **Find** button near the Build picker (same pattern as FC WWPN Find). Placeholder: `Search volume, purpose, or host…`. Enter runs Find.

**Match fields (case-insensitive substring):**

- Host rows: host / LPAR name fields used in the Hosts table.
- LUN rows: `purpose`, `host_names`, and **expanded volume names** (same strings shown in the Volume names column).

**Outcomes:**

| Outcome | Behavior |
|---------|----------|
| Empty query | Clear row filter; show all hosts/LUNs in the open build |
| Matches in open build | Hide non-matching host and LUN rows; status `Showing N matching row(s)` (or equivalent) |
| No match in open build; matches elsewhere | Select first matching build by name A–Z; apply the same row filter; status notes extras if multiple builds match |
| No match anywhere | Status `No matching hosts, volumes, or purposes` |

Filter is view-only; it does not change persisted data or enable/disable Run Create.

### Consistency Groups Find

**UI:** Search input + **Find** near the Group picker. Placeholder: `Search group, host, or volume…`. Enter runs Find.

**Match order:**

1. **Group name / location** across all loaded groups — on hit, select first match by name A–Z; note extras; clear inner-table filter (show full selected group).
2. Else **inside groups:** host `name` / WWPNs, volume `name`, map volume/host fields — select first matching group A–Z; **filter** Hosts / Volumes / Maps tables to matching rows; note extras.
3. Else status `No matching groups, hosts, or volumes`.

Empty query clears the inner-table filter and leaves the current group selected.

Wizard tables (source/target snap wizard) are out of scope for v1 filtering unless they share the same render path with negligible cost; primary target is the main Hosts / Volumes / Maps sections.

## Architecture

- Small pure helpers (Python and/or mirrored JS logic covered by tests): normalize query; `build_matches` / `group_matches`; `filter_host_indices` / `filter_lun_indices` / `filter_group_row_indices`; pick first by name A–Z.
- Wire helpers into existing page JS in `lun_builder.py` and `contingency_groups.py` (inline scripts), plus string updates across nav HTML.
- No new HTTP routes for find.

## Testing

- Unit tests for match/filter helpers (LUN Builder and Consistency Groups).
- Page/HTML assertions: “Consistency Groups” in title/h1/nav; `/contingency-groups` path unchanged.
- Smoke: empty query clears filters; multi-match picks A–Z first.

## Delivery

- Branch off `feature/contingency-groups`.
- Bump `APP_VERSION` to **1.6.54**.
- Merge back to install tip after PR (same workflow as FC WWPN search).

## Success criteria

1. LUN Builder Find filters or switches builds as specified; miss message is clear.
2. Consistency Groups Find selects by group name or switches + filters inner tables as specified.
3. Operators see **Consistency Groups** in UI; bookmarks to `/contingency-groups` still work.
4. Version shows **1.6.54** after rebuild.
