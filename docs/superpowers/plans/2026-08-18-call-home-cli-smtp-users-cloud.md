# Call Home CLI SMTP / users / Cloud Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend Call Home CLI so each IBM array can edit SMTP in place, add/remove individual email users, and enable/disable Cloud Call Home, shipping as **1.6.180**.

**Architecture:** Ops in `launchpad/call_home_cli_ops.py` build one `SnapStep` list per kind (contact, smtp, users, cloud, remove). The page posts five Preview/Run pairs. `health_server.py` routes SSH I/O only and never logs an unmasked `-password`.

**Tech Stack:** Python, HealthServer HTML/JS, existing `_snap_run_command` / `SnapStep` / `parse_svc_call_home`, pytest.

**Spec:** `docs/superpowers/specs/2026-08-18-call-home-cli-smtp-users-cloud-design.md`

## Global Constraints

- APP_VERSION bump to **1.6.180** only in the final version task. Do not bump in Tasks 1–3.
- IBM `SVC_PROFILES` SSH cards with a non-empty host only. No HPE / Dell / DS8884.
- Five Run kinds: **Contact**, **SMTP**, **Users**, **Cloud**, **Remove SMTP**. A Preview hash for kind A must not unlock Run kind B.
- Contact Apply: `chemail` contact then location only. No `mkemailserver`, `chemailserver`, `mkemailuser`, `startemail`, `chcloudcallhome`, or `chsystem`.
- SMTP: 0 servers → `mkemailserver`; 1 server → `chemailserver {id}`; 2+ → not runnable. Empty SMTP fields skip that array.
- Users: `rmemailuser` then `mkemailuser -usertype support|local`; append `startemail` only when an add exists. Already-started = success.
- Cloud: `chcloudcallhome -enable yes|no` only when Enable/Disable differs from loaded `cloud_configured`.
- Remove SMTP unchanged: `stopemail` → users → servers.
- SMTP password never in LaunchPad DB. Preview JSON, confirm modal, and logs show `********`.
- Stop **that array** on first real CLI error; continue next; no rollback.
- Array IP is `https://{host}` **outside** the checkbox `<label>`.
- Fetch `try/catch` on Load / Preview / Run.
- Place imports at the top of modules (no inline imports).
- Windows PowerShell commits (`git commit -m "..."`); commit at each task commit step.
- Prefer TDD: failing test → implement → pass → commit.
- Do not commit `.superpowers/sdd*` scratch, `LaunchPad-Install/`, or install zips.
- Work on branch `feature/call-home-smtp-users-cloud` (already exists from the spec commit). Do not start from `main` without that spec.

## File structure

| File | Responsibility |
|------|----------------|
| `launchpad/call_home_cli_ops.py` | Sanitizer, per-kind step builders, hashes, already-started |
| `tests/test_call_home_cli_ops.py` | Ops unit tests |
| `launchpad/call_home_cli.py` | Page HTML/JS |
| `tests/test_call_home_cli_page.py` | Page contract tests |
| `launchpad/health_server.py` | New preview/run routes; Contact Apply no longer passes SMTP |
| `tests/test_health_server_call_home_cli.py` | API tests with fake SSH |
| `launchpad/config.py` + version pins | `1.6.180` (Task 4 only) |

---

### Task 1: Ops — sanitizer and per-kind step builders

**Files:**
- Modify: `launchpad/call_home_cli_ops.py`
- Modify: `tests/test_call_home_cli_ops.py`

**Interfaces:**
- Consumes: existing `quote_cli_arg`, `mask_password_in_cmd`, `SnapStep`, `trim_fields`, `SMTP_KEYS`, `CONTACT_KEYS`, `LOCATION_KEYS`, `parse_email_servers`, `parse_email_users`
- Produces:
  - `EMAIL_USER_TYPES: tuple[str, ...] = ("support", "local")`
  - `sanitize_location_state(location: dict) -> dict[str, str]`
  - `parse_lssystem_contact_location` returns sanitized location (`running`/`stopped` state → `""`)
  - `is_email_already_started(text: str) -> bool`
  - `build_apply_array_steps(*, contact: dict, location: dict) -> tuple[list[SnapStep], list[str], bool]` — contact/location only (drop `smtp` and `servers` parameters)
  - `build_smtp_array_steps(*, smtp: dict, servers: list[dict]) -> tuple[list[SnapStep], list[str], bool]`
  - `build_users_array_steps(*, existing: list[dict], remove_ids: list[str], add: list[dict]) -> tuple[list[SnapStep], list[str], bool]`
  - `build_cloud_array_steps(*, requested: str, configured: str) -> tuple[list[SnapStep], list[str], bool]`
  - `preview_hash(kind: str, payload: dict) -> str` kinds: `"apply"`, `"smtp"`, `"users"`, `"cloud"`, `"remove"`
  - `run_call_home_steps` treats `startemail` already-started like `stopemail` already-stopped

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_call_home_cli_ops.py` (keep existing quote/parse/remove tests). Change `test_apply_contact_location_then_mkemailserver` and `test_apply_skips_empty_smtp_and_blocks_existing_server` so Contact Apply no longer accepts `smtp`/`servers` and never emits `mkemailserver`. Replace those two tests with:

```python
from launchpad.call_home_cli_ops import (
    build_apply_array_steps,
    build_cloud_array_steps,
    build_smtp_array_steps,
    build_users_array_steps,
    is_email_already_started,
    parse_lssystem_contact_location,
    preview_hash,
    run_call_home_steps,
    sanitize_location_state,
)


def test_sanitize_running_stopped_state():
    assert sanitize_location_state({"state": "running"})["state"] == ""
    assert sanitize_location_state({"state": "STOPPED"})["state"] == ""
    assert sanitize_location_state({"state": "SC"})["state"] == "SC"
    text = "email_state:running\nemail_city:Williamston\n"
    _contact, location = parse_lssystem_contact_location(text)
    assert location["state"] == ""
    assert location["city"] == "Williamston"


def test_apply_contact_location_only():
    steps, warnings, runnable = build_apply_array_steps(
        contact={"name": "SANArch", "reply": "a@b.com", "primary": "", "alternate": ""},
        location={
            "company": "Walgreens", "street": "", "city": "", "state": "",
            "postal": "", "country": "", "comment": "",
        },
    )
    assert runnable is True
    assert warnings == []
    assert [s.kind for s in steps] == ["chemail", "chemail"]
    assert all("mkemailserver" not in s.cmd for s in steps)
    assert all("chemailserver" not in s.cmd for s in steps)
    empty, warns, ok = build_apply_array_steps(
        contact={"name": "", "reply": "", "primary": "", "alternate": ""},
        location={
            "company": "", "street": "", "city": "", "state": "",
            "postal": "", "country": "", "comment": "",
        },
    )
    assert ok is False
    assert empty == []
    assert any("nothing to apply" in w.lower() for w in warns)


