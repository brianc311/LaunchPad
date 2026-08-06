from launchpad.capacity_excel_alerts import (
    banner_message_for_max_pct,
    capacity_excel_banner_summary,
)
from launchpad.capacity_export import HEADERS, POOL_HEADERS, _styled_workbook


def test_banner_message_thresholds():
    assert banner_message_for_max_pct(79.9) is None
    assert banner_message_for_max_pct(80.0) == (
        "WARNING: Please check storage — capacity over 80%."
    )
    assert banner_message_for_max_pct(89.9) == (
        "WARNING: Please check storage — capacity over 80%."
    )
    assert banner_message_for_max_pct(90.0) == (
        "CRITICAL: Please check storage — capacity over 90%."
    )
    assert banner_message_for_max_pct(99.4) == (
        "CRITICAL: Please check storage — capacity over 90%."
    )
    assert banner_message_for_max_pct(99.5) == (
        "CRITICAL: Please check storage — drives are full."
    )
    assert banner_message_for_max_pct(100.0) == (
        "CRITICAL: Please check storage — drives are full."
    )


def test_summary_none_under_80():
    assert capacity_excel_banner_summary(pool_used_pcts=[10.0, 50.0]) is None


def test_summary_warn_and_counts():
    summary = capacity_excel_banner_summary(
        pool_used_pcts=[82.0, 50.0, 81.0],
        site_keys_over={"A", "B"},
    )
    assert summary is not None
    assert summary["severity"] == "warn"
    assert summary["pool_count"] == 2
    assert summary["site_count"] == 2
    assert summary["message"].startswith("WARNING:")
    assert "2 site(s) / 2 pool(s) over threshold" in summary["message"]


def test_summary_critical_from_max_pool():
    summary = capacity_excel_banner_summary(
        pool_used_pcts=[91.0],
        site_keys_over={"A"},
    )
    assert summary is not None
    assert summary["severity"] == "critical"
    assert "capacity over 90%" in summary["message"]


def test_styled_workbook_no_banner_under_80():
    inv = [("Loc", "Dev", "1.1.1.1", "Name", "SN", "IBM")]
    fills = [("ok", "pools")]
    pools = [("Loc", "Dev", "1.1.1.1", "CPG_A", 50.0, "1 GB", "2 GB", "1 GB")]
    wb = _styled_workbook(inv, fills, [], pools)
    ws = wb["Storage Capacity"]
    assert ws.cell(1, 1).value == HEADERS[0]
    assert ws.cell(2, 1).value == "Loc"
    ws_pools = wb["Pool Capacity"]
    assert ws_pools.cell(1, 1).value == POOL_HEADERS[0]


def test_styled_workbook_banner_on_both_sheets_when_critical():
    inv = [("Loc", "Dev", "1.1.1.1", "Name", "SN", "IBM")]
    fills = [("91%", "pools")]
    pools = [
        ("Loc", "Dev", "1.1.1.1", "CPG_A", 91.0, "9 GB", "10 GB", "1 GB"),
        ("Loc", "Dev", "1.1.1.1", "CPG_B", 50.0, "1 GB", "2 GB", "1 GB"),
    ]
    wb = _styled_workbook(inv, fills, [], pools)
    for title, col_count in (("Storage Capacity", len(HEADERS)), ("Pool Capacity", len(POOL_HEADERS))):
        ws = wb[title]
        assert "CRITICAL:" in str(ws.cell(1, 1).value)
        assert "1 site(s) / 1 pool(s) over threshold" in str(ws.cell(1, 1).value)
        assert list(ws.merged_cells.ranges)
        expected_header = HEADERS[0] if title == "Storage Capacity" else POOL_HEADERS[0]
        assert ws.cell(2, 1).value == expected_header
