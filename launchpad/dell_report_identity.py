"""Resolve Dell Report Facility / Storage Array / Model Number."""

from __future__ import annotations

from launchpad.dell_report_facility import facility_from_name
from launchpad.storage_presets import DEVICE_PROFILES


def resolve_dell_identity(
    *,
    card_id: int | str,
    site_name: str,
    device_profile: str,
    summary_name: str = "",
    overrides: dict[str, dict[str, str]] | None = None,
) -> dict[str, str]:
    ov = (overrides or {}).get(str(card_id), {})
    facility = ov.get("facility") or facility_from_name(site_name)
    array_name = (
        ov.get("array_name")
        or (summary_name.strip() if summary_name else "")
        or site_name
    )
    profile_label = DEVICE_PROFILES.get(device_profile) or device_profile or ""
    model = ov.get("model") or profile_label
    return {"facility": facility, "array_name": array_name, "model": model}
