# Capacity Report Email Schedule Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add in-app scheduled and on-demand email of the capacity Excel report via Gmail SMTP or local Outlook COM while LaunchPad is unlocked/open.

**Architecture:** Three core modules (`capacity_email_settings`, `capacity_email_scheduler`, `capacity_email_send`) plus Admin UI and Dashboard Export/poller wiring. Reuse `export_storage_capacity_excel`. Gmail password encrypted with admin crypto key. Scheduler lives on `DashboardView` (destroyed on lock → naturally pauses).

**Tech Stack:** Python 3, `smtplib`/`email`, `pywin32` (Windows Outlook COM), CustomTkinter Admin/Dashboard, SQLite settings, pytest.

**Spec:** `docs/superpowers/specs/2026-07-21-capacity-email-schedule-design.md`

## Global Constraints

- Runner: in-app only; LaunchPad must be open
- Transports: Gmail SMTP (`smtp.gmail.com:587` STARTTLS) and Outlook COM (`win32com`)
- Cadence modes: `daily` | `weekly` | `every_n_days`
- Recipients: multiple To (comma/semicolon); optional Cc
- While locked: no send (Dashboard gone); enable/send UI only exists unlocked; `enabled` may stay true and resume after unlock
- No OAuth, no Task Scheduler, no catch-up for closed-app misses
- Weekday uses `datetime.date.weekday()` (**Monday = 0**)
- Setting key: `capacity_email_settings`
- Add `pywin32` with Windows environment marker to `requirements.txt`
- Bump `APP_VERSION` one patch from the tip at Task 0 (final task)
- Commit at each task’s commit step

---

## File map

| File | Responsibility |
|------|----------------|
| `launchpad/capacity_email_settings.py` | Normalize/validate settings; parse addresses; load/save JSON; encrypt Gmail password |
| `launchpad/capacity_email_scheduler.py` | Pure `is_due(...)` math; optional thin poller helper |
| `launchpad/capacity_email_send.py` | Export temp xlsx → Gmail SMTP or Outlook COM → status update |
| `launchpad/ui/admin_view.py` | New **Capacity Email** Admin tab |
| `launchpad/ui/dashboard_view.py` | Export → Email Capacity Now; 60s schedule poll |
| `requirements.txt` | `pywin32` on Windows |
| `tests/test_capacity_email_settings.py` | Settings contracts |
| `tests/test_capacity_email_scheduler.py` | Due-window math |
| `tests/test_capacity_email_send.py` | Send orchestration with mocks |
| `launchpad/config.py` | Version bump |

---

### Task 0: Branch / worktree

**Files:** none (git only)

**Interfaces:**
- Consumes: current `feature/contingency-groups` (or main working branch tip with the design commit)
- Produces: `feature/capacity-email-schedule` worktree

- [ ] **Step 1: Create worktree**

```powershell
cd C:\Users\BrianColley\LaunchPad
git fetch origin
git worktree add .worktrees/capacity-email-schedule -b feature/capacity-email-schedule feature/contingency-groups
cd .worktrees/capacity-email-schedule
```

- [ ] **Step 2: Record baseline version**

```powershell
python -c "from launchpad.config import APP_VERSION; print(APP_VERSION)"
```

Note the printed version; final task bumps to the next patch (e.g. `1.6.41` → `1.6.42`, or `1.6.42` → `1.6.43` if Woodland Hills is already merged).

- [ ] **Step 3: No commit**

---

### Task 1: Settings normalize, address parse, load/save

**Files:**
- Create: `launchpad/capacity_email_settings.py`
- Test: `tests/test_capacity_email_settings.py`

