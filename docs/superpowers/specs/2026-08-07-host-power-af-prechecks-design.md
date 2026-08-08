# Host Power A–F Prechecks — Design

**Date:** 2026-08-07  
**Status:** Approved (awaiting operator review of this spec)  
**App version target:** 1.6.143  
**Depends on:** Host Power (`host_power.py`, `host_power_ops.py`, `health_server.py`); `hadoop_linux` presets; card SSH runner + sudo password path  
**Parent:** `docs/superpowers/specs/2026-08-07-hadoop-host-power-design.md`

## Problem

Operators can Preview/Run Hadoop stop → OS shutdown, but they cannot run read-only checks from Host Power. The Run log is output-only (not editable). Health/HDFS/YARN commands on the card only run during dashboard refresh, not before shutdown.

They want **A–F** on the Host Power page: click a letter to run that precheck on the selected host(s) and see output in the Run log, without confirming a mutate.

## Goals

- Host Power shows six clickable prechecks **A–F**.
- Click a letter → run that precheck over SSH on checked Hadoop hosts → **append** output to the Run log.
- Prechecks are read-only: **no confirm checkbox**.
- Preview / Run stay stop-Hadoop-then-shutdown (`Power -` only) and still require confirm.
- Default A–F commands ship on the `hadoop_linux` preset as `Precheck - A …` through `Precheck - F …` so Admin can edit the command strings.
- Existing Hadoop cards without those lines still work via catalog fallback (and optional promote on health register).

## Non-goals

- Editing the Run log by typing.
- Checkboxes to include/skip individual `Power -` stop/shutdown steps.
- Auto-running A–F as part of Preview or Run.
- Blocking Run if a precheck “looks bad” (no parsing/gate; operator reads the log).
- Cluster drain / decommission beyond the command strings.
- Ansible Pad for this flow.

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Run log | Output only; not editable |
| A–F | Clickable buttons on Host Power |
| Mapping | Recommended six (below) |
| Confirm | Not required for A–F; still required for Run |
| Preview / Run | Unchanged: `Power -` stop then OS shutdown only |
| Admin | Can edit `Precheck -` command strings on the card |
| Missing card lines | Use built-in catalog default for that letter |

## A–F catalog (normative)

| Letter | Label | Default command |
|--------|--------|-----------------|
| A | Precheck - A Uptime / load | `uptime; cat /proc/loadavg` |
| B | Precheck - B Failed systemd units | `systemctl --failed --no-pager 2>/dev/null \|\| true` |
| C | Precheck - C Hadoop / HDFS / YARN units | `systemctl list-units 'hadoop*' 'hdfs*' 'yarn*' --no-pager 2>/dev/null \|\| true` |
| D | Precheck - D HDFS dfsadmin report | `hdfs dfsadmin -report 2>/dev/null \| head -n 40 \|\| true` |
| E | Precheck - E YARN node list | `yarn node -list 2>/dev/null \|\| true` |
| F | Precheck - F YARN running apps | `yarn application -list 2>/dev/null \|\| true` |

Letters are always A–F in this order on the page. Button text: **A** … **F** plus a short hint (e.g. `A Uptime / load`).

## Behavior

### Page

- New **Prechecks** row on Host Power (above or beside Preview/Run): six buttons A–F.
- Hint: prechecks are read-only; check one or more hosts, then click a letter.
- If no host is checked, clicking A–F writes a clear error into the Run log and does not call SSH.
- While a precheck (or Preview/Run) is in flight, disable A–F, Preview, and Run (same lock as today).
- Run log: **append** precheck results (do not wipe prior Preview/Run text). Prefix each click with a separator line, e.g. `--- Precheck A @ timestamp ---`. Preview/Run may still replace the log as they do today.

### Command resolution (per host, per letter)

1. Parse the card’s resolved command list (`resolve_card_commands`).
2. If a label starts with `Precheck - {letter}` (e.g. `Precheck - E` or `Precheck - E YARN node list`) and has a non-empty command, use that command.
3. Else use the catalog default for that letter.
4. Run via the same Paramiko / sudo path as Host Power `Power -` steps.

Invalid letter → API 400. Ineligible / missing host → that host fails in the payload; other selected hosts continue.

### API

- `GET /api/host-power/prechecks` — `{ "prechecks": [ { "letter": "A", "label": "…", "hint": "Uptime / load" }, … ] }` (catalog only; no SSH).
- `POST /api/host-power/precheck` — `{ "card_ids": [...], "letter": "A" }` → per-host ok/output/error. **No `confirm` field.**

Reuse existing host selection (`hadoop_linux` + non-empty host).

### Presets and promote

- Add `Precheck - A` … `Precheck - F` to `HADOOP_LINUX_COMMANDS` **before** existing `Power -` stop/shutdown lines.
- Keep current `Power -` NodeManager, DataNode, OS shutdown.
- `ensure_hadoop_linux_cards`: if profile is `hadoop_linux` (or being promoted) and any A–F `Precheck -` letter is missing, append the missing catalog lines. Do not rewrite operator-edited commands for letters that already exist.

### Safety

- A–F must not run `shutdown`, `reboot`, `halt`, or `poweroff`. Catalog defaults do not. If a card’s custom `Precheck -` command matches those tokens (case-insensitive word match), reject that host’s precheck with an error and skip SSH for that host.
- Precheck failure (SSH error or `ERROR:` output) fails that host’s letter only; does not abort other hosts; does not affect later Preview/Run.

## Architecture

| Piece | Role |
|-------|------|
| `storage_presets.py` | `Precheck - A`…`F` on `hadoop_linux` |
| `hadoop_linux_promote.py` | Merge missing A–F lines onto existing Hadoop cards |
| `host_power_ops.py` | Catalog, letter validation, resolve command, mutate-guard |
| `health_server.py` | `GET …/prechecks`, `POST …/precheck` |
| `host_power.py` | A–F buttons, append log, call precheck API |

## Testing

- Catalog: six letters A–F; labels/commands match the table.
- Resolve: card `Precheck - E …` overrides catalog; missing letter uses default.
- Mutate-guard: custom precheck containing `shutdown` is rejected without calling `run_command`.
- API: precheck does not require confirm; invalid letter 400; no hosts → ok false + warning.
- Page: A–F markers, `/api/host-power/precheck`, `/api/host-power/prechecks`.
- Promote: Hadoop card missing prechecks gains A–F; existing custom `Precheck - D` is left unchanged.
- Regression: Preview still extracts only `Power -`; Run still requires confirm.

## Out of scope follow-ups

- Auto-run A–F before Run.
- Checkboxes to pick which `Power -` steps execute.
- Parse precheck output to block shutdown.
- Editable Run log.
