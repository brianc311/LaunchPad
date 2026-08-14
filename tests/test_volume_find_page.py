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


def test_volume_find_progress_markers():
    html = VOLUME_FIND_HTML
    script = html.split("<script>", 1)[1]
    assert 'id="vf-progress-wrap"' in html
    assert 'id="vf-progress-bar"' in html
    assert "/api/volume-find/progress" in script
    assert "progressActive" in script
    assert '"<div class="' not in script
    assert '"<tr class="' not in script


def test_volume_find_progress_ignores_polls_after_hide():
    script = VOLUME_FIND_HTML.split("<script>", 1)[1]
    hide_fn = script.split("function hideProgress()", 1)[1].split("function applyProgress", 1)[0]
    apply_fn = script.split("function applyProgress(data)", 1)[1].split("async function pollProgress", 1)[0]
    poll_fn = script.split("async function pollProgress()", 1)[1].split("async function runSearch", 1)[0]
    search_fn = script.split("async function runSearch(mode)", 1)[1].split("bodyEl.addEventListener", 1)[0]
    assert "progressActive = false" in hide_fn
    assert "if (!progressActive)" in apply_fn
    assert poll_fn.count("if (!progressActive)") >= 2
    assert "progressActive = true" in search_fn
    assert "hideProgress()" in search_fn
    assert 'if (!q)' in search_fn