**Interfaces:**
- Consumes: `encrypt_text` / `decrypt_text` from `launchpad.crypto`; `Database.get_setting` / `set_setting`
- Produces:
  - `CAPACITY_EMAIL_SETTING = "capacity_email_settings"`
  - `parse_address_list(text: str) -> list[str]`
  - `normalize_capacity_email_settings(raw: Any) -> dict`
  - `validate_for_send(settings: dict, *, crypto_key: bytes | None) -> list[str]` (warning/error strings; empty = ok)
  - `load_capacity_email_settings(db) -> dict`
  - `save_capacity_email_settings(db, settings: dict) -> dict`
  - `set_gmail_password(settings: dict, crypto_key: bytes, plaintext: str) -> dict`
  - `get_gmail_password(settings: dict, crypto_key: bytes) -> str`

Normalized dict shape:

```python
{
    "enabled": False,
    "provider": "gmail",  # or "outlook"
    "gmail_address": "",
    "gmail_password_encrypted": "",
    "to": [],
    "cc": [],
    "mode": "weekly",  # daily | weekly | every_n_days
    "time_local": "08:00",
    "weekday": 0,  # Monday=0
    "every_n_days": 7,
    "last_sent_at": "",
    "last_status": "",
    "last_error": "",
}
```

- [ ] **Step 1: Write failing tests**

Create `tests/test_capacity_email_settings.py`:

```python
from launchpad.capacity_email_settings import (
    CAPACITY_EMAIL_SETTING,
    get_gmail_password,
    normalize_capacity_email_settings,
    parse_address_list,
    set_gmail_password,
    validate_for_send,
)
from launchpad.crypto import derive_key, generate_salt


def test_setting_key():
    assert CAPACITY_EMAIL_SETTING == "capacity_email_settings"


def test_parse_address_list_splits_comma_semicolon_and_strips():
    assert parse_address_list(" a@x.com, b@y.com;c@z.com ,,") == [
        "a@x.com",
        "b@y.com",
        "c@z.com",
    ]


def test_normalize_defaults_and_clamps():
    s = normalize_capacity_email_settings({})
    assert s["enabled"] is False
    assert s["provider"] == "gmail"
    assert s["mode"] == "weekly"
    assert s["time_local"] == "08:00"
    assert s["weekday"] == 0
    assert s["every_n_days"] == 7
    assert s["to"] == []
    bad = normalize_capacity_email_settings(
        {"provider": "nope", "mode": "hourly", "weekday": 99, "every_n_days": 0, "time_local": "25:99"}
    )
    assert bad["provider"] == "gmail"
    assert bad["mode"] == "weekly"
    assert bad["weekday"] == 0
    assert bad["every_n_days"] == 1
    assert bad["time_local"] == "08:00"


def test_gmail_password_roundtrip_and_validate():
    key = derive_key("secret", generate_salt())
    s = normalize_capacity_email_settings(
        {"provider": "gmail", "gmail_address": "ops@gmail.com", "to": ["a@b.com"]}
    )
    assert validate_for_send(s, crypto_key=key)
    s = set_gmail_password(s, key, "app-pass-here")
    assert get_gmail_password(s, key) == "app-pass-here"
    assert validate_for_send(s, crypto_key=key) == []
    outlook = normalize_capacity_email_settings(
        {"provider": "outlook", "to": ["a@b.com"]}
    )
    assert validate_for_send(outlook, crypto_key=key) == []
```

- [ ] **Step 2: Run RED**

```powershell
python -m pytest tests/test_capacity_email_settings.py -v
```

Expected: FAIL (import / missing module).

- [ ] **Step 3: Implement `launchpad/capacity_email_settings.py`**

