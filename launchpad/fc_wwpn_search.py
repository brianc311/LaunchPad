"""Pure helpers for FC WWPN search matching."""

from __future__ import annotations

import re
from typing import Any


def normalize_wwpn(value: str) -> str:
    return re.sub(r"[\s:]", "", str(value or "")).upper()


def _wwpn_field_tokens(field: Any) -> list[str]:
    text = str(field or "").strip()
    if not text:
        return []
    return [normalize_wwpn(part) for part in re.split(r"[;,]+", text) if part.strip()]


def _field_matches_text(field: Any, q_text: str) -> bool:
    if not q_text:
        return False
    text = str(field or "").strip()
    if not text:
        return False
    return q_text in text.lower()


def _field_matches_wwpn(field: Any, q_wwpn: str) -> bool:
    if not q_wwpn:
        return False
    return any(q_wwpn in token for token in _wwpn_field_tokens(field))


def card_matches_fc_query(card: dict[str, Any], query: str) -> bool:
    raw = str(query or "").strip()
    if not raw:
        return True
    q_text = raw.lower()
    q_wwpn = normalize_wwpn(raw)

    text_fields: list[Any] = []
    wwpn_fields: list[Any] = []

    for port in card.get("fc_ports") or []:
        if not isinstance(port, dict):
            continue
        wwpn_fields.append(port.get("wwpn"))
        wwpn_fields.append(port.get("remote_wwpns"))
    for node in card.get("fc_ports_by_node") or []:
        if not isinstance(node, dict):
            continue
        for port in node.get("ports") or []:
            if not isinstance(port, dict):
                continue
            wwpn_fields.append(port.get("wwpn"))
            wwpn_fields.append(port.get("remote_wwpns"))
    for host in card.get("fc_hosts") or []:
        if not isinstance(host, dict):
            continue
        text_fields.append(host.get("host_name") or host.get("name"))
        wwpn_fields.append(host.get("wwpns"))
        wwpn_fields.append(host.get("wwpn"))
        wwpn_fields.append(host.get("host_wwpns"))
    for mapping in card.get("fc_mappings") or []:
        if not isinstance(mapping, dict):
            continue
        text_fields.append(mapping.get("vdisk_name") or mapping.get("volume"))
        text_fields.append(mapping.get("host_name") or mapping.get("host"))
        wwpn_fields.append(mapping.get("host_wwpns"))
    for login in card.get("fc_fabric") or []:
        if not isinstance(login, dict):
            continue
        text_fields.append(login.get("host_name"))
        wwpn_fields.append(login.get("local_wwpn"))
        wwpn_fields.append(login.get("remote_wwpn"))

    if any(_field_matches_text(field, q_text) for field in text_fields):
        return True
    if any(_field_matches_wwpn(field, q_wwpn) for field in wwpn_fields):
        return True
    return False


def find_cards_matching_fc_query(cards: list[dict[str, Any]], query: str) -> list[dict[str, Any]]:
    if not str(query).strip():
        return []
    return sorted(
        [card for card in cards if card_matches_fc_query(card, query)],
        key=lambda card: str(card.get("name") or "").lower(),
    )
