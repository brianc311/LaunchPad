# Call Home CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a HealthServer Call Home CLI page that applies shared contact and per-array location, optionally adds an SMTP server, and removes the SMTP stack, shipping as **1.6.178**.

**Architecture:** Pure ops in `launchpad/call_home_cli_ops.py` parse live IBM email/Call Home state and build Apply/Remove `SnapStep`s. `launchpad/call_home_cli.py` is the page. `health_server.py` routes SSH I/O only and must never log an unmasked `-password`. Dashboard opens the page with `_open_sync_browser_report`.

**Tech Stack:** Python, HealthServer HTML/JS, existing `_snap_run_command` / `SnapStep` / `cli_token` / `parse_svc_call_home`, pytest.

**Spec:** `docs/superpowers/specs/2026-08-18-call-home-cli-design.md`

## Global Constraints

- APP_VERSION bump to **1.6.178** only in the final version task. Do not bump in Tasks 1–3.
- IBM `SVC_PROFILES` SSH cards with a non-empty host only. No HPE / Dell / DS8884.
- Two Run kinds: **Apply fields** and **Remove SMTP**. Apply Preview hash must not unlock Run Remove, and vice versa.
- Apply CLI order: contact `chemail` → location `chemail` → optional `mkemailserver`. No `chsystem`, `mkemailuser`, `startemail`, `chcloudcallhome`, or `chemailserver`.
- Apply sets **non-empty flags only**. Do not send `-nocontact` or blank fields.
- If SMTP add is requested and live `lsemailserver` has any row, that array is not runnable and Run sends **no** commands on that array.
- Remove SMTP: `stopemail` → each `rmemailuser` → each `rmemailserver`. Leave cloud Call Home, contact, and location.
- SMTP password is never stored in the LaunchPad DB. Preview JSON, confirm modal, and logs show `********`. Real SSH uses the typed password.
- Stop **that array** on the first real CLI error; continue the next array; no rollback.
- Array IP is `https://{host}` **outside** the checkbox `<label>` (`target="_blank"` `rel="noopener"`).
- Fetch `try/catch` so Load / Preview / Run never sit on a spinner forever.
- Mutating SSH and fleet decrypt never run on the Tk UI thread. Header opener uses `_open_sync_browser_report`.
- Do not put CLI assembly in `health_server.py` beyond routing and SSH I/O.
- Place imports at the top of modules (no inline imports).
- Windows PowerShell commits (`git commit -m "..."`); commit at each task commit step.
- Prefer TDD: failing test → implement → pass → commit.
- Do not commit `.superpowers/sdd*` scratch, `LaunchPad-Install/`, or install zips.
- Work from a feature branch off current `main`. Create an isolated worktree via using-git-worktrees at execution time. Branch name: `feature/call-home-cli`.

## File structure

| File | Responsibility |
|------|----------------|
| `launchpad/call_home_cli_ops.py` | Quote/mask, parse live state, Apply/Remove steps, preview hash, masked runner |
| `tests/test_call_home_cli_ops.py` | Unit tests for ops |
| `launchpad/call_home_cli.py` | Page HTML/JS (`CALL_HOME_CLI_PATH`, `CALL_HOME_CLI_HTML`) |
| `tests/test_call_home_cli_page.py` | Page contract tests |
| `launchpad/health_server.py` | GET/POST routes, SSH I/O, `open_call_home_cli`, Health nav link |
| `tests/test_health_server_call_home_cli.py` | API tests with fake SSH |
| `launchpad/ui/dashboard_view.py` | Header button + opener |
| `tests/test_dashboard_ui_freeze.py` | Add `_open_call_home_cli` to `HEADER_OPENERS` |
| `launchpad/config.py` + version pins | `1.6.178` (Task 4 only) |

---

### Task 1: Ops — quote, parse, Apply/Remove steps, hash, runner

**Files:**
- Create: `launchpad/call_home_cli_ops.py`
- Create: `tests/test_call_home_cli_ops.py`

**Interfaces:**
- Consumes: `SnapStep`, `cli_token` from `launchpad.contingency_snap_create`; `_get`, `_table_records` from `launchpad.flashsystem_fc`; `_parse_key_values` from `launchpad.flashsystem_parse`; `parse_svc_call_home` from `launchpad.system_connectivity`
- Produces:
  - `CONTACT_KEYS: tuple[str, ...]` = `("name", "reply", "primary", "alternate")`
  - `LOCATION_KEYS: tuple[str, ...]` = `("company", "street", "city", "state", "postal", "country", "comment")`
  - `SMTP_KEYS: tuple[str, ...]` = `("ip", "port", "username", "password")`
  - `quote_cli_arg(value: str) -> str`
  - `mask_password_in_cmd(cmd: str) -> str`
  - `is_email_already_stopped(text: str) -> bool`
  - `smtp_add_requested(smtp: dict | None) -> bool`
  - `trim_fields(data: dict | None, keys: tuple[str, ...]) -> dict[str, str]`
  - `parse_email_servers(output: str) -> list[dict[str, str]]` keys `id`, `name`, `ip`, `port`, `username`
  - `parse_email_users(output: str) -> list[dict[str, str]]` keys `id`, `name`, `address`, `user_type`
  - `parse_lssystem_contact_location(output: str) -> tuple[dict[str, str], dict[str, str]]`
  - `format_smtp_summary(servers: list[dict], users: list[dict]) -> str`
  - `collect_call_home_state(run_cmd: Callable[[str], str]) -> dict[str, Any]` keys `ok`, `error`, `cloud_configured`, `cloud_status`, `cloud_details`, `servers`, `users`, `contact`, `location`, `smtp_summary`
  - `build_apply_array_steps(*, contact: dict, location: dict, smtp: dict, servers: list[dict]) -> tuple[list[SnapStep], list[str], bool]`
  - `build_remove_array_steps(*, users: list[dict], servers: list[dict]) -> tuple[list[SnapStep], list[str], bool]`
  - `preview_hash(kind: str, payload: dict) -> str` where `kind` is `"apply"` or `"remove"`
  - `masked_steps_payload(steps: list[SnapStep]) -> list[dict]`
  - `run_call_home_steps(steps: list[SnapStep], run_cmd: Callable[[str], str]) -> dict[str, Any]`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_call_home_cli_ops.py`:

```python
from launchpad.call_home_cli_ops import (
    build_apply_array_steps,
    build_remove_array_steps,
    collect_call_home_state,
    is_email_already_stopped,
    mask_password_in_cmd,
    masked_steps_payload,
    parse_email_servers,
    parse_email_users,
    parse_lssystem_contact_location,
    preview_hash,
    quote_cli_arg,
    run_call_home_steps,
    smtp_add_requested,
)


SERVER_SAMPLE = """id:name:IP_address:port:username
0:emailserver0:172.29.62.98:25:avijaytc
"""

USER_SAMPLE = """id:name:address:user_type
0:support:callhome0@de.ibm.com:support
1:local:EISSAN-Alerts@walgreens.com:local
"""

LSYSTEM_SAMPLE = """id:0001
name:V5kHOU-g3v1
email_contact:SANArch
email_reply:sanarch@walgreens.com
email_contact_primary:224-567-8901
email_contact_alternate:224-567-8902
email_organization:Walgreens
email_street:1805 GREENS RD
email_city:Houston
email_state:TX
email_zip:77032
email_country:US
email_contact_location:Walgreens Houston 1805 GREENS RD
"""

CLOUD_SAMPLE = """id:status
0:active
"""


def test_quote_cli_arg_quotes_email_and_spaces():
    assert quote_cli_arg("25") == "25"
    assert quote_cli_arg("172.29.62.98") == "172.29.62.98"
    assert quote_cli_arg("sanarch@walgreens.com") == '"sanarch@walgreens.com"'
    assert quote_cli_arg("Walgreens Houston") == '"Walgreens Houston"'


def test_quote_cli_arg_rejects_quote_and_newline():
    try:
        quote_cli_arg('bad"value')
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError")
    try:
        quote_cli_arg("bad\nvalue")
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError")


def test_mask_password_and_already_stopped():
    cmd = 'svctask mkemailserver -ip 1.2.3.4 -port 25 -username avijaytc -password "s3cret"'
    masked = mask_password_in_cmd(cmd)
    assert "s3cret" not in masked
    assert "********" in masked
    assert is_email_already_stopped("CMMVC6186E The e-mail service is already stopped.")
    assert not is_email_already_stopped("CMMVC0000E some other failure")


def test_parse_servers_users_and_lssystem():
    servers = parse_email_servers(SERVER_SAMPLE)
    assert servers[0]["ip"] == "172.29.62.98"
    assert servers[0]["port"] == "25"
    assert servers[0]["username"] == "avijaytc"
    users = parse_email_users(USER_SAMPLE)
    assert users[0]["address"] == "callhome0@de.ibm.com"
    assert users[1]["user_type"] == "local"
    contact, location = parse_lssystem_contact_location(LSYSTEM_SAMPLE)
    assert contact["name"] == "SANArch"
    assert contact["reply"] == "sanarch@walgreens.com"
    assert location["company"] == "Walgreens"
    assert location["comment"] == "Walgreens Houston 1805 GREENS RD"
    assert location["postal"] == "77032"