```python
"""Capacity email schedule settings: normalize, validate, persist."""

from __future__ import annotations

import json
import re
from typing import Any

from launchpad.crypto import decrypt_text, encrypt_text

CAPACITY_EMAIL_SETTING = "capacity_email_settings"

_PROVIDERS = frozenset({"gmail", "outlook"})
_MODES = frozenset({"daily", "weekly", "every_n_days"})
_TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def parse_address_list(text: str) -> list[str]:
    parts = re.split(r"[;,]+", str(text or ""))
    result: list[str] = []
    seen: set[str] = set()
    for part in parts:
        addr = part.strip()
        if not addr:
            continue
        key = addr.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(addr)
    return result


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _clamp_weekday(value: Any) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return 0
    return n if 0 <= n <= 6 else 0


def _clamp_every_n(value: Any) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return 7
    return n if n >= 1 else 1


def _normalize_time(value: Any) -> str:
    text = str(value or "").strip()
    if _TIME_RE.match(text):
        return text
    return "08:00"


def normalize_capacity_email_settings(raw: Any) -> dict:
    data = raw if isinstance(raw, dict) else {}
    provider = str(data.get("provider") or "gmail").strip().lower()
    if provider not in _PROVIDERS:
        provider = "gmail"
    mode = str(data.get("mode") or "weekly").strip().lower()
    if mode not in _MODES:
        mode = "weekly"
    to_raw = data.get("to")
    cc_raw = data.get("cc")
    if isinstance(to_raw, str):
        to_list = parse_address_list(to_raw)
    elif isinstance(to_raw, list):
        to_list = parse_address_list(";".join(str(x) for x in to_raw))
    else:
        to_list = []
    if isinstance(cc_raw, str):
        cc_list = parse_address_list(cc_raw)
    elif isinstance(cc_raw, list):
        cc_list = parse_address_list(";".join(str(x) for x in cc_raw))
    else:
        cc_list = []
    return {
        "enabled": _as_bool(data.get("enabled")),
        "provider": provider,
        "gmail_address": str(data.get("gmail_address") or "").strip(),
        "gmail_password_encrypted": str(data.get("gmail_password_encrypted") or ""),
        "to": to_list,
        "cc": cc_list,
        "mode": mode,
        "time_local": _normalize_time(data.get("time_local")),
        "weekday": _clamp_weekday(data.get("weekday")),
        "every_n_days": _clamp_every_n(data.get("every_n_days")),
        "last_sent_at": str(data.get("last_sent_at") or "").strip(),
        "last_status": str(data.get("last_status") or "").strip(),
        "last_error": str(data.get("last_error") or "").strip(),
    }


def set_gmail_password(settings: dict, crypto_key: bytes, plaintext: str) -> dict:
    out = normalize_capacity_email_settings(settings)
    out["gmail_password_encrypted"] = encrypt_text(crypto_key, plaintext or "")
    return out


def get_gmail_password(settings: dict, crypto_key: bytes) -> str:
    enc = str(settings.get("gmail_password_encrypted") or "")
    return decrypt_text(crypto_key, enc) if enc else ""


def validate_for_send(settings: dict, *, crypto_key: bytes | None) -> list[str]:
    s = normalize_capacity_email_settings(settings)
    errors: list[str] = []
    if not s["to"]:
        errors.append("At least one To address is required.")
    else:
        for addr in s["to"] + s["cc"]:
            if not _EMAIL_RE.match(addr):
                errors.append(f"Invalid email address: {addr}")
    if s["provider"] == "gmail":
        if not s["gmail_address"]:
            errors.append("Gmail address is required.")
        elif not _EMAIL_RE.match(s["gmail_address"]):
            errors.append("Gmail address is invalid.")
        if crypto_key is None:
            errors.append("LaunchPad must be unlocked to send via Gmail.")
        elif not get_gmail_password(s, crypto_key):
            errors.append("Gmail app password is required.")
    return errors


def load_capacity_email_settings(db) -> dict:
    raw = db.get_setting(CAPACITY_EMAIL_SETTING, "")
    if not raw:
        return normalize_capacity_email_settings({})
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return normalize_capacity_email_settings({})
    return normalize_capacity_email_settings(parsed)


def save_capacity_email_settings(db, settings: dict) -> dict:
    normalized = normalize_capacity_email_settings(settings)
    db.set_setting(CAPACITY_EMAIL_SETTING, json.dumps(normalized))
    return normalized
```

- [ ] **Step 4: Run GREEN**

