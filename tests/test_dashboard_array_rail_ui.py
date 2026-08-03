from pathlib import Path

SOURCE = Path("launchpad/ui/dashboard_view.py").read_text(encoding="utf-8")


def test_dashboard_array_rail_markers():
    assert "SETTING_ARRAY_RAIL_COLLAPSED" in SOURCE
    assert "open_rail_gui" in SOURCE
    assert "_rebuild_array_rail" in SOURCE
    assert "_toggle_array_rail" in SOURCE
    assert "No arrays match." in SOURCE
    assert "Arrays" in SOURCE
