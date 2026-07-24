from launchpad.volume_find_page import VOLUME_FIND_HTML, VOLUME_FIND_PATH
from launchpad.fc_wwpn_report import FC_WWPN_REPORT_HTML


def test_volume_find_path_and_controls():
    assert VOLUME_FIND_PATH == "/volume-find"
    for text in (
        "Host / Volume Find",
        'id="volume-search"',
        'id="volume-find-btn"',
        'id="volume-live-btn"',
        "/api/volume-find",
        '&mode=" + mode',
        "type=",
        "Search live",
        "No cache matches — try Search live",
    ):
        assert text in VOLUME_FIND_HTML


def test_host_volume_find_page_chrome():
    html = VOLUME_FIND_HTML
    assert "Host / Volume Find" in html
    assert 'name="find-type"' in html or 'id="find-type-host"' in html
    assert "host_name" in html or "WWPNs" in html
    assert "type=" in html
    assert "Search host name" in html or "Search host" in html


def test_fc_wwpn_links_to_volume_find():
    assert 'href="/volume-find">Host / Volume Find</a>' in FC_WWPN_REPORT_HTML


def test_volume_find_site_ip_ui():
    html = VOLUME_FIND_HTML
    for text in (
        "Site IP",
        "/api/volume-find/card-host",
        "https://",
        'colspan="6"',
        "data-card-id",
        "site-ip-edit",
        "site-ip-save",
        "site-ip-cancel",
    ):
        assert text in html
