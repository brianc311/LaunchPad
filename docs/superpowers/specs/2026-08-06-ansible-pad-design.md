# Ansible Pad — LaunchPad ↔ plp5-dz5-nw bridge

**Date:** 2026-08-06  
**Status:** Approved  
**App version target:** next patch after tip (1.6.130+)  
**Depends on:** HealthServer report pages; SSH cards; Contingency Groups; FlashCopy CG step builders (`build_snap_steps` / `build_fc_consistgrp_steps`); Paramiko SSH already used for arrays  
**Approach:** New Ansible Pad page — keep LaunchPad native snap/CG SSH as Path A; Path B generates Ansible packages and/or runs `ansible-playbook` on control host `plp5-dz5-nw`

## Problem

Operators need two ways to update IBM arrays (volumes, CGs, snap copy, start CGs):

1. **LaunchPad** — Contingency Groups / FlashCopy CGs Preview → Run over SSH (already works).  
2. **Ansible** — YAML/playbooks on control host **`plp5-dz5-nw`**, which already has connectivity to the arrays.

Today those paths are disconnected: LaunchPad cannot export matching stubs or trigger playbooks on `plp5-dz5-nw`.

## Goals

- Keep Path A unchanged (native LaunchPad SSH for Contingency snap + FlashCopy CG actions).
- Add **Ansible Pad** (`/ansible-pad`) with:
  - **Generate package** — inventory + stub playbooks + vars derived from LaunchPad cards / Contingency Groups / CG actions.
  - **Download ZIP** always.
  - **Sync & Run** — SCP package to `plp5-dz5-nw`, then SSH-run `ansible-playbook` (optional `--check`).
  - **Run existing** — SSH-run an existing remote playbook path already on that host (no generate required).
- Persist Ansible control-host settings (host default `plp5-dz5-nw`, user, key/password, remote project dir, optional default playbook paths).
- Confirm gate before non-check mutating runs; show streamed (or captured) stdout/stderr in the page log.
- Document dual-path operator model in-page (short README in the package too).

## Non-goals (v1)

- HPE CPG create/start playbooks.
- In-LaunchPad editor for remote playbooks.
- Waiting until FlashCopy reaches idle/complete.
- Replacing Contingency / FlashCopy CG Run with Ansible-only.
- Multi-control-host fleet (single control host setting is enough).
- Ansible Tower/AWX API integration.

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Day-to-day IBM snap/CG | LaunchPad native (Approach A) |
| Ansible control host | `plp5-dz5-nw` (configurable) |
| Package contents | Full stubs: inventory + playbooks wrapping same `svctask` style steps |
| Delivery | Download ZIP **and** Sync (SCP) to control host |
| Run modes | Generate+SCP+Run **and** Run existing remote playbook |
| UI surface | New Ansible Pad browser page (Approach 1) |
| Mutating runs | Confirm required; prefer check/dry-run available |

## Behavior

### Entry

- Dashboard button **Ansible Pad** (alongside Contingency Groups / FlashCopy CGs).
- Opens HealthServer `/ansible-pad`.

### Settings

Persisted via LaunchPad settings backend (unlocked):

| Key (illustrative) | Purpose |
|--------------------|---------|
| `ansible_pad_host` | Default `plp5-dz5-nw` |
| `ansible_pad_user` | SSH user on control host |
| `ansible_pad_key_path` / passphrase or password | Auth to control host (not array creds) |
| `ansible_pad_remote_dir` | Remote project directory for synced packages |
| `ansible_pad_default_playbook` | Optional path for “Run existing” |

Settings UI on the Ansible Pad page (or Admin subsection linked from it).

### Generate package

From current LaunchPad data:

1. **`inventory/hosts.yml`** — SSH storage cards (IBM/SVC-focused for stubs; include host/user hints; do not embed private keys in the ZIP).
2. **`group_vars` / host_vars`** — Contingency Group names, volumes, maps, CG names where available.
3. **Stub playbooks** (read-only check tags + mutating tasks gated by vars):
   - Snap-copy style steps aligned with Contingency `build_snap_steps` / Preview CLI.
   - CG start: `prestartfcconsistgrp` / `startfcconsistgrp` aligned with FlashCopy CG `start_group`.
4. **`README.md`** — copy to `plp5-dz5-nw`, example `ansible-playbook` commands, note that LaunchPad Path A remains available.

ZIP download via API. Generate does not mutate arrays.

### Sync & Run

1. Generate package to a temp dir (or reuse last generate).
2. SCP into `ansible_pad_remote_dir` on control host (create dir if needed when permitted).
3. SSH: `ansible-playbook <playbook> -i inventory ...` with optional `--check`.
4. Capture output into page log; on failure show remote stderr and leave remote files in place for debugging.

### Run existing

1. Operator supplies or selects remote playbook path (default from settings).
2. Confirm (unless check mode).
3. SSH run `ansible-playbook` on control host only — no SCP of LaunchPad package.

### Safety

- Non-check Run requires explicit confirm.
- Check/dry-run is the default suggestion in UI copy.
- Control-host SSH failures must not fall through to running commands on arrays from LaunchPad in this path.
- Do not store array root passwords inside exported YAML; use Ansible’s existing vault/key setup on `plp5-dz5-nw`.

## Components

| Piece | Responsibility |
|-------|----------------|
| `launchpad/ansible_pad.py` (or similar) | Page HTML/JS |
| `launchpad/ansible_pad_export.py` | Build inventory/vars/playbook files + ZIP bytes |
| `launchpad/ansible_pad_remote.py` | SCP + remote `ansible-playbook` via Paramiko |
| `launchpad/health_server.py` | Routes: page, settings, export ZIP, sync-run, run-existing |
| `launchpad/ui/dashboard_view.py` | Dashboard button |
| Settings keys | Persist control-host config |
| Tests | Export shape; dry-run command construction; confirm gating; mock SSH |

Reuse Contingency / FC CG step builders where possible so stubs stay aligned with Preview CLI.

## Error handling

- Missing settings / unlocked backend → clear error; no partial remote run.
- SCP or SSH auth failure → log + stop before playbook.
- Playbook non-zero exit → show output; do not retry automatically.
- Generate with no cards/groups → empty inventory warning; still allow ZIP of stubs/README.

## Testing

- Export ZIP contains inventory + at least one stub playbook + README mentioning `plp5-dz5-nw`.
- Sync & Run with `--check` builds expected remote command (mocked SSH).
- Run existing uses configured remote path.
- Mutating run API rejects without confirm flag.
- Dashboard exposes Ansible Pad entry.

## Out of scope reminders

Native Contingency / FlashCopy CG Run paths stay as-is. HPE CPG lifecycle and AWX are later phases.
