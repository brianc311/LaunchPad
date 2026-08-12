# IBM DS8884 Management-Desktop SSH + DSCLI — Design

**Date:** 2026-08-12  
**Status:** Approved  
**App version target:** 1.6.163  
**Profile:** `ibm_ds8884` (IBM DS8884 / DS8000 family via DSCLI)

## Problem

Operators reach DS8000 through a **management desktop**: RDP in, run the **DSCLI GUI**. LaunchPad cards for DS8884 instead **SSH** to the card Host and run shell `dscli …` commands. Today that Connect/Refresh path fails at **SSH authentication**, and even after SSH works the desktop may only have the GUI — CLI/`PATH`/HMC targeting is unclear.

LaunchPad must make the **SSH → remote DSCLI CLI** path work against that management desktop (Approach A), without adding local DSCLI-to-HMC protocol or RDP/GUI automation.

## Goals

- Card **Host** = management desktop; SSH with card username/password (keyboard-interactive supported).
- Optional Admin fields for **DSCLI path** and **HMC host** so commands run reliably when PATH/profile are incomplete.
- Rewrite all DS8884 `dscli` command lists (health presets, inventory, system connectivity, LUN create hints as applicable) through one wrapper.
- Clear errors for auth vs missing `dscli` vs HMC reachability.
- Document one-time desktop setup (OpenSSH Server + CLI smoke test).

## Non-goals

- Local DSCLI client talking to HMC ports 1750/8451 from the LaunchPad PC (no SSH).
- RDP or GUI automation of the DSCLI application.
- Changing FlashSystem / HPE / XIV SSH behavior.
- Requiring public-key-only auth as the primary path (password/KI remains primary for this card).

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Reach method | SSH to management desktop, then remote `dscli` CLI |
| Host field | Management desktop IP (not array data port) |
| Auth failure focus | Fix/clarify password + keyboard-interactive SSH |
| Extra Admin fields | Optional DSCLI path + optional HMC host |
| Local DSCLI / RDP automation | Out of scope |

## Behavior

### Connection model

1. Unlock LaunchPad; open the DS8884 card in Admin.
2. Set **Host** to the management desktop, **Port** 22 (or desktop SSH port), **Username** / **Password** for OpenSSH on that desktop.
3. Optionally set **DSCLI path** (e.g. `C:\Program Files\IBM\dscli\dscli.bat`) and **HMC host** (HMC IP/hostname DSCLI should use).
4. Save card → Connect / Refresh.
5. LaunchPad SSHs in and runs wrapped `dscli` commands for health/capacity (and inventory / system connectivity when those features scan this profile).

### Command wrapping

Shared helper (name in plan), e.g. `wrap_dscli_command(cmd, *, dscli_path="", hmc_host="", username="", password="")`:

- If `cmd` does not start with / contain a `dscli` invocation, return unchanged.
- If `dscli_path` set, replace leading `dscli` with the quoted path.
- If `hmc_host` set, inject `-hmc1 <hmc_host>` after the executable.
- When `hmc_host` is set and card password is available, also pass DSCLI `-user` / `-passwd` (or equivalent non-interactive flags) so a remote `dscli.profile` is not required. Do not log the password.
- When path and HMC are empty, commands stay as today’s `dscli lssi` etc. (remote PATH + profile).

Apply wrapper when building the command list for `ibm_ds8884` refreshes and for DS8884 inventory / system-connectivity topic commands.

### Admin UX

- Show DSCLI path + HMC host only when device profile is `ibm_ds8884`.
- Hint copy (short): Host is the management desktop; enable OpenSSH Server; confirm `dscli` works in a remote shell; set path/HMC if needed.
- Persist fields on the card (new columns or equivalent card settings).

### Errors

| Failure | Operator message direction |
|---------|----------------------------|
| SSH auth failed | Check desktop Host, username/password, OpenSSH enabled; KI prompts if shown |
| SSH OK, `dscli` not found | Set DSCLI path or install/add CLI to PATH on the desktop |
| `dscli` HMC/auth errors | Set HMC host and ensure DSCLI user/password (card) match HMC |

### Setup checklist (docs / Admin hint)

1. On management desktop: enable OpenSSH Server; allow card user to log in.
2. From another machine: `ssh user@desktop` succeeds with the same password stored in LaunchPad.
3. On desktop (or over SSH): `dscli lssi` (or full path) reaches the storage image.
4. Then LaunchPad Connect/Refresh.

## Components

| Area | Change |
|------|--------|
| `launchpad/database.py` / Card | Persist optional `dscli_path`, `dscli_hmc` (exact column names in plan) |
| `launchpad/ui/admin_view.py` | DS8884-only fields + hint |
| New helper module or `storage_presets` / small `dscli_wrap.py` | Command wrapping |
| `launchpad/ssh_commands.py` / health refresh path | Use wrapped commands for `ibm_ds8884` |
| `storage_inventory` / `system_connectivity` | Wrap DS8884 topic commands |
| `launchpad/ssh_paramiko.py` / interactive Connect | Keep KI auth; clearer auth errors where easy |
| `launchpad/config.py` | `APP_VERSION` → `1.6.163` |
| Tests | Wrapper unit tests; Admin field round-trip; existing KI tests |

## Testing

- Wrapper: empty options → unchanged `dscli lssi`.
- Wrapper: path only → quoted path replaces `dscli`.
- Wrapper: path + HMC → `-hmc1` present; user/pass flags when password provided.
- Non-dscli commands untouched.
- Admin save/load of path/HMC for `ibm_ds8884`; fields hidden for other profiles.
- Keyboard-interactive auth tests remain passing.

## Success criteria

- [ ] Operator can SSH-authenticate to the management desktop via the DS8884 card credentials.
- [ ] Refresh runs remote DSCLI CLI and returns parseable health/capacity (or a clear DSCLI/HMC error).
- [ ] Optional path/HMC fields fix PATH/profile gaps without requiring local DSCLI on the LaunchPad PC.
- [ ] Focused unit tests for wrapper + Admin persistence pass.
