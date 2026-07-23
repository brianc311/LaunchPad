from launchpad.fc_wwpn_report import FC_WWPN_REPORT_HTML


def test_fc_wwpn_exposes_search_and_wag_controls():
    for text in (
        'id="fc-search"',
        "Search WWPN, remote WWPN, host, or volume",
        'id="fc-search-btn"',
        "function runFcSearch(",
        "/api/fc-wwpn-find",
        "can't locate site",
        'id="filter-wag1"',
        'id="filter-wag2"',
        'id="filter-other"',
        "groups=",
    ):
        assert text in FC_WWPN_REPORT_HTML
