"""Persisted vCenters directory (settings-backed JSON list)."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from launchpad.crypto import encrypt_text

SETTING_VCENTERS_DIRECTORY = "vcenters_directory"

VCENTER_PASSWORD_PLACEHOLDER = "***"
VPXCLIENT_PATH = Path(
    r"C:\Program Files (x86)\VMware\Infrastructure\Virtual Infrastructure Client\Launcher\VpxClient.exe"
)


def use_vsphere_client_enabled(value: object) -> bool:
    if value is True:
        return True
    text = str(value or "").strip().lower()
    return text in {"true", "1", "on", "yes"}


def public_vcenter(record: dict) -> dict:
    encrypted = str(record.get("password_encrypted") or "").strip()
    return {
        "id": str(record.get("id") or ""),
        "name": str(record.get("name") or ""),
        "location": str(record.get("location") or ""),
        "address": str(record.get("address") or ""),
        "url": str(record.get("url") or ""),
        "use_vsphere_client": use_vsphere_client_enabled(
            record.get("use_vsphere_client")
        ),
        "username": str(record.get("username") or ""),
        "password": VCENTER_PASSWORD_PLACEHOLDER if encrypted else "",
        "description": str(record.get("description") or ""),
        "vm_notes": str(record.get("vm_notes") or ""),
    }


def public_vcenters(store: list[dict]) -> list[dict]:
    return [public_vcenter(row) for row in store]


def vcenter_matches_query(row: dict, query: str) -> bool:
    needle = str(query or "").strip().casefold()
    if not needle:
        return True
    haystacks = (
        str(row.get("name") or ""),
        str(row.get("address") or ""),
        str(row.get("vm_notes") or ""),
    )
    return any(needle in part.casefold() for part in haystacks)


def resolve_password_encrypted(
    incoming: dict, existing_encrypted: str, crypto_key: bytes
) -> str:
    if "password" not in incoming:
        return str(existing_encrypted or "")
    text = incoming.get("password")
    if text is None:
        return str(existing_encrypted or "")
    raw = str(text)
    if raw == VCENTER_PASSWORD_PLACEHOLDER:
        return str(existing_encrypted or "")
    if not raw.strip():
        return ""
    return encrypt_text(crypto_key, raw)


def vpxclient_argv(address: str, username: str = "", password: str = "") -> list[str]:
    cmd = [str(VPXCLIENT_PATH), "-s", str(address)]
    user = str(username or "").strip()
    secret = str(password or "")
    if user:
        cmd.extend(["-u", user])
    if secret:
        cmd.extend(["-p", secret])
    return cmd


def vcenter_default_url(address: str) -> str:
    return f"https://{str(address).strip()}/ui"


def effective_vcenter_url(record: dict) -> str:
    override = str(record.get("url") or "").strip()
    if override:
        return override
    return vcenter_default_url(str(record.get("address") or ""))


def normalize_vcenter(raw: dict, *, assign_id: bool = False) -> dict:
    if not isinstance(raw, dict):
        raise ValueError("vCenter must be an object")
    name = str(raw.get("name") or "").strip()
    location = str(raw.get("location") or "").strip()
    address = str(raw.get("address") or "").strip()
    url = str(raw.get("url") or "").strip()
    description = str(raw.get("description") or "").strip()
    vm_notes = str(raw.get("vm_notes") or "").strip()
    if not name:
        raise ValueError("name is required")
    if not address:
        raise ValueError("address is required")
    if "://" in address:
        raise ValueError("address must be an IP or hostname")
    if url and not (
        url.lower().startswith("http://") or url.lower().startswith("https://")
    ):
        raise ValueError("url must start with http:// or https://")
    record_id = str(raw.get("id") or "").strip()
    if not record_id:
        if not assign_id:
            raise ValueError("id is required")
        record_id = uuid.uuid4().hex
    return {
        "id": record_id,
        "name": name,
        "location": location,
        "address": address,
        "url": url,
        "description": description,
        "vm_notes": vm_notes,
        "use_vsphere_client": use_vsphere_client_enabled(
            raw.get("use_vsphere_client")
        ),
        "username": str(raw.get("username") or "").strip(),
        "password_encrypted": str(raw.get("password_encrypted") or "").strip(),
    }


def normalize_vcenters(raw: Any) -> list[dict]:
    if not isinstance(raw, list):
        return []
    out: list[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            out.append(normalize_vcenter(item, assign_id=True))
        except ValueError:
            continue
    out.sort(key=lambda row: row["name"].casefold())
    return out


def parse_vcenters_setting(raw: str | None) -> list[dict]:
    text = str(raw or "").strip() or "[]"
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return []
    return normalize_vcenters(parsed)


def upsert_vcenter(store: list[dict], raw: dict) -> list[dict]:
    cleaned = normalize_vcenter(raw, assign_id=True)
    by_id = {row["id"]: row for row in normalize_vcenters(store)}
    by_id[cleaned["id"]] = cleaned
    return normalize_vcenters(list(by_id.values()))


def delete_vcenter(store: list[dict], vcenter_id: str) -> list[dict]:
    target = str(vcenter_id or "").strip()
    kept = [row for row in normalize_vcenters(store) if row["id"] != target]
    return kept