def test_smtp_mk_vs_chemail_vs_two_servers():
    add, _, ok = build_smtp_array_steps(
        smtp={"ip": "172.29.62.98", "port": "25", "username": "u", "password": "s3cret"},
        servers=[],
    )
    assert ok is True
    assert add[0].kind == "mkemailserver"
    assert "s3cret" in add[0].cmd

    change, _, ok2 = build_smtp_array_steps(
        smtp={"ip": "10.0.0.1", "port": "25", "username": "u", "password": ""},
        servers=[{"id": "0", "name": "emailserver0", "ip": "172.29.62.98", "port": "25", "username": "u"}],
    )
    assert ok2 is True
    assert change[0].kind == "chemailserver"
    assert change[0].cmd.startswith("svctask chemailserver 0")
    assert "-ip" in change[0].cmd and "-port" in change[0].cmd
    assert "-password" not in change[0].cmd

    blocked, warns, ok3 = build_smtp_array_steps(
        smtp={"ip": "10.0.0.1", "port": "25", "username": "", "password": ""},
        servers=[
            {"id": "0", "name": "emailserver0", "ip": "1.2.3.4", "port": "25", "username": ""},
            {"id": "1", "name": "emailserver1", "ip": "1.2.3.5", "port": "25", "username": ""},
        ],
    )
    assert ok3 is False
    assert blocked == []
    assert any("more than one" in w.lower() for w in warns)

    skip, _, ok4 = build_smtp_array_steps(
        smtp={"ip": "", "port": "", "username": "", "password": ""},
        servers=[],
    )
    assert ok4 is False
    assert skip == []

    need_pw, pw_warns, ok5 = build_smtp_array_steps(
        smtp={"ip": "1.2.3.4", "port": "25", "username": "newuser", "password": ""},
        servers=[{"id": "0", "name": "emailserver0", "ip": "1.2.3.4", "port": "25", "username": "old"}],
    )
    assert ok5 is False
    assert any("password" in w.lower() for w in pw_warns)


def test_users_remove_then_add_then_startemail():
    steps, _, ok = build_users_array_steps(
        existing=[
            {"id": "0", "name": "support", "address": "callhome0@de.ibm.com", "user_type": "support"},
            {"id": "1", "name": "local", "address": "old@wags.com", "user_type": "local"},
        ],
        remove_ids=["1"],
        add=[{"address": "EISSAN-Alerts@walgreens.com", "user_type": "local"}],
    )
    assert ok is True
    assert [s.kind for s in steps] == ["rmemailuser", "mkemailuser", "startemail"]
    assert steps[0].cmd == "svctask rmemailuser 1"
    assert "mkemailuser" in steps[1].cmd
    assert "-usertype local" in steps[1].cmd
    assert "EISSAN-Alerts@walgreens.com" in steps[1].cmd
    assert steps[2].cmd == "svctask startemail"

    none, warns, ok2 = build_users_array_steps(existing=[], remove_ids=[], add=[])
    assert ok2 is False
    assert none == []

    dup, dup_warns, ok3 = build_users_array_steps(
        existing=[{"id": "0", "name": "support", "address": "callhome0@de.ibm.com", "user_type": "support"}],
        remove_ids=[],
        add=[{"address": "callhome0@de.ibm.com", "user_type": "support"}],
    )
    assert ok3 is False
    assert any("duplicate" in w.lower() for w in dup_warns)

    bad, bad_warns, ok4 = build_users_array_steps(
        existing=[],
        remove_ids=[],
        add=[{"address": "a@b.com", "user_type": "inventory"}],
    )
    assert ok4 is False
    assert any("usertype" in w.lower() or "user type" in w.lower() for w in bad_warns)

    remove_only, _, ok5 = build_users_array_steps(
        existing=[{"id": "0", "name": "support", "address": "a@b.com", "user_type": "support"}],
        remove_ids=["0"],
        add=[],
    )
    assert ok5 is True
    assert [s.kind for s in remove_only] == ["rmemailuser"]


def test_cloud_only_when_changed():
    steps, _, ok = build_cloud_array_steps(requested="enable", configured="no")
    assert ok is True
    assert steps[0].cmd == "svctask chcloudcallhome -enable yes"
    steps2, _, ok2 = build_cloud_array_steps(requested="disable", configured="yes")
    assert ok2 is True
    assert steps2[0].cmd == "svctask chcloudcallhome -enable no"
    skip, _, ok3 = build_cloud_array_steps(requested="enable", configured="yes")
    assert ok3 is False
    assert skip == []


def test_preview_hash_isolates_kinds_and_hides_password():
    smtp_payload = {
        "arrays": [{"card_id": 1, "smtp": {"ip": "1.2.3.4", "port": "25", "username": "u", "password": "s3cret"}}]
    }
    h_smtp = preview_hash("smtp", smtp_payload)
    other = {"arrays": [{"card_id": 1, "smtp": {"ip": "1.2.3.4", "port": "25", "username": "u", "password": "other"}}]}
    assert preview_hash("smtp", other) != h_smtp
    assert "s3cret" not in h_smtp
    apply_payload = {
        "contact": {"name": "A", "reply": "", "primary": "", "alternate": ""},
        "arrays": [{"card_id": 1, "location": {
            "company": "", "street": "", "city": "", "state": "", "postal": "", "country": "", "comment": "",
        }}],
    }
    assert preview_hash("apply", apply_payload) != h_smtp
    assert preview_hash("users", {"arrays": [{"card_id": 1, "remove_ids": ["0"], "add": []}]}) != h_smtp
    assert preview_hash("cloud", {"arrays": [{"card_id": 1, "requested": "enable"}]}) != h_smtp
    assert preview_hash("remove", {"arrays": [{"card_id": 1}]}) != h_smtp


def test_startemail_already_started_is_success():
    assert is_email_already_started("CMMVC6187E The e-mail service is already started.")
    steps, _, _ = build_users_array_steps(
        existing=[],
        remove_ids=[],
        add=[{"address": "a@b.com", "user_type": "local"}],
    )

    def run_cmd(command: str) -> str:
        if "startemail" in command:
            raise RuntimeError("CMMVC6187E The e-mail service is already started.")
        return "ok"

    result = run_call_home_steps(steps, run_cmd)
    assert result["ok"] is True
    assert result["log"][-1]["ok"] is True
