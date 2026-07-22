from launchpad.fc_wwpn_report import FC_WWPN_REPORT_HTML


def test_fc_wwpn_page_has_include_bar_and_search():
    html = FC_WWPN_REPORT_HTML
    assert "Include in list / Excel" in html
    assert 'id="filter-wag1"' in html
    assert 'id="filter-wag2"' in html
    assert 'id="filter-other"' in html
    assert "Uncheck a group to hide it from the report and export." in html
    assert 'id="fc-search"' in html
    assert "Search WWPN, remote WWPN, host, or volume" in html


def test_fc_wwpn_excel_passes_groups_query():
    html = FC_WWPN_REPORT_HTML
    assert "groups=" in html or "groups:${" in html or 'groups=${' in html
    assert "selectedSiteGroups" in html
    assert "cardMatchesSearch" in html
    assert "siteGroup" in html
