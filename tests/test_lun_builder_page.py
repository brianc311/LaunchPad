from pathlib import Path

from launchpad.lun_builder import LUN_BUILDER_HTML, LUN_BUILDER_PATH
from launchpad.lun_builder_data import LUN_BUILDER_PROFILES


def test_lun_builder_path():
    assert LUN_BUILDER_PATH == "/lun-builder"


def test_lun_builder_page_contract():
    for text in (
        "LUN Builder",
        "Hosts",
        "LUN specs",
        "Export Excel",
        "Export CSV",
        'id="export-excel-btn"',
        'id="export-csv-btn"',
        "/api/lun-builds-export?id=",
        "&format=xlsx",
        "&format=csv",
        "Import",
        'id="import-file"',
        "/api/lun-builds/import",
        "Pull from FC WWPN",
        "/api/lun-builds/pull-fc",
        "Preview / Dry-run",
        "Run Create",
        ".modal-backdrop[hidden] { display:none !important; }",
        "__lastLunPreviewOk",
        "{{APP_VERSION}}",
    ):
        assert text in LUN_BUILDER_HTML

    assert "Import will be added in a later task." not in LUN_BUILDER_HTML
    assert "FC WWPN pull will be added in a later task." not in LUN_BUILDER_HTML
    assert "Preview engine is not connected yet." not in LUN_BUILDER_HTML
    assert "Create engine is not connected yet." not in LUN_BUILDER_HTML


def test_lun_builder_wizard_overlay():
    for text in (
        "first-time wizard",
        "wizard-step",
        "Skip wizard",
        "launchpad.lunBuilder.wizardDone",
    ):
        assert text in LUN_BUILDER_HTML


def test_lun_builder_exposes_collapsed_cli_panel():
    for text in (
        'id="cli-panel"',
        "Command checklist (Preview)",
        "fillCliChecklist",
        "clearCliChecklist",
    ):
        assert text in LUN_BUILDER_HTML


def test_lun_builder_command_checklist():
    for text in (
        "Command checklist",
        "Copy All Remaining",
        'id="cli-checklist"',
        'id="cli-warnings"',
        'id="copy-all-remaining-btn"',
        "command_done",
        "groupLunStepsByVolume",
        "commandGroupSignature",
        "fillCliChecklist",
    ):
        assert text in LUN_BUILDER_HTML


def test_lun_builder_exposes_build_defaults_that_fill_luns():
    for text in (
        'id="default-storage-profile"',
        'id="default-pool-or-cpg"',
        'id="default-card-hint"',
        "applyBuildDefaultsToLuns",
        "onBuildDefaultsChanged",
        "Card hint is the LaunchPad SSH Health Card name",
    ):
        assert text in LUN_BUILDER_HTML


def test_lun_builder_exposes_template_picker_ux():
    for text in (
        "Templates",
        "Saved builds",
        "template-banner",
        "Save as new",
        "is_template",
        "templates",
    ):
        assert text in LUN_BUILDER_HTML
    assert (
        'document.getElementById("export-excel-btn").disabled = !currentId || Boolean(build.is_template);'
        in LUN_BUILDER_HTML
    )
    assert "builds[0]?.id || templates[0]?.id" in LUN_BUILDER_HTML
    assert "Save as new before exporting a template." in LUN_BUILDER_HTML


def test_lun_builder_page_wires_preview_and_confirmed_create():
    for text in (
        "/api/lun-builds/preview",
        "/api/lun-builds/create",
        "persistCurrentBuildBeforeOps",
        "previewLuns",
        "runLunCreate",
        "confirm:true",
        "__lastLunHasRunnableSteps",
        "plan-only",
        "window.confirm",
    ):
        assert text in LUN_BUILDER_HTML


def test_lun_builder_page_ignores_stale_preview_responses():
    preview_function = LUN_BUILDER_HTML.split(
        "async function previewLuns()", 1
    )[1].split("async function runLunCreate", 1)[0]

    assert "previewRequestId" in LUN_BUILDER_HTML
    assert "requestId !== previewRequestId" in preview_function


def test_lun_builder_structural_edits_reset_preview_gate():
    add_row = LUN_BUILDER_HTML.split("function addRow(kind)", 1)[1].split(
        "function updateField", 1
    )[0]
    remove_handler = LUN_BUILDER_HTML.split(
        'body.addEventListener("click"', 1
    )[1].split("});", 1)[0]

    assert "invalidatePreview()" in add_row
    assert "invalidatePreview()" in remove_handler


def test_switching_build_identity_resets_preview_gate():
    save_function = LUN_BUILDER_HTML.split(
        "async function save(saveAsNew)", 1
    )[1].split("async function removeBuild", 1)[0]
    delete_function = LUN_BUILDER_HTML.split(
        "async function removeBuild()", 1
    )[1].split("function showModal", 1)[0]

    assert "invalidatePreview()" in save_function
    assert "invalidatePreview()" in delete_function


def test_lun_builder_page_contains_supported_profiles():
    for key, label in LUN_BUILDER_PROFILES:
        assert f'value="{key}"' in LUN_BUILDER_HTML
        assert label in LUN_BUILDER_HTML


def test_dashboard_view_exposes_lun_builder_button():
    source = (
        Path(__file__).parents[1] / "launchpad" / "ui" / "dashboard_view.py"
    ).read_text(encoding="utf-8")

    assert 'text="LUN Builder"' in source
    assert "command=self._open_lun_builder" in source
