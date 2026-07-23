"""Pure helpers for Consistency Groups (contingency) Find matching."""

from __future__ import annotations

import re
from typing import Any


def normalize_query(value: str) -> str:
    return str(value or "").strip().lower()


def _text_matches(field: Any, q: str) -> bool:
    if not q:
        return False
    text = str(field or "").strip().lower()
    return bool(text) and q in text


def _wwpn_matches(field: Any, q: str) -> bool:
    if not q:
        return False
    q_norm = re.sub(r"[\s:]", "", q).upper()
    if isinstance(field, list):
        parts = field
    else:
        parts = re.split(r"[;,\s]+", str(field or ""))
    for part in parts:
        token = re.sub(r"[\s:]", "", str(part or "")).upper()
        if token and q_norm in token:
            return True
    return False


def group_identity_matches(group: dict[str, Any], query: str) -> bool:
    q = normalize_query(query)
    if not q:
        return True
    return _text_matches(group.get("name"), q) or _text_matches(group.get("location"), q)


def host_row_matches(host: dict[str, Any], query: str) -> bool:
    q = normalize_query(query)
    if not q:
        return True
    return _text_matches(host.get("name"), q) or _wwpn_matches(host.get("wwpns"), q)


def volume_row_matches(volume: dict[str, Any], query: str) -> bool:
    q = normalize_query(query)
    if not q:
        return True
    return _text_matches(volume.get("name"), q)


def map_row_matches(mapping: dict[str, Any], query: str) -> bool:
    q = normalize_query(query)
    if not q:
        return True
    return _text_matches(mapping.get("volume"), q) or _text_matches(mapping.get("host"), q)


def group_content_matches(group: dict[str, Any], query: str) -> bool:
    q = normalize_query(query)
    if not q:
        return True
    if any(host_row_matches(h, query) for h in (group.get("hosts") or []) if isinstance(h, dict)):
        return True
    if any(volume_row_matches(v, query) for v in (group.get("volumes") or []) if isinstance(v, dict)):
        return True
    if any(map_row_matches(m, query) for m in (group.get("maps") or []) if isinstance(m, dict)):
        return True
    return False


def find_groups_matching_identity(groups: list[dict[str, Any]], query: str) -> list[dict[str, Any]]:
    if not str(query or "").strip():
        return []
    return sorted(
        [g for g in groups if isinstance(g, dict) and group_identity_matches(g, query)],
        key=lambda g: str(g.get("name") or "").lower(),
    )


def find_groups_matching_content(groups: list[dict[str, Any]], query: str) -> list[dict[str, Any]]:
    if not str(query or "").strip():
        return []
    return sorted(
        [g for g in groups if isinstance(g, dict) and group_content_matches(g, query)],
        key=lambda g: str(g.get("name") or "").lower(),
    )
