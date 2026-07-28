from launchpad.system_connectivity_page import (
    SYSTEM_CONNECTIVITY_HTML,
    SYSTEM_CONNECTIVITY_PATH,
)


def test_system_connectivity_path_and_controls():
    assert SYSTEM_CONNECTIVITY_PATH == "/system-connectivity"
    for text in (
        "System Connectivity",
        'id="sc-site-select"',
        '<option value="">None</option>',
        'id="sc-refresh-btn"',
        'id="sc-export-xlsx-btn"',
        'id="sc-export-csv-btn"',
        "/api/system-connectivity/live",
        "/api/system-connectivity/export",
        'id="sc-call_home-body"',
        'id="sc-dns-body"',
        'id="sc-snmp-body"',
        'id="sc-ntp-body"',
        "Service Processor",
        "{{APP_VERSION}}",
        'href="/host-volume-health"',
    ):
        assert text in SYSTEM_CONNECTIVITY_HTML
