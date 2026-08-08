# Host Power Mutate Buttons + Clear Log — Design

**Date:** 2026-08-07  
**Status:** Approved (awaiting operator review of this spec)  
**App version target:** 1.6.145  
**Depends on:** Host Power (`host_power.py`, `host_power_ops.py`, `health_server.py`); `hadoop_linux` `Power -` presets; A–F prechecks  
**Parent:** `docs/superpowers/specs/2026-08-07-hadoop-host-power-design.md`  
**Related:** `docs/superpowers/specs/2026-08-07-host-power-af-prechecks-design.md`

## Problem

Host Power A–F prechecks work as clickable buttons, but the mutate path is still a generic **Preview** / **Run** pair. Operators cannot:

- Clear the Run log before another selection without refreshing or clicking Preview.
- Click a labeled **Stop services then shutdown** or **Shutdown only** button the same way they click A–F.
- Tell Preview from Run: Preview is dry-run only; Run is the only mutate. There is no shutdown-only path.

Precheck **F** (`yarn application -list`) can sit disabled/spinning for up to 120s with nothing in the log until SSH returns.

## Goals

- Host Power shows **Preview**, **Stop services then shutdown**, **Shutdown only**, and **Clear log**.
- Remove the page **Run** button. Mutate is only the two labeled buttons.
- One confirm checkbox still gates both mutate actions.
- Preview is dry-run only and lists **both** planned sequences.
- `POST /api/host-power/run` stays the mutate API with a required `mode`.
- Clear log is client-only (no API, no SSH).
- Precheck F writes `Running…` immediately; precheck SSH timeout is **45s**. Mutate Run timeout stays **120s**.

## Non-goals

- Editing the Run log by typing.
- Checkboxes to include/skip individual `Power -` stop steps inside stop-then-shutdown.
- New Admin command labels or preset lines (existing `Power -` lines remain the source of truth).
- Changing the default F command string.
- Treating shutdown as extra A–F letters (G/H).
- Auto-running A–F before mutate.
- Ansible Pad for this flow.

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Mutate confirm | Required (same as today’s Run) |
| Stop vs shutdown | Two distinct actions |
| Preview / Run on page | Keep Preview; remove Run |
| Confirm UI | One checkbox covering both mutate buttons |
| Preview content | One Preview listing both sequences |
| Implementation | Extend preview/run with `mode` (not new endpoints, not G/H) |
| Clear log | Client-only wipe |
| F hang | Immediate `Running…` + 45s precheck timeout |

## Page

Keep A–F as read-only prechecks (no confirm).

Action row (below A–F):

- **Preview** — dry-run; no SSH. Replaces the Run log with both planned sequences per selected host.
- **Stop services then shutdown** — confirm required; runs all `Power -` steps in card order (default: stop YARN NodeManager, stop HDFS DataNode, OS shutdown). Same as today’s Run.
- **Shutdown only** — confirm required; runs only the OS shutdown `Power -` step.
- **Clear log** — wipes the Run log locally. Does not uncheck hosts or confirm. No API.

Confirm checkbox (one control):

> I confirm this will stop Hadoop and/or shut down the selected hosts.

**Stop services then shutdown** and **Shutdown only** stay disabled until the checkbox is checked. While any Preview, mutate, or precheck request is in flight, disable Preview, both mutate buttons, and A–F (same lock as today). **Clear log** stays enabled (local only). Preview and A–F never require confirm.

### Log rules

| Action | Log behavior |
|--------|----------------|
| Preview | **Replace** with both planned sequences |
| Stop services then shutdown | **Replace** with that run’s results |
| Shutdown only | **Replace** with that run’s results |
| A–F | **Append** (unchanged) |
| Clear log | Reset to hint: `Choose one or more hosts, then preview.` |

Click F (or any precheck): immediately append `--- Precheck {letter} @ timestamp ---` and `Running…`, then append the API result or error when SSH returns.

## Step selection

Card `Power -` commands remain the only mutate source (`extract_power_steps`).

- **stop_then_shutdown:** all `Power -` steps in card order.
- **shutdown_only:** the OS shutdown `Power -` step: last `Power -` whose label is `Power - OS Shutdown` **or** whose command matches `\b(shutdown|reboot|halt|poweroff)\b` (case-insensitive). If none exists → Preview warning for that host; `shutdown_only` run fails that host with a clear error and no SSH.

Stop-then-shutdown failure rule unchanged: first failed step aborts remaining steps on **that host only** (so a failed Hadoop stop never reaches OS shutdown). Other selected hosts continue.

## API

### `POST /api/host-power/preview`

Body: `{ "card_ids": [...] }`

No SSH. Per host include:

- `stop_then_shutdown`: list of `{ label, command }`
- `shutdown_only`: list of `{ label, command }` (0 or 1 step)

Warnings when no eligible hosts, no `Power -` steps, or no shutdown step.

### `POST /api/host-power/run`

Body: `{ "card_ids": [...], "confirm": true, "mode": "stop_then_shutdown" | "shutdown_only" }`

- Missing/invalid `mode` → HTTP 400.
- `confirm` not true → same error as today (`Host Power requires explicit confirm=True`).
- `stop_then_shutdown` → run all `Power -` steps (today’s Run).
- `shutdown_only` → run only the shutdown step.

No new mutate endpoints.

### Precheck timeout

`POST /api/host-power/precheck` SSH timeout: **45 seconds**.

Mutate `/run` SSH timeout: **120 seconds** (unchanged).

## Architecture

| Piece | Role |
|-------|------|
| `host_power.py` | Remove Run; add mutate buttons + Clear log; confirm label; Preview both sequences; F `Running…` |
| `host_power_ops.py` | Preview both step lists; pick shutdown step; Run filters by `mode` |
| `health_server.py` | Preview payload; `/run` requires `mode`; precheck timeout 45s; mutate timeout 120s |
| Presets / Admin | Unchanged `Power -` / `Precheck -` lines |

## Errors

- No hosts selected → Preview/mutate fail with a clear warning; no SSH.
- Confirm unchecked → UI does not call `/run`; API still rejects `confirm: false`.
- Invalid `mode` → 400.
- No shutdown `Power -` step → Preview warning; `shutdown_only` fails that host.
- Stop-then-shutdown: first failed step aborts remaining steps on that host only.
- F timeout/SSH error → that host’s precheck fails; log gets the error; other hosts continue; buttons unlock.

## Testing

- Preview returns both `stop_then_shutdown` and `shutdown_only` step lists.
- Run without `mode` or bad `mode` → 400; without confirm still rejected.
- `stop_then_shutdown` runs all `Power -` steps; stop failure skips shutdown on that host.
- `shutdown_only` runs only the shutdown step.
- Page markers: no lone Run button; new button labels; Clear log; confirm text covers both.
- Precheck timeout is 45s; mutate timeout still 120s.
- Version pin **1.6.145**.

## Out of scope follow-ups

- Editable Run log.
- Extra A–F letters or changing default F command.
- Per-step checkboxes inside stop-then-shutdown.
- Parsing precheck output to block shutdown.
- Ansible export of Host Power sequences.
