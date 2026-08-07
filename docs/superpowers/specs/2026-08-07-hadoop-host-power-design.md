# Hadoop Host Power — Design

**Date:** 2026-08-07  
**Status:** Approved  
**App version target:** next patch after tip (1.6.131+)  
**Depends on:** Health Dashboard / `health_server.py` page routing; SSH cards + Paramiko runners; `storage_presets.py` device profiles and editable card commands; Contingency / FlashCopy Preview → Confirm → Run pattern  
**Approach:** Native LaunchPad SSH only (Approach A) — new `hadoop_linux` profile with Linux + sample Hadoop health/capacity presets, Host Power page for bulk stop→shutdown, plus per-card dashboard shortcut. No Ansible / `plp5-dz5-nw`.

## Problem

Operators need to manage Hadoop Linux hosts the same way they manage storage arrays in LaunchPad: register SSH cards, see health and capacity on refresh, and safely run an ordered power-off sequence (stop Hadoop services, then OS shutdown) from the app — without using the Ansible control host.

Today LaunchPad has **General Linux / SSH** and Vultr VPS Linux presets for metrics, but no Hadoop profile, no tagged power-off command subset, and no Preview → Confirm → Run UI for multi-host OS shutdown.

## Goals

- Add device profile **`hadoop_linux`** labeled **Hadoop / Linux SSH**.
- Ship editable card command presets:
  - OS health (uptime, failed units, CPU, memory)
  - OS capacity (`df` root + filesystems)
  - Sample Hadoop CLI health/status defaults (HDFS/YARN-style; operator-editable)
  - Ordered **Power -** labeled stop-Hadoop-then-shutdown commands
- Operators may also place these cards in a separate **category** for dashboard grouping (category is existing Admin UX; not new LaunchPad code).
- New **Host Power** HealthServer page (`/host-power`): list `hadoop_linux` cards, multi-select, Preview → Confirm → Run over native SSH.
- Dashboard: entry button to Host Power; Hadoop cards get a **Power off…** shortcut that opens the page with that `card_id` pre-selected.
- Mutating runs require `confirm: true`; health refresh remains read-only.
- On per-host stop failure: **do not** run OS shutdown for that host; continue other selected hosts; summarize ok/fail.

## Non-goals (v1)

- Ansible Pad / control host `plp5-dz5-nw` for this flow.
- Cluster-aware drain / decommission beyond the operator’s editable command list.
- Capacity Report Excel / vendor pool toggles parity for Hadoop (dashboard card metrics only in v1).
- Automatic discovery of Hadoop nodes.
- Parallelism guarantees beyond a simple sequential (or small capped parallel) run; sequential is acceptable.
- Password prompting for `sudo` at run time (hosts must allow non-interactive sudo for power commands, or commands must not need a password).

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Delivery path | Native LaunchPad SSH only (not Ansible) |
| Power sequence | Ordered: stop Hadoop, then OS shutdown |
| Commands | Editable on the card, same model as storage arrays |
| UI | Host Power page (bulk) **and** per-card dashboard shortcut |
| Card identity | New `hadoop_linux` profile; operator also uses a separate category |
| Health / capacity | OS metrics **plus** sample Hadoop CLI defaults |
| Confirm gate | Required for Run (Preview → Confirm → Run) |
| Stop failure | Abort shutdown for that host only; continue others |

## Behavior

### Profile and presets

- Register `hadoop_linux` in `DEVICE_PROFILES` as **Hadoop / Linux SSH**.
- Default command list includes:
  - Health / CPU / Memory / Capacity labels aligned with existing Vultr VPS Linux presets.
  - Sample Hadoop CLI status commands (e.g. best-effort `hdfs` / `yarn` / `systemctl` status lines). Failures on refresh are non-fatal for the card (same as other optional commands).
  - Power-off subset with labels prefixed exactly **`Power -`**, ordered stop services then OS shutdown (default includes `sudo shutdown -h now`). Exact default command strings are chosen at implementation; Admin can edit freely.
- Selecting the profile when creating/editing a card loads these defaults; subsequent edits persist on the card like arrays.

### Health refresh

- Unchanged HealthServer / monitor path: SSH runs the card’s command list and surfaces results on the dashboard card.
- Linux-style CPU/memory/disk outputs should parse into card metrics where existing parsers already support them (reuse Vultr VPS / Linux patterns where practical).
- Sample Hadoop CLI outputs appear in command results; rich HDFS capacity charts are not required in v1.

### Host Power page

- Entry: dashboard **Host Power** button; opens `/host-power`.
- Lists only cards with `device_profile == hadoop_linux` (and host configured).
- Operator multi-selects hosts (deep-link `?card_id=` or equivalent pre-selects one from the card shortcut).
- **Preview:** builds ordered steps from each selected card’s `Power -` commands only; shows commands and any blocking warnings (no power commands, no creds).
- **Run:** requires `confirm: true`; executes steps per host via existing Paramiko card SSH runner; captures stdout/stderr into page log; returns per-host and aggregate status.

### Per-card shortcut

- On dashboard cards with `hadoop_linux`, show **Power off…** (or equivalent) that opens Host Power with that card selected.
- Same Preview → Confirm → Run APIs as the page.

### Safety

- Preview never mutates hosts.
- Run without confirm → HTTP/API error with clear message.
- Empty power command set → blocking Preview warning; Run disabled/rejected.
- If any `Power -` step fails for a host, skip remaining `Power -` steps for that host (so a failed Hadoop stop never reaches OS shutdown).
- SSH/auth failures fail that host only.

## Architecture

| Piece | Role |
|-------|------|
| `storage_presets.py` | `hadoop_linux` profile + default command tuples |
| `host_power.py` (page HTML/JS) | Host Power UI |
| `host_power_ops.py` (or similar) | Select `Power -` steps, Preview payload, Run orchestration, stop-before-shutdown rule |
| `health_server.py` | Routes `/host-power`, `/api/host-power/preview`, `/api/host-power/run`; filter Hadoop cards |
| `dashboard_view.py` / monitor | Dashboard button + per-card Power off shortcut |
| Existing SSH runner | Reuse card Paramiko path (same family as Contingency / LUN runners) |

## API (illustrative)

- `GET /api/host-power/cards` — Hadoop cards eligible for power-off.
- `POST /api/host-power/preview` — `{ card_ids: [...] }` → steps + warnings.
- `POST /api/host-power/run` — `{ card_ids: [...], confirm: true }` → per-host results.

Exact path names may match repo conventions; behavior above is normative.

## Testing

- Preset tests: profile exists; includes Linux health/capacity, sample Hadoop, and ordered `Power -` stop-then-shutdown.
- Ops tests: Preview extracts only `Power -` commands; Run rejects without confirm; stop failure skips shutdown for that card; multi-card continues after one failure.
- API/page smoke: only `hadoop_linux` listed; deep-link selection works.

## Out of scope follow-ups

- Capacity Report / Excel inclusion for Hadoop hosts.
- Rich HDFS/YARN capacity parsing beyond raw command output.
- Sudo password UI.
- Ansible export of Host Power sequences.
