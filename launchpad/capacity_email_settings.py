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
