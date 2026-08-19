from launchpad.vcenters import VCENTERS_HTML, VCENTERS_PATH


def test_vcenters_page_markers():
    assert VCENTERS_PATH == "/vcenters"
    assert "vCenters" in VCENTERS_HTML
    assert "No vCenters yet" in VCENTERS_HTML
    assert "/api/vcenters" in VCENTERS_HTML
    assert "/api/vcenters/delete" in VCENTERS_HTML
    assert 'id="name"' in VCENTERS_HTML
    assert 'id="location"' in VCENTERS_HTML
    assert 'id="address"' in VCENTERS_HTML
    assert 'id="url"' in VCENTERS_HTML
    assert 'target="_blank"' in VCENTERS_HTML
    assert 'rel="noopener"' in VCENTERS_HTML
    assert "Unlock LaunchPad" in VCENTERS_HTML
    assert "{{APP_VERSION}}" in VCENTERS_HTML
