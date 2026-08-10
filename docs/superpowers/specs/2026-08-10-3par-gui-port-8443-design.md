# 3PAR Array GUI Port 8443 — Design

**Date:** 2026-08-10  
**Status:** Approved (awaiting operator review of this spec)  
**App version target:** 1.6.146  
**Depends on:** `resolve_gui_url` (`host_volume_health.py`); Arrays side rail (`dashboard_array_rail.py`); FC Open GUI (`app.py` `open_card_gui`); `HP_3PAR_PROFILES` in `storage_presets.py`  
**Related:** `docs/superpowers/specs/2026-08-03-dashboard-array-rail-design.md`

## Problem

The Connection Dashboard Arrays side rail and FC Consistency Groups **Open GUI** open a browser URL via `resolve_gui_url`: Admin URL if set, else `https://{host}` with **no port**.

HPE 3PAR PAR management GUIs (SSMC) listen on **8443**. Operators expect links like `https://pla-w023par01:8443`. Without the port, Open GUI often fails unless each card’s Admin URL is hand-filled. **HPE Primera 600 4-way** must not get this port default.

## Goals

- When Admin URL is empty and the card’s Device Profile is a 3PAR profile, Open GUI uses `https://{host}:8443`.
- Prefer Admin URL when present (unchanged override).
- Same rule for Arrays side rail and FC **Open GUI**.
- Primera (`hpe_primera_600`) and non-3PAR profiles keep `https://{host}` (no auto-`:8443`).
- Do not double a port if Host already includes one.

## Non-goals

- Changing SSH Connect or treating the rail as CLI.
- Seeding Admin URL fields on save.
- Applying `:8443` to Volume Find / Snapcopy host hyperlinks.
- New Device Profile keys or Primera GUI defaults.
- Editing card Host/URL values in Admin as part of this change.

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Which profiles get `:8443` | Only `HP_3PAR_PROFILES`: `hpe_3par_8200`, `hpe_3par_8400`, `hpe_3par_8450` |
| Primera | Excluded (`hpe_primera_600` stays `https://{host}`) |
| Admin URL empty | Build from Host + profile default |
| Admin URL set | Prefer Admin URL as typed (normalize scheme only) |
| Where it applies | Shared `resolve_gui_url` — Arrays rail **and** FC Open GUI |
| Implementation | Extend `resolve_gui_url` with optional `device_profile` |

## Behavior

Resolution order for Open GUI:

1. If Admin **URL** is non-empty → `normalize_gui_url(url)` (add `https://` if no scheme).
2. Else if **Host** is non-empty and `device_profile` ∈ `HP_3PAR_PROFILES` → `https://{host}:8443`, unless the host string already ends with `:<digits>` (a port) — then use `normalize_gui_url(host)` without adding another `:8443`.
3. Else if Host is non-empty → `https://{host}`.
4. Else → empty string; callers keep today’s error (“set Host or URL in Admin”).

Host may be a DNS name (`pla-w023par01`) or an IP. Both get `:8443` for 3PAR when no port is present.

SSH Connect is unchanged. The Arrays rail remains Open GUI only.

## Architecture

| Piece | Role |
|-------|------|
| `launchpad/host_volume_health.py` | `resolve_gui_url(url="", host="", device_profile="")` implements the rules above |
| `launchpad/dashboard_array_rail.py` | `rail_gui_url(card)` passes `card.device_profile` |
| `launchpad/app.py` | `open_card_gui` passes `card.device_profile` |
| `launchpad/storage_presets.py` | Reuse `HP_3PAR_PROFILES` (no new keys) |
| `launchpad/config.py` | `APP_VERSION` → `1.6.146` |

Callers that omit `device_profile` keep today’s non-3PAR behavior (`https://{host}`).

## Errors

Unchanged: missing URL and Host still fail Open GUI with the existing clear message. No new error paths for wrong profile.

## Testing

- `resolve_gui_url("", "pla-w023par01", "hpe_3par_8200")` → `https://pla-w023par01:8443`
- Admin URL preferred over 3PAR host default
- `hpe_primera_600` / empty / non-3PAR profile → `https://{host}` (no `:8443`)
- Host already including `:8443` is not doubled
- `rail_gui_url` for a 3PAR card (empty URL) includes `:8443`
- Version pin **1.6.146**

## Out of scope follow-ups

- Profile-aware ports for other vendors
- Primera-specific GUI URL shape
- Volume Find / Snapcopy Site IP links using the same helper
