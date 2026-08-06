"""Derive Dell Report Facility from card/site/array name heuristics.

Distribution center when the lowercased name contains ``distribution``,
``distribution center``, a standalone ``dc`` token (``\\bdc\\b``), or a
``v5k`` / ``v7k`` host token (unless ``remote`` wins later).

WAG1/WAG2 and VAG1/VAG2 substrings map to data-center facilities.
Names containing ``remote`` map to ``Remote``. Everything else is ``Other``.
"""

from __future__ import annotations

import re

_DISTRIBUTION_CENTER = "Distribution center"
_DATA_CENTER_WAG1 = "Data center -WAG1"
_DATA_CENTER_WAG2 = "Data center -WAG2"
_REMOTE = "Remote"
_OTHER = "Other"

_DC_TOKEN = re.compile(r"\bdc\b")
_V57K_TOKEN = re.compile(r"\bv[57]k")


def facility_from_name(name: str) -> str:
    """WAG1/VAG1 → 'Data center -WAG1'; WAG2/VAG2 → 'Data center -WAG2';
    distribution/DC/v5k/v7k → 'Distribution center'; remote → 'Remote';
    else 'Other'."""
    lowered = (name or "").lower()

    if "distribution" in lowered or "distribution center" in lowered:
        return _DISTRIBUTION_CENTER
    if _DC_TOKEN.search(lowered):
        return _DISTRIBUTION_CENTER

    if "wag1" in lowered or "vag1" in lowered:
        return _DATA_CENTER_WAG1
    if "wag2" in lowered or "vag2" in lowered:
        return _DATA_CENTER_WAG2

    if "remote" in lowered:
        return _REMOTE

    if _V57K_TOKEN.search(lowered):
        return _DISTRIBUTION_CENTER

    return _OTHER
