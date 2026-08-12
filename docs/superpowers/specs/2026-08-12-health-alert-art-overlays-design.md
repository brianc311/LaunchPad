# Sci-fi health alert art overlays + I/O / power intel

**Date:** 2026-08-12  
**Status:** Approved for implementation  
**App version target:** 1.6.156  
**Depends on:** Critical health alert popups (1.6.155) — `health_alert_state`, Health Server `/api/health-alerts*`, desktop `HealthAlertDialog`, Health Dashboard modal  
**Approach:** Asset pack + card-name match (Approach A)  
**Base branch:** `main` (tip at 1.6.155)

## Problem

Operators want critical alerts to look like the site/array “ALERT” art (Mount Vernon, Valparaiso, HPE/IBM host cards, etc.): big card name, warning triangle, issue text, and clear buttons. Today’s popup is a plain dialog. Detection is strong for canister offline, network down, and drive failures, but weak for **I/O card / FC** failures and inconsistent for **canister lost power** wording.

## Goals

- Ship PNG alert art under app branding; match by **card name** (normalize punctuation/spaces; ignore trailing “distribution center”-style suffixes).
- On critical alert show:
  - **Connection Dashboard:** overlay on that card using matching PNG (styled fallback if no art).
  - **Topmost dialog** with the same art when attention is needed / card not in view.
  - **Health Dashboard:** same art-backed modal.
- Button labels: **Suppress** (Acknowledge), **Snooze 5/10/15/20** (Pause), **Alarm off/on**, **Close** — same semantics as 1.6.155.
- Add FC / I/O critical popup eligibility from `lsportfc` (and HPE equivalents when available).
- Prefer short operator-facing lines when classifiable: Canister down/failed/offline, Canister lost power, Network down, Hard drive failed, I/O card failed; otherwise keep raw array message.
- Bump `APP_VERSION` to **1.6.156**.

## Non-goals (v1)

- Admin UI to pick a custom image per card.
- Email / SMS / Windows Action Center.
- Inventing “lost power” without array/event evidence.
- Redesigning non-alert Connection Dashboard card chrome.
- Changing acknowledge / pause / mute state machine rules.
- Collapsible Active Issues or Excel CLI export.

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Surfaces | Card overlay + topmost dialog + Health Dashboard modal |
| Button labels | Suppress, Snooze 5/10/15/20, Alarm off/on, Close |
| Art source | Bundled PNGs matched by card name |
| Architecture | Asset pack + name match (Approach A) |
| Popup severity | Critical only (unchanged) |

## Behavior

### Art matching

1. Install/copy alert PNGs to a stable directory (e.g. under `BRANDING_DIR/health-alerts/` or packaged resources mirrored there).
2. Build a lookup key from card `name`: uppercase, strip trailing location-role suffixes like `distribution center` / `distrib…`, replace non-alphanumerics with `_`, collapse repeats.
3. Match filename stem similarly (existing assets like `VALPARAISO__IN-…`, `HPE-hpew202sstor01-WAG2-…`).
4. If multiple candidates, prefer exact stem match then longest prefix match.
5. If no match → dark styled fallback (red ALERT header, card name, issue list) — still fully functional.

### Overlay vs dialog

- When a card has open critical popups and is visible on Connection Dashboard, show a card-level overlay with art + buttons.
- Always keep the interruptive dialog path for when the card is off-screen, collapsed, or Health Server browser-only.
- Health Dashboard uses the art-backed modal (no Tk card widgets).
- Actions call existing acknowledge / pause / alarm APIs; labels only change in UI.

### Detection

| Operator text | Rule |
|---------------|------|
| Network down | Existing connectivity critical |
| Hard drive failed | Existing drive/disk/mdisk/nvme offline/degraded |
| Canister down / failed / offline | Existing node/controller/canister bad status; prefer short wording when status is offline/failed/down |
| Canister lost power | Critical when alert/event/description mentions power/PSU/UPS/battery **or** canister offline combined with such an alert on the same card |
| I/O card failed | **New:** analyze `lsportfc` (status offline/failed/degraded/inactive) → category `io` / `fc`, severity critical, operator text “I/O card failed” (include port id when known). HPE: use existing port/health command output when present |

Warn-only issues still do not popup.

## Architecture

| Unit | Responsibility |
|------|----------------|
| `launchpad/health_alert_art.py` (new) | Normalize names; resolve PNG path; list bundled assets |
| Branding / install resources | Copy user-provided alert PNGs into `health-alerts/` |
| `ui/health_alert_dialog.py` + `card_widget` / dashboard | Art background; Suppress/Snooze/Alarm/Close; card overlay |
| `health_server.py` Health HTML/JS | Modal background-image from resolved art URL/API; same button labels |
| Optional `GET /api/health-alerts/art/<card_id>` or include `art_url` in alert payload | Browser can load PNG |
| `flashsystem_health.py` (+ HPE analyze path) | FC/I/O critical issues; power wording helpers |
| `config.APP_VERSION` | `1.6.156` |

Reuse `health_alert_state` unchanged for fingerprints, ack, pause, mute.

## Testing

- Name normalization matches Valparaiso / Mount Vernon / HPE host-style filenames.
- Unknown card → fallback UI, no crash.
- Suppress/Snooze/Alarm/Close labels present on desktop and browser contracts.
- FC port offline → critical candidate / popup-eligible with I/O wording.
- Power-related alert + canister offline → “Canister lost power” (or equivalent) when rules match.
- Version pins expect `1.6.156`.

## Out of scope follow-ups

- Admin per-card image picker.
- Email notifications.
- Full FC matrix UI beyond critical popup eligibility.
