"""Contract tests for FlashCopy Consistency Groups page HTML/JS."""

from launchpad.fc_consistgrp import FC_CONSISTGRP_HTML


def test_fc_consistgrp_size_column_and_total_hint():
    html = FC_CONSISTGRP_HTML
    assert ">Size</th>" in html or ">Size<" in html
    assert "source_size" in html
    assert "Total size" in html
