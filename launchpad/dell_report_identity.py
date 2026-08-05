"""Resolve Dell Report Facility / Storage Array / Model Number."""

from __future__ import annotations

from launchpad.dell_report_facility import facility_from_name
from launchpad.storage_presets import DEVICE_PROFILES

_POOL_ROLLUP_NAMES = frozenset({"all cpgs", "all pools", "all cpg"})


def _is_pool_rollup_name(name: str) -> bool:
    return (name or "").strip().lower() in _POOL_ROLLUP_NAMES


def resolve_dell_identity(
    *,
    card_id: int | str,
    site_name: str,
    device_profile: str,
    summary_name: str = "",
    overrides: dict[str, dict[str, str]] | None = None,
) -> dict[str, str]:
    ov = (overrides or {}).get(str(card_id), {})
    clean_summary = ""
    if summary_name and not _is_pool_rollup_name(summary_name):
        clean_summary = summary_name.strip()

    array_name = ov.get("array_name") or clean_summary or site_name

    facility = ov.get("facility")
    if not facility:
        facility = facility_from_name(site_name)
        if facility == "Other":
            facility = facility_from_name(array_name)
        if facility == "Other" and clean_summary:
            facility = facility_from_name(clean_summary)

    profile_label = DEVICE_PROFILES.get(device_profile) or device_profile or ""
    model = ov.get("model") or profile_label
    return {"facility": facility, "array_name": array_name, "model": model}
