# Active issues since date (hide old health alerts)

**Date:** 2026-08-14  
**Status:** Approved for implementation  
**App version target:** 1.6.166  
**Depends on:** `health_alert_state` (`issue_fingerprint`, `list_popup_alerts`, `HEALTH_ALERT_SETTING`), Health Dashboard Active Issues (`health_issues` on `HealthCard.to_api`), Admin Branding tab, critical popup / overlay / beep  
**Approach:** Admin date + On/Off toggle; grandfather currently open issues on save and on first upgrade; filter popups and Active Issues  
**Base branch:** `main` (tip at 1.6.165)

## Problem

Critical popups and Health Dashboard Active Issues still surface leftover array problems the operator already treated as fixed. LaunchPad has no start date for an issue, so every unacknowledged critical on a monitored card keeps popping. After the 8/14/2026 reset, only **new** issues should be visible.

## Goals

- Global **Active issues since** date (default **2026-08-14**), editable in Admin.
- Global **Limit to new issues** toggle (default **On**) so the operator can turn old issues back on without losing the date.
- When the limit is On: hide pre-baseline issues from **critical popups** (dialog, overlay, beep) **and** Health Dashboard **Active Issues**, even if the array still reports them.
- Saving a new date (limit On) grandfather-hides whatever is open at that moment.
- Recurrence after an issue **clears** can show again as new.
- Bump `APP_VERSION` to **1.6.166**.

## Non-goals

- Parsing IBM/HPE event-log timestamps as the issue start time.
- Changing per-card Alerts On/Off (`alarm_muted`), Suppress, or Snooze.
- Filtering Storage Inventory Issues, Capacity Report live tables, or Excel exports.
- Email / SMS notifications.
- Per-card cutoff dates.

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Surfaces | Popups **and** Active Issues (not popups-only) |
| Still-live pre-cutoff issues | Stay hidden |
| Mechanism | Admin date + grandfather currently open issues (not date-only first-seen, not event-log parse) |
| Safety valve | Admin On/Off toggle; Off shows everything including grandfathered |
| Admin placement | Branding tab — Health alerts block |
| Default date | 2026-08-14 |
| Default toggle | On |
| First upgrade | Apply default date and grandfather current leftovers automatically |

## Behavior

### Limit On

1. Issues whose fingerprint is **grandfathered** are hidden.
2. Issues first recorded **before** the cutoff local date are hidden.
3. Issues first recorded **on or after** the cutoff date, and not grandfathered, are shown (popups still require critical + monitor-on + not muted/paused/acknowledged, unchanged).
4. Hidden issues do not appear in Health Dashboard Active Issues for that card.

### Limit Off

- Date and grandfather list are kept.
- Popups and Active Issues behave as today (no date filter).

### Saving the date

- Persist `YYYY-MM-DD` (local calendar date; cutoff is that local midnight, inclusive for “on or after”).
- If Limit is On, union **all currently open** `health_issues` fingerprints (any severity) into the grandfathered set so leftovers open at save time stay hidden.
- Invalid/blank date: keep the previous valid date and show an Admin status error. Do not grandfather.

### Toggle

- **On (limit new issues):** apply filter.
- **Off:** show old and new; date field remains editable.
- Toggle persists immediately (same idea as Alerts On/Off).

### Upgrade / first run with no keys

- `limit_new_issues` defaults true.
- `active_issues_since` defaults `2026-08-14`.
- On the first health-alert evaluation after upgrade, persist those defaults and grandfather currently open fingerprints so the operator does not need to open Admin once.

### Recurrence

- When a fingerprint is no longer in the active issue set, drop it from grandfathered and `first_seen` (same prune idea as acknowledgements).
- If that problem returns later, it is treated as new.

### Moving the date back

- Does **not** un-grandfather fingerprints already hidden. They stay hidden until they clear.

## Admin UI

On **Admin → Branding**, add a **Health alerts** block (above or below White Label is fine; keep it on this tab because the setting is global):

- Switch: **Limit to new issues** — On / Off (default On). Hint: “Off shows all Active Issues and popups, including older ones.”
- Date: **Active issues since** — text or date entry, default `2026-08-14`.
- Button: **Save date** — persists date and, if Limit is On, grandfathers currently open issues.
- Status line: confirm save, or explain invalid date.

Per-card **Alerts** On/Off on Connections stays as-is.

## Architecture

| Unit | Responsibility |
|------|----------------|
| `health_alert_state.py` | Extend stored state; `visible_health_issues`; grandfather helpers; prune `first_seen` / grandfathered with acknowledgements |
| `HealthCard.to_api` | Emit filtered `health_issues` when limit is On (Health Dashboard Active Issues and dashboard overlays). Capacity Report / Storage Inventory keep raw `analyze_health`. |
| `list_popup_alerts` | Skip candidates whose fingerprint is not visible under the limit |
| `ui/admin_view.py` | Branding Health alerts block; load/save setting; on date save, grandfather from unfiltered HealthCard issues |
| `config.APP_VERSION` | `1.6.166` |

Raw `analyze_health` output stays unfiltered so Storage Inventory / other collectors keep full issue text.

### State (`HEALTH_ALERT_SETTING` JSON)

Existing keys unchanged. Add:

```json
{
  "acknowledged": [],
  "alarm_muted": {},
  "paused_until": {},
  "limit_new_issues": true,
  "active_issues_since": "2026-08-14",
  "first_seen": { "<fingerprint>": 1755129600.0 },
  "grandfathered": ["<fingerprint>", "..."]
}
```

- `issue_fingerprint(card_id, category, message)` — existing helper (use `fingerprint_message` when present, same as popup candidates).
- `first_seen`: unix timestamp when LaunchPad first observed that fingerprint after prune.
- `grandfathered`: fingerprints hidden by a baseline save / first upgrade.

`_normalize_state` must default missing keys (`limit_new_issues` true, date `2026-08-14`, empty maps/lists) without dropping old mute/ack data.

### Data flow

1. Health poll / `to_api`: for each issue, ensure `first_seen` is recorded if new; if limit On, omit issue when grandfathered or `local_date(first_seen) < active_issues_since`.
2. `list_popup_alerts`: after existing mute/pause/ack/monitor checks, drop candidates that fail the same visibility rule.
3. Admin Save date: write date; if limit On, add fingerprints from each Health Server `HealthCard`’s **unfiltered** `analyze_health` / `command_results` issues (not the filtered `to_api` list) to `grandfathered`.
4. Persist via existing `set_setting(HEALTH_ALERT_SETTING, dump_state(...))`.

### Error handling

- Corrupt JSON: `load_state` already falls back to empty state; then apply the same defaults as upgrade.
- Health Server not running on date save: persist the date anyway; grandfather an empty set; status warns that open issues will be grandfathered on the next health poll.
- Unparseable date: no write, Admin error.

## Testing

- Limit On + grandfathered fingerprint: omitted from `visible_health_issues` and `list_popup_alerts`.
- Limit Off: same fingerprint is visible even if grandfathered.
- New fingerprint on/after cutoff: visible; before cutoff via `first_seen`: hidden.
- Save date while On: currently open fingerprints become grandfathered.
- Prune: inactive fingerprint leaves grandfathered/`first_seen`; if it returns, it is visible (limit On, date today).
- `_normalize_state` on 1.6.165-shaped JSON (no new keys) yields defaults without losing `alarm_muted`.
- Admin markers: Limit switch, Active issues since, Save date on Branding panel.

## Version pins

Update `APP_VERSION` and the existing version-assert tests to **1.6.166**.
