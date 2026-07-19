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


def test_contingency_groups_snap_modal_stays_hidden_by_default():
    assert 'id="snap-modal-backdrop" class="modal-backdrop" hidden>' in CONTINGENCY_GROUPS_HTML
    assert ".modal-backdrop[hidden] { display:none !important; }" in CONTINGENCY_GROUPS_HTML


def test_contingency_groups_exposes_collapsed_cli_panel():
    for text in (
        'id="cli-panel"',
        "CLI commands (Preview)",
        "fillCliPanel",
        "clearCliPanel",
    ):
        assert text in CONTINGENCY_GROUPS_HTML


def test_contingency_groups_page_exposes_wizard_shell():
    for text in (
        "1 Source",
        "2 Target",
        "3 Create & Map",
        "wizard-step-1",
        "advanced-panel",
        "Advanced edit",
        "wizardStep",
    ):
        assert text in CONTINGENCY_GROUPS_HTML


def test_contingency_groups_wizard_exposes_source_only_editor():
    for text in (
        "Only source volumes are shown here.",
        "Use the Storage hint above",
        'id="wizard-source-volumes-body"',
        'id="wizard-source-maps-body"',
        'id="add-source-volume-btn"',
        "Add source volume",
    ):
        assert text in CONTINGENCY_GROUPS_HTML


def test_contingency_groups_wizard_exposes_source_target_pairs():
    assert "<th>Source</th><th>Target</th><th>Pool</th><th>Capacity</th>" in (
        CONTINGENCY_GROUPS_HTML
    )
    assert 'id="wizard-snap-pairs-body"' in CONTINGENCY_GROUPS_HTML
    assert "source_volume" in CONTINGENCY_GROUPS_HTML


def test_contingency_groups_wizard_places_snap_actions_in_their_steps():
    hero = CONTINGENCY_GROUPS_HTML.split('<section class="hero">', 1)[1].split(
        "</section>", 1
    )[0]
    step_two = CONTINGENCY_GROUPS_HTML.split('id="wizard-step-2"', 1)[1].split(
        "</section>", 1
    )[0]
    step_three = CONTINGENCY_GROUPS_HTML.split('id="wizard-step-3"', 1)[1].split(
        "</section>", 1
    )[0]

    assert "generate-snaps-btn" not in hero
    assert "snap-preview-btn" not in hero
    assert "snap-create-btn" not in hero
    assert 'id="generate-snaps-btn"' in step_two
    assert 'id="snap-preview-btn"' in step_three
    assert 'id="snap-create-btn"' in step_three


def test_contingency_groups_wizard_exposes_create_and_map_plan():
    for text in (
        "Create target volumes",
        "Create FlashCopy (source → target)",
        "Start FlashCopy",
        "Map targets to hosts (same SCSI as source)",
        "<th>Source</th><th>Target</th><th>Hosts / SCSI</th>",
        'id="wizard-create-pairs-body"',
        "Preview will mark each operation as create or skip",
        'id="wizard-storage-warning"',
        "Storage hint is required before Preview or Run Create.",
        "renderWizardCreateStep",
    ):
        assert text in CONTINGENCY_GROUPS_HTML


def test_contingency_groups_wizard_validates_and_generates_before_step_two():
    for text in (
        "At least one source volume is required",
        "Source volume name is required",
        "Missing pool for source volume",
        "Missing target volume for source",
        "await generateSnapRows()",
    ):
        assert text in CONTINGENCY_GROUPS_HTML


def test_delete_group_resets_wizard_before_render():
    reset = "wizardStep = 1;\n      showWizardErrors([]);\n      render();"
    assert reset in CONTINGENCY_GROUPS_HTML


def test_health_server_exposes_contingency_groups_url():
    server = HealthServer()

    assert server.contingency_groups_url.endswith(CONTINGENCY_GROUPS_PATH)
