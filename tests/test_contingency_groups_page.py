from launchpad.contingency_groups import (
    CONTINGENCY_GROUPS_HTML,
    CONTINGENCY_GROUPS_PATH,
)
from launchpad.fc_wwpn_report import FC_WWPN_REPORT_HTML
from launchpad.health_server import HealthServer


def test_contingency_groups_page_exposes_required_editor_actions():
    assert CONTINGENCY_GROUPS_PATH == "/contingency-groups"
    for text in (
        "Save",
        "Save as new",
        "Export Excel",
        "Export All Excel",
        "export-all-btn",
        "WWPN",
        "/api/contingency-groups",
        "/api/contingency-groups-export",
        'window.location.assign("/api/contingency-groups-export")',
        "launchpad.contingencyGroups",
        "{{APP_VERSION}}",
    ):
        assert text in CONTINGENCY_GROUPS_HTML


def test_save_as_new_keeps_source_group_in_client_logic():
    assert "if (saveAsNew && group.id)" in CONTINGENCY_GROUPS_HTML
    assert "groups.push(copy)" in CONTINGENCY_GROUPS_HTML
    assert "item.id !== currentId" not in CONTINGENCY_GROUPS_HTML


def test_contingency_groups_page_exposes_snap_copy_actions():
    for text in (
        "Generate _snap rows",
        "Preview / Dry-run",
        "Run Create",
        "SNAP",
        "/api/contingency-groups/generate-snaps",
        "/api/contingency-groups/snap-preview",
        "/api/contingency-groups/snap-create",
        "window.__lastSnapPreviewOk",
        "operator-initiated",
        "persistCurrentGroupBeforeSnapOps",
        "formatResolvedCard",
    ):
        assert text in CONTINGENCY_GROUPS_HTML


def test_contingency_groups_hero_lede_describes_planning_and_create():
    assert "never applied to a storage array" not in CONTINGENCY_GROUPS_HTML
    assert "planning-only" in CONTINGENCY_GROUPS_HTML
    assert "Run Create (after Preview)" in CONTINGENCY_GROUPS_HTML


def test_fc_wwpn_report_links_to_contingency_groups():
    assert 'href="/contingency-groups">Contingency Groups</a>' in FC_WWPN_REPORT_HTML


def test_fc_wwpn_report_exposes_contingency_group_filter_contract():
    for text in (
        'id="group-select"',
        'fetch("/api/contingency-groups")',
        'new URLSearchParams(window.location.search)',
        "function groupMatchesHost(",
        "function groupMatchesVolume(",
        "function filterCardByGroup(",
    ):
        assert text in FC_WWPN_REPORT_HTML


def test_fc_wwpn_map_modal_uses_group_filtered_card():
    assert "openModal(cards.find((c) => c.id === id));" in FC_WWPN_REPORT_HTML
    assert "openModal(cardsCache.find((c) => c.id === id));" not in FC_WWPN_REPORT_HTML


def test_fc_wwpn_filter_mappings_match_host_wwpns():
    assert "mapping.host_wwpns || \"\"" in FC_WWPN_REPORT_HTML


def test_health_server_exposes_contingency_groups_url():
    server = HealthServer()

    assert server.contingency_groups_url.endswith(CONTINGENCY_GROUPS_PATH)
