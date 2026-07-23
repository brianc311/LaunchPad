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
    assert 'href="/contingency-groups">Consistency Groups</a>' in FC_WWPN_REPORT_HTML


def test_consistency_groups_ui_label_keeps_contingency_path():
    assert CONTINGENCY_GROUPS_PATH == "/contingency-groups"
    assert "<h1>Consistency Groups</h1>" in CONTINGENCY_GROUPS_HTML
    assert "LaunchPad Consistency Groups" in CONTINGENCY_GROUPS_HTML
    assert 'aria-label="Consistency group"' in CONTINGENCY_GROUPS_HTML
    assert 'window.confirm("Delete this consistency group?")' in CONTINGENCY_GROUPS_HTML
    assert 'statusEl.textContent = "Syncing Consistency Group via SSH…";' in CONTINGENCY_GROUPS_HTML
    assert "/api/contingency-groups" in CONTINGENCY_GROUPS_HTML


def test_fc_wwpn_report_exposes_site_picker_contract():
    for text in (
        'id="site-select"',
        'aria-label="Site"',
        ">Site</label>",
        'option value="">None</option>',
        "function updateSiteOptions(",
        "function filterCardsBySite(",
        'new URLSearchParams(window.location.search).get("site")',
        'url.searchParams.set("site"',
        'url.searchParams.delete("site")',
    ):
        assert text in FC_WWPN_REPORT_HTML
    for text in (
        'id="group-select"',
        'aria-label="Contingency group"',
        'fetch("/api/contingency-groups")',
        "function filterCardByGroup(",
        "function groupMatchesHost(",
        "function loadGroups(",
        'get("group")',
    ):
        assert text not in FC_WWPN_REPORT_HTML


def test_fc_wwpn_map_modal_uses_filtered_card_list():
    assert "openModal(cards.find((c) => c.id === id));" in FC_WWPN_REPORT_HTML
    assert "openModal(cardsCache.find((c) => c.id === id));" not in FC_WWPN_REPORT_HTML


def test_fc_wwpn_excel_passes_selected_site():
    assert "function downloadExcel(" in FC_WWPN_REPORT_HTML
    assert "groups=" in FC_WWPN_REPORT_HTML
    assert "`&card_id=${encodeURIComponent(activeSiteId)}`" in FC_WWPN_REPORT_HTML
    assert "/api/fc-wwpn-export?" in FC_WWPN_REPORT_HTML


def test_contingency_groups_open_fc_wwpn_without_group_query():
    assert 'window.location.assign(`/fc-wwpn?group=${encodeURIComponent(currentId)}`)' not in CONTINGENCY_GROUPS_HTML
    assert 'window.location.assign("/fc-wwpn")' in CONTINGENCY_GROUPS_HTML


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


def test_contingency_groups_wizard_step2_validation_resolves_live_snap_targets():
    validate_fn = CONTINGENCY_GROUPS_HTML.split(
        "function validateWizardStep(group, step) {", 1
    )[1].split("\n    function showWizardErrors", 1)[0]
    step_two_block = validate_fn.split("if (step === 2) {", 1)[1]
    assert "source_volume" in step_two_block
    assert "isSnapVolume(target)" in step_two_block


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


def test_contingency_groups_page_has_sync_from_array():
    assert "Sync from array" in CONTINGENCY_GROUPS_HTML
    assert 'id="sync-array-btn"' in CONTINGENCY_GROUPS_HTML
    assert "/api/contingency-groups/sync-inventory" in CONTINGENCY_GROUPS_HTML


def test_consistency_groups_exposes_find_search():
    for text in (
        'id="cg-search"',
        'id="cg-search-btn"',
        "function runCgSearch(",
        "Search group, host, or volume",
        "No matching groups, hosts, or volumes",
    ):
        assert text in CONTINGENCY_GROUPS_HTML
    run_cg_search = CONTINGENCY_GROUPS_HTML.split("function runCgSearch(", 1)[1]
    assert 'cgSearchQuery = ""' in run_cg_search
    assert run_cg_search.index('cgSearchQuery = ""') < run_cg_search.index(
        "No matching groups, hosts, or volumes"
    )
