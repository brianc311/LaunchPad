from launchpad.capacity_excel_alerts import (
    banner_message_for_max_pct,
    capacity_excel_banner_summary,
)


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
