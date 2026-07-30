from launchpad.health_server import HealthServer
from launchpad.snapcopy_summary_page import (
    SNAPCOPY_SUMMARY_HTML,
    SNAPCOPY_SUMMARY_PATH,
)


def test_snapcopy_summary_markers():
    assert SNAPCOPY_SUMMARY_PATH == "/snapcopy-summary"
    assert 'id="snapcopy-refresh"' in SNAPCOPY_SUMMARY_HTML
    assert 'id="snapcopy-export"' in SNAPCOPY_SUMMARY_HTML
    assert "/api/contingency-groups/fc-cg-summary/live" in SNAPCOPY_SUMMARY_HTML
    assert "/api/contingency-groups/fc-cg-summary/export-selected" in SNAPCOPY_SUMMARY_HTML
    assert "https://" in SNAPCOPY_SUMMARY_HTML
    assert 'href="/contingency-groups"' in SNAPCOPY_SUMMARY_HTML


def test_health_server_serves_snapcopy_summary():
    assert hasattr(HealthServer, "open_snapcopy_summary")
