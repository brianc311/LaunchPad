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
EMAIL_USER_TYPES: tuple[str, ...] = ("support", "local")
_STATUS_STATE = frozenset({"running", "stopped"})
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


def is_email_already_started(text: str) -> bool:
    return "already started" in str(text or "").lower()


def sanitize_location_state(location: dict | None) -> dict[str, str]:
    loc = trim_fields(location, LOCATION_KEYS)
    if loc["state"].lower() in _STATUS_STATE:
        loc["state"] = ""
    return loc


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
    return contact, sanitize_location_state(location)


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


def build_testemail_array_steps(
    *,
    user_id: str = "",
    address: str = "",
) -> tuple[list[SnapStep], list[str], bool]:
    token = str(user_id or "").strip() or str(address or "").strip()
    if not token:
        return [], ["ERROR: select a test user"], False
    try:
        quoted = quote_cli_arg(token)
    except ValueError as exc:
        return [], [f"ERROR: {exc}"], False
    return (
        [
            SnapStep(
                kind="testemail",
                purpose=f"test email to {token}",
                cmd=f"svctask testemail {quoted}",
            )
        ],
        [],
        True,
    )


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

    def card_ids(extra=None) -> list[dict]:
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
    elif kind == "testemail":
        def test_row(item: dict) -> dict:
            return {
                "user_id": str(item.get("user_id") or item.get("id") or "").strip(),
                "address": str(item.get("address") or "").strip(),
            }
        blob = {"kind": "testemail", "arrays": card_ids(test_row)}
    else:
        blob = {"kind": "remove", "arrays": card_ids()}
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
            if step.kind == "startemail" and is_email_already_started(text):
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
        if step.kind == "startemail" and is_email_already_started(text):
            entry["ok"] = True
            entry["output"] = text
            log.append(entry)
            continue
        entry["ok"] = True
        entry["output"] = text
        log.append(entry)
    return {"ok": True, "log": log, "warnings": []}