def test_collect_uses_four_commands():
    calls: list[str] = []

    def run_cmd(command: str) -> str:
        calls.append(command)
        if "lscloudcallhome" in command:
            return CLOUD_SAMPLE
        if "lsemailserver" in command:
            return SERVER_SAMPLE
        if "lsemailuser" in command:
            return USER_SAMPLE
        if "lssystem" in command:
            return LSYSTEM_SAMPLE
        raise AssertionError(command)

    state = collect_call_home_state(run_cmd)
    assert state["ok"] is True
    assert state["cloud_status"].lower() == "active"
    assert "172.29.62.98:25" in state["smtp_summary"]
    assert any("lscloudcallhome" in c for c in calls)
    assert any("lsemailserver" in c for c in calls)
    assert any("lsemailuser" in c for c in calls)
    assert any(c.strip() == "svcinfo lssystem" or c.startswith("svcinfo lssystem") for c in calls)
    assert not any("lsvolumegroupmember" in c for c in calls)
    assert len([c for c in calls if c.startswith("svcinfo ")]) <= 8


def test_apply_contact_location_then_mkemailserver():
    steps, warnings, runnable = build_apply_array_steps(
        contact={
            "name": "SANArch",
            "reply": "sanarch@walgreens.com",
            "primary": "224-567-8901",
            "alternate": "",
        },
        location={
            "company": "Walgreens",
            "street": "1805 GREENS RD",
            "city": "Houston",
            "state": "TX",
            "postal": "77032",
            "country": "US",
            "comment": "Walgreens Houston",
        },
        smtp={
            "ip": "172.29.62.98",
            "port": "25",
            "username": "avijaytc",
            "password": "s3cret",
        },
        servers=[],
    )
    assert runnable is True
    assert warnings == []
    assert [s.kind for s in steps] == ["chemail", "chemail", "mkemailserver"]
    assert steps[0].cmd.startswith("svctask chemail")
    assert "-contact" in steps[0].cmd and "-reply" in steps[0].cmd
    assert "-organization" in steps[1].cmd and "-location" in steps[1].cmd
    assert "svctask mkemailserver -ip 172.29.62.98 -port 25" in steps[2].cmd
    assert "-username avijaytc" in steps[2].cmd
    assert "s3cret" in steps[2].cmd
    assert all("mkemailuser" not in s.cmd for s in steps)
    assert all("startemail" not in s.cmd for s in steps)
    assert all("chcloudcallhome" not in s.cmd for s in steps)
    assert all("chsystem" not in s.cmd for s in steps)
    payload = masked_steps_payload(steps)
    assert "s3cret" not in payload[2]["cmd"]
    assert "********" in payload[2]["cmd"]


def test_apply_skips_empty_smtp_and_blocks_existing_server():
    steps, warnings, runnable = build_apply_array_steps(
        contact={"name": "SANArch", "reply": "", "primary": "", "alternate": ""},
        location={
            "company": "",
            "street": "",
            "city": "",
            "state": "",
            "postal": "",
            "country": "",
            "comment": "",
        },
        smtp={"ip": "", "port": "", "username": "", "password": ""},
        servers=[],
    )
    assert runnable is True
    assert [s.kind for s in steps] == ["chemail"]
    assert "mkemailserver" not in steps[0].cmd

    steps2, warnings2, runnable2 = build_apply_array_steps(
        contact={"name": "SANArch", "reply": "", "primary": "", "alternate": ""},
        location={
            "company": "",
            "street": "",
            "city": "",
            "state": "",
            "postal": "",
            "country": "",
            "comment": "",
        },
        smtp={
            "ip": "172.29.62.98",
            "port": "25",
            "username": "avijaytc",
            "password": "s3cret",
        },
        servers=[{"id": "0", "name": "emailserver0", "ip": "1.2.3.4", "port": "25", "username": ""}],
    )
    assert runnable2 is False
    assert steps2 == []
    assert any("already exists" in w.lower() for w in warnings2)

    steps3, warnings3, runnable3 = build_apply_array_steps(
        contact={"name": "", "reply": "", "primary": "", "alternate": ""},
        location={
            "company": "",
            "street": "",
            "city": "",
            "state": "",
            "postal": "",
            "country": "",
            "comment": "",
        },
        smtp={"ip": "", "port": "", "username": "", "password": ""},
        servers=[],
    )
    assert runnable3 is False
    assert any("nothing to apply" in w.lower() for w in warnings3)
    assert smtp_add_requested({"ip": "1.2.3.4", "port": "", "username": "", "password": ""}) is True
    assert smtp_add_requested({"ip": "", "port": "", "username": "", "password": ""}) is False


def test_remove_order_stop_users_servers():
    steps, warnings, runnable = build_remove_array_steps(
        users=[
            {"id": "0", "name": "support", "address": "callhome0@de.ibm.com", "user_type": "support"},
            {"id": "1", "name": "local", "address": "a@b.com", "user_type": "local"},
        ],
        servers=[{"id": "0", "name": "emailserver0", "ip": "1.2.3.4", "port": "25", "username": ""}],
    )
    assert runnable is True
    assert [s.kind for s in steps] == [
        "stopemail",
        "rmemailuser",
        "rmemailuser",
        "rmemailserver",
    ]
    assert steps[0].cmd == "svctask stopemail"
    assert steps[1].cmd == "svctask rmemailuser 0"
    assert steps[3].cmd == "svctask rmemailserver 0"

    empty_steps, _, empty_ok = build_remove_array_steps(users=[], servers=[])
    assert empty_ok is True
    assert [s.kind for s in empty_steps] == ["stopemail"]


def test_preview_hash_kind_and_password_not_plaintext():
    payload = {
        "contact": {"name": "SANArch", "reply": "a@b.com", "primary": "", "alternate": ""},
        "smtp": {"ip": "1.2.3.4", "port": "25", "username": "u", "password": "s3cret"},
        "arrays": [
            {
                "card_id": 2,
                "location": {
                    "company": "Wags",
                    "street": "",
                    "city": "",
                    "state": "",
                    "postal": "",
                    "country": "",
                    "comment": "",
                },
            }
        ],
    }
    apply_hash = preview_hash("apply", payload)
    other = dict(payload)
    other["smtp"] = dict(payload["smtp"], password="other")
    assert preview_hash("apply", other) != apply_hash
    assert "s3cret" not in apply_hash
    remove_hash = preview_hash("remove", {"arrays": [{"card_id": 2}]})
    assert remove_hash != apply_hash


