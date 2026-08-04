"""Derive Dell Report Facility from card/site name heuristics.

Distribution center when the lowercased name contains ``distribution``,
``distribution center``, or a standalone ``dc`` token (``\\bdc\\b``).
WAG1/WAG2 substrings map to data-center facilities. Names starting with
Walgreens DC host prefixes ``v5k`` / ``v7k`` (unless ``remote`` is present)
also map to distribution center. Everything else is ``Other``.
"""

from __future__ import annotations

import re

_DISTRIBUTION_CENTER = "Distribution center"
_DATA_CENTER_WAG1 = "Data center -WAG1"
_DATA_CENTER_WAG2 = "Data center -WAG2"
_OTHER = "Other"

_DC_TOKEN = re.compile(r"\bdc\b")
_DC_PREFIX = re.compile(r"^v[57]k")


def facility_from_name(name: str) -> str:
    """WAG1 → 'Data center -WAG1'; WAG2 → 'Data center -WAG2';
    distribution/DC patterns → 'Distribution center'; else 'Other'."""
    lowered = name.lower()

    if "distribution" in lowered or "distribution center" in lowered:
        return _DISTRIBUTION_CENTER
    if _DC_TOKEN.search(lowered):
        return _DISTRIBUTION_CENTER

    if "wag1" in lowered:
        return _DATA_CENTER_WAG1
    if "wag2" in lowered:
        return _DATA_CENTER_WAG2

    if "remote" not in lowered and _DC_PREFIX.match(lowered):
        return _DISTRIBUTION_CENTER

    return _OTHER
