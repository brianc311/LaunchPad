"""Tests for normal vs raw/physical capacity parsing (capacity layers Task 1)."""

from launchpad.flashsystem_parse import parse_capacity_summary, parse_raw_capacity_summary

HPE_SHOWSYS_WITH_RAW = """------------General-------------
System Name : ARRAY1
System Model : InServ E200
-----System Capacity (MB)-----
Total Capacity : 1000000
Allocated Capacity : 270000
Free Capacity : 730000
Failed Capacity : 0
Raw Capacity : 1200000
Raw Free Capacity : 930000
"""

IBM_LSSYSTEM_WITH_PHYSICAL = """name : FS9500
id : 00000200ABCDEF
physical_capacity : 120.00TB
physical_free_capacity : 90.00TB
total_mdisk_capacity : 100.00TB
total_free_space : 75.00TB
allocated_capacity : 25.00TB
"""

IBM_LSSYSTEM_NO_ALLOCATED = """name : FS9500
physical_capacity : 120.00TB
physical_free_capacity : 90.00TB
total_mdisk_capacity : 100.00TB
total_free_space : 75.00TB
"""


def test_parse_capacity_summary_prefers_allocated_not_physical():
    capacity = parse_capacity_summary(HPE_SHOWSYS_WITH_RAW)
    assert capacity is not None
    assert capacity["total_bytes"] == 1000000 * 1024**2
    assert capacity["used_bytes"] == 270000 * 1024**2
    assert capacity["free_bytes"] == 730000 * 1024**2
    assert capacity["used_pct"] == 27.0

    ibm = parse_capacity_summary(IBM_LSSYSTEM_WITH_PHYSICAL)
    assert ibm is not None
    assert ibm["total_bytes"] == 100 * 1024**4
    assert ibm["used_bytes"] == 25 * 1024**4
    assert ibm["used_pct"] == 25.0


def test_parse_raw_capacity_summary_from_physical_fields():
    raw = parse_raw_capacity_summary(HPE_SHOWSYS_WITH_RAW)
    assert raw is not None
    assert raw["name"] == "ARRAY1"
    assert raw["total_bytes"] == 1200000 * 1024**2
    assert raw["free_bytes"] == 930000 * 1024**2
    assert raw["used_bytes"] == 270000 * 1024**2
    assert raw["used_pct"] == 22.5

    ibm_raw = parse_raw_capacity_summary(IBM_LSSYSTEM_WITH_PHYSICAL)
    assert ibm_raw is not None
    assert ibm_raw["total_bytes"] == 120 * 1024**4
    assert ibm_raw["free_bytes"] == 90 * 1024**4
    assert ibm_raw["used_bytes"] == 30 * 1024**4
    assert ibm_raw["used_pct"] == 25.0


def test_parse_capacity_summary_ibm_usable_free_without_allocated():
    """Regression: free_capacity must not match physical_free_capacity."""
    ibm = parse_capacity_summary(IBM_LSSYSTEM_NO_ALLOCATED)
    assert ibm is not None
    assert ibm["total_bytes"] == 100 * 1024**4
    assert ibm["free_bytes"] == 75 * 1024**4
    assert ibm["used_bytes"] == 25 * 1024**4
    assert ibm["used_pct"] == 25.0

    ibm_raw = parse_raw_capacity_summary(IBM_LSSYSTEM_NO_ALLOCATED)
    assert ibm_raw is not None
    assert ibm_raw["total_bytes"] == 120 * 1024**4
    assert ibm_raw["free_bytes"] == 90 * 1024**4
    assert ibm_raw["used_bytes"] == 30 * 1024**4
    assert ibm_raw["used_pct"] == 25.0


def test_parse_raw_capacity_summary_none_when_absent():
    showsys_no_raw = """System Name : S424
Total Capacity : 6277120
Allocated Capacity : 687872
Free Capacity : 5589248
"""
    assert parse_raw_capacity_summary(showsys_no_raw) is None
    assert parse_raw_capacity_summary("") is None
