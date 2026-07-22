from launchpad.site_lookup import SITE_LOOKUP_HTML, SITE_LOOKUP_PATH


def test_site_lookup_path_and_markers():
    assert SITE_LOOKUP_PATH == "/site-lookup"
    assert "Site Lookup" in SITE_LOOKUP_HTML
    assert "/api/site-lookup/cards" in SITE_LOOKUP_HTML
    assert "/api/site-lookup/detail?card=" in SITE_LOOKUP_HTML
    assert "/api/site-lookup/refresh" in SITE_LOOKUP_HTML
    assert 'id="siteSelect"' in SITE_LOOKUP_HTML
    assert "filterRows" in SITE_LOOKUP_HTML
    assert "window.open" in SITE_LOOKUP_HTML
