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


def test_page_has_firmware_tab_after_ntp():
    html = SYSTEM_CONNECTIVITY_HTML
    assert 'data-tab="firmware"' in html
    assert html.index('data-tab="ntp"') < html.index('data-tab="firmware"')
    assert "Versions behind" in html
    assert "Admin Firmware catalog" in html
    assert 'id="sc-panel-firmware"' in html
    assert 'id="sc-firmware-body"' in html
    compact = html.replace(" ", "")
    assert '"firmware"' in compact and "TOPICS" in compact
    assert compact.index('"ntp"') < compact.index('"firmware"')


def test_firmware_panel_includes_ibm_upgrade_matrix_link():
    from launchpad.system_connectivity_page import SYSTEM_CONNECTIVITY_HTML

    html = SYSTEM_CONNECTIVITY_HTML
    assert 'id="sc-panel-firmware"' in html
    assert 'href="https://www.ibm.com/support/pages/node/5692850"' in html
    assert 'target="_blank"' in html
    assert 'rel="noopener noreferrer"' in html
    assert "IBM FlashSystem software upgrade matrix" in html


def test_firmware_panel_includes_hpe_spock_upgrade_matrix_link():
    from launchpad.system_connectivity_page import SYSTEM_CONNECTIVITY_HTML

    html = SYSTEM_CONNECTIVITY_HTML
    assert 'href="https://www.hpe.com/storage/spock"' in html
    assert "HPE software upgrade matrix (SPOCK)" in html


def test_page_has_license_key_tab_after_firmware():
    html = SYSTEM_CONNECTIVITY_HTML
    assert 'data-tab="license_key"' in html
    assert html.index('data-tab="firmware"') < html.index('data-tab="license_key"')
    assert 'id="sc-panel-license_key"' in html
    assert 'id="sc-license_key-body"' in html
    assert "Key generation date" in html
    assert "Encryption licensed" in html
    compact = html.replace(" ", "")
    assert compact.index('"firmware"') < compact.index('"license_key"')


def test_system_connectivity_styles_content_links_for_dark_theme():
    from launchpad.system_connectivity_page import SYSTEM_CONNECTIVITY_HTML

    html = SYSTEM_CONNECTIVITY_HTML
    assert "a:not(.btn)" in html
    assert "#9ec1ff" in html
    assert "#c5d9ff" in html
    assert 'href="https://www.ibm.com/support/pages/node/5692850"' in html
