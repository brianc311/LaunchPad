"""Map device profile (and optional manufacturer) to Dell Report vendor family."""

from __future__ import annotations

_IBM_MARKERS = ("flashsystem", "storwize", "svc", "xiv", "ds8", "ibm_")
_HP_MARKERS = ("hpe", "3par", "primera")
_HP_PREFIX = "hp_"


def dell_report_family(device_profile: str, *, manufacturer: str = "") -> str | None:
    """Return 'ibm' | 'hp' | None. HP includes HPE/3PAR/Primera; IBM includes
    flashsystem/storwize/svc/xiv/ds8k-style profiles."""
    profile = device_profile.lower()
    vendor = manufacturer.lower()

    if any(marker in profile for marker in _IBM_MARKERS) or vendor == "ibm":
        return "ibm"

    if (
        profile.startswith(_HP_PREFIX)
        or any(marker in profile for marker in _HP_MARKERS)
        or vendor in ("hpe", "hp")
    ):
        return "hp"

    return None
