# Scheduled Capacity Report Email (Gmail SMTP + Outlook COM)

**Date:** 2026-07-21  
**Status:** Approved for implementation  
**App version target:** Next patch on the implementation branch (after current tip at start of work)  
**Depends on:** `export_storage_capacity_excel` (`launchpad/capacity_export.py`); encrypted settings / admin unlock (`launchpad/database.py`, `launchpad/crypto.py`)

## Problem

Operators need the storage capacity Excel report emailed on a recurring cadence. LaunchPad can already export the workbook manually (Export → Capacity) but has no mail transport and no in-app schedule. Operators use **Gmail** and/or **local Outlook** on Windows.

## Goals

- Email the same capacity `.xlsx` that Capacity Excel export produces (live SSH fill + pool sheets).
- Support two transports: **Gmail SMTP** and **local Outlook COM**.
- In-app schedule while LaunchPad is **open**: daily, weekly, or every N days (operator chooses).
- Multiple **To** addresses; optional **Cc** list.
- **Send now** for testing, plus last-sent / last-error status in UI.
- Schedule fires only when LaunchPad is **unlocked**; while locked, schedule does not fire and the enable control is disabled.

## Non-goals

- Windows Task Scheduler / send while LaunchPad is closed.
- OAuth (Google / Microsoft Graph).
- Outlook SMTP / Exchange online without desktop Outlook.
- Non-Windows Outlook paths.
- Choosing a subset of inventory sites (reuse the same SSH card set as Capacity Excel).
- Rich HTML digests, charts in the body, or PDF substitute.
- Catch-up backlog for missed occurrences while the app was closed.

## Operator decisions (locked)

| Choice | Decision |
|--------|----------|
| Runner | In-app only (LaunchPad must be open) |
| Transports | Gmail SMTP + local Outlook COM |
| Cadence | Daily **or** weekly **or** every N days (operator selects mode) |
| Recipients | Multiple To (comma/semicolon); optional Cc |
| Unlock | Enable control disabled while locked; never fire while locked; if `enabled` was true, resume firing after unlock without forcing a re-toggle |
| Delivery shape | Settings panel + shared mailer; Export menu “Email Capacity Now” |

## Architecture

```
┌─────────────────────┐     ┌──────────────────────────┐
│ Capacity Email UI   │────▶│ capacity_email_settings  │  (DB settings JSON)
│ (Admin/settings +   │     │ + encrypted Gmail secret │
│  Export → Email Now)│     └────────────┬─────────────┘
└─────────┬───────────┘                  │
          │ Send now / schedule due      ▼
          │              ┌───────────────────────────┐
          └─────────────▶│ capacity_email_send       │
                         │ 1) export_storage_…xlsx   │
                         │ 2) smtp_gmail | outlook   │
                         └───────────────────────────┘
          ┌───────────────────────────┐
          │ capacity_email_scheduler  │  ~60s poll while unlocked
          │ due? → send once / window │
          └───────────────────────────┘
```

### Modules (proposed)

| Module | Responsibility |
|--------|----------------|
| `launchpad/capacity_email_settings.py` | Normalize/validate settings; setting key; encrypt/decrypt Gmail password helpers |
| `launchpad/capacity_email_send.py` | Build temp workbook via `export_storage_capacity_excel`; dispatch Gmail SMTP or Outlook COM; subject/body; cleanup |
| `launchpad/capacity_email_scheduler.py` | Due-window math; poller hook; `last_sent_at` update; skip when locked |
| UI (Admin settings section + dashboard Export menu) | Configure, enable, Send now, status |

## Transport details

### Gmail SMTP

- Host `smtp.gmail.com`, port `587`, STARTTLS.
- Auth: Gmail address + **App Password** (required when Google 2FA is on).
- Password stored encrypted under the admin crypto key (same pattern as SSH card secrets).
- From = configured Gmail address.

### Outlook COM

- Windows only; requires Outlook installed and a configured profile.
- Create `MailItem` via `win32com.client`, attach workbook, set To/Cc/Subject/Body, `Send()`.
- No SMTP password stored for Outlook.
- From = Outlook’s default send account (optional future: pick account; out of scope for v1).
- Clear error if Outlook is missing or COM fails.

## Schedule model

Settings fields (conceptual):

- `enabled: bool`
- `provider: "gmail" | "outlook"`
- `gmail_address: str`, `gmail_password_encrypted: str` (Gmail only)
- `to: list[str]`, `cc: list[str]`
- `mode: "daily" | "weekly" | "every_n_days"`
- `time_local: "HH:MM"` (24h local wall clock)
- `weekday: 0–6` (weekly only; Monday=0 or match existing app convention — lock in plan to `time.strftime` weekday)
- `every_n_days: int` (≥ 1; every_n_days mode)
- `last_sent_at: ISO-8601 or empty`
- `last_status: str`, `last_error: str`

**Due rules**

- Poll about once per minute while the main window is alive and unlocked.
- A window is due when local date/time matches the schedule and `last_sent_at` is not already in this occurrence’s window (e.g. same local calendar day for daily; same ISO week+weekday for weekly; at least N midnights since last send date for every_n_days, and time-of-day reached).
- If LaunchPad was closed past the due time: **no catch-up**; wait for the next occurrence.
- If locked at poll time: do not send; do not advance `last_sent_at`.

**Unlock / enable**

- While locked: Enable checkbox disabled; Send now disabled; scheduler does not fire.
- `enabled` may remain `true` in stored settings; UI shows “Paused while locked” when `enabled` and locked.
- After unlock: if `enabled`, scheduler may fire again when next due (including “due now” if still in window and not yet sent for that occurrence).

## Email content

- **Subject:** `LaunchPad Capacity Report — YYYY-MM-DD` (local date of send).
- **Body:** Short plain text: generated timestamp, filled site count, pool-filled count, error count, extra rows (from export result fields).
- **Attachment:** `Storage_Capacity_Report_YYYYMMDD_HHMM.xlsx` (same naming spirit as manual export).
- Temp path under system/app temp; delete after successful send. On failure, leave file and surface path in `last_error` / status for debugging.

## UI

1. **Capacity Email** settings section (prefer Admin settings area alongside other app settings):
   - Provider radio/select: Gmail | Outlook
   - Gmail fields shown only for Gmail
   - To, Cc (multi-address text)
   - Mode + weekday / N / time
   - Enable schedule
   - Send now
   - Last sent / last status / last error (read-only)
2. **Export** menu: **Email Capacity Now** (same code path as Send now; requires unlock).

Validation before send: provider configured; ≥1 valid To; Gmail password present when provider=gmail; crypto unlocked.

## Testing

- Unit: schedule due math (daily/weekly/every_n_days); address parsing; settings normalize.
- Unit: Gmail SMTP path with mocked `smtplib`; Outlook path with mocked COM (or skip on non-Windows).
- Integration-lite: send orchestration calls export with a temp path and invokes the chosen transport mock.
- UI not required for first automated coverage beyond settings round-trip if costly.

## Out of scope follow-ups

- Task Scheduler unattended sends
- OAuth / Graph
- Per-site recipient routing
- Auto-resume catch-up for missed closed-app windows
