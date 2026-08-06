from launchpad.site_lookup import SITE_LOOKUP_HTML, SITE_LOOKUP_PATH


def test_site_lookup_path_and_markers():
    assert SITE_LOOKUP_PATH == "/site-lookup"
    html = SITE_LOOKUP_HTML
    assert "Site Lookup" in html
    assert "/api/cards" in html
    assert "/api/site-lookup/refresh" in html
    assert "Live Refresh" in html
    for label in ("Hosts", "Volumes", "Consistency Groups", "Pools"):
        assert label in html


def test_site_lookup_page_contracts():
    html = SITE_LOOKUP_HTML
    assert "{{APP_VERSION}}" in html
    assert "Not available for this profile" in html
    assert "No rows" in html
    assert 'method: "POST"' in html
    assert "refreshBtn.disabled = true" in html
    assert "Last updated:" in html
    assert "fc_hosts" in html
    assert "fc_mappings" in html
    assert "V7KTMP-G2V1" not in html
