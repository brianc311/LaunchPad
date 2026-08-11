from launchpad.dell_report_capacity import (
    select_dell_array_snapshot_summary,
    select_dell_capacity_summary,
)

SYSTEM = {"name": "sys1", "total_bytes": 100, "used_bytes": 40, "used_pct": 40.0}
RAW = {"name": "sys1", "total_bytes": 200, "used_bytes": 50, "used_pct": 25.0, "raw": True}


def test_include_pools_false_prefers_raw():
    chosen = select_dell_capacity_summary(
        capacity_summary=None,
        raw_capacity_summary=RAW,
        pools=[],
        include_pools=False,
    )
    assert chosen is RAW
    assert chosen["total_bytes"] == 200


def test_include_pools_false_falls_back_to_system():
    chosen = select_dell_capacity_summary(
        capacity_summary=SYSTEM,
        raw_capacity_summary=None,
        pools=[],
        include_pools=False,
    )
    assert chosen is SYSTEM


def test_include_pools_true_prefers_system_over_raw():
    chosen = select_dell_capacity_summary(
        capacity_summary=SYSTEM,
        raw_capacity_summary=RAW,
        pools=[],
        include_pools=True,
    )
    assert chosen is SYSTEM


def test_include_pools_false_skips_all_cpgs_system_for_raw():
    all_cpgs = {
        "name": "All CPGs",
        "total_bytes": 100,
        "used_bytes": 99,
        "used_pct": 99.0,
    }
    chosen = select_dell_capacity_summary(
        capacity_summary=all_cpgs,
        raw_capacity_summary=RAW,
        pools=[],
        include_pools=False,
    )
    assert chosen is RAW


def test_include_pools_false_rejects_all_cpgs_without_raw():
    all_cpgs = {
        "name": "All CPGs",
        "total_bytes": 100,
        "used_bytes": 99,
        "used_pct": 99.0,
    }
    chosen = select_dell_capacity_summary(
        capacity_summary=all_cpgs,
        raw_capacity_summary=None,
        pools=[],
        include_pools=False,
    )
    assert chosen is None


def test_array_snapshot_uses_non_rollup_system_not_raw():
    chosen = select_dell_array_snapshot_summary(capacity_summary=SYSTEM)
    assert chosen is SYSTEM


def test_array_snapshot_rejects_all_cpgs():
    all_cpgs = {
        "name": "All CPGs",
        "total_bytes": 100,
        "used_bytes": 99,
        "used_pct": 99.0,
    }
    assert select_dell_array_snapshot_summary(capacity_summary=all_cpgs) is None


def test_array_snapshot_none_when_missing():
    assert select_dell_array_snapshot_summary(capacity_summary=None) is None
