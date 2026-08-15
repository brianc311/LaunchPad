# Hosts & Volumes, Volume Find, and Capacity Report live progress

**Date:** 2026-08-14  
**Status:** Approved for implementation  
**App version target:** 1.6.171  
**Depends on:** Storage Inventory live progress (1.6.169) — same bar look, poll, and hide-after-403 rules  
**Approach:** Poll server progress during one-shot live/find requests; drive Capacity Refresh On Sites from the existing sequential browser loop; show the bar during Capacity card-list load without fake N/M  
**Base branch:** `main` (1.6.170)

## Problem

Hosts & Volumes **Refresh live** only shows **Scanning live…**. Host / Volume Find **Find** / **Search live** only show **Searching cache…** / **Searching live…**. Capacity **Refresh On Sites** already prints `Refreshing Name (3/36)...` as text with no bar. **Loading servers from LaunchPad…** has no bar. Operators cannot tell how far a fleet pass has gone.

## Goals

- Same orange progress bar and **`done / total arrays · current site`** status as Storage Inventory on:
  - Hosts & Volumes **Refresh live**
  - Host / Volume Find **Find** and **Search live**
  - Capacity **Refresh On Sites**
- Capacity **Loading servers** shows the bar with **Loading servers…** until the card list is rendered, then hides (no fake per-site count).
- Hide on finish, error, and 403 (unlock). Late polls must not resurrect the bar.
- Bump `APP_VERSION` to **1.6.171**.

## Non-goals

- Changing Storage Inventory progress behavior or URL.
- Changing Excel/CSV export, Find match rules, Capacity formulas, or Monitor toggles.
- Per-array live HTTP from the Hosts & Volumes or Volume Find browser (those stay one request).
- Fake N/M during Capacity card-list load.
- Progress on other pages (System Connectivity, FlashCopy CGs, etc.).

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Capacity when | Refresh On Sites **and** Loading servers |
| Volume Find when | Find **and** Search live |
| Implementation | Approach 1 — SI-style poll for one-shot APIs; client bar for Capacity sequential refresh and loadCards |
| Label | `{done} / {total} arrays · {current}` while a card walk runs |

## Behavior

### Shared bar UI

Copy Storage Inventory: wrap + inner bar, accent fill, `hidden` until a run starts, max-width ~420px, under the hero actions (Capacity: next to the existing status line). Poll ~400ms where a server snapshot exists. `progressActive` false in `hideProgress`; ignore in-flight polls after hide.

403 / unlock: hide the bar, then show unlock text (no bar).

### Hosts & Volumes Health

On **Refresh live**: disable button, show bar at 0, start poll of `GET /api/host-volume-health/progress` (no unlock), in parallel `GET /api/host-volume-health/live` (unlock required). Scan loop: eligible cards first, `begin(len)`, `start_card(name)` / `finish_card()` per card, `end()` in `finally`. Site filter `card_id` → total 1. Snapshot shape: `{running, done, total, current}` (idle: running false, done 0, total 0, current `""`).

### Host / Volume Find

On **Find** (`mode=cache`) and **Search live** (`mode=live`): same bar. Poll `GET /api/volume-find/progress` (no unlock) while `GET /api/volume-find?...` runs. Live still 403 if locked. The card walk inside `find_volumes` publishes the same begin/start/finish/end. Cache mode still walks eligible cards (fast); still real N/M.

### Capacity Report

**Refresh On Sites:** keep sequential `POST /api/refresh/{id}`. Before each site, set bar to `(index) / length` or `(index+1) / length` with current name — match Storage Inventory **as the site starts** (`start_card` semantics: current name, done = finished count). After the last site, hide bar, status **Refresh complete.**

**Loading servers (`loadCards`):** if not already in Refresh On Sites / export, show bar, status **Loading servers…**, width 0% (or indeterminate fill at 0). On success or failure, hide bar (failure still shows **Could not load servers**). Do not invent a site total for this fetch.

### Storage Inventory

Unchanged (`GET /api/storage-inventory/progress`).

## Architecture

| Unit | Responsibility |
|------|----------------|
| Reuse `StorageInventoryProgress` (or same-shaped helper) | Thread-safe snapshot; **separate instances** on HealthServer so SI / HV / Find do not share one bar |
| `launchpad/health_server.py` | Publish during `scan_host_volume_health_live` and `find_volumes`; `GET /api/host-volume-health/progress` and `GET /api/volume-find/progress` |
| `launchpad/host_volume_health_page.py` | Bar + poll + hide guards |
| `launchpad/volume_find_page.py` | Bar + poll on Find and Search live |
| `launchpad/capacity_report.py` | Bar from sequential refresh loop; bar during `loadCards` |
| Tests + version pins | Progress JSON, page markers, Capacity loop labels; **1.6.171** |

Progress GET must not require unlock. Live/find still do.

## Testing

- HV and Volume Find progress idle snapshot and counts increment per card.
- Progress routes exist and are not unlock-gated (source or API).
- Page markers: progress wrap/bar ids, poll path, `progressActive` hide guard.
- Capacity script contains bar updates in `refreshAllSequential` and `loadCards`.
- Version pins `1.6.171`.
