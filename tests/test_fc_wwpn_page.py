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


def test_fc_wwpn_exposes_cell_clamp_controls():
    for text in (
        ".cell-clamp",
        "is-expanded",
        "function applyCellClamps(",
        "function collapseAllClampedCells(",
        "function cellNeedsClamp(",
        'aria-expanded',
        "Click to expand",
    ):
        assert text in FC_WWPN_REPORT_HTML
    assert "@media print" in FC_WWPN_REPORT_HTML
    # print must disable clamp
    assert "cell-clamp" in FC_WWPN_REPORT_HTML
    print_block = FC_WWPN_REPORT_HTML[
        FC_WWPN_REPORT_HTML.index("@media print") : FC_WWPN_REPORT_HTML.index("</style>")
    ]
    assert "line-clamp: none" in print_block or "-webkit-line-clamp: unset" in print_block or "overflow: visible" in print_block
