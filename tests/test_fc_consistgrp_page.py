"""Contract tests for FlashCopy Consistency Groups page HTML/JS."""

from launchpad.fc_consistgrp import FC_CONSISTGRP_HTML


def test_fc_consistgrp_size_column_and_total_hint():
    html = FC_CONSISTGRP_HTML
    assert ">Size</th>" in html or ">Size<" in html
    assert "source_size" in html
    assert "Total size" in html


def test_fc_consistgrp_groups_table_summary_headers():
    html = FC_CONSISTGRP_HTML
    # Groups table: Name | Status | Maps | Host maps | Size | Policy | Snaps/week
    assert "<th>Name</th>" in html
    assert "<th>Status</th>" in html
    assert "<th>Maps</th>" in html
    assert "<th>Host maps</th>" in html
    assert "<th>Policy</th>" in html
    assert "<th>Snaps/week</th>" in html
    compact = "".join(html.split())
    assert (
        "<th>Maps</th><th>Hostmaps</th><th>Size</th><th>Policy</th><th>Snaps/week</th>"
        in compact
    )


def test_fc_consistgrp_render_groups_uses_summaries_fields():
    html = FC_CONSISTGRP_HTML
    assert "inventory.summaries" in html
    assert "fc_map_count" in html
    assert "host_map_count" in html
    assert "total_size" in html
    assert "snaps_per_week" in html
    assert "snaps_source" in html
    assert "Snaps/week from Snapshot Schedule" in html


def test_fc_consistgrp_styles_content_links_for_dark_theme():
    html = FC_CONSISTGRP_HTML
    assert "a:not(.btn)" in html
    assert "#9ec1ff" in html
