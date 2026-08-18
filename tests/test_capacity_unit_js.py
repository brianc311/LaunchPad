from launchpad.config import APP_VERSION
from launchpad.fc_consistgrp import FC_CONSISTGRP_HTML
from launchpad.health_server import DASHBOARD_HTML
from launchpad.site_lookup import SITE_LOOKUP_HTML
from launchpad.snapshot_schedule import SNAPSHOT_SCHEDULE_HTML


def test_pages_include_capacity_unit_mode_placeholder():
    for html in (
        DASHBOARD_HTML,
        SITE_LOOKUP_HTML,
        SNAPSHOT_SCHEDULE_HTML,
        FC_CONSISTGRP_HTML,
    ):
        assert "{{CAPACITY_UNIT_MODE}}" in html
        assert "CAPACITY_UNIT_MODE" in html


def test_fc_consistgrp_format_bytes_uses_mode():
    assert "GiB" in FC_CONSISTGRP_HTML
    assert "1024" in FC_CONSISTGRP_HTML
    assert "1000" in FC_CONSISTGRP_HTML


def test_polled_pages_update_capacity_unit_mode_from_cards():
    for html in (
        DASHBOARD_HTML,
        SITE_LOOKUP_HTML,
        SNAPSHOT_SCHEDULE_HTML,
        FC_CONSISTGRP_HTML,
    ):
        assert 'let CAPACITY_UNIT_MODE = "{{CAPACITY_UNIT_MODE}}";' in html
        assert "capacity_unit_mode" in html


def test_app_version_153():
    assert APP_VERSION == "1.6.178"