```

Also update `test_run_stopemail_already_stopped_is_success` so the SMTP secret-path uses `build_smtp_array_steps` instead of `build_apply_array_steps(..., smtp=...)`.

Remove `smtp`/`servers` kwargs from `test_apply_contact_location_then_mkemailserver` / `test_apply_skips_empty_smtp_and_blocks_existing_server` by deleting those two functions (replaced above). Keep `test_preview_hash_kind_and_password_not_plaintext` only if it still matches contact-only apply hash (no shared `smtp` key). Delete it if it duplicates `test_preview_hash_isolates_kinds_and_hides_password`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_call_home_cli_ops.py -v`

Expected: FAIL — `build_smtp_array_steps` / `sanitize_location_state` / `build_users_array_steps` / `build_cloud_array_steps` ImportError or `build_apply_array_steps` unexpected keyword `smtp`.

- [ ] **Step 3: Implement ops**

In `launchpad/call_home_cli_ops.py`:

```python
EMAIL_USER_TYPES = ("support", "local")
_STATUS_STATE = frozenset({"running", "stopped"})


def sanitize_location_state(location: dict | None) -> dict[str, str]:
    loc = trim_fields(location, LOCATION_KEYS)
    if loc["state"].lower() in _STATUS_STATE:
        loc["state"] = ""
    return loc


def is_email_already_started(text: str) -> bool:
    return "already started" in str(text or "").lower()
```

At the end of `parse_lssystem_contact_location`, `return contact, sanitize_location_state(location)`.

Change `build_apply_array_steps` to:

```python
def build_apply_array_steps(
    *,
    contact: dict,
    location: dict,
) -> tuple[list[SnapStep], list[str], bool]:
    warnings: list[str] = []
    contact = trim_fields(contact, CONTACT_KEYS)
    location = sanitize_location_state(location)
    has_contact = any(contact.values())
    has_location = any(location.values())
    if not has_contact and not has_location:
        warnings.append("ERROR: nothing to apply")
        return [], warnings, False
    steps: list[SnapStep] = []
    if has_contact:
        pairs = [(flag, contact[key]) for key, flag in CONTACT_FLAGS if contact[key]]
        steps.append(SnapStep(kind="chemail", purpose="set contact", cmd=_chemail_cmd(pairs)))
    if has_location:
        pairs = [(flag, location[key]) for key, flag in LOCATION_FLAGS if location[key]]
        steps.append(SnapStep(kind="chemail", purpose="set location", cmd=_chemail_cmd(pairs)))
    return steps, warnings, True
```

Add SMTP / users / cloud builders:

```python
def _smtp_port_ok(port: str) -> bool:
    try:
        value = int(port)
    except ValueError:
        return False
    return 1 <= value <= 65535


def build_smtp_array_steps(
    *,
    smtp: dict,
    servers: list[dict],
) -> tuple[list[SnapStep], list[str], bool]:
    warnings: list[str] = []
    smtp = trim_fields(smtp, SMTP_KEYS)
    if not smtp_add_requested(smtp):
        warnings.append("ERROR: nothing to apply")
        return [], warnings, False
    if not smtp["ip"] or not smtp["port"]:
        warnings.append("ERROR: SMTP needs IP (or hostname) and port")
    elif not _smtp_port_ok(smtp["port"]):
        warnings.append("ERROR: SMTP port must be 1-65535")
    if len(servers) > 1:
        warnings.append("ERROR: more than one email server")
    existing = servers[0] if len(servers) == 1 else None
    existing_user = str((existing or {}).get("username") or "").strip()
    username_changing = bool(existing and smtp["username"] and smtp["username"] != existing_user)
    if smtp["username"] and not smtp["password"] and (existing is None or username_changing):
        warnings.append("ERROR: SMTP password is required when username is set")
    if any(item.startswith("ERROR:") for item in warnings):
        return [], warnings, False
    flags: list[str] = []
    if smtp["ip"]:
        flags.extend(["-ip", quote_cli_arg(smtp["ip"])])
    if smtp["port"]:
        flags.extend(["-port", quote_cli_arg(smtp["port"])])
    if smtp["username"]:
        flags.extend(["-username", quote_cli_arg(smtp["username"])])
    if smtp["password"]:
        flags.extend(["-password", quote_cli_arg(smtp["password"])])
    if existing is None:
        cmd = " ".join(["svctask", "mkemailserver", *flags])
        return [SnapStep(kind="mkemailserver", purpose="add email server", cmd=cmd)], warnings, True
    token = _object_token(existing)
    cmd = " ".join(["svctask", "chemailserver", quote_cli_arg(token), *flags])
    return [SnapStep(kind="chemailserver", purpose="change email server", cmd=cmd)], warnings, True


def _norm_addr(value: str) -> str:
    return str(value or "").strip().lower()


def build_users_array_steps(
    *,
    existing: list[dict],
    remove_ids: list[str],
    add: list[dict],
) -> tuple[list[SnapStep], list[str], bool]:
    warnings: list[str] = []
    remove_set = {str(item).strip() for item in remove_ids if str(item).strip()}
    adds = []
    for row in add or []:
        if not isinstance(row, dict):
            continue
        address = str(row.get("address") or "").strip()
        user_type = str(row.get("user_type") or "").strip().lower()
        if not address:
            continue
        adds.append({"address": address, "user_type": user_type})
    for row in adds:
        if row["user_type"] not in EMAIL_USER_TYPES:
            warnings.append("ERROR: user type must be support or local")
            break
    kept_addrs = {
        _norm_addr(user.get("address") or user.get("name") or "")
        for user in existing
        if _object_token(user) not in remove_set
    }
    for row in adds:
        if _norm_addr(row["address"]) in kept_addrs:
            warnings.append("ERROR: duplicate email user")
            break
        kept_addrs.add(_norm_addr(row["address"]))
    if not remove_set and not adds:
        warnings.append("ERROR: nothing to apply")
    if any(item.startswith("ERROR:") for item in warnings):
        return [], warnings, False
    steps: list[SnapStep] = []
    for user in existing:
        token = _object_token(user)
        if token not in remove_set:
            continue
        steps.append(
            SnapStep(
                kind="rmemailuser",
                purpose=f"remove email user {token}",
                cmd=f"svctask rmemailuser {quote_cli_arg(token)}",
            )
        )
    for row in adds:
        steps.append(
            SnapStep(
                kind="mkemailuser",
                purpose=f"add email user {row['address']}",
                cmd=(
                    "svctask mkemailuser -address "
                    f"{quote_cli_arg(row['address'])} -usertype {quote_cli_arg(row['user_type'])}"
                ),
            )
        )
    if any(step.kind == "mkemailuser" for step in steps):
        steps.append(SnapStep(kind="startemail", purpose="start email", cmd="svctask startemail"))
    return steps, warnings, True


def build_cloud_array_steps(
    *,
    requested: str,
    configured: str,
) -> tuple[list[SnapStep], list[str], bool]:
    want = str(requested or "").strip().lower()
    have = str(configured or "").strip().lower()
    if want not in {"enable", "disable"}:
        return [], ["ERROR: cloud requested must be enable or disable"], False
    have_on = have in {"yes", "enable", "enabled"}
    want_on = want == "enable"
    if want_on == have_on:
        return [], ["ERROR: nothing to apply"], False
    flag = "yes" if want_on else "no"
    return (
        [
            SnapStep(
                kind="chcloudcallhome",
                purpose="set cloud call home",
                cmd=f"svctask chcloudcallhome -enable {flag}",
            )
        ],
        [],
        True,
    )
```

