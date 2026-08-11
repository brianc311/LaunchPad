from __future__ import annotations

from typing import Any

SETTING_CAPACITY_UNIT_MODE = "capacity_unit_mode"

_MODE = "iec"
_IEC_GIGA = 1024**3
_SI_GIGA = 1000**3


def normalize_capacity_unit_mode(raw: str | None) -> str:
    return "si" if str(raw or "").strip().lower() == "si" else "iec"


def get_capacity_unit_mode() -> str:
    return _MODE


def set_capacity_unit_mode(mode: str | None) -> str:
    global _MODE
    _MODE = normalize_capacity_unit_mode(mode)
    return _MODE


def load_capacity_unit_mode(db: Any) -> str:
    raw = db.get_setting(SETTING_CAPACITY_UNIT_MODE, "iec")
    return set_capacity_unit_mode(raw)


def capacity_unit_header() -> str:
    return "GB" if _MODE == "si" else "GiB"


def bytes_to_capacity_unit(num_bytes: float) -> float:
    base = _SI_GIGA if _MODE == "si" else _IEC_GIGA
    return float(num_bytes) / base


def iec_gib_to_display(gib: float) -> float:
    if _MODE == "si":
        return float(gib) * _IEC_GIGA / _SI_GIGA
    return float(gib)


def format_bytes(num_bytes: float) -> str:
    if num_bytes <= 0:
        return f"0 {capacity_unit_header()}"
    if _MODE == "si":
        units = ["GB", "TB", "PB"]
        step = 1000.0
        value = num_bytes / _SI_GIGA
    else:
        units = ["GiB", "TiB", "PiB"]
        step = 1024.0
        value = num_bytes / _IEC_GIGA
    unit = units[0]
    if value >= step:
        value /= step
        unit = units[1]
    if value >= step:
        value /= step
        unit = units[2]
    return f"{value:.1f} {unit}"
