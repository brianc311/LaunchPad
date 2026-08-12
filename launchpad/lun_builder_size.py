"""LUN Builder size amount/unit split and join helpers."""

from __future__ import annotations

import re

DEFAULT_LUN_SIZE_UNIT = "GB"
LUN_SIZE_UNITS = ("GB", "TB")

_SIZE_RE = re.compile(
    r"^(-?\d+(?:\.\d+)?)\s*(GB|TB|MB|KB|PB|B)?$",
    re.IGNORECASE,
)
_UI_UNITS = frozenset(LUN_SIZE_UNITS)


def split_lun_size_for_ui(size: str) -> tuple[str, str]:
    text = str(size or "").strip()
    if not text:
        return "", DEFAULT_LUN_SIZE_UNIT

    match = _SIZE_RE.match(text)
    if not match:
        return text, DEFAULT_LUN_SIZE_UNIT

    amount = match.group(1)
    suffix = (match.group(2) or "").upper()
    if suffix in _UI_UNITS:
        return amount, suffix
    return amount, DEFAULT_LUN_SIZE_UNIT


def join_lun_size(amount: str, unit: str) -> str:
    text = str(amount or "").strip()
    if not text:
        return ""

    match = _SIZE_RE.match(text)
    if match:
        suffix = (match.group(2) or "").upper()
        if suffix in _UI_UNITS:
            return f"{match.group(1)}{suffix}"

    normalized_unit = str(unit or "").strip().upper()
    if normalized_unit not in _UI_UNITS:
        normalized_unit = DEFAULT_LUN_SIZE_UNIT
    return f"{text}{normalized_unit}"