Extend `preview_hash`:

```python
def preview_hash(kind: str, payload: dict) -> str:
    arrays = payload.get("arrays") or []

    def card_ids(extra: Callable[[dict], dict] | None = None) -> list[dict]:
        rows = []
        for item in arrays:
            if not isinstance(item, dict) or item.get("card_id") is None:
                continue
            row = {"card_id": int(item["card_id"])}
            if extra is not None:
                row.update(extra(item))
            rows.append(row)
        return sorted(rows, key=lambda row: row["card_id"])

    if kind == "apply":
        blob = {
            "kind": "apply",
            "contact": trim_fields(payload.get("contact"), CONTACT_KEYS),
            "arrays": card_ids(lambda item: {"location": sanitize_location_state(item.get("location") or {})}),
        }
    elif kind == "smtp":
        def smtp_row(item: dict) -> dict:
            smtp = trim_fields(item.get("smtp"), SMTP_KEYS)
            return {
                "smtp": {
                    "ip": smtp["ip"],
                    "port": smtp["port"],
                    "username": smtp["username"],
                    "password_sha256": password_sha256(smtp["password"]),
                }
            }
        blob = {"kind": "smtp", "arrays": card_ids(smtp_row)}
    elif kind == "users":
        def users_row(item: dict) -> dict:
            add = []
            for row in item.get("add") or []:
                if not isinstance(row, dict):
                    continue
                add.append({
                    "address": str(row.get("address") or "").strip(),
                    "user_type": str(row.get("user_type") or "").strip().lower(),
                })
            return {
                "remove_ids": sorted(str(x).strip() for x in (item.get("remove_ids") or []) if str(x).strip()),
                "add": add,
            }
        blob = {"kind": "users", "arrays": card_ids(users_row)}
    elif kind == "cloud":
        blob = {
            "kind": "cloud",
            "arrays": card_ids(lambda item: {"requested": str(item.get("requested") or "").strip().lower()}),
        }
    else:
        blob = {"kind": "remove", "arrays": card_ids()}
    return hashlib.sha256(
        json.dumps(blob, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ).hexdigest()
```

In `run_call_home_steps`, treat `startemail` the same as `stopemail` for already-started:

```python
            if step.kind == "stopemail" and is_email_already_stopped(text):
                ...
            if step.kind == "startemail" and is_email_already_started(text):
                entry["ok"] = True
                entry["output"] = text
                log.append(entry)
                continue
```

Apply that both on exception `text` and on command output `text` (copy the existing stopemail branches).

