"""Pure helpers for FC WWPN report search matching."""

from __future__ import annotations

import re
from typing import Any


def normalize_wwpn(value: str) -> str:
    return re.sub(r"[\s:]", "", str(value or "")).upper()


def _text_haystack(parts: list[Any]) -> str:
    return " ".join(str(p or "") for p in parts).lower()


def _wwpn_haystack(parts: list[Any]) -> str:
    return "".join(normalize_wwpn(str(p or "")) for p in parts)


def card_matches_search(card: dict[str, Any], query: str) -> bool:
    raw = str(query or "").strip()
    if not raw:
        return True
    q_text = raw.lower()
    q_wwpn = normalize_wwpn(raw)

    text_parts: list[Any] = []
    wwpn_parts: list[Any] = []

    for port in card.get("fc_ports") or []:
        if not isinstance(port, dict):
            continue
        wwpn_parts.append(port.get("wwpn"))
        wwpn_parts.append(port.get("remote_wwpns"))
    for node in card.get("fc_ports_by_node") or []:
        if not isinstance(node, dict):
            continue
        for port in node.get("ports") or []:
            if not isinstance(port, dict):
                continue
            wwpn_parts.append(port.get("wwpn"))
            wwpn_parts.append(port.get("remote_wwpns"))
    for host in card.get("fc_hosts") or []:
        if not isinstance(host, dict):
            continue
        text_parts.append(host.get("host_name") or host.get("name"))
        wwpn_parts.append(host.get("wwpns"))
        wwpn_parts.append(host.get("wwpn"))
        wwpn_parts.append(host.get("host_wwpns"))
    for mapping in card.get("fc_mappings") or []:
        if not isinstance(mapping, dict):
            continue
        text_parts.append(mapping.get("vdisk_name") or mapping.get("volume"))
        text_parts.append(mapping.get("host_name") or mapping.get("host"))
        wwpn_parts.append(mapping.get("host_wwpns"))
    for login in card.get("fc_fabric") or []:
        if not isinstance(login, dict):
            continue
        text_parts.append(login.get("host_name"))
        wwpn_parts.append(login.get("local_wwpn"))
        wwpn_parts.append(login.get("remote_wwpn"))

    if q_text and q_text in _text_haystack(text_parts):
        return True
    if q_wwpn and q_wwpn in _wwpn_haystack(wwpn_parts):
        return True
    return False
