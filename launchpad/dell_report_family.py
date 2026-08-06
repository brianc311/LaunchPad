"""Map device profile (and optional manufacturer / site name) to Dell Report family."""

from __future__ import annotations

_IBM_MARKERS = ("flashsystem", "storwize", "svc", "xiv", "ds8", "ibm_", "ibm ", "ds8884")
_HP_MARKERS = ("hpe", "3par", "primera")
_HP_PREFIX = "hp_"


def dell_report_family(device_profile: str, *, manufacturer: str = "") -> str | None:
    """Return 'ibm' | 'hp' | None. HP includes HPE/3PAR/Primera; IBM includes
    flashsystem/storwize/svc/xiv/ds8k-style profiles."""
    profile = (device_profile or "").lower()
    vendor = (manufacturer or "").lower()

    if any(marker in profile for marker in _IBM_MARKERS) or vendor == "ibm":
        return "ibm"

    if (
        profile.startswith(_HP_PREFIX)
        or any(marker in profile for marker in _HP_MARKERS)
        or vendor in ("hpe", "hp")
    ):
        return "hp"

    return None


def dell_report_family_for_site(
    device_profile: str,
    *,
    site_name: str = "",
    manufacturer: str = "",
) -> str | None:
    """Family from profile, then manufacturer, then site-name tokens (IBM/XIV/HPE…)."""
    family = dell_report_family(device_profile, manufacturer=manufacturer)
    if family is not None:
        return family
    return dell_report_family(site_name or "", manufacturer=manufacturer)