```powershell
python -m pytest tests/test_capacity_email_settings.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add launchpad/capacity_email_settings.py tests/test_capacity_email_settings.py
git commit -m "Add capacity email settings normalize and persist helpers."
```

---

### Task 2: Schedule due-window math

**Files:**
- Create: `launchpad/capacity_email_scheduler.py`
- Test: `tests/test_capacity_email_scheduler.py`

**Interfaces:**
- Consumes: normalized settings dict from Task 1
- Produces: `is_capacity_email_due(settings: dict, now: datetime | None = None) -> bool`

Rules (local time):

- Not due if `enabled` is false.
- Parse `time_local` as today’s hour:minute; due only if `now.time() >= scheduled time`.
- **daily:** due if `last_sent_at` date (local) != today.
- **weekly:** due if `now.weekday() == weekday` and last sent is not the same ISO calendar date as today.
- **every_n_days:** if never sent, due when time reached; else due when `(today - last_sent_date).days >= every_n_days` and time reached.
- Invalid `last_sent_at` → treat as never sent.
- No catch-up beyond “due now if still in window and not yet sent for this occurrence.”

- [ ] **Step 1: Write failing tests**

```python
from datetime import datetime

from launchpad.capacity_email_scheduler import is_capacity_email_due
from launchpad.capacity_email_settings import normalize_capacity_email_settings


def _settings(**kwargs):
    base = {
        "enabled": True,
        "mode": "daily",
        "time_local": "08:00",
        "weekday": 0,
        "every_n_days": 7,
        "last_sent_at": "",
    }
    base.update(kwargs)
    return normalize_capacity_email_settings(base)


def test_disabled_never_due():
    assert not is_capacity_email_due(_settings(enabled=False), datetime(2026, 7, 21, 9, 0))


def test_daily_due_once_per_day_after_time():
    s = _settings(mode="daily", time_local="08:00")
    assert not is_capacity_email_due(s, datetime(2026, 7, 21, 7, 59))
    assert is_capacity_email_due(s, datetime(2026, 7, 21, 8, 0))
    s["last_sent_at"] = "2026-07-21T08:05:00"
    assert not is_capacity_email_due(s, datetime(2026, 7, 21, 18, 0))
    assert is_capacity_email_due(s, datetime(2026, 7, 22, 8, 0))


def test_weekly_monday_only():
    s = _settings(mode="weekly", weekday=0, time_local="08:00")  # 2026-07-20 is Monday
    assert is_capacity_email_due(s, datetime(2026, 7, 20, 8, 0))
    assert not is_capacity_email_due(s, datetime(2026, 7, 21, 8, 0))  # Tuesday


def test_every_n_days():
    s = _settings(mode="every_n_days", every_n_days=3, time_local="08:00", last_sent_at="2026-07-18T08:00:00")
    assert not is_capacity_email_due(s, datetime(2026, 7, 20, 8, 0))  # 2 days
    assert is_capacity_email_due(s, datetime(2026, 7, 21, 8, 0))  # 3 days
```

- [ ] **Step 2: Run RED**

```powershell
python -m pytest tests/test_capacity_email_scheduler.py -v
```

Expected: FAIL.

- [ ] **Step 3: Implement `launchpad/capacity_email_scheduler.py`**

```python
"""Capacity email schedule due-window helpers."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from launchpad.capacity_email_settings import normalize_capacity_email_settings


def _parse_last_sent(value: str) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return datetime.fromisoformat(text).replace(tzinfo=None)
    except ValueError:
        return None


def _time_reached(now: datetime, time_local: str) -> bool:
    hour_s, minute_s = time_local.split(":")
    return (now.hour, now.minute) >= (int(hour_s), int(minute_s))


def is_capacity_email_due(settings: dict[str, Any], now: datetime | None = None) -> bool:
    s = normalize_capacity_email_settings(settings)
    if not s["enabled"]:
        return False
    current = now or datetime.now()
    if not _time_reached(current, s["time_local"]):
        return False
    last = _parse_last_sent(s["last_sent_at"])
    last_date = last.date() if last else None
    today = current.date()
    mode = s["mode"]
    if mode == "daily":
        return last_date != today
    if mode == "weekly":
        if current.weekday() != int(s["weekday"]):
            return False
        return last_date != today
    # every_n_days
    if last_date is None:
        return True
    return (today - last_date).days >= int(s["every_n_days"])
```

