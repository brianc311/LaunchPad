# System Connectivity License Key Tab

**Date:** 2026-07-29  
**Status:** Approved for implementation  
**App version target:** 1.6.78  
**Depends on:** System Connectivity report (1.6.70+), Firmware tab (1.6.73+), IBM Firmware link (1.6.77)  
**Approach:** Sixth System Connectivity tab with flattened HPE feature rows (Approach 1)  
**Base branch:** `feature/contingency-groups`

## Problem

Operators must open each array GUI to check HPE **License Key** (key generation date + feature expirations) and FlashSystem **encryption licensed** / system clock state. System Connectivity already live-scans Call Home through Firmware but has no License Key topic.

## Goals

- Add System Connectivity tab **License Key** after Firmware, with matching Excel sheet and CSV member.
- **HPE:** live `showlicense` → key generation date + full Enabled Feature / Expiration Date (one row per feature).
- **FlashSystem / SVC:** encryption licensed + system date/time + key generation date when CLI exposes it (else blank).
- **DS8884:** eligible card rows with `n/a` for license-specific fields.
- Same site filter, unlock gate, and Refresh live as other topics.
- Bump `APP_VERSION` to **1.6.78**.

## Non-goals

- Installing or changing licenses (`setlicense` / `chlicense` / GUI apply).
- Full IBM Licensed Functions SCU / External Virtualization capacity tables.
- Per-site Available Update Versions (slice A — later).
- Changing Firmware tab or IBM upgrade-matrix link behavior.
- A separate Dashboard button or standalone License Key report URL.

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Placement | Sixth System Connectivity tab after Firmware (+ Excel/CSV) |
| Platforms | FlashSystem/SVC + HPE; DS8884 n/a for license fields |
| HPE detail | Full feature + expiration table (flattened rows) |
| FlashSystem detail | Encryption licensed + date + time + key generation date (best-effort) |
| Row model | FlashSystem: 1 row/card; HPE: 1 row/feature; DS8884: 1 n/a row/card |
| Implementation | Approach 1 — extend existing System Connectivity scan |

## Behavior

### License Key tab / sheet columns

Identity columns match other topics (Site, Card, Host, Vendor, Profile), plus:

| Column | Meaning |
|--------|---------|
| Key generation date | HPE from `showlicense`; FlashSystem blank unless CLI exposes a known field |
| Date | FlashSystem system date from clock command; HPE/DS blank or n/a |
| Time | FlashSystem system time from clock command; HPE/DS blank or n/a |
| Encryption licensed | FlashSystem `yes` / `no` / `unknown` from `lsencryption`; HPE/DS blank or n/a |
| Feature | HPE enabled feature name; FlashSystem/DS blank |
| Expiration | HPE expiration (`—` stored as empty or literal `—`); FlashSystem/DS blank |
| Configured | `yes` if topic data collected; `no` / `unknown` / `n/a` per existing topic rules |
| Status | Short state (ok, expired features, unknown, error, n/a, …) |
| Details | Human summary (e.g. key gen date, feature count, encryption state) |
| Error | Per-card collect/parse error if any |

Sort: card name A–Z; for HPE, features A–Z within a card. Site filter and unlock rules unchanged.

### Collectors (read-only)

| Family | Commands | Notes |
|--------|----------|-------|
| FlashSystem / SVC | `lsencryption` (via `svcinfo` prefix path used by System Connectivity); clock via `svqueryclock` (best-effort) | Encryption licensed from licensed/status fields; parse clock into Date + Time; Key generation date blank if not present |
| HPE 3PAR / Primera | `showlicense` | Parse “License key was generated on …”; emit one row per currently enabled feature with expiration; if trial/expired sections exist, include them with Status/Details distinguishing expired/trial when parseable |
| DS8884 | none | Emit n/a row |

If a command fails: set Error, Configured/Status per existing System Connectivity patterns; do not invent feature rows.

### Export

- Excel workbook gains a **License Key** sheet with the same columns.
- CSV zip/member includes License Key alongside other topics.
- No Admin catalog for this topic.

## Architecture

- Extend `TOPICS` with `license_key` in `system_connectivity.py`.
- Add parsers for HPE `showlicense`, FlashSystem `lsencryption`, and clock output.
- Extend `topic_commands_for_profile` and `health_server` scan paths to collect and flatten HPE rows.
- Update `system_connectivity_page.py` (tab + panel + JS TOPICS) and `system_connectivity_export.py`.
- Version bump in `config.py` + version test.

## Tests

- Parser unit tests with fixtures shaped like sample HPE `showlicense` and FlashSystem `lsencryption` / clock output (including `—` expirations and multi-feature cards).
- Page/nav: License Key tab after Firmware; panel id present.
- Export: License Key sheet/member present when rows exist.
- Version assert `1.6.78`.

## Follow-up (out of scope)

1. Per-site Available Update Versions catalogs (slice A).
2. Richer IBM Licensed Functions (SCU virtualization) reporting.
3. HPE nested UI (non-flat) if operators prefer a sub-table later.