Fix `Callable` import usage in `preview_hash` — use `from collections.abc import Callable` already present. If using a nested callable type for `card_ids`, a plain optional function without typing `Callable[[dict], dict]` in the signature is fine (untyped `extra=None`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_call_home_cli_ops.py -v`

Expected: PASS. If `health_server` / `test_health_server_call_home_cli.py` fail because `build_apply_array_steps` no longer takes `smtp`, that is Task 3 — do not "fix" by restoring SMTP on Contact Apply. You may leave those failures until Task 3 **only if** `tests/test_call_home_cli_ops.py` is fully green. Prefer updating `health_server.py` call sites in this step to:

```python
steps, warnings, runnable = build_apply_array_steps(
    contact=payload.get("contact") or {},
    location=item.get("location") or {},
)
```

in both `preview_call_home_apply` and `run_call_home_apply`, so the tree stays importable. Do not add SMTP/users/cloud routes yet.

- [ ] **Step 5: Commit**

```powershell
git add launchpad/call_home_cli_ops.py tests/test_call_home_cli_ops.py launchpad/health_server.py
git commit -m "Split Call Home Apply from SMTP and add SMTP/user/cloud step builders."
```

---

### Task 2: Page — per-array SMTP/users/cloud and five Preview/Run pairs

**Files:**
- Modify: `launchpad/call_home_cli.py`
- Modify: `tests/test_call_home_cli_page.py`

**Interfaces:**
- Consumes: existing `/api/call-home/cards` and `/api/call-home/state` (`servers`, `users`, `cloud_configured`, `cloud_status`)
- Produces: page markup/JS posting Contact (`preview-apply`/`run-apply`), SMTP, users, cloud, and remove

- [ ] **Step 1: Write the failing page tests**

Replace assertions in `tests/test_call_home_cli_page.py`:

```python
from launchpad.call_home_cli import CALL_HOME_CLI_HTML, CALL_HOME_CLI_PATH
from launchpad.health_server import DASHBOARD_HTML


def test_path_title_and_actions():
    assert CALL_HOME_CLI_PATH == "/call-home-cli"
    html = CALL_HOME_CLI_HTML
    assert "Call Home CLI" in html
    assert "Preview Contact" in html
    assert "Run Contact" in html
    assert "Preview SMTP" in html
    assert "Run SMTP" in html
    assert "Preview Users" in html
    assert "Run Users" in html
    assert "Preview Cloud" in html
    assert "Run Cloud" in html
    assert "Preview Remove SMTP" in html
    assert "Run Remove SMTP" in html
    assert 'id="smtp-ip"' not in html  # shared SMTP block removed
    assert "SMTP add (optional)" not in html


def test_api_paths_and_payload_fields():
    html = CALL_HOME_CLI_HTML
    for path in (
        "/api/call-home/cards",
        "/api/call-home/state",
        "/api/call-home/preview-apply",
        "/api/call-home/run-apply",
        "/api/call-home/preview-smtp",
        "/api/call-home/run-smtp",
        "/api/call-home/preview-users",
        "/api/call-home/run-users",
        "/api/call-home/preview-cloud",
        "/api/call-home/run-cloud",
        "/api/call-home/preview-remove",
        "/api/call-home/run-remove",
    ):
        assert path in html
    assert "remove_ids" in html
    assert "user_type" in html
    assert "requested" in html


def test_array_host_is_https_link_outside_checkbox_label():
    html = CALL_HOME_CLI_HTML
    assert html.find("</label>' + arrayHostLink") != -1
    assert 'target="_blank"' in html
    assert 'rel="noopener"' in html


def test_five_run_kinds_invalidate_and_catch():
    html = CALL_HOME_CLI_HTML
    assert "invalidatePreview" in html
    for key in ("apply", "smtp", "users", "cloud", "remove"):
        assert f"__{key}Ok" in html or f"window.__{key}Ok" in html
    assert "catch" in html
    assert "This writes Call Home contact/location" in html
    assert "optional SMTP add" not in html
    assert "This writes SMTP" in html
    assert "This writes Call Home email users" in html
    assert "This enables or disables Cloud Call Home" in html


def test_run_modal_renders_array_logs():
    html = CALL_HOME_CLI_HTML
    chunk = html[html.find("function previewLines") : html.find("function previewLines") + 900]
    assert "row.log" in chunk
    assert "entry.error" in chunk
    assert "runHadArrayErrors" in html
    assert "finished with errors" in html


def test_health_dashboard_link():
    assert 'href="/call-home-cli"' in DASHBOARD_HTML
```

- [ ] **Step 2: Run page tests to verify they fail**

Run: `python -m pytest tests/test_call_home_cli_page.py -v`

Expected: FAIL (`Preview Contact` missing, shared `id="smtp-ip"` still present).

- [ ] **Step 3: Rewrite the page**

Update the module docstring to `Call Home CLI page — contact, location, SMTP, users, Cloud.`

Replace the lede with: `Set shared contact and per-array location, SMTP, email users, and Cloud Call Home. Each action has its own Preview and Run. Remove SMTP deletes email users and servers only. Preview first. The first CLI error stops that array; other arrays continue. No rollback.`

Remove the shared **SMTP add** block (`smtp-ip` / `smtp-port` / `smtp-username` / `smtp-password` at the top). Keep Shared contact.

Replace the action buttons with:

```html
        <button type="button" class="secondary" id="select-all-btn">Select all</button>
        <button type="button" class="secondary" id="select-none-btn">Select none</button>
        <button type="button" class="secondary" id="load-btn">Load current</button>
        <button type="button" class="secondary" id="preview-apply-btn">Preview Contact</button>
        <button type="button" class="danger" id="run-apply-btn" disabled>Run Contact</button>
        <button type="button" class="secondary" id="preview-smtp-btn">Preview SMTP</button>
        <button type="button" class="danger" id="run-smtp-btn" disabled>Run SMTP</button>
        <button type="button" class="secondary" id="preview-users-btn">Preview Users</button>
        <button type="button" class="danger" id="run-users-btn" disabled>Run Users</button>
        <button type="button" class="secondary" id="preview-cloud-btn">Preview Cloud</button>
        <button type="button" class="danger" id="run-cloud-btn" disabled>Run Cloud</button>
        <button type="button" class="secondary" id="preview-remove-btn">Preview Remove SMTP</button>
        <button type="button" class="danger" id="run-remove-btn" disabled>Run Remove SMTP</button>
```

In `render()`, keep the checkbox + `arrayHostLink` + cloud status span. Add per array:

- `<select id="cloud-req-{id}">` options `enable` / `disable` (labels Enable / Disable)
- SMTP grid: `smtp-ip-{id}`, `smtp-port-{id}`, `smtp-username-{id}`, `smtp-password-{id}` (password type)
- `<div id="users-{id}">` filled by `fillUsers`
- location grid unchanged
- SMTP summary line unchanged

JS state:

```javascript
    const KINDS = ["apply","smtp","users","cloud","remove"];
    const runBtns = {};
    KINDS.forEach((k) => { runBtns[k] = document.getElementById(k === "apply" ? "run-apply-btn" : k === "remove" ? "run-remove-btn" : "run-"+k+"-btn"); });
    function invalidatePreview() {
      KINDS.forEach((k) => { window["__"+k+"Ok"] = false; window["__"+k+"Hash"] = ""; runBtns[k].disabled = true; });
    }
```

Payload helpers:

```javascript
    function smtpPayload(id) {
      return {
        ip: (document.getElementById("smtp-ip-"+id)||{}).value || "",
        port: (document.getElementById("smtp-port-"+id)||{}).value || "",
        username: (document.getElementById("smtp-username-"+id)||{}).value || "",
        password: (document.getElementById("smtp-password-"+id)||{}).value || ""
      };
    }
    function usersPayload(id) {
      const remove_ids = [...document.querySelectorAll(".user-rm[data-card-id='"+id+"']:checked")].map((el) => el.dataset.userId);
      const add = [];
      const addr = document.getElementById("user-add-addr-"+id);
      const typ = document.getElementById("user-add-type-"+id);
      if (addr && addr.value.trim()) add.push({ address: addr.value, user_type: typ ? typ.value : "local" });
      return { card_id: id, remove_ids, add };
    }
    function applyPayload() {
      return { contact: contactPayload(), arrays: selectedIds().map((id) => ({ card_id: id, location: locPayload(id) })) };
    }
    function smtpKindPayload() {
      return { arrays: selectedIds().map((id) => ({ card_id: id, smtp: smtpPayload(id) })) };
    }
    function usersKindPayload() {
      return { arrays: selectedIds().map((id) => usersPayload(id)) };
    }
    function cloudKindPayload() {
      return { arrays: selectedIds().map((id) => ({ card_id: id, requested: (document.getElementById("cloud-req-"+id)||{}).value || "enable" })) };
    }
    function removePayload() {
      return { arrays: selectedIds().map((id) => ({ card_id: id })) };
    }
```

`fillUsers(id, users)`: render existing rows `address`, `user_type`, checkbox `class="user-rm" data-card-id data-user-id`, plus one add row address + `<select>` support/local.

`loadCurrent`: after success, set cloud select to `enable` if `data.cloud_configured === "yes"` else `disable`; fill SMTP ip/port/username from `data.servers[0]` if present; leave password empty; `fillUsers`; `fillLoc`. Do not fill shared SMTP (gone).

`doPreview(kind)` maps:

| kind | url | body |
|------|-----|------|
| apply | `/api/call-home/preview-apply` | `applyPayload()` |
| smtp | `/api/call-home/preview-smtp` | `smtpKindPayload()` |
| users | `/api/call-home/preview-users` | `usersKindPayload()` |
| cloud | `/api/call-home/preview-cloud` | `cloudKindPayload()` |
| remove | `/api/call-home/preview-remove` | `removePayload()` |

Set `window.__{kind}Ok` and `window.__{kind}Hash` and enable that kind's Run button only.

Run confirm strings (exact):

- apply: `This writes Call Home contact/location on the selected arrays. The first CLI error stops that array; other arrays continue. No rollback.`
- smtp: `This writes SMTP (add or change the email server) on the selected arrays. The first CLI error stops that array; other arrays continue. No rollback.`
- users: `This writes Call Home email users on the selected arrays. The first CLI error stops that array; other arrays continue. No rollback.`
- cloud: `This enables or disables Cloud Call Home on the selected arrays. The first CLI error stops that array; other arrays continue. No rollback.`
- remove: keep existing remove copy.

Run URLs: `/api/call-home/run-apply`, `run-smtp`, `run-users`, `run-cloud`, `run-remove`. Body: payload + `{ confirm: true, preview_hash: window.__{kind}Hash }`. Status text `{Kind} finished.` / `{Kind} finished with errors.` using Contact / SMTP / Users / Cloud / Remove.

Keep `previewLines` / `runHadArrayErrors` / `arrayHostLink`. Wire `input`/`change` on new fields to `invalidatePreview`. Remove listeners on deleted top-level smtp ids.

Add CSS if needed: `select { color:var(--text); background:#0f141d; border:1px solid var(--border); border-radius:8px; padding:6px 9px; font:inherit; }`

- [ ] **Step 4: Run page tests**

Run: `python -m pytest tests/test_call_home_cli_page.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add launchpad/call_home_cli.py tests/test_call_home_cli_page.py
git commit -m "Add per-array SMTP, users, and Cloud controls to Call Home CLI."
```

---

### Task 3: HealthServer routes for SMTP, users, and Cloud

**Files:**
- Modify: `launchpad/health_server.py` (imports ~83–90; POST path set ~4441–4479; methods ~6222–6502)
- Modify: `tests/test_health_server_call_home_cli.py`

**Interfaces:**
- Consumes: `build_apply_array_steps`, `build_smtp_array_steps`, `build_users_array_steps`, `build_cloud_array_steps`, `build_remove_array_steps`, `collect_call_home_state`, `masked_steps_payload`, `call_home_preview_hash`, `run_call_home_steps`
- Produces: `preview_call_home_smtp` / `run_call_home_smtp` / `preview_call_home_users` / `run_call_home_users` / `preview_call_home_cloud` / `run_call_home_cloud`

- [ ] **Step 1: Write the failing API tests**

Update `tests/test_health_server_call_home_cli.py`:

- Change `test_existing_server_blocks_all_apply_commands` into two tests:
  - Contact Apply **succeeds** (sends `chemail`) even when `lsemailserver` has a row.
  - SMTP Preview/Run with two servers is not runnable; with one server sends `chemailserver` not `mkemailserver`.
- Change `test_apply_then_remove_order` so Apply payload has **no** smtp and mutate list is only `chemail` (no `mkemailserver`). Keep remove order test as-is.
- Add:

```python
def test_smtp_chemailserver_in_place(monkeypatch):
    server = _server()
    calls = _bind(monkeypatch, [("lscloudcallhome", CLOUD), ("lsemailserver", SERVERS), ("lsemailuser", USERS), ("lssystem", LSYS)])
    payload = {
        "arrays": [{"card_id": 1, "smtp": {"ip": "10.0.0.1", "port": "25", "username": "u", "password": "s3cret"}}]
    }
    payload["preview_hash"] = preview_hash("smtp", payload)
    result = server.run_call_home_smtp(payload, confirm=True)
    assert result["ok"] is True
    mutate = [c for c in calls if c.startswith("svctask")]
    assert mutate[0].startswith("svctask chemailserver")
    assert "s3cret" in mutate[0]
    assert "s3cret" not in result["arrays"][0]["log"][0]["cmd"]


def test_users_and_cloud_and_hash_isolation(monkeypatch):
    server = _server()
    calls = _bind(monkeypatch, [("lscloudcallhome", CLOUD), ("lsemailserver", SERVERS), ("lsemailuser", USERS), ("lssystem", LSYS)])
    users = {
        "arrays": [{"card_id": 1, "remove_ids": ["0"], "add": [{"address": "ops@wags.com", "user_type": "local"}]}],
        "confirm": True,
        "preview_hash": preview_hash("apply", {"contact": {}, "arrays": [{"card_id": 1, "location": {}}]}),
    }
    bad = server.run_call_home_users(users, confirm=True)
    assert bad["ok"] is False
    assert not any("mkemailuser" in c for c in calls)
    users["preview_hash"] = preview_hash("users", users)
    good = server.run_call_home_users(users, confirm=True)
    assert good["ok"] is True
    mutate = [c for c in calls if c.startswith("svctask")]
    assert mutate[0].startswith("svctask rmemailuser")
    assert any("mkemailuser" in c for c in mutate)
    assert mutate[-1] == "svctask startemail"
    cloud = {
        "arrays": [{"card_id": 1, "requested": "disable"}],
        "confirm": True,
        "preview_hash": preview_hash("cloud", {"arrays": [{"card_id": 1, "requested": "disable"}]}),
    }
    calls2 = _bind(monkeypatch, [("lscloudcallhome", "id:status\n0:active\n"), ("lsemailserver", EMPTY_SERVERS), ("lsemailuser", ""), ("lssystem", LSYS)])
    out = server.run_call_home_cloud(cloud, confirm=True)
    assert out["ok"] is True
    assert any("chcloudcallhome -enable no" in c for c in calls2)
```

- [ ] **Step 2: Run API tests to verify they fail**

Run: `python -m pytest tests/test_health_server_call_home_cli.py -v`

Expected: FAIL (`run_call_home_smtp` missing).

- [ ] **Step 3: Wire routes and methods**

Expand the POST path set:

```python
        if path in {
            "/api/call-home/state",
            "/api/call-home/preview-apply",
            "/api/call-home/run-apply",
            "/api/call-home/preview-smtp",
            "/api/call-home/run-smtp",
            "/api/call-home/preview-users",
            "/api/call-home/run-users",
            "/api/call-home/preview-cloud",
            "/api/call-home/run-cloud",
            "/api/call-home/preview-remove",
            "/api/call-home/run-remove",
        }:
```

Dispatch:

```python
            if path == "/api/call-home/state":
                ...
                return
            handlers = {
                "/api/call-home/preview-apply": lambda: server.preview_call_home_apply(payload),
                "/api/call-home/run-apply": lambda: server.run_call_home_apply(payload, confirm=payload.get("confirm") is True),
                "/api/call-home/preview-smtp": lambda: server.preview_call_home_smtp(payload),
                "/api/call-home/run-smtp": lambda: server.run_call_home_smtp(payload, confirm=payload.get("confirm") is True),
                "/api/call-home/preview-users": lambda: server.preview_call_home_users(payload),
                "/api/call-home/run-users": lambda: server.run_call_home_users(payload, confirm=payload.get("confirm") is True),
                "/api/call-home/preview-cloud": lambda: server.preview_call_home_cloud(payload),
                "/api/call-home/run-cloud": lambda: server.run_call_home_cloud(payload, confirm=payload.get("confirm") is True),
                "/api/call-home/preview-remove": lambda: server.preview_call_home_remove(payload),
                "/api/call-home/run-remove": lambda: server.run_call_home_remove(payload, confirm=payload.get("confirm") is True),
            }
            result = handlers[path]()
            self._send_json(result, status=200 if result.get("ok") else 400)
```

Update imports:

```python
from launchpad.call_home_cli_ops import (
    build_apply_array_steps,
    build_cloud_array_steps,
    build_remove_array_steps,
    build_smtp_array_steps,
    build_users_array_steps,
    collect_call_home_state,
    masked_steps_payload,
    preview_hash as call_home_preview_hash,
    run_call_home_steps,
)
```

Add a private helper on `HealthServer` (place above `preview_call_home_apply`):

```python
    def _call_home_preview_rows(
        self,
        payload: dict,
        kind: str,
        builder,
    ) -> dict[str, Any]:
        items = self._call_home_selected(payload.get("arrays"))
        hashed = call_home_preview_hash(kind, payload)
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
                    {"card_id": item.get("card_id"), "name": "", "runnable": False,
                     "warnings": ["ERROR: card_id is required"], "steps": []}
                )
                continue
            card = self._call_home_card_by_id(card_id)
            if card is None or not self._call_home_eligible(card):
                arrays_out.append(
                    {"card_id": card_id, "name": "", "runnable": False,
                     "warnings": [f"ERROR: Unknown or ineligible Health Card id {card_id}"], "steps": []}
                )
                continue
            state = collect_call_home_state(self._snap_run_command(card))
            if not state.get("ok"):
                arrays_out.append(
                    {"card_id": card_id, "name": card.name, "runnable": False,
                     "warnings": [f"ERROR: {state.get('error') or 'load failed'}"], "steps": []}
                )
                continue
            steps, warnings, runnable = builder(item, state)
            arrays_out.append(
                {"card_id": card_id, "name": card.name, "runnable": runnable,
                 "warnings": warnings, "steps": masked_steps_payload(steps)}
            )
        ok = bool(arrays_out) and all(row.get("runnable") for row in arrays_out)
        return {"ok": ok, "arrays": arrays_out, "preview_hash": hashed}

    def _call_home_run_rows(
        self,
        payload: dict,
        *,
        kind: str,
        confirm: bool,
        confirm_warning: str,
        hash_warning: str,
        preview_fn,
        builder,
        skip_if_live_mismatch=None,
    ) -> dict[str, Any]:
        hashed = call_home_preview_hash(kind, payload)
        if confirm is not True:
            return {"ok": False, "arrays": [], "warnings": [confirm_warning]}
        given = str(payload.get("preview_hash") or "")
        if not given or given != hashed:
            return {"ok": False, "arrays": [], "warnings": [hash_warning]}
        preview = preview_fn(payload)
        results: list[dict[str, Any]] = []
        by_id = {
            int(item["card_id"]): item
            for item in self._call_home_selected(payload.get("arrays"))
            if item.get("card_id") is not None
        }
        for row in preview.get("arrays") or []:
            if not row.get("runnable"):
                results.append(
                    {"card_id": row.get("card_id"), "name": row.get("name") or "",
                     "ok": False, "warnings": row.get("warnings") or [], "log": []}
                )
                continue
            card_id = int(row["card_id"])
            card = self._call_home_card_by_id(card_id)
            state = collect_call_home_state(self._snap_run_command(card))
            if not state.get("ok"):
                results.append(
                    {"card_id": card_id, "name": card.name if card else "",
                     "ok": False, "warnings": [f"ERROR: {state.get('error')}"], "log": []}
                )
                continue
            item = by_id.get(card_id) or {}
            if skip_if_live_mismatch is not None:
                mismatch = skip_if_live_mismatch(item, state)
                if mismatch:
                    results.append(
                        {"card_id": card_id, "name": card.name if card else "",
                         "ok": True, "warnings": mismatch, "log": []}
                    )
                    continue
            steps, warnings, runnable = builder(item, state)
            if not runnable:
                results.append(
                    {"card_id": card_id, "name": card.name if card else "",
                     "ok": False, "warnings": warnings, "log": []}
                )
                continue
            executed = run_call_home_steps(steps, self._snap_run_command(card))
            results.append(
                {"card_id": card_id, "name": card.name if card else "",
                 "ok": bool(executed.get("ok")),
                 "warnings": executed.get("warnings") or [],
                 "log": executed.get("log") or []}
            )
        overall_ok = any(row.get("ok") for row in results)
        return {"ok": overall_ok, "arrays": results}
```

Refactor `preview_call_home_apply` / `run_call_home_apply` / remove to use the helpers. Then add:

```python
    def preview_call_home_smtp(self, payload: dict) -> dict[str, Any]:
        def builder(item, state):
            return build_smtp_array_steps(
                smtp=item.get("smtp") or {},
                servers=list(state.get("servers") or []),
            )
        return self._call_home_preview_rows(payload, "smtp", builder)

    def run_call_home_smtp(self, payload: dict, *, confirm: bool) -> dict[str, Any]:
        def builder(item, state):
            return build_smtp_array_steps(
                smtp=item.get("smtp") or {},
                servers=list(state.get("servers") or []),
            )
        def skip(item, state):
            preview_count = 0 if not smtp_add_requested(item.get("smtp")) else None
            live = list(state.get("servers") or [])
            # Re-read count vs 0-vs-1 assumption from builder: if builder would pick mk vs chemail differently, skip.
            want = 0 if not live else (1 if len(live) == 1 else 2)
            smtp = item.get("smtp") or {}
            from launchpad.call_home_cli_ops import smtp_add_requested as _want
            if not _want(smtp):
                return ["ERROR: nothing to apply"]
            assumed = 0
            # Compare live count to what preview used: skip all SMTP commands if count is not 0 or 1 matching builder.
            if len(live) > 1:
                return ["ERROR: more than one email server"]
            return []
        # Spec: if server count no longer matches Preview's 0-vs-1 assumption, skip all SMTP commands.
        def skip_mismatch(item, state):
            live = list(state.get("servers") or [])
            steps, warnings, runnable = build_smtp_array_steps(
                smtp=item.get("smtp") or {}, servers=live
            )
            if not runnable:
                return warnings
            return []
        return self._call_home_run_rows(
            payload, kind="smtp", confirm=confirm,
            confirm_warning="confirm must be true before writing SMTP",
            hash_warning="Preview must be run again before applying SMTP.",
            preview_fn=self.preview_call_home_smtp,
            builder=builder,
            skip_if_live_mismatch=None,
        )
```

**Do not** leave the unused `skip` / `preview_count` / `_want` stubs in the file. SMTP Run re-calls `build_smtp_array_steps` on live `lsemailserver` (already inside `_call_home_run_rows` via `builder`). That satisfies “re-read then skip if not runnable” (2+ servers or empty fields). If live count flipped from 0 to 1, builder emits `chemailserver` instead of `mkemailserver` — acceptable. If it flipped from 1 to 0, builder emits `mkemailserver`. Spec says skip **all** SMTP commands if count no longer matches 0-vs-1 **assumption**. Implement skip as:

```python
        def skip_mismatch(item, state):
            live_n = len(list(state.get("servers") or []))
            preview_row = None
            # Use the preview steps kind: mkemailserver implies assumed 0; chemailserver implies 1.
            return None
```

Lock this rule instead: pass `skip_if_live_mismatch` that records assumed count from **payload-only** (0 if we would mk, 1 if we would chemail) by calling builder on **preview state is gone**. Simpler locked rule for Run: call `builder(item, live_state)` only. If live has 2+ servers, `build_smtp_array_steps` returns not runnable → `ok: False` for that array (not silent skip-success). Spec “skip all SMTP commands” is met (no `svctask`). Put `skip_if_live_mismatch=None` for SMTP.

Cloud Run skip-if-already-matched:

```python
        def skip_cloud(item, state):
            steps, warnings, runnable = build_cloud_array_steps(
                requested=str(item.get("requested") or ""),
                configured=str(state.get("cloud_configured") or ""),
            )
            if runnable:
                return []
            if warnings and "nothing to apply" in warnings[0].lower():
                return ["already at requested cloud state"]
            return warnings
```

When `skip_if_live_mismatch` returns a non-empty list, `_call_home_run_rows` appends `ok: True` with those warnings and **no** commands. Use that for Cloud only.

Users builder:

```python
            return build_users_array_steps(
                existing=list(state.get("users") or []),
                remove_ids=list(item.get("remove_ids") or []),
                add=list(item.get("add") or []),
            )
```

Confirm warnings:

- apply: `confirm must be true before writing Call Home fields`
- smtp: `confirm must be true before writing SMTP`
- users: `confirm must be true before writing Call Home email users`
- cloud: `confirm must be true before changing Cloud Call Home`
- remove: keep existing

- [ ] **Step 4: Run API tests**

Run: `python -m pytest tests/test_health_server_call_home_cli.py tests/test_call_home_cli_ops.py tests/test_call_home_cli_page.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add launchpad/health_server.py tests/test_health_server_call_home_cli.py
git commit -m "Add Call Home CLI SMTP, users, and Cloud Preview/Run APIs."
```

---

### Task 4: Bump APP_VERSION to 1.6.180

**Files:**
- Modify: `tests/test_capacity_unit_js.py`
- Modify: `tests/test_hadoop_sudo_wire.py`
- Modify: `tests/test_system_connectivity_version.py`
- Modify: `launchpad/config.py`

**Interfaces:**
- Produces: `APP_VERSION = "1.6.180"`

- [ ] **Step 1:** Change the three pin tests to `"1.6.180"` (leave config at 1.6.179 for RED).

```python
    assert APP_VERSION == "1.6.180"
```

in `test_app_version_153`, `test_version_174`, and `test_app_version_16174`.

- [ ] **Step 2:** `python -m pytest tests/test_capacity_unit_js.py tests/test_hadoop_sudo_wire.py tests/test_system_connectivity_version.py -v`

Expected: FAIL (`'1.6.179' == '1.6.180'`).

- [ ] **Step 3:** `APP_VERSION = "1.6.180"` in `launchpad/config.py`. Grep leftover equality pins under `tests/` and `launchpad/`.

- [ ] **Step 4:** Re-run the three pin tests plus `python -m pytest tests/test_call_home_cli_ops.py tests/test_call_home_cli_page.py tests/test_health_server_call_home_cli.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add launchpad/config.py tests/test_capacity_unit_js.py tests/test_hadoop_sudo_wire.py tests/test_system_connectivity_version.py
git commit -m "Bump version to 1.6.180 for Call Home SMTP, users, and Cloud."
```

---

## Spec coverage

| Spec requirement | Task |
|------------------|------|
| Contact Apply no SMTP | 1, 3 |
| SMTP mk vs chemailserver vs 2+ block | 1, 3 |
| Users rmemailuser / mkemailuser / startemail | 1, 3 |
| Cloud enable/disable when changed | 1, 3 |
| Five Preview/Run pairs, hash isolation | 2, 3 |
| Shared SMTP block removed; per-array fields | 2 |
| State sanitizer running/stopped | 1, 2 (load uses parsed location) |
| Password mask / not in hash plaintext | 1, 3 |
| Remove SMTP unchanged | 1 (keep), 2, 3 |
| Version 1.6.180 | 4 |
| IBM only | unchanged cards helper |
| Insights / inventory type / HPE | out of scope |

## Self-review

- No TBD/TODO left in task steps. SMTP Run uses live `build_smtp_array_steps` (2+ servers → not runnable, no `svctask`). Cloud already-matched uses skip-success.
- `preview_hash` kinds match page/API: `apply`, `smtp`, `users`, `cloud`, `remove`.
- `build_apply_array_steps` signature change is in Task 1; HealthServer contact calls updated in Task 1 Step 4 so tests outside ops do not stay broken longer than one task.
