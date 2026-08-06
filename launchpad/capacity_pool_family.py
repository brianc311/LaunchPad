"""Map a storage card to Capacity Report pool-display family."""

from __future__ import annotations

from launchpad.dell_report_family import dell_report_family_for_site


def capacity_pool_family(device_profile: str, *, site_name: str = "") -> str:
    """Return 'ibm' | 'hpe' | 'dell' | '' for Capacity Report pool visibility."""
    profile = (device_profile or "").strip()
    if profile.lower().startswith("dell_"):
        return "dell"
    family = dell_report_family_for_site(profile, site_name=site_name or "")
    if family == "ibm":
        return "ibm"
    if family == "hp":
        return "hpe"
    return ""
