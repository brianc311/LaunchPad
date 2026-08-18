# Site Lookup — IBM snapshot Policy tab

**Date:** 2026-08-18  
**Status:** Approved for implementation (pending user review of this file)  
**App version target:** 1.6.181  
**Extends:** `docs/superpowers/specs/2026-08-06-site-lookup-live-design.md`  
**Depends on:** Site Lookup live page (`/site-lookup`); IBM `lssnapshotpolicy` (Storage Virtualize 8.5.1+)  
**Approach:** One extra SSH command on IBM Live Refresh. Same payload as hosts/volumes. Policy tab + header count. No create/edit.

## Problem

Site Lookup shows Hosts, Volumes, Consistency Groups, and Pools for a selected array. Operators cannot tell from that page whether the array already has an IBM snapshot policy (for example `esx_snap`), or how often it runs and how long snapshots are kept. That check today means leaving Site Lookup for ESX-snap Policy or the array GUI.

## Goals

- IBM FlashSystem / Storwize / SVC Site Lookup shows a **Policy** tab and a header **Policies** count.
- Tab lists every snapshot policy from `lssnapshotpolicy`: **name**, **schedule**, **retention**.
- Live Refresh collects policies with the rest of that site’s inventory (one extra SSH command).
- Empty array shows **0** and **No snapshot policies on this array**.
- Firmware too old or command failure does not fail Refresh; policies stay empty with a short explanation.
- Excel/CSV export includes a **Policies** sheet when the tab exists.
- Bump `APP_VERSION` to **1.6.181**.

## Non-goals

- Creating, editing, or deleting snapshot policies (stays on ESX-snap Policy).
- Volume groups or which volumes use a policy.
- FlashCopy consistency-group schedules / Snapcopy Summary Policy column.
- Extra SSH on HPE or DS8884.
- A separate policies API or a second fetch when the tab is opened.

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Kind | IBM snapshot policies (`lssnapshotpolicy`), not FlashCopy CG schedules |
| Columns | Name, schedule (`every {interval} {unit}`), retention (`keep {n} days`) |
| Header | **Policies** count after Consistency Groups, before Pools |
| Tab | **Policy**, same order as the header |
| Non-IBM | Hide tab and header count (same pattern as Consistency Groups) |
| Collect | Fold into Live Refresh (one extra command) |
| Edit | Read-only |

## Visibility

Use the **same predicates as Consistency Groups**:

- **Page tab + header count:** show when `device_profile` contains `flashsystem`, `storwize`, or `svc` (case-insensitive), matching `profileSupportsConsistencyGroups`.
- **SSH collect:** run `lssnapshotpolicy` only when `card.device_profile in SVC_PROFILES`, matching `lsconsistgrp` in `refresh_site_lookup`.
- HPE and DS: never run the command; never show the tab or Policies count.

Old cached payloads with no `policies` field: IBM still shows the tab and **0 Policies** until the next successful Live Refresh fills the list.

## Data flow

On IBM Live Refresh, after the existing consistency-group command:

1. `svcinfo lssnapshotpolicy -delim :`
2. If that output is empty, `svcinfo lssnapshotpolicy`

Parse table rows (and key-value fallback if the output is a single object). Skip rows with no **name**.

| Source field (case-insensitive, `_get` style) | Payload |
|-----------------------------------------------|---------|
| `name` | `name` |
| `backup_interval` (fallback `backupinterval`) | used in `schedule` |
| `backup_unit` (fallback `backupunit`) | used in `schedule` |
| `retention_days` (fallback `retentiondays`, `retention`) | used in `retention` |

Display strings (shared by the page and export; format in Python):

- **schedule:** `every {interval} {unit}` using the IBM unit token as returned (typically `day`). Missing interval or unit → `—`.
- **retention:** `keep {n} days` when `n` is a number. Missing → `—`. Always the word `days` (including `keep 1 days`).

Do **not** call `collect_esx_snap_inventory` (that also runs `lsvolumegroup` and `lsvdisk`). Parser lives in `site_lookup_data.py`.

### Payload

`_build_payload` / live / cache / offline snapshot include:

```text
policies: [{ "name", "schedule", "retention" }, ...]
stats.policies: len(policies)
policies_error: "" or explanation
```

`payload_from_live` and cache builders take `policies` and `policies_error` (default `[]` / `""`). Offline `normalize_snapshot` persists `policies` and `policies_error` so a later cache read still has them.

The page sets `snapshot_policies_available` the same way it sets `consistency_groups_available` (IBM profile helper). Export includes the Policies sheet when that flag is true **or** `policies` is a non-empty list — same helper shape as `consistency_groups_sheet_wanted`.

## Errors

- Command output contains `not a valid command` (case-insensitive) → `policies = []`, `policies_error` = `Snapshot policies need IBM Storage Virtualize 8.5.1 or later`. Refresh **succeeds**.
- SSH/exception → `policies = []`, `policies_error` = that error text (may include the firmware sentence). Refresh **succeeds**. Hosts, volumes, CGs, and pools are unchanged.
- Empty successful list → `policies = []`, `policies_error` = `""`. Tab copy: **No snapshot policies on this array**.

Do not put policy errors into the existing HPE `warning` field.

## Page

Path stays `/site-lookup`. Read-only.

**Header stats (IBM):** Hosts · Volumes · Consistency Groups · **Policies** · Pools/CPGs.

**Tabs (IBM):** Hosts · Volumes · Consistency Groups · **Policy** · Pools/CPGs.

Table columns: **Name** · **Schedule** · **Retention**. Same table styling as Hosts.

Empty: `emptyMessage` with **No snapshot policies on this array**, or `policies_error` when set (firmware / command failure).

The existing row filter also matches policy **name**. Placeholder may stay “Filter host or volume names…” (no required copy change).

## Export

When the Policies sheet is wanted:

- Excel sheet title **Policies**.
- CSV zip member **Policies.csv**.
- Headers: Name, Schedule, Retention.
- Rows from `payload["policies"]`.

HPE/DS exports omit the sheet unless a non-empty `policies` list is present (should not happen).

## Architecture

| Unit | Role |
|------|------|
| `launchpad/site_lookup_data.py` | Parse `lssnapshotpolicy`; shape rows; include `policies` / `stats.policies` / `policies_error` in payloads |
| `launchpad/site_lookup_offline.py` | Persist `policies` and `policies_error` on snapshots |
| `launchpad/health_server.py` | IBM Live Refresh: extra `lssnapshotpolicy`; pass into `payload_from_live` |
| `launchpad/site_lookup.py` | Header count, Policy tab, table, empty/error copy, filter |
| `launchpad/site_lookup_export.py` | Policies sheet / CSV member |
| `launchpad/config.py` | **1.6.181** |

## Testing

- Parse sample `id:name:backup_unit:backup_interval:retention_days` → name `other-policy`, schedule `every 1 day`, retention `keep 7 days`.
- Missing schedule/retention fields → `—`; nameless row skipped.
- IBM page HTML/JS: Policy tab, Policies stat, empty copy; HPE has no Policy tab and no Policies stat.
- `refresh_site_lookup` (mocked SSH): IBM payload includes parsed `policies`; command failure still returns hosts and empty `policies` plus `policies_error`.
- Offline snapshot round-trip keeps `policies`.
- Excel/CSV: IBM payload gets Policies sheet; HPE without policies does not.
- Version pins **1.6.181**.

## Out of scope follow-ups

- Volume group names on the Policy tab.
- Pluralizing `day` / `days` from the IBM unit token.
- Opening ESX-snap Policy from this tab.
