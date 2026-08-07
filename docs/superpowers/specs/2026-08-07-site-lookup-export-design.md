# Site Lookup export — Design

**Date:** 2026-08-07  
**Status:** Approved  
**App version target:** next patch after tip (1.6.137+)  
**Depends on:** Site Lookup payload (`/api/site-lookup/cache`, `/api/site-lookup/refresh`); existing HealthServer XLSX/CSV export patterns (Hosts & Volumes)  
**Approach:** Approach B — server-side export API; Excel via openpyxl; CSV as zip of section files.

## Problem

Site Lookup shows live/cached inventory (Hosts, Volumes, CPGs/Pools, optional Consistency Groups) but has no download path. Operators need Excel and CSV exports of the currently looked-up site, plus an optional Excel sheet for offline/degraded hosts and volumes.

## Goals

- Add **Export Excel** and **Export CSV** controls on Site Lookup.
- Excel workbook: one sheet per inventory section present for the site.
- Optional checkbox **Include Offline sheet** (Excel only): add a combined **Offline** sheet of offline/degraded hosts and volumes.
- Export the **current looked-up inventory** (cache or last Live Refresh), not a new SSH pull.
- Match Hosts & Volumes Health export UX (buttons enable when data is available; download via health API).

## Non-goals (v1)

- Multi-site bulk export from Site Lookup.
- Refresh-on-export (no automatic Live Refresh when exporting).
- PDF or other formats.
- Separate Offline Hosts / Offline Volumes sheets (v1 uses one combined Offline sheet).
- Offline option on CSV.

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Normal export | CSV (same dual-button pattern as Hosts & Volumes) |
| Offline Excel option | One combined **Offline** sheet (hosts + volumes that are offline/degraded) |
| Default Excel sheets | One sheet per inventory tab: Hosts, Volumes, CPGs/Pools, Consistency Groups when available |

## UI

Place next to **Look Up** / **Live Refresh**:

- Button: **Export Excel**
- Button: **Export CSV**
- Checkbox: **Include Offline sheet** (applies to Excel only; ignored for CSV)

Buttons are **disabled** until a site payload is loaded (after Look Up / cache load / Live Refresh). Checkbox may stay enabled whenever Excel is usable; default **unchecked**.

## Excel workbook

Always (when the corresponding data exists in the payload):

| Sheet name | Source |
|------------|--------|
| Hosts | `payload.hosts` |
| Volumes | `payload.volumes` |
| CPGs or Pools | `payload.pools` — sheet title **CPGs** for HPE profiles, **Pools** otherwise |
| Consistency Groups | `payload.consistency_groups` — omit sheet when profile does not support CGs / list empty and unavailable |

When **Include Offline sheet** is checked, append:

| Sheet name | Contents |
|------------|----------|
| Offline | Combined rows for hosts and volumes whose status is offline or degraded (same rule as Hosts & Volumes Health: case-insensitive status contains `offline` or `degraded`). Include a Type column (`host` / `volume`) plus the usual identifying columns. If no rows match, still emit the sheet with headers only. |

## CSV

- Zip of CSV files, one per section that would appear as an Excel sheet (**excluding** Offline).
- Filenames e.g. `Hosts.csv`, `Volumes.csv`, `CPGs.csv` or `Pools.csv`, `Consistency_Groups.csv` when present.
- No Offline file / no checkbox effect.

## Data & API

- **Source of truth:** current Site Lookup payload for the selected card (in-memory after Look Up / Live Refresh). Client sends that payload (or card_id + server re-reads last offline/cache snapshot — prefer **POST body with current payload** so export matches what the operator sees, including Live Refresh results not yet persisted elsewhere).
- Recommended endpoints (names may align with existing style):
  - `POST /api/site-lookup/export` with JSON `{ format: "xlsx"|"csv", include_offline: bool, payload: <current payload> }`
  - Response: file download (`application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` or `application/zip`)
- Pure helpers in a dedicated module (e.g. `site_lookup_export.py`) for building workbook/zip bytes from a normalized payload.
- Reuse `status_is_offline_or_degraded` from `host_volume_health` for Offline filtering.

## Errors

- No payload / empty selection → buttons disabled; if called anyway, `400` with clear message.
- Invalid format → `400`.
- Export failure → `500` with short error; UI shows status text like other pages.

## Testing

- Unit tests: sheet names (HPE CPGs vs IBM Pools); Offline filter; CSV zip membership; CG sheet omitted when unavailable.
- Page contract: Export Excel / Export CSV / Include Offline sheet markers present; export disabled until payload loaded.

## Out of scope follow-ups

- Multi-site export; refresh-on-export; separate Offline Hosts / Offline Volumes sheets.
