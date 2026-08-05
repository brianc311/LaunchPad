from launchpad.dell_report_capacity import select_dell_capacity_summary

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


def test_include_pools_true_raw_last_resort():
    chosen = select_dell_capacity_summary(
        capacity_summary=None,
        raw_capacity_summary=RAW,
        pools=[],
        include_pools=True,
    )
    assert chosen is RAW
