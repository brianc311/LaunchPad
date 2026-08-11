from pathlib import Path

from launchpad.ui.dashboard_view import HEADER_TOOLS_PER_ROW


def test_header_tools_per_row_is_two_row_layout():
    # 11 tools with 6 per row => row0 has 6, row1 has 5.
    assert HEADER_TOOLS_PER_ROW == 6
    assert 11 > HEADER_TOOLS_PER_ROW
    assert (11 + HEADER_TOOLS_PER_ROW - 1) // HEADER_TOOLS_PER_ROW == 2


def test_dashboard_header_uses_two_row_tools_layout():
    source = (
        Path(__file__).parents[1] / "launchpad" / "ui" / "dashboard_view.py"
    ).read_text(encoding="utf-8")

    assert "HEADER_TOOLS_PER_ROW" in source
    assert "divmod(index, HEADER_TOOLS_PER_ROW)" in source
    assert '"System Connectivity"' in source
    assert "def _reflow_header_tools" not in source


def test_dashboard_header_has_capacity_unit_switch():
    source = (
        Path(__file__).parents[1] / "launchpad" / "ui" / "dashboard_view.py"
    ).read_text(encoding="utf-8")
    assert "capacity_unit_switch" in source
    assert "SETTING_CAPACITY_UNIT_MODE" in source
    assert "GiB/TiB" in source
    assert "GB/TB" in source
    assert "_probe_monitored_ssh_status" in source


def test_capacity_unit_toggle_reformats_cached_card_stats_without_refreshing_cards():
    source = (
        Path(__file__).parents[1] / "launchpad" / "ui" / "dashboard_view.py"
    ).read_text(encoding="utf-8")
    toggle = source.split("    def _toggle_capacity_unit_mode", 1)[1].split(
        "    def apply_theme", 1
    )[0]

    assert "def _reformat_visible_card_stats" in source
    assert "_reformat_visible_card_stats()" in toggle
    assert "refresh_cards" not in toggle


def test_capacity_unit_toggle_reformats_metrics_only_cards():
    source = (
        Path(__file__).parents[1] / "launchpad" / "ui" / "dashboard_view.py"
    ).read_text(encoding="utf-8")
    reformat = source.split("    def _reformat_visible_card_stats", 1)[1].split(
        "    def apply_theme", 1
    )[0]

    assert "card_stats_columns(metrics)" in reformat
    assert "widget.set_stats(left, right)" in reformat
