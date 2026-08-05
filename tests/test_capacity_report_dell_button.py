from pathlib import Path


def test_capacity_report_html_has_dell_report_button():
    from launchpad.capacity_report import CAPACITY_REPORT_HTML

    assert "Dell Report" in CAPACITY_REPORT_HTML
    assert 'id="dell-report-btn"' in CAPACITY_REPORT_HTML
    assert "/api/dell-report-export" in CAPACITY_REPORT_HTML
    assert "/api/dell-report-settings" in CAPACITY_REPORT_HTML
    assert "dell-include-switch" in CAPACITY_REPORT_HTML
    assert "loadDellIncludeState" in CAPACITY_REPORT_HTML
    assert 'id="dell-include-noss-btn"' in CAPACITY_REPORT_HTML
    assert "Include no-SSH on Dell Report" in CAPACITY_REPORT_HTML
    assert "includeNoSshOnDellReport" in CAPACITY_REPORT_HTML
    # Do not clobber "Building…" status while Export Excel / Dell Report is in flight.
    assert "exportBusy" in CAPACITY_REPORT_HTML
    assert "excelBtn.disabled" in CAPACITY_REPORT_HTML


def test_admin_view_has_show_dell_report_checkbox():
    source = (
        Path(__file__).parents[1] / "launchpad" / "ui" / "admin_view.py"
    ).read_text(encoding="utf-8")
    assert "Show Dell Report button" in source
    assert "save_dell_report_settings" in source
    assert "load_dell_report_settings" in source
    assert "_save_dell_report_form" in source
    assert "dell_report_overrides_text" in source
    assert "Card overrides" in source


def test_card_widget_has_dell_report_include_hook():
    source = (
        Path(__file__).parents[1] / "launchpad" / "ui" / "card_widget.py"
    ).read_text(encoding="utf-8")
    assert "Dell Report" in source
    assert "dell_report_include" in source
    assert "show_dell_report_include" in source


def test_dashboard_wires_dell_report_include():
    source = (
        Path(__file__).parents[1] / "launchpad" / "ui" / "dashboard_view.py"
    ).read_text(encoding="utf-8")
    assert "include_card_ids" in source
    assert "_set_dell_report_include" in source


def test_dashboard_export_menu_has_dell_report_label():
    source = (
        Path(__file__).parents[1] / "launchpad" / "ui" / "dashboard_view.py"
    ).read_text(encoding="utf-8")
    assert "Dell Report…" in source
    assert "_export_dell_report_excel" in source
    assert "is_dell_report_enabled" in source