def test_run_stopemail_already_stopped_is_success():
    def run_cmd(command: str) -> str:
        raise RuntimeError("CMMVC6186E The e-mail service is already stopped.")

    steps, _, _ = build_remove_array_steps(users=[], servers=[])
    result = run_call_home_steps(steps, run_cmd)
    assert result["ok"] is True
    assert result["log"][0]["ok"] is True

    secret_steps, _, _ = build_apply_array_steps(
        contact={"name": "", "reply": "", "primary": "", "alternate": ""},
        location={
            "company": "",
            "street": "",
            "city": "",
            "state": "",
            "postal": "",
            "country": "",
            "comment": "",
        },
        smtp={"ip": "1.2.3.4", "port": "25", "username": "u", "password": "s3cret"},
        servers=[],
    )
    logged: list[str] = []

    def run_smtp(command: str) -> str:
        logged.append(command)
        return "ok"

    result2 = run_call_home_steps(secret_steps, run_smtp)
    assert "s3cret" in logged[0]
    assert "s3cret" not in result2["log"][0]["cmd"]
    assert "********" in result2["log"][0]["cmd"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_call_home_cli_ops.py -v`

Expected: FAIL (module not found)

- [ ] **Step 3: Write minimal implementation**

Create `launchpad/call_home_cli_ops.py` with this module (imports at top):

```python
"""IBM Call Home contact/location/SMTP preview and run helpers."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from typing import Any

from launchpad.contingency_snap_create import SnapStep, cli_token
from launchpad.flashsystem_fc import _get, _table_records
from launchpad.flashsystem_parse import _parse_key_values
from launchpad.system_connectivity import parse_svc_call_home

CONTACT_KEYS = ("name", "reply", "primary", "alternate")
LOCATION_KEYS = ("company", "street", "city", "state", "postal", "country", "comment")
SMTP_KEYS = ("ip", "port", "username", "password")
CONTACT_FLAGS = (
    ("name", "-contact"),
    ("reply", "-reply"),
    ("primary", "-primary"),
    ("alternate", "-alternate"),
)
LOCATION_FLAGS = (
    ("company", "-organization"),
    ("street", "-address"),
    ("city", "-city"),
    ("state", "-state"),
    ("postal", "-zip"),
    ("country", "-country"),
    ("comment", "-location"),
)
_PASSWORD_RE = re.compile(r"(-password\s+)(\"[^\"]*\"|\S+)", re.IGNORECASE)
_UNSAFE_QUOTE = re.compile(r'["\r\n\x00]')


def quote_cli_arg(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError("Unsafe empty CLI value")
    if _UNSAFE_QUOTE.search(text):
        raise ValueError("CLI value contains a quote or newline")
    try:
        return cli_token(text)
    except ValueError:
        return f'"{text}"'


def mask_password_in_cmd(cmd: str) -> str:
    return _PASSWORD_RE.sub(r"\1********", str(cmd or ""))


def is_email_already_stopped(text: str) -> bool:
    return "already stopped" in str(text or "").lower()


def smtp_add_requested(smtp: dict | None) -> bool:
    data = smtp or {}
    return any(str(data.get(key) or "").strip() for key in SMTP_KEYS)


def trim_fields(data: dict | None, keys: tuple[str, ...]) -> dict[str, str]:
    src = data or {}
    return {key: str(src.get(key) or "").strip() for key in keys}


def password_sha256(password: str) -> str:
    return hashlib.sha256(str(password or "").encode("utf-8")).hexdigest()


def _pick(values: dict[str, str], *keys: str) -> str:
    lower = {str(key).lower(): val for key, val in values.items()}
    for key in keys:
        val = lower.get(key.lower())
        if val is not None and str(val).strip():
            return str(val).strip()
    return ""


def parse_email_servers(output: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for record in _table_records(output):
        ident = _get(record, "id")
        name = _get(record, "name")
        if not ident and not name:
            continue
        rows.append(
            {
                "id": ident,
                "name": name,
                "ip": _get(record, "IP_address", "ip_address", "IP", "ip"),
                "port": _get(record, "port"),
                "username": _get(record, "username", "user"),
            }
        )
    return rows


def parse_email_users(output: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for record in _table_records(output):
        ident = _get(record, "id")
        name = _get(record, "name")
        if not ident and not name:
            continue
        rows.append(
            {
                "id": ident,
                "name": name,
                "address": _get(record, "address", "email", "user_name"),
                "user_type": _get(record, "user_type", "usertype", "type"),
            }
        )
    return rows


def parse_lssystem_contact_location(
    output: str,
) -> tuple[dict[str, str], dict[str, str]]:
    values = _parse_key_values(output)
    contact = {
        "name": _pick(values, "email_contact", "contact"),
        "reply": _pick(values, "email_reply", "reply"),
        "primary": _pick(values, "email_contact_primary", "email_primary"),
        "alternate": _pick(values, "email_contact_alternate", "email_alternate"),
    }
    location = {
        "company": _pick(values, "email_organization", "organization"),
        "street": _pick(values, "email_street", "email_address", "email_machine_address"),
        "city": _pick(values, "email_city", "email_machine_city"),
        "state": _pick(values, "email_state", "email_machine_state"),
        "postal": _pick(values, "email_zip", "email_machine_zip"),
        "country": _pick(values, "email_country", "email_machine_country"),
        "comment": _pick(values, "email_contact_location", "email_location", "location"),
    }
    return contact, location


def format_smtp_summary(servers: list[dict], users: list[dict]) -> str:
    if not servers and not users:
        return "none"
    parts: list[str] = []
    for server in servers:
        ip = str(server.get("ip") or "").strip()
        port = str(server.get("port") or "").strip()
        name = str(server.get("name") or "").strip()
        bit = f"{ip}:{port}" if ip and port else ip or name
        user = str(server.get("username") or "").strip()
        if user:
            bit = f"{bit} user={user}"
        if bit:
            parts.append(bit)
    addrs = [
        str(user.get("address") or user.get("name") or "").strip()
        for user in users
    ]
    addrs = [item for item in addrs if item]
    if addrs:
        parts.append("users=" + ", ".join(addrs))
    return "; ".join(parts) if parts else "none"


def _run_info(run_cmd: Callable[[str], str], base: str) -> str:
    out = run_cmd(f"{base} -delim :")
    if not str(out or "").strip():
        out = run_cmd(base)
    return out


def collect_call_home_state(run_cmd: Callable[[str], str]) -> dict[str, Any]:
    empty = {
        "ok": False,
        "error": "",
        "cloud_configured": "",
        "cloud_status": "",
        "cloud_details": "",
        "servers": [],
        "users": [],
        "contact": trim_fields({}, CONTACT_KEYS),
        "location": trim_fields({}, LOCATION_KEYS),
        "smtp_summary": "none",
    }
    try:
        cloud_out = _run_info(run_cmd, "svcinfo lscloudcallhome")
        server_out = _run_info(run_cmd, "svcinfo lsemailserver")
        user_out = _run_info(run_cmd, "svcinfo lsemailuser")
        sys_out = run_cmd("svcinfo lssystem")
    except Exception as exc:
        empty["error"] = str(exc)
        return empty
    configured, status, details = parse_svc_call_home(cloud_out)
    servers = parse_email_servers(server_out)
    users = parse_email_users(user_out)
    contact, location = parse_lssystem_contact_location(sys_out)
    return {
        "ok": True,
        "error": "",
        "cloud_configured": configured,
        "cloud_status": status,
        "cloud_details": details,
        "servers": servers,
        "users": users,
        "contact": contact,
        "location": location,
        "smtp_summary": format_smtp_summary(servers, users),
    }


def _chemail_cmd(pairs: list[tuple[str, str]]) -> str:
    parts = ["svctask", "chemail"]
    for flag, value in pairs:
        parts.append(flag)
        parts.append(quote_cli_arg(value))
    return " ".join(parts)


def build_apply_array_steps(
    *,
    contact: dict,
    location: dict,
    smtp: dict,
    servers: list[dict],
) -> tuple[list[SnapStep], list[str], bool]:
    warnings: list[str] = []
    contact = trim_fields(contact, CONTACT_KEYS)
    location = trim_fields(location, LOCATION_KEYS)
    smtp = trim_fields(smtp, SMTP_KEYS)
    want_smtp = smtp_add_requested(smtp)
    if want_smtp:
        if not smtp["ip"] or not smtp["port"]:
            warnings.append("ERROR: SMTP add needs IP (or hostname) and port")
        else:
            try:
                port = int(smtp["port"])
            except ValueError:
                port = -1
            if port < 1 or port > 65535:
                warnings.append("ERROR: SMTP port must be 1-65535")
        if smtp["username"] and not smtp["password"]:
            warnings.append("ERROR: SMTP password is required when username is set")
        if servers:
            warnings.append("ERROR: email server already exists")
    has_contact = any(contact.values())
    has_location = any(location.values())
    if not has_contact and not has_location and not want_smtp:
        warnings.append("ERROR: nothing to apply")
    if any(item.startswith("ERROR:") for item in warnings):
        return [], warnings, False
    steps: list[SnapStep] = []
    if has_contact:
        pairs = [(flag, contact[key]) for key, flag in CONTACT_FLAGS if contact[key]]
        steps.append(SnapStep(kind="chemail", purpose="set contact", cmd=_chemail_cmd(pairs)))
    if has_location:
        pairs = [(flag, location[key]) for key, flag in LOCATION_FLAGS if location[key]]
        steps.append(SnapStep(kind="chemail", purpose="set location", cmd=_chemail_cmd(pairs)))
    if want_smtp:
        parts = [
            "svctask",
            "mkemailserver",
            "-ip",
            quote_cli_arg(smtp["ip"]),
            "-port",
            quote_cli_arg(smtp["port"]),
        ]
        if smtp["username"]:
            parts.extend(["-username", quote_cli_arg(smtp["username"])])
        if smtp["password"]:
            parts.extend(["-password", quote_cli_arg(smtp["password"])])
        steps.append(
            SnapStep(kind="mkemailserver", purpose="add email server", cmd=" ".join(parts))
        )
    return steps, warnings, True


def _object_token(row: dict) -> str:
    return str(row.get("id") or row.get("name") or "").strip()


def build_remove_array_steps(
    *,
    users: list[dict],
    servers: list[dict],
) -> tuple[list[SnapStep], list[str], bool]:
    steps = [
        SnapStep(kind="stopemail", purpose="stop email sending", cmd="svctask stopemail")
    ]
    for user in users:
        token = _object_token(user)
        if not token:
            continue
        steps.append(
            SnapStep(
                kind="rmemailuser",
                purpose=f"remove email user {token}",
                cmd=f"svctask rmemailuser {quote_cli_arg(token)}",
            )
        )
    for server in servers:
        token = _object_token(server)
        if not token:
            continue
        steps.append(
            SnapStep(
                kind="rmemailserver",
                purpose=f"remove email server {token}",
                cmd=f"svctask rmemailserver {quote_cli_arg(token)}",
            )
        )
    return steps, [], True


def preview_hash(kind: str, payload: dict) -> str:
    arrays = payload.get("arrays") or []
    if kind == "apply":
        smtp = trim_fields(payload.get("smtp"), SMTP_KEYS)
        blob: dict[str, Any] = {
            "kind": "apply",
            "contact": trim_fields(payload.get("contact"), CONTACT_KEYS),
            "smtp": {
                "ip": smtp["ip"],
                "port": smtp["port"],
                "username": smtp["username"],
                "password_sha256": password_sha256(smtp["password"]),
            },
            "arrays": sorted(
                [
                    {
                        "card_id": int(item["card_id"]),
                        "location": trim_fields(item.get("location"), LOCATION_KEYS),
                    }
                    for item in arrays
                    if isinstance(item, dict) and item.get("card_id") is not None
                ],
                key=lambda row: row["card_id"],
            ),
        }
    else:
        blob = {
            "kind": "remove",
            "arrays": sorted(
                [
                    {"card_id": int(item["card_id"])}
                    for item in arrays
                    if isinstance(item, dict) and item.get("card_id") is not None
                ],
                key=lambda row: row["card_id"],
            ),
        }
    return hashlib.sha256(
        json.dumps(blob, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ).hexdigest()


def masked_steps_payload(steps: list[SnapStep]) -> list[dict]:
    return [
        {
            "kind": step.kind,
            "purpose": step.purpose,
            "cmd": mask_password_in_cmd(step.cmd),
            "skip": step.skip,
            "reason": step.reason,
        }
        for step in steps
    ]


def run_call_home_steps(
    steps: list[SnapStep],
    run_cmd: Callable[[str], str],
) -> dict[str, Any]:
    log: list[dict[str, Any]] = []
    for step in steps:
        entry: dict[str, Any] = {
            "kind": step.kind,
            "purpose": step.purpose,
            "cmd": mask_password_in_cmd(step.cmd),
            "skipped": step.skip,
        }
        if step.skip:
            entry["reason"] = step.reason
            log.append(entry)
            continue
        try:
            output = run_cmd(step.cmd)
        except Exception as exc:
            text = str(exc)
            if step.kind == "stopemail" and is_email_already_stopped(text):
                entry["ok"] = True
                entry["output"] = text
                log.append(entry)
                continue
            entry["ok"] = False
            entry["error"] = text
            log.append(entry)
            return {"ok": False, "log": log, "warnings": []}
        text = str(output or "")
        if step.kind == "stopemail" and is_email_already_stopped(text):
            entry["ok"] = True
            entry["output"] = text
            log.append(entry)
            continue
        entry["ok"] = True
        entry["output"] = text
        log.append(entry)
    return {"ok": True, "log": log, "warnings": []}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_call_home_cli_ops.py -v`

Expected: PASS. If `quote_cli_arg("172.29.62.98")` fails `cli_token` (dots are allowed in `cli_token`), keep the unquoted form. If it unexpectedly quotes, update `quote_cli_arg` only enough to satisfy the test (dots/hyphens stay unquoted via `cli_token`).

- [ ] **Step 5: Commit**

```powershell
git add -- launchpad/call_home_cli_ops.py tests/test_call_home_cli_ops.py
git commit -m "Add Call Home CLI quote, parse, and Apply/Remove step builders."
```

---

### Task 2: Page HTML/JS

**Files:**
- Create: `launchpad/call_home_cli.py`
- Create: `tests/test_call_home_cli_page.py`

**Interfaces:**
- Consumes: none
- Produces: `CALL_HOME_CLI_PATH = "/call-home-cli"` and `CALL_HOME_CLI_HTML` with the contract tests below

- [ ] **Step 1: Write the failing tests**

Create `tests/test_call_home_cli_page.py`:

```python
from launchpad.call_home_cli import CALL_HOME_CLI_HTML, CALL_HOME_CLI_PATH
from launchpad.health_server import DASHBOARD_HTML


def test_path_title_and_actions():
    assert CALL_HOME_CLI_PATH == "/call-home-cli"
    html = CALL_HOME_CLI_HTML
    assert "Call Home CLI" in html
    assert "Preview Apply" in html
    assert "Run Apply" in html
    assert "Preview Remove SMTP" in html
    assert "Run Remove SMTP" in html
    assert "Load current" in html
    assert "Select all" in html
    assert "Select none" in html
    assert 'id="run-apply-btn"' in html
    assert 'id="run-remove-btn"' in html
    assert "disabled" in html


def test_api_paths_and_payload_fields():
    html = CALL_HOME_CLI_HTML
    assert "/api/call-home/cards" in html
    assert "/api/call-home/state" in html
    assert "/api/call-home/preview-apply" in html
    assert "/api/call-home/run-apply" in html
    assert "/api/call-home/preview-remove" in html
    assert "/api/call-home/run-remove" in html
    assert "preview_hash" in html
    assert "confirm" in html
    assert "contact" in html
    assert "smtp" in html
    assert "location" in html
    assert 'type="password"' in html


def test_array_host_is_https_link_outside_checkbox_label():
    html = CALL_HOME_CLI_HTML
    assert "function arrayHostLink" in html
    assert 'class="array-ip-link"' in html
    assert 'target="_blank"' in html
    assert 'rel="noopener"' in html
    assert '"https://"' in html
    assert html.find("</label>' + arrayHostLink") != -1
    assert html.find("<span class=\"hint\">' + (card.host") == -1


def test_fetch_catch_and_separate_run_kinds():
    html = CALL_HOME_CLI_HTML
    assert "invalidatePreview" in html
    assert "catch" in html
    load_at = html.find("async function loadCurrent")
    assert load_at != -1
    assert "catch" in html[load_at:load_at + 1600]
    assert 'id="run-apply-btn"' in html
    assert 'id="run-remove-btn"' in html
    apply_at = html.find('getElementById("run-apply-btn").onclick')
    remove_at = html.find('getElementById("run-remove-btn").onclick')
    assert apply_at != -1 and remove_at != -1
    assert html.find('runApplyBtn.disabled = true', apply_at) != -1
    assert html.find('runRemoveBtn.disabled = true', remove_at) != -1
    assert "/api/call-home/run-apply" in html[apply_at:apply_at + 1200]
    assert "/api/call-home/run-remove" in html[remove_at:remove_at + 1200]
    assert "no rollback" in html.lower()
    assert "cloud Call Home" in html or "Cloud Call Home" in html


def test_health_dashboard_link():
    assert 'href="/call-home-cli"' in DASHBOARD_HTML
```

`test_health_dashboard_link` will still fail until Task 3 adds the Health dashboard `<a>`. Leave that assertion in this file; Task 3 makes it pass. For Task 2 Step 4, run the other tests excluding `test_health_dashboard_link`:

`python -m pytest tests/test_call_home_cli_page.py -v -k "not test_health_dashboard_link"`

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_call_home_cli_page.py -v -k "not test_health_dashboard_link"`

Expected: FAIL (module not found)

- [ ] **Step 3: Write the page**

Create `launchpad/call_home_cli.py`. Match ESX-snap Policy styling (dark card, `--accent` orange). Required IDs/functions: `contact-name`, `contact-reply`, `contact-primary`, `contact-alternate`, `smtp-ip`, `smtp-port`, `smtp-username`, `smtp-password`, `load-btn`, `preview-apply-btn`, `run-apply-btn`, `preview-remove-btn`, `run-remove-btn`, `arrayHostLink`, `invalidatePreview`, `loadCurrent`, `applyPayload`, `removePayload`. Run buttons start `disabled`.

Use this page (keep the JS strings exactly enough to satisfy Step 1 tests):

```python
"""Call Home CLI page — contact, location, SMTP add/remove."""

CALL_HOME_CLI_PATH = "/call-home-cli"

CALL_HOME_CLI_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>LaunchPad Call Home CLI</title>
  <style>
    :root { --bg:#0b0f14; --panel:#121821; --text:#e8edf5; --muted:#8b98ab; --accent:#ff6b00; --accent2:#ff8533; --ok:#4ade80; --border:#2a3444; --card:#151c27; --danger:#f87171; }
    * { box-sizing:border-box; }
    body { margin:0; min-height:100vh; color:var(--text); font-family:Segoe UI,Inter,Arial,sans-serif; background:radial-gradient(circle at top,#172033 0%,var(--bg) 45%); }
    .wrap { max-width:1280px; margin:0 auto; padding:28px 20px 48px; }
    .hero, .section { background:var(--card); border:1px solid var(--border); border-radius:16px; padding:20px; margin-bottom:18px; }
    .hero { background:linear-gradient(135deg,#1a2230 0%,#101722 100%); }
    h1 { margin:0 0 8px; color:var(--accent); font-size:1.85rem; }
    h2 { margin:0 0 10px; color:var(--accent2); font-size:1.05rem; }
    p, .lede, .hint, .footer { color:var(--muted); line-height:1.45; }
    a:not(.btn) { color:#9ec1ff; text-decoration:underline; text-underline-offset:2px; }
    .actions { display:flex; flex-wrap:wrap; align-items:center; gap:10px; margin-top:14px; }
    button, .btn { min-height:34px; padding:0 14px; border:0; border-radius:10px; background:var(--accent); color:#111; font:inherit; font-weight:600; cursor:pointer; text-decoration:none; display:inline-flex; align-items:center; justify-content:center; }
    button.secondary, .btn.secondary { color:var(--text); background:#0f141d; border:1px solid var(--border); }
    button.danger { color:#fff; background:#b91c1c; }
    button:disabled { cursor:not-allowed; opacity:.6; }
    input { color:var(--text); background:#0f141d; border:1px solid var(--border); border-radius:8px; padding:6px 9px; font:inherit; }
    label { color:var(--muted); font-size:.85rem; font-weight:600; }
    .grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:8px; }
    .array { border:1px solid var(--border); border-radius:12px; padding:12px; margin-top:10px; background:#0f141d; }
    .array-head { display:flex; flex-wrap:wrap; gap:10px; align-items:center; }
    .modal-backdrop { position:fixed; inset:0; z-index:10; display:grid; place-items:center; padding:20px; background:rgba(0,0,0,.72); }
    .modal-backdrop[hidden] { display:none !important; }
    .modal { width:min(900px,100%); max-height:85vh; overflow:auto; padding:20px; border:1px solid var(--border); border-radius:14px; background:var(--panel); }
    pre { margin:0; padding:12px; overflow:auto; border:1px solid var(--border); border-radius:8px; background:#0b0f14; color:#d8e3f2; white-space:pre-wrap; }
    .warning { margin:8px 0; padding:9px 10px; border-left:3px solid var(--danger); background:#32151a; color:#fecaca; }
  </style>
</head>
<body>
  <main class="wrap">
    <section class="hero">
      <h1>Call Home CLI</h1>
      <p class="lede">Set shared contact and per-array location. Optionally add an SMTP server. Remove SMTP deletes email users and servers only — Cloud Call Home, contact, and location stay. Preview first. The first CLI error stops that array; other arrays continue. No rollback.</p>
      <div class="actions">
        <a class="btn secondary" href="/">Health Dashboard</a>
        <a class="btn secondary" href="/system-connectivity">System Connectivity</a>
      </div>
    </section>
    <section class="section">
      <h2>Shared contact</h2>
      <div class="grid">
        <label>Name <input id="contact-name"></label>
        <label>Reply email <input id="contact-reply"></label>
        <label>Primary phone <input id="contact-primary"></label>
        <label>Alternate phone <input id="contact-alternate"></label>
      </div>
      <h2>SMTP add (optional)</h2>
      <p class="hint">Leave empty to skip. If any field is filled, IP and port are required. Password is never stored.</p>
      <div class="grid">
        <label>IP or hostname <input id="smtp-ip"></label>
        <label>Port <input id="smtp-port"></label>
        <label>Username <input id="smtp-username"></label>
        <label>Password <input id="smtp-password" type="password"></label>
      </div>
      <div class="actions">
        <button type="button" class="secondary" id="select-all-btn">Select all</button>
        <button type="button" class="secondary" id="select-none-btn">Select none</button>
        <button type="button" class="secondary" id="load-btn">Load current</button>
        <button type="button" class="secondary" id="preview-apply-btn">Preview Apply</button>
        <button type="button" class="danger" id="run-apply-btn" disabled>Run Apply</button>
        <button type="button" class="secondary" id="preview-remove-btn">Preview Remove SMTP</button>
        <button type="button" class="danger" id="run-remove-btn" disabled>Run Remove SMTP</button>
        <span class="hint" id="status"></span>
      </div>
      <div id="arrays"><p class="hint">Loading arrays…</p></div>
    </section>
  </main>
  <div class="modal-backdrop" id="modal" hidden>
    <div class="modal">
      <h2 id="modal-title">Preview</h2>
      <pre id="modal-body"></pre>
      <div class="actions"><button type="button" class="secondary" id="modal-close">Close</button></div>
    </div>
  </div>
  <p class="footer wrap">LaunchPad {{APP_VERSION}}</p>
  <script>
    const arraysEl = document.getElementById("arrays");
    const statusEl = document.getElementById("status");
    const runApplyBtn = document.getElementById("run-apply-btn");
    const runRemoveBtn = document.getElementById("run-remove-btn");
    const modal = document.getElementById("modal");
    const modalBody = document.getElementById("modal-body");
    const modalTitle = document.getElementById("modal-title");
    const LOC = ["company","street","city","state","postal","country","comment"];
    let cards = [];
    window.__applyOk = false; window.__applyHash = "";
    window.__removeOk = false; window.__removeHash = "";

    function invalidatePreview() {
      window.__applyOk = false; window.__applyHash = "";
      window.__removeOk = false; window.__removeHash = "";
      runApplyBtn.disabled = true; runRemoveBtn.disabled = true;
    }
    function showModal(title, text) { modalTitle.textContent = title; modalBody.textContent = text; modal.hidden = false; }
    function arrayHostLink(host) {
      const raw = String(host || "").trim();
      if (!raw) return "";
      const lower = raw.toLowerCase();
      const href = (lower.startsWith("https://") || lower.startsWith("http://")) ? raw : ("https://" + raw);
      return ' <a class="array-ip-link" href="' + href + '" target="_blank" rel="noopener">' + raw + '</a>';
    }
    function selectedIds() {
      return [...document.querySelectorAll(".array-check:checked")].map((el) => Number(el.dataset.cardId));
    }
    function contactPayload() {
      return {
        name: document.getElementById("contact-name").value,
        reply: document.getElementById("contact-reply").value,
        primary: document.getElementById("contact-primary").value,
        alternate: document.getElementById("contact-alternate").value
      };
    }
    function smtpPayload() {
      return {
        ip: document.getElementById("smtp-ip").value,
        port: document.getElementById("smtp-port").value,
        username: document.getElementById("smtp-username").value,
        password: document.getElementById("smtp-password").value
      };
    }
    function locPayload(id) {
      const out = {};
      LOC.forEach((k) => { const el = document.getElementById("loc-" + k + "-" + id); out[k] = el ? el.value : ""; });
      return out;
    }
    function applyPayload() {
      return { contact: contactPayload(), smtp: smtpPayload(), arrays: selectedIds().map((id) => ({ card_id: id, location: locPayload(id) })) };
    }
    function removePayload() {
      return { arrays: selectedIds().map((id) => ({ card_id: id })) };
    }
    function contactEmpty() {
      const c = contactPayload();
      return !c.name && !c.reply && !c.primary && !c.alternate;
    }
    function fillContact(c) {
      if (!c) return;
      document.getElementById("contact-name").value = c.name || "";
      document.getElementById("contact-reply").value = c.reply || "";
      document.getElementById("contact-primary").value = c.primary || "";
      document.getElementById("contact-alternate").value = c.alternate || "";
    }
    function fillLoc(id, loc) {
      if (!loc) return;
      LOC.forEach((k) => { const el = document.getElementById("loc-" + k + "-" + id); if (el) el.value = loc[k] || ""; });
    }
    function render() {
      if (!cards.length) { arraysEl.innerHTML = '<p class="hint">No IBM FlashSystem / SVC SSH cards.</p>'; return; }
      arraysEl.innerHTML = cards.map((card) => {
        const checked = document.querySelector('.array-check[data-card-id="'+card.id+'"]');
        const on = checked ? checked.checked : false;
        const loc = locPayload(card.id);
        const cloud = document.getElementById("cloud-" + card.id);
        const smtp = document.getElementById("smtp-sum-" + card.id);
        return '<div class="array" data-card-id="'+card.id+'">'
          + '<div class="array-head"><label><input class="array-check" type="checkbox" data-card-id="'+card.id+'"'+(on?" checked":"")+'> '+card.name+'</label>'
          + arrayHostLink(card.host)
          + '<span class="hint" id="cloud-'+card.id+'">'+(cloud ? cloud.textContent : "Cloud Call Home: —")+'</span></div>'
          + '<p class="hint" id="smtp-sum-'+card.id+'">'+(smtp ? smtp.textContent : "SMTP: —")+'</p>'
          + '<div class="grid">'
          + LOC.map((k) => '<label>'+k+' <input id="loc-'+k+'-'+card.id+'" value="'+(loc[k]||"").replace(/"/g,"")+'"></label>').join("")
          + '</div></div>';
      }).join("");
      arraysEl.querySelectorAll("input").forEach((el) => el.addEventListener("input", invalidatePreview));
      arraysEl.querySelectorAll(".array-check").forEach((el) => el.addEventListener("change", invalidatePreview));
    }
    async function loadCards() {
      try {
        const res = await fetch("/api/call-home/cards");
        const data = await res.json();
        cards = data.cards || [];
        render();
      } catch (err) { arraysEl.innerHTML = '<p class="warning">'+(err.message||err)+'</p>'; }
    }
    async function loadCurrent() {
      invalidatePreview();
      statusEl.textContent = "Loading…";
      let ids = selectedIds();
      if (!ids.length) ids = cards.map((c) => c.id);
      let filledShared = !contactEmpty();
      for (const id of ids) {
        try {
          const res = await fetch("/api/call-home/state", { method:"POST", headers:{ "Content-Type":"application/json" }, body: JSON.stringify({ card_id: id }) });
          const data = await res.json();
          const cloud = document.getElementById("cloud-" + id);
          const smtp = document.getElementById("smtp-sum-" + id);
          if (!data.ok) {
            if (cloud) cloud.textContent = data.error || "Load failed";
            continue;
          }
          if (cloud) cloud.textContent = "Cloud Call Home: " + (data.cloud_status || data.cloud_details || "unknown");
          if (smtp) smtp.textContent = "SMTP: " + (data.smtp_summary || "none");
          fillLoc(id, data.location);
          if (!filledShared) { fillContact(data.contact); filledShared = true; }
        } catch (err) {
          const cloud = document.getElementById("cloud-" + id);
          if (cloud) cloud.textContent = err.message || String(err);
        }
      }
      statusEl.textContent = "Load current finished.";
    }
    function previewLines(data) {
      const lines = [];
      (data.arrays || []).forEach((row) => {
        lines.push("# " + (row.name || row.card_id) + " runnable=" + row.runnable);
        (row.warnings || []).forEach((w) => lines.push(w));
        (row.steps || []).forEach((s) => lines.push(s.cmd));
        lines.push("");
      });
      (data.warnings || []).forEach((w) => lines.push(w));
      return lines.join("\\n") || JSON.stringify(data, null, 2);
    }
    async function doPreview(kind) {
      invalidatePreview();
      statusEl.textContent = "Preview…";
      const url = kind === "apply" ? "/api/call-home/preview-apply" : "/api/call-home/preview-remove";
      const body = kind === "apply" ? applyPayload() : removePayload();
      try {
        const res = await fetch(url, { method:"POST", headers:{ "Content-Type":"application/json" }, body: JSON.stringify(body) });
        const data = await res.json();
        showModal(kind === "apply" ? "Preview Apply" : "Preview Remove SMTP", previewLines(data));
        if (kind === "apply") {
          window.__applyOk = !!data.ok; window.__applyHash = data.preview_hash || "";
          runApplyBtn.disabled = !window.__applyOk;
        } else {
          window.__removeOk = !!data.ok; window.__removeHash = data.preview_hash || "";
          runRemoveBtn.disabled = !window.__removeOk;
        }
        statusEl.textContent = data.ok ? "Preview succeeded." : "Preview found blocking errors.";
      } catch (err) { statusEl.textContent = "Preview failed: " + (err.message || err); }
    }
    document.getElementById("select-all-btn").onclick = () => { document.querySelectorAll(".array-check").forEach((el) => { el.checked = true; }); invalidatePreview(); };
    document.getElementById("select-none-btn").onclick = () => { document.querySelectorAll(".array-check").forEach((el) => { el.checked = false; }); invalidatePreview(); };
    document.getElementById("load-btn").onclick = () => loadCurrent();
    document.getElementById("preview-apply-btn").onclick = () => doPreview("apply");
    document.getElementById("preview-remove-btn").onclick = () => doPreview("remove");
    ["contact-name","contact-reply","contact-primary","contact-alternate","smtp-ip","smtp-port","smtp-username","smtp-password"].forEach((id) => {
      document.getElementById(id).addEventListener("input", invalidatePreview);
    });
    document.getElementById("modal-close").onclick = () => { modal.hidden = true; };
    document.getElementById("run-apply-btn").onclick = async () => {
      if (!window.__applyOk) return;
      if (!confirm("This writes Call Home contact/location and optional SMTP add on the selected arrays. The first CLI error stops that array; other arrays continue. No rollback.")) return;
      runApplyBtn.disabled = true; window.__applyOk = false;
      const body = Object.assign(applyPayload(), { confirm: true, preview_hash: window.__applyHash });
      try {
        const res = await fetch("/api/call-home/run-apply", { method:"POST", headers:{ "Content-Type":"application/json" }, body: JSON.stringify(body) });
        const data = await res.json();
        showModal("Run Apply", previewLines(data));
        statusEl.textContent = data.ok ? "Apply finished." : "Apply finished with errors.";
      } catch (err) { statusEl.textContent = "Apply failed: " + (err.message || err); }
    };
    document.getElementById("run-remove-btn").onclick = async () => {
      if (!window.__removeOk) return;
      if (!confirm("This stops email sending and deletes email users and email servers on the selected arrays. Cloud Call Home, contact, and location are not changed.")) return;
      runRemoveBtn.disabled = true; window.__removeOk = false;
      const body = Object.assign(removePayload(), { confirm: true, preview_hash: window.__removeHash });
      try {
        const res = await fetch("/api/call-home/run-remove", { method:"POST", headers:{ "Content-Type":"application/json" }, body: JSON.stringify(body) });
        const data = await res.json();
        showModal("Run Remove SMTP", previewLines(data));
        statusEl.textContent = data.ok ? "Remove finished." : "Remove finished with errors.";
      } catch (err) { statusEl.textContent = "Remove failed: " + (err.message || err); }
    };
    loadCards();
  </script>
</body>
</html>"""
```

In the `.py` file, write the JS as `lines.join("\\n")` inside the HTML triple-quoted string so the browser receives `lines.join("\n")`.

- [ ] **Step 4: Run page tests (except dashboard link)**

Run: `python -m pytest tests/test_call_home_cli_page.py -v -k "not test_health_dashboard_link"`

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add -- launchpad/call_home_cli.py tests/test_call_home_cli_page.py
git commit -m "Add Call Home CLI page with separate Apply and Remove SMTP runs."
```

---

### Task 3: HealthServer routes, dashboard button, freeze test

**Files:**
- Modify: `launchpad/health_server.py`
- Create: `tests/test_health_server_call_home_cli.py`
- Modify: `launchpad/ui/dashboard_view.py`
- Modify: `tests/test_dashboard_ui_freeze.py`
- Modify: `tests/test_call_home_cli_page.py` (dashboard link now passes)

**Interfaces:**
- Consumes: Task 1 ops functions (import `preview_hash` as `call_home_preview_hash` so it does not shadow ESX-snap `preview_hash`); `CALL_HOME_CLI_HTML`, `CALL_HOME_CLI_PATH`
- Produces:
  - `HealthServer.call_home_cards() -> list[dict]`
  - `HealthServer.call_home_state(card_id: int) -> dict`
  - `HealthServer.preview_call_home_apply(payload: dict) -> dict`
  - `HealthServer.run_call_home_apply(payload: dict, *, confirm: bool) -> dict`
  - `HealthServer.preview_call_home_remove(payload: dict) -> dict`
  - `HealthServer.run_call_home_remove(payload: dict, *, confirm: bool) -> dict`
  - `HealthServer.call_home_cli_url` property and `open_call_home_cli() -> str`
  - GET `CALL_HOME_CLI_PATH`, GET `/api/call-home/cards`, POST `/api/call-home/state|preview-apply|run-apply|preview-remove|run-remove`

- [ ] **Step 1: Write the failing API tests**

Create `tests/test_health_server_call_home_cli.py`:

```python
from launchpad.call_home_cli_ops import preview_hash
from launchpad.health_server import HealthServer


def _server() -> HealthServer:
    server = HealthServer()
    server.register_card(
        card_id=1, name="Houston", host="hou.example", port=22,
        username="admin", key_path="/dev/null", device_profile="flashsystem_9200",
    )
    server.register_card(
        card_id=2, name="Anderson", host="and.example", port=22,
        username="admin", key_path="/dev/null", device_profile="flashsystem_9200",
    )
    server.register_card(
        card_id=3, name="HPE box", host="hpe.example", port=22,
        username="3paradm", key_path="/dev/null", device_profile="hpe_3par_8450",
    )
    return server


CLOUD = "id:status\n0:active\n"
SERVERS = "id:name:IP_address:port:username\n0:emailserver0:172.29.62.98:25:avijaytc\n"
USERS = "id:name:address:user_type\n0:support:callhome0@de.ibm.com:support\n"
LSYS = "email_contact:SANArch\nemail_reply:a@b.com\nemail_organization:Wags\n"
EMPTY_SERVERS = "id:name:IP_address:port\n"


def _bind(monkeypatch, mapping):
    calls: list[str] = []

    def bind_host(card, **kwargs):
        def run_cmd(command: str) -> str:
            calls.append(command)
            for needle, out in mapping:
                if needle in command:
                    return out
            return ""
        return run_cmd

    monkeypatch.setattr(HealthServer, "_snap_run_command", staticmethod(bind_host))
    return calls


def test_cards_ibm_only():
    names = {row["name"] for row in _server().call_home_cards()}
    assert names == {"Houston", "Anderson"}


def test_run_without_confirm_or_wrong_kind_hash_does_not_mutate(monkeypatch):
    server = _server()
    calls = _bind(monkeypatch, [("lscloudcallhome", CLOUD), ("lsemailserver", EMPTY_SERVERS), ("lsemailuser", ""), ("lssystem", LSYS)])
    payload = {
        "contact": {"name": "SANArch", "reply": "a@b.com", "primary": "", "alternate": ""},
        "smtp": {"ip": "", "port": "", "username": "", "password": ""},
        "arrays": [{"card_id": 1, "location": {"company": "Wags", "street": "", "city": "", "state": "", "postal": "", "country": "", "comment": ""}}],
    }
    out = server.run_call_home_apply(payload, confirm=False)
    assert out["ok"] is False
    assert not any(c.startswith("svctask") for c in calls)
    payload["preview_hash"] = preview_hash("remove", payload)
    payload["confirm"] = True
    out2 = server.run_call_home_apply(payload, confirm=True)
    assert out2["ok"] is False
    assert not any(c.startswith("svctask") for c in calls)


def test_existing_server_blocks_all_apply_commands(monkeypatch):
    server = _server()
    calls = _bind(monkeypatch, [("lscloudcallhome", CLOUD), ("lsemailserver", SERVERS), ("lsemailuser", USERS), ("lssystem", LSYS)])
    payload = {
        "contact": {"name": "SANArch", "reply": "a@b.com", "primary": "", "alternate": ""},
        "smtp": {"ip": "10.0.0.1", "port": "25", "username": "u", "password": "s3cret"},
        "arrays": [{"card_id": 1, "location": {"company": "Wags", "street": "", "city": "", "state": "", "postal": "", "country": "", "comment": ""}}],
    }
    preview = server.preview_call_home_apply(payload)
    assert preview["ok"] is False
    assert preview["arrays"][0]["runnable"] is False
    joined = str(preview)
    assert "s3cret" not in joined
    payload["preview_hash"] = preview_hash("apply", payload)
    result = server.run_call_home_apply(payload, confirm=True)
    assert result["ok"] is False
    assert not any(c.startswith("svctask chemail") for c in calls)
    assert not any("mkemailserver" in c for c in calls)


def test_apply_then_remove_order(monkeypatch):
    server = _server()
    calls = _bind(monkeypatch, [("lscloudcallhome", CLOUD), ("lsemailserver", EMPTY_SERVERS), ("lsemailuser", USERS), ("lssystem", LSYS)])
    payload = {
        "contact": {"name": "SANArch", "reply": "a@b.com", "primary": "", "alternate": ""},
        "smtp": {"ip": "10.0.0.1", "port": "25", "username": "u", "password": "s3cret"},
        "arrays": [{"card_id": 1, "location": {"company": "Wags", "street": "", "city": "", "state": "", "postal": "", "country": "", "comment": ""}}],
    }
    payload["preview_hash"] = preview_hash("apply", payload)
    result = server.run_call_home_apply(payload, confirm=True)
    assert result["ok"] is True
    mutate = [c for c in calls if c.startswith("svctask")]
    assert mutate[0].startswith("svctask chemail")
    assert mutate[-1].startswith("svctask mkemailserver")
    assert "s3cret" in mutate[-1]
    log_cmd = result["arrays"][0]["log"][-1]["cmd"]
    assert "s3cret" not in log_cmd
    remove = {"arrays": [{"card_id": 1}]}
    remove["preview_hash"] = preview_hash("remove", remove)
    calls2 = _bind(
        monkeypatch,
        [
            ("lscloudcallhome", CLOUD),
            ("lsemailserver", SERVERS),
            ("lsemailuser", USERS),
            ("lssystem", LSYS),
        ],
    )
    removed = server.run_call_home_remove(remove, confirm=True)
    assert removed["ok"] is True
    mutate2 = [c for c in calls2 if c.startswith("svctask")]
    assert mutate2[0] == "svctask stopemail"
    assert any(c.startswith("svctask rmemailuser") for c in mutate2)
    assert mutate2[-1].startswith("svctask rmemailserver")
```

- [ ] **Step 2: Run API tests to verify they fail**

Run: `python -m pytest tests/test_health_server_call_home_cli.py -v`

Expected: FAIL (`call_home_cards` missing)

- [ ] **Step 3: Wire HealthServer and dashboard**

In `launchpad/health_server.py`:

1. Add imports next to the ESX-snap imports:

```python
from launchpad.call_home_cli import CALL_HOME_CLI_HTML, CALL_HOME_CLI_PATH
from launchpad.call_home_cli_ops import (
    build_apply_array_steps,
    build_remove_array_steps,
    collect_call_home_state,
    masked_steps_payload,
    preview_hash as call_home_preview_hash,
    run_call_home_steps,
)
```

2. In `DASHBOARD_HTML` hero-actions, immediately after the System Connectivity `<a>`, add:

```html
        <a class="btn secondary" href="/call-home-cli" style="font:inherit;border-radius:10px;height:34px;display:inline-flex;align-items:center;justify-content:center;text-decoration:none;padding:0 14px;font-weight:600;background:#0f141d;color:var(--text);border:1px solid var(--border);">Call Home CLI</a>
```

3. In `_HealthHandler.do_GET`, after `if path == ESX_SNAP_POLICY_PATH:` (or next to System Connectivity page GET):

```python
        if path == CALL_HOME_CLI_PATH:
            self._send_html(_fill_page(CALL_HOME_CLI_HTML))
            return
```

and next to `/api/esx-snap-policy/cards`:

```python
        if path == "/api/call-home/cards":
            self._send_json({"cards": server.call_home_cards()})
            return
```

4. In `do_POST`, insert this block after the `/api/esx-snap-policy/*` POST handler:

```python
        if path in {
            "/api/call-home/state",
            "/api/call-home/preview-apply",
            "/api/call-home/run-apply",
            "/api/call-home/preview-remove",
            "/api/call-home/run-remove",
        }:
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b"{}"
            try:
                payload = json.loads(raw.decode("utf-8") or "{}")
            except json.JSONDecodeError:
                self._send_json({"ok": False, "error": "Invalid JSON"}, status=400)
                return
            if not isinstance(payload, dict):
                self._send_json({"ok": False, "error": "JSON object required"}, status=400)
                return
            if path == "/api/call-home/state":
                try:
                    card_id = int(payload.get("card_id"))
                except (TypeError, ValueError):
                    self._send_json({"ok": False, "error": "card_id is required"}, status=400)
                    return
                result = server.call_home_state(card_id)
                self._send_json(result, status=200 if result.get("ok") else 400)
                return
            if path == "/api/call-home/preview-apply":
                result = server.preview_call_home_apply(payload)
            elif path == "/api/call-home/run-apply":
                result = server.run_call_home_apply(
                    payload, confirm=payload.get("confirm") is True
                )
            elif path == "/api/call-home/preview-remove":
                result = server.preview_call_home_remove(payload)
            else:
                result = server.run_call_home_remove(
                    payload, confirm=payload.get("confirm") is True
                )
            self._send_json(result, status=200 if result.get("ok") else 400)
            return
```

5. Add methods on `HealthServer` next to the ESX-snap methods. Do **not** `_log` raw SMTP passwords or unmasked `SnapStep.cmd`.

```python
    def _call_home_eligible(self, card: HealthCard) -> bool:
        return (
            str(card.device_profile or "") in SVC_PROFILES
            and str(card.host or "").strip() != ""
        )

    def _call_home_card_by_id(self, card_id: int) -> HealthCard | None:
        with self._lock:
            return self._cards.get(card_id)

    def call_home_cards(self) -> list[dict[str, Any]]:
        with self._lock:
            stored = list(sorted(self._cards.values(), key=lambda card: card.card_id))
        return [
            {
                "id": card.card_id,
                "name": card.name,
                "host": card.host,
                "device_profile": card.device_profile or "",
            }
            for card in stored
            if self._call_home_eligible(card)
        ]

    def call_home_state(self, card_id: int) -> dict[str, Any]:
        card = self._call_home_card_by_id(card_id)
        if card is None or not self._call_home_eligible(card):
            return {"ok": False, "error": f"Unknown or ineligible Health Card id {card_id}"}
        state = collect_call_home_state(self._snap_run_command(card))
        state["card_id"] = card_id
        state["name"] = card.name
        state["host"] = card.host
        return state

    def _call_home_selected(self, raw_arrays: Any) -> list[dict]:
        if not isinstance(raw_arrays, list):
            return []
        return [item for item in raw_arrays if isinstance(item, dict)]

    def preview_call_home_apply(self, payload: dict) -> dict[str, Any]:
        items = self._call_home_selected(payload.get("arrays"))
        hashed = call_home_preview_hash("apply", payload)
        if not items:
            return {
                "ok": False,
                "arrays": [],
                "preview_hash": hashed,
                "warnings": ["ERROR: select at least one array"],
            }
        arrays_out: list[dict[str, Any]] = []
        for item in items:
            try:
                card_id = int(item.get("card_id"))
            except (TypeError, ValueError):
                arrays_out.append(
                    {
                        "card_id": item.get("card_id"),
                        "name": "",
                        "runnable": False,
                        "warnings": ["ERROR: card_id is required"],
                        "steps": [],
                    }
                )
                continue
            card = self._call_home_card_by_id(card_id)
            if card is None or not self._call_home_eligible(card):
                arrays_out.append(
                    {
                        "card_id": card_id,
                        "name": "",
                        "runnable": False,
                        "warnings": [f"ERROR: Unknown or ineligible Health Card id {card_id}"],
                        "steps": [],
                    }
                )
                continue
            state = collect_call_home_state(self._snap_run_command(card))
            if not state.get("ok"):
                arrays_out.append(
                    {
                        "card_id": card_id,
                        "name": card.name,
                        "runnable": False,
                        "warnings": [f"ERROR: {state.get('error') or 'load failed'}"],
                        "steps": [],
                    }
                )
                continue
            steps, warnings, runnable = build_apply_array_steps(
                contact=payload.get("contact") or {},
                location=item.get("location") or {},
                smtp=payload.get("smtp") or {},
                servers=list(state.get("servers") or []),
            )
            arrays_out.append(
                {
                    "card_id": card_id,
                    "name": card.name,
                    "runnable": runnable,
                    "warnings": warnings,
                    "steps": masked_steps_payload(steps),
                }
            )
        ok = bool(arrays_out) and all(row.get("runnable") for row in arrays_out)
        return {"ok": ok, "arrays": arrays_out, "preview_hash": hashed}

    def run_call_home_apply(self, payload: dict, *, confirm: bool) -> dict[str, Any]:
        hashed = call_home_preview_hash("apply", payload)
        if confirm is not True:
            return {
                "ok": False,
                "arrays": [],
                "warnings": ["confirm must be true before writing Call Home fields"],
            }
        given = str(payload.get("preview_hash") or "")
        if not given or given != hashed:
            return {
                "ok": False,
                "arrays": [],
                "warnings": ["Preview must be run again before applying Call Home fields."],
            }
        preview = self.preview_call_home_apply(payload)
        results: list[dict[str, Any]] = []
        by_id = {
            int(item["card_id"]): item
            for item in self._call_home_selected(payload.get("arrays"))
            if item.get("card_id") is not None
        }
        for row in preview.get("arrays") or []:
            if not row.get("runnable"):
                results.append(
                    {
                        "card_id": row.get("card_id"),
                        "name": row.get("name") or "",
                        "ok": False,
                        "warnings": row.get("warnings") or [],
                        "log": [],
                    }
                )
                continue
            card_id = int(row["card_id"])
            card = self._call_home_card_by_id(card_id)
            state = collect_call_home_state(self._snap_run_command(card))
            if not state.get("ok"):
                results.append(
                    {
                        "card_id": card_id,
                        "name": card.name if card else "",
                        "ok": False,
                        "warnings": [f"ERROR: {state.get('error')}"],
                        "log": [],
                    }
                )
                continue
            item = by_id.get(card_id) or {}
            steps, warnings, runnable = build_apply_array_steps(
                contact=payload.get("contact") or {},
                location=item.get("location") or {},
                smtp=payload.get("smtp") or {},
                servers=list(state.get("servers") or []),
            )
            if not runnable:
                results.append(
                    {
                        "card_id": card_id,
                        "name": card.name if card else "",
                        "ok": False,
                        "warnings": warnings,
                        "log": [],
                    }
                )
                continue
            executed = run_call_home_steps(steps, self._snap_run_command(card))
            results.append(
                {
                    "card_id": card_id,
                    "name": card.name if card else "",
                    "ok": bool(executed.get("ok")),
                    "warnings": executed.get("warnings") or [],
                    "log": executed.get("log") or [],
                }
            )
        overall_ok = any(row.get("ok") for row in results)
        return {"ok": overall_ok, "arrays": results}

    def preview_call_home_remove(self, payload: dict) -> dict[str, Any]:
        items = self._call_home_selected(payload.get("arrays"))
        hashed = call_home_preview_hash("remove", payload)
        if not items:
            return {
                "ok": False,
                "arrays": [],
                "preview_hash": hashed,
                "warnings": ["ERROR: select at least one array"],
            }
        arrays_out: list[dict[str, Any]] = []
        for item in items:
            try:
                card_id = int(item.get("card_id"))
            except (TypeError, ValueError):
                arrays_out.append(
                    {
                        "card_id": item.get("card_id"),
                        "name": "",
                        "runnable": False,
                        "warnings": ["ERROR: card_id is required"],
                        "steps": [],
                    }
                )
                continue
            card = self._call_home_card_by_id(card_id)
            if card is None or not self._call_home_eligible(card):
                arrays_out.append(
                    {
                        "card_id": card_id,
                        "name": "",
                        "runnable": False,
                        "warnings": [f"ERROR: Unknown or ineligible Health Card id {card_id}"],
                        "steps": [],
                    }
                )
                continue
            state = collect_call_home_state(self._snap_run_command(card))
            if not state.get("ok"):
                arrays_out.append(
                    {
                        "card_id": card_id,
                        "name": card.name,
                        "runnable": False,
                        "warnings": [f"ERROR: {state.get('error') or 'load failed'}"],
                        "steps": [],
                    }
                )
                continue
            steps, warnings, runnable = build_remove_array_steps(
                users=list(state.get("users") or []),
                servers=list(state.get("servers") or []),
            )
            arrays_out.append(
                {
                    "card_id": card_id,
                    "name": card.name,
                    "runnable": runnable,
                    "warnings": warnings,
                    "steps": masked_steps_payload(steps),
                }
            )
        ok = bool(arrays_out) and all(row.get("runnable") for row in arrays_out)
        return {"ok": ok, "arrays": arrays_out, "preview_hash": hashed}

    def run_call_home_remove(self, payload: dict, *, confirm: bool) -> dict[str, Any]:
        hashed = call_home_preview_hash("remove", payload)
        if confirm is not True:
            return {
                "ok": False,
                "arrays": [],
                "warnings": ["confirm must be true before removing SMTP"],
            }
        given = str(payload.get("preview_hash") or "")
        if not given or given != hashed:
            return {
                "ok": False,
                "arrays": [],
                "warnings": ["Preview must be run again before removing SMTP."],
            }
        preview = self.preview_call_home_remove(payload)
        results: list[dict[str, Any]] = []
        for row in preview.get("arrays") or []:
            if not row.get("runnable"):
                results.append(
                    {
                        "card_id": row.get("card_id"),
                        "name": row.get("name") or "",
                        "ok": False,
                        "warnings": row.get("warnings") or [],
                        "log": [],
                    }
                )
                continue
            card_id = int(row["card_id"])
            card = self._call_home_card_by_id(card_id)
            state = collect_call_home_state(self._snap_run_command(card))
            if not state.get("ok"):
                results.append(
                    {
                        "card_id": card_id,
                        "name": card.name if card else "",
                        "ok": False,
                        "warnings": [f"ERROR: {state.get('error')}"],
                        "log": [],
                    }
                )
                continue
            steps, warnings, runnable = build_remove_array_steps(
                users=list(state.get("users") or []),
                servers=list(state.get("servers") or []),
            )
            if not runnable:
                results.append(
                    {
                        "card_id": card_id,
                        "name": card.name if card else "",
                        "ok": False,
                        "warnings": warnings,
                        "log": [],
                    }
                )
                continue
            executed = run_call_home_steps(steps, self._snap_run_command(card))
            results.append(
                {
                    "card_id": card_id,
                    "name": card.name if card else "",
                    "ok": bool(executed.get("ok")),
                    "warnings": executed.get("warnings") or [],
                    "log": executed.get("log") or [],
                }
            )
        overall_ok = any(row.get("ok") for row in results)
        return {"ok": overall_ok, "arrays": results}
```

6. Add URL property next to `esx_snap_policy_url`:

```python
    @property
    def call_home_cli_url(self) -> str:
        return f"http://127.0.0.1:{self._port}{CALL_HOME_CLI_PATH}"
```

7. Add opener next to `open_esx_snap_policy`:

```python
    def open_call_home_cli(self) -> str:
        """Open the Call Home CLI page in the default browser."""
        self.ensure_running()
        webbrowser.open(self.call_home_cli_url)
        _log(f"Opened Call Home CLI in browser: {self.call_home_cli_url}")
        return self.call_home_cli_url
```

8. In `launchpad/ui/dashboard_view.py` `tool_specs`, insert immediately after System Connectivity:

```python
            ("Call Home CLI", self._open_call_home_cli, None),
```

Add opener next to `_open_system_connectivity`:

```python
    def _open_call_home_cli(self) -> None:
        worker = self._open_sync_browser_report(
            status="Opening Call Home CLI…",
            fail_log="Call Home CLI failed",
            open_url=lambda server: server.open_call_home_cli(),
            summary="Call Home CLI opened — Preview then Run Apply or Run Remove SMTP mutates the selected arrays.",
        )
        threading.Thread(target=worker, daemon=True).start()
```

9. In `tests/test_dashboard_ui_freeze.py` `HEADER_OPENERS`, add `"_open_call_home_cli"` immediately after `"_open_system_connectivity"`.

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_call_home_cli_ops.py tests/test_call_home_cli_page.py tests/test_health_server_call_home_cli.py tests/test_dashboard_ui_freeze.py::test_header_openers_register_off_ui_thread -v`

Expected: PASS. `test_health_dashboard_link` now passes. `test_apply_then_remove_order` must see `svctask` after live re-read — empty `lsemailserver` header-only output must parse as **no servers** so Apply is runnable.

- [ ] **Step 5: Commit**

```powershell
git add -- launchpad/health_server.py launchpad/ui/dashboard_view.py tests/test_health_server_call_home_cli.py tests/test_dashboard_ui_freeze.py tests/test_call_home_cli_page.py
git commit -m "Wire Call Home CLI HealthServer APIs and dashboard button."
```

---

### Task 4: Bump APP_VERSION to 1.6.178

**Files:**
- Modify: `launchpad/config.py`
- Modify: `tests/test_capacity_unit_js.py`
- Modify: `tests/test_hadoop_sudo_wire.py`
- Modify: `tests/test_system_connectivity_version.py`
- Grep remaining `assert APP_VERSION == "1.6.177"` under `tests/` and `launchpad/`

**Interfaces:**
- Produces: `APP_VERSION = "1.6.178"`

- [ ] **Step 1:** Change the three pin tests to `"1.6.178"` (leave config at 1.6.177 for RED).

In `tests/test_capacity_unit_js.py` (`test_app_version_153`):

```python
    assert APP_VERSION == "1.6.178"
```

In `tests/test_hadoop_sudo_wire.py` (`test_version_174`):

```python
    assert APP_VERSION == "1.6.178"
```

In `tests/test_system_connectivity_version.py` (`test_app_version_16174`):

```python
    assert APP_VERSION == "1.6.178"
```

- [ ] **Step 2:** `python -m pytest tests/test_capacity_unit_js.py tests/test_hadoop_sudo_wire.py tests/test_system_connectivity_version.py -v` — Expected FAIL (`'1.6.177' == '1.6.178'`).

- [ ] **Step 3:** `APP_VERSION = "1.6.178"` in `launchpad/config.py`. Grep leftover equality pins under `tests/` and `launchpad/`.

- [ ] **Step 4:** `python -m pytest tests/test_call_home_cli_ops.py tests/test_call_home_cli_page.py tests/test_health_server_call_home_cli.py tests/test_capacity_unit_js.py tests/test_hadoop_sudo_wire.py tests/test_system_connectivity_version.py tests/test_dashboard_ui_freeze.py::test_header_openers_register_off_ui_thread -v` — Expected PASS.

- [ ] **Step 5:**

```powershell
git add -- launchpad/config.py tests/test_capacity_unit_js.py tests/test_hadoop_sudo_wire.py tests/test_system_connectivity_version.py
git commit -m "Bump version to 1.6.178 for Call Home CLI."
```

---

## Spec coverage

| Spec requirement | Task |
|------------------|------|
| Dashboard button, `_open_sync_browser_report`, IBM only | 3 |
| Path `/call-home-cli`, layout, two Run kinds, Load current | 2 |
| IP link outside checkbox label, fetch try/catch | 2 |
| APIs cards/state/preview-apply/run-apply/preview-remove/run-remove | 3 |
| Four SSH commands, parse aliases, cloud status via `parse_svc_call_home` | 1 |
| Quote helper, mask password, hash uses sha256(password) | 1 |
| Apply chemail contact → chemail location → mkemailserver | 1, 3 |
| Existing server blocks all Apply commands on that array | 1, 3 |
| Skip empty SMTP; nothing-to-apply | 1 |
| Remove stopemail → rmemailuser → rmemailserver; already-stopped success | 1, 3 |
| Password not in preview JSON / logs | 1, 3 |
| Health dashboard secondary link | 3 |
| Version 1.6.178 | 4 |
| Out of v1: cloud on/off, Insights, chemailserver, startemail, HPE/Dell | none (intentionally omitted) |
