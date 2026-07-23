"""Pure helpers for LUN Builder Find matching."""

from __future__ import annotations

from typing import Any

from launchpad.lun_builder_data import expand_lun_batch


def normalize_query(value: str) -> str:
    return str(value or "").strip().lower()


def _text_matches(field: Any, q: str) -> bool:
    if not q:
        return False
    text = str(field or "").strip().lower()
    return bool(text) and q in text


def host_row_matches(host: dict[str, Any], query: str) -> bool:
    q = normalize_query(query)
    if not q:
        return True
    return _text_matches(host.get("lpar_name"), q)


def lun_row_matches(lun: dict[str, Any], query: str) -> bool:
    q = normalize_query(query)
    if not q:
        return True
    if _text_matches(lun.get("purpose"), q):
        return True
    for name in lun.get("host_names") or []:
        if _text_matches(name, q):
            return True
    for row in expand_lun_batch(lun):
        if _text_matches(row.get("name"), q):
            return True
    return False


def build_matches_query(build: dict[str, Any], query: str) -> bool:
    q = normalize_query(query)
    if not q:
        return True
    if any(host_row_matches(host, query) for host in (build.get("hosts") or []) if isinstance(host, dict)):
        return True
    if any(lun_row_matches(lun, query) for lun in (build.get("luns") or []) if isinstance(lun, dict)):
        return True
    return False


def find_builds_matching_query(builds: list[dict[str, Any]], query: str) -> list[dict[str, Any]]:
    if not str(query or "").strip():
        return []
    return sorted(
        [b for b in builds if isinstance(b, dict) and build_matches_query(b, query)],
        key=lambda b: str(b.get("name") or "").lower(),
    )