- [ ] **Step 4: Run GREEN**

```powershell
python -m pytest tests/test_capacity_email_scheduler.py tests/test_capacity_email_settings.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add launchpad/capacity_email_scheduler.py tests/test_capacity_email_scheduler.py
git commit -m "Add capacity email schedule due-window math."
```

---

### Task 3: Send orchestration (Gmail SMTP + Outlook COM)

**Files:**
- Create: `launchpad/capacity_email_send.py`
- Modify: `requirements.txt` (add pywin32 Windows marker)
- Test: `tests/test_capacity_email_send.py`

**Interfaces:**
- Consumes: `export_storage_capacity_excel`, settings helpers, crypto key, `Database`
- Produces:
  - `send_capacity_email(db, crypto_key, settings=None, *, progress=None, export_fn=None, smtp_send_fn=None, outlook_send_fn=None) -> dict`
  - Return dict: `{"ok": bool, "settings": dict, "path": str, "error": str}`
  - Updates `last_sent_at` / `last_status` / `last_error` via `save_capacity_email_settings` on success or failure
  - Subject: `LaunchPad Capacity Report — YYYY-MM-DD`
  - Attachment name: `Storage_Capacity_Report_YYYYMMDD_HHMM.xlsx` under `TEMP_DIR` (from `launchpad.config`)
  - Delete temp file after successful send only

Inject `export_fn` / `smtp_send_fn` / `outlook_send_fn` for tests (defaults call real implementations).

- [ ] **Step 1: Add dependency line to `requirements.txt`**

```
pywin32>=306; platform_system=="Windows"
```

- [ ] **Step 2: Write failing tests**

```python
from pathlib import Path
from types import SimpleNamespace

from launchpad.capacity_email_send import send_capacity_email
from launchpad.capacity_email_settings import (
    normalize_capacity_email_settings,
    set_gmail_password,
)
from launchpad.crypto import derive_key, generate_salt


class _FakeDb:
    def __init__(self):
        self.values = {}

    def get_setting(self, key, default=""):
        return self.values.get(key, default)

    def set_setting(self, key, value):
        self.values[key] = value


def test_send_gmail_success_updates_status_and_deletes_temp(tmp_path, monkeypatch):
    key = derive_key("pw", generate_salt())
    db = _FakeDb()
    settings = set_gmail_password(
        normalize_capacity_email_settings(
            {
                "provider": "gmail",
                "gmail_address": "ops@gmail.com",
                "to": ["a@b.com"],
                "cc": ["c@d.com"],
            }
        ),
        key,
        "app-pass",
    )
    created = tmp_path / "Storage_Capacity_Report_20260721_0800.xlsx"
    created.write_bytes(b"xlsx")

    def fake_export(db_, crypto_key, output_path, progress=None):
        Path(output_path).write_bytes(b"xlsx")
        return SimpleNamespace(
            path=Path(output_path),
            filled_count=2,
            pool_filled_count=1,
            pool_rows_written=3,
            error_count=0,
            extra_rows=0,
            generated_at="2026-07-21T08:00:00",
        )

    sent = {}

    def fake_smtp(**kwargs):
        sent.update(kwargs)
        return None

    result = send_capacity_email(
        db,
        key,
        settings,
        export_fn=fake_export,
        smtp_send_fn=fake_smtp,
        temp_dir=tmp_path,
    )
    assert result["ok"] is True
    assert sent["to"] == ["a@b.com"]
    assert sent["cc"] == ["c@d.com"]
    assert "LaunchPad Capacity Report" in sent["subject"]
    assert not Path(result["path"]).exists()  # deleted after success
    saved = normalize_capacity_email_settings(__import__("json").loads(db.values["capacity_email_settings"]))
    assert saved["last_status"].startswith("Sent")
    assert saved["last_sent_at"]


def test_send_outlook_uses_outlook_transport(tmp_path):
    key = derive_key("pw", generate_salt())
    db = _FakeDb()
    settings = normalize_capacity_email_settings(
        {"provider": "outlook", "to": ["a@b.com"]}
    )
    called = {}

    def fake_export(db_, crypto_key, output_path, progress=None):
        Path(output_path).write_bytes(b"xlsx")
        return SimpleNamespace(
            path=Path(output_path),
            filled_count=1,
            pool_filled_count=0,
            pool_rows_written=0,
            error_count=0,
            extra_rows=0,
            generated_at="2026-07-21T08:00:00",
        )

    def fake_outlook(**kwargs):
        called.update(kwargs)

    result = send_capacity_email(
        db,
        key,
        settings,
        export_fn=fake_export,
        outlook_send_fn=fake_outlook,
        temp_dir=tmp_path,
    )
    assert result["ok"] is True
    assert called["to"] == ["a@b.com"]
```

