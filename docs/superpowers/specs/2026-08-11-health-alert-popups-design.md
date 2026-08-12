# Critical health alert popups (desktop + Health Dashboard)

**Date:** 2026-08-11  
**Status:** Approved for implementation  
**App version target:** 1.6.155  
**Depends on:** Health Server card refresh / `analyze_health` → `health_issues`, Connection Dashboard capacity-alert poll pattern, Health Dashboard Active Issues  
**Approach:** Shared alert store + dual UI (Approach A)  
**Base branch:** `main` (tip at 1.6.154)

## Problem

Operators missed a Valparaiso outage (~15 minutes, canisters offline after power loss) because LaunchPad only shows issues on the Health Dashboard if someone is watching. There is no interruptive popup with the **card/site name**, and no Acknowledge / Pause / per-card alarm mute. Active Issues rows from `lseventlog` often render as empty `alert ·` (message column blank). Physical drive offline/degraded is weakly covered (MDisk/NVMe paths exist; FlashSystem `lsdrive` is not in the SVC preset).

## Goals

- Popup alerts on **both** Connection Dashboard (desktop) and Health Dashboard (browser) for **critical** issues only.
- Each popup shows **card name** + issue summary.
- Actions:
  - **Acknowledge** — suppress that issue fingerprint until it clears; re-alert if it returns.
  - **Pause** — 5 / 10 / 15 / 20 minutes; suppress popups for that card until expiry (Active Issues still show).
  - **Alarm off** — mute popups/sound for that **one card** until Alarm on (Active Issues still show).
- Detect critical failures including unreachable/refresh failed, node/canister/controller offline/failed, and drive/disk/MDisk/NVMe offline or degraded (degraded drives promoted to critical for popup eligibility).
- Fix Active Issues alert text so operators see real messages (not blank `alert ·`).
- Shared server-side state so desktop and browser stay in sync.
- Bump `APP_VERSION` to **1.6.155**.

## Non-goals (v1)

- Email / SMS / PagerDuty.
- Windows Action Center / toast outside LaunchPad.
- Collapsible Active Issues section.
- Health Excel / per-card CLI log export.
- Full FC-port matrix analysis (lsportfc stays inventory; not a popup source in v1).
- Changing the existing capacity-alert strip beyond feeding the same critical popup pipeline where applicable.
- Warn-severity popups (warn stays in Active Issues only).

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Surfaces | Both desktop Connection Dashboard and browser Health Dashboard |
| Popup severity | Critical only |
| Acknowledge | Hide until issue clears; re-alert if it returns |
| Alarm off | Mute popups/sound for that one card until turned back on; Active Issues remain |
| Pause | 5, 10, 15, 20 minutes per card |
| Architecture | Shared Health Server alert store + dual UI |

## Behavior

### Critical eligibility

After each Monitor-on refresh (or when card error is set), derive popup-eligible items:

1. **Unreachable** — Monitor on and refresh failed / card `error` with no usable health data → critical issue `category=connectivity`, message includes failure text, `server` = card name.
2. **Existing critical `health_issues`** — already `severity=critical`.
3. **Drive / disk promotion** — issues in categories `nvme`, `disk`, `mdisk`, or new `drive` whose status/message indicates offline or degraded → treat as critical for popup (and store as critical in `health_issues` when produced by drive analysis).
4. **Node / canister / controller** — offline/failed/degraded via existing status analysis remain critical when status is in the bad set.

Warn capacity / soft alerts do **not** open popups.

### Fingerprint

Stable key per open issue: `card_id` + `category` + normalized message (or connectivity sentinel). Used for acknowledge-until-clear and de-duplication.

### Acknowledge

Persist fingerprint as acknowledged while the issue is still present. No popup for that fingerprint. When the issue disappears from the next refresh, drop the acknowledgement. If the same fingerprint returns later, popup again.

### Pause

Per `card_id`: `paused_until` monotonic/wall timestamp. While active, no popups for that card (sound muted). Active Issues unchanged. Pause options: 5, 10, 15, 20 minutes. New pause replaces previous pause end time.

### Alarm off / on

Per `card_id`: `alarm_muted` boolean. While muted, no popups/sound for that card. Active Issues unchanged. Explicit Alarm on clears mute. Distinct from Acknowledge (issue-level) and Pause (timed).

### Popup UX

- Title/body: card name prominent; severity; category · message (one or a short list of open critical items for that card).
- Buttons: Acknowledge (per shown issue or “acknowledge all listed”), Pause submenu (5/10/15/20), Alarm off, Close (dismiss UI only — does **not** acknowledge; if still eligible and not paused/muted, may reappear on next poll).
- Desktop: optional short beep while not muted/paused when a new eligible fingerprint appears.
- Browser: modal dialog; poll shared API on an interval similar to capacity alerts (~30s) and after refresh.

### Active Issues text fix

`_analyze_alerts` must populate `message` from the first non-empty of: `message`, `description`, `event_id`+`object_name`, `object_name`, else `"Alert"`. Empty strings must not block the fallback (treat `""` as missing).

### Drive detection

Add FlashSystem preset command `Health - Drives` → `svcinfo lsdrive -delim :` (or equivalent already used in family presets). Analyze status into `health_issues` with category `drive`; offline/degraded → critical. Prefer `lsnodecanister` for canister health where Controllers currently duplicate `lsnode` if that is the correct family command (keep lsnode for nodes).

## Architecture

| Unit | Responsibility |
|------|----------------|
| `launchpad/health_alert_state.py` (new) | Load/save mute, pause, acknowledgements; compute open popup alerts from cards + state |
| Health Server HTTP API | `GET /api/health-alerts` — open critical popups + card mute/pause flags; `POST /api/health-alerts/acknowledge`; `POST .../pause`; `POST .../alarm` (off/on) |
| `flashsystem_health.py` / presets | Alert message fallbacks; `lsdrive` (+ canister command fix); drive critical issues |
| `health_server.py` Health HTML/JS | Modal + poll + actions |
| `dashboard_view.py` / related UI | Desktop dialog + poll + actions + beep |
| Settings / JSON | Persist ack fingerprints, mute set, pause until (card id keys) |
| `config.APP_VERSION` | `1.6.155` |

Persistence: reuse Health Server settings backend (JSON setting key, e.g. `health_alert_state`) so state survives process restart.

## Testing

- Unreachable card → connectivity critical → appears in `GET /api/health-alerts`.
- Drive/disk offline or degraded → critical popup-eligible.
- Acknowledge suppresses fingerprint until issue cleared; return re-opens.
- Pause 5/10/15/20 sets expiry; no popup while paused; resumes after.
- Alarm off mutes one card only; other cards still popup; Alarm on restores.
- Warn issue never in popup list.
- `_analyze_alerts` with empty `message` but `description` present → non-empty Active Issues text.
- Version pins expect `1.6.155`.

## Out of scope follow-ups

- Collapsible Active Issues.
- Excel CLI export confirmation.
- FC port health popups.
- Email notifications.
