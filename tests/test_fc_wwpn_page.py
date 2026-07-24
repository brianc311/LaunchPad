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


def test_fc_wwpn_js_newline_escape_is_valid():
    # Python """ must use \\n so the browser receives a JS \n escape, not a real newline
    # (which breaks the whole page script with SyntaxError).
    assert 'text.includes("\\n")' in FC_WWPN_REPORT_HTML
    assert not any(
        line.lstrip().startswith('") || text.includes')
        for line in FC_WWPN_REPORT_HTML.splitlines()
    )


def test_fc_wwpn_find_expands_and_clears_clamped_cells():
    for text in (
        "function expandClampedCellsMatching(",
        "collapseAllClampedCells(",
        "Search cleared.",
    ):
        assert text in FC_WWPN_REPORT_HTML
    # empty query path must collapse
    assert "if (!q)" in FC_WWPN_REPORT_HTML
    empty_idx = FC_WWPN_REPORT_HTML.index("function runFcSearch(")
    chunk = FC_WWPN_REPORT_HTML[empty_idx : empty_idx + 2500]
    assert "collapseAllClampedCells(" in chunk
    assert "expandClampedCellsMatching(" in chunk