- [ ] **Step 3: Run RED**

```powershell
python -m pytest tests/test_capacity_email_send.py -v
```

Expected: FAIL.

- [ ] **Step 4: Implement `launchpad/capacity_email_send.py`**

Implement:

- `_build_subject(now) -> str`
- `_build_body(export_result) -> str`
- `_send_via_gmail_smtp(*, host, port, user, password, from_addr, to, cc, subject, body, attachment_path)`
- `_send_via_outlook_com(*, to, cc, subject, body, attachment_path)` using `win32com.client.Dispatch("Outlook.Application")` — raise clear `RuntimeError` if import/COM fails
- `send_capacity_email(...)` as specified: validate → export to `temp_dir / filename` → transport → update settings → unlink on success

Gmail SMTP sketch:

```python
import smtplib
from email.message import EmailMessage

msg = EmailMessage()
msg["Subject"] = subject
msg["From"] = from_addr
msg["To"] = ", ".join(to)
if cc:
    msg["Cc"] = ", ".join(cc)
msg.set_content(body)
msg.add_attachment(
    Path(attachment_path).read_bytes(),
    maintype="application",
    subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    filename=Path(attachment_path).name,
)
with smtplib.SMTP("smtp.gmail.com", 587, timeout=60) as smtp:
    smtp.starttls()
    smtp.login(user, password)
    smtp.send_message(msg)
```

Outlook sketch:

```python
import win32com.client

outlook = win32com.client.Dispatch("Outlook.Application")
mail = outlook.CreateItem(0)
mail.To = "; ".join(to)
mail.CC = "; ".join(cc)
mail.Subject = subject
mail.Body = body
mail.Attachments.Add(str(attachment_path))
mail.Send()
```

- [ ] **Step 5: Run GREEN**

```powershell
python -m pytest tests/test_capacity_email_send.py tests/test_capacity_email_settings.py tests/test_capacity_email_scheduler.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add launchpad/capacity_email_send.py requirements.txt tests/test_capacity_email_send.py
git commit -m "Add capacity email send via Gmail SMTP and Outlook COM."
```

---

### Task 4: Admin UI + Dashboard Export + schedule poller

**Files:**
- Modify: `launchpad/ui/admin_view.py` (add **Capacity Email** tab)
- Modify: `launchpad/ui/dashboard_view.py` (Export menu item + 60s poll)

**Interfaces:**
- Consumes: load/save/set_gmail_password/validate_for_send/send_capacity_email/is_capacity_email_due
- Produces: operator-facing configure + Send now + automatic due sends while dashboard is alive

**Admin tab fields**

- Provider: Gmail | Outlook (segmented or OptionMenu)
- Gmail address + password entry (show only when Gmail)
- To / Cc text entries (hint: comma or semicolon)
- Mode OptionMenu: Daily / Weekly / Every N days
- Weekday OptionMenu (Mon–Sun → 0–6) visible for Weekly
- Every N days spin/entry visible for Every N days
- Time local `HH:MM` entry
- Enable schedule checkbox
- Save button; Send now button
- Labels for last_sent / last_status / last_error

**Dashboard**

- Export menu: add `Email Capacity Now` calling same send path on a worker thread (status_label updates like Capacity export).
- On `DashboardView.__init__` (after existing timers): start `_schedule_capacity_email_timer` with `after(60_000, ...)`.
- Tick: if `is_capacity_email_due(load...)`: spawn daemon thread to `send_capacity_email`; on completion `after(0, ...)` refresh status_label briefly.
- Destroy/cancel timer in existing cleanup if present; otherwise store id and cancel when view destroyed if hook exists — follow SSH status timer pattern (`_ssh_status_timer`).

- [ ] **Step 1: Implement Admin Capacity Email tab**

In `_build_authenticated_ui` (or wherever tabs are created), add:

```python
email_tab = self.tabs.add("Capacity Email")
email_tab.grid_columnconfigure(0, weight=1)
self._build_capacity_email_panel(email_tab)
```

Implement `_build_capacity_email_panel`, `_load_capacity_email_form`, `_save_capacity_email_form`, `_send_capacity_email_now` mirroring branding panel style (CTkFrame, labels, entries). On Save: read form → normalize → if password field non-empty call `set_gmail_password` else keep existing encrypted → `save_capacity_email_settings`. On Send now: save first, then thread `send_capacity_email`.

- [ ] **Step 2: Wire Dashboard export + poller**

In `_open_export_excel_menu`:

```python
menu.add_command(label="Email Capacity Now", command=self._email_capacity_now)
```

Implement `_email_capacity_now` similar to `_export_capacity_excel` but without save dialog — calls `send_capacity_email(self.db, self.crypto_key, progress=...)`.

Add poller methods using `CAPACITY_EMAIL_POLL_MS = 60_000`.

- [ ] **Step 3: Manual smoke (optional in agent)** — skip automated UI tests.

- [ ] **Step 4: Run unit suites still green**

```powershell
python -m pytest tests/test_capacity_email_settings.py tests/test_capacity_email_scheduler.py tests/test_capacity_email_send.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add launchpad/ui/admin_view.py launchpad/ui/dashboard_view.py
git commit -m "Wire capacity email Admin settings and Dashboard schedule poller."
```

---

### Task 5: Version bump and full regression

**Files:**
- Modify: `launchpad/config.py`

**Interfaces:**
- Consumes: Tasks 1–4
- Produces: `APP_VERSION` next patch from Task 0 baseline

- [ ] **Step 1: Bump version**

Set `APP_VERSION` to baseline+1 patch (e.g. if Task 0 printed `1.6.42`, set `1.6.43`).

- [ ] **Step 2: Full suite**

```powershell
python -m pytest tests
```

Expected: all PASS.

- [ ] **Step 3: Commit**

```powershell
git add launchpad/config.py
git commit -m "Bump version for capacity email schedule."
```

---

## Spec coverage checklist

| Requirement | Task |
|-------------|------|
| Settings JSON + encrypted Gmail password | Task 1 |
| Daily / weekly / every N days due math | Task 2 |
| Gmail SMTP + Outlook COM + export attach | Task 3 |
| pywin32 Windows dependency | Task 3 |
| Admin configure UI + Send now | Task 4 |
| Export → Email Capacity Now | Task 4 |
| In-app 60s poll while dashboard unlocked | Task 4 |
| No fire when locked (dashboard destroyed) | Task 4 |
| Version bump | Task 5 |
| No OAuth / Task Scheduler / catch-up | (non-goals — do not implement) |
