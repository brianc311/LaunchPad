import json
import shutil
import subprocess
from pathlib import Path

import pytest

from launchpad.lun_builder import LUN_BUILDER_HTML, LUN_BUILDER_PATH
from launchpad.lun_builder_data import LUN_BUILDER_PROFILES


def _run_completion_sync(build: dict) -> dict:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required to execute the embedded JavaScript helper")

    helpers = LUN_BUILDER_HTML.split("const SITE_HOST_RE =", 1)[1].split(
        "function emptyBuild()", 1
    )[0]
    script = (
        "const SITE_HOST_RE ="
        + helpers
        + f"\nconst build = {json.dumps(build)};"
        + "\nsyncCompletionFromPlan(build);"
        + "\nprocess.stdout.write(JSON.stringify(build));"
    )
    result = subprocess.run(
        [node, "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def _completion_build() -> dict:
    return {
        "plan_done": {
            "pconsps_root_1": True,
            "pconsps_root_2": True,
            "pconsps_data": True,
        },
        "hosts": [
            {"lpar_name": "PCONSPS3", "done": False},
            {"lpar_name": "unmapped", "done": True},
        ],
        "luns": [
            {
                "purpose": "root",
                "count": 2,
                "shared": True,
                "cluster": "sps",
                "name_prefix": "pcon",
                "host_names": [" pconsps3 "],
                "done": False,
            },
            {
                "purpose": "data",
                "count": 1,
                "shared": True,
                "cluster": "sps",
                "name_prefix": "pcon",
                "host_names": ["PCONSPS3"],
                "done": False,
            },
        ],
    }


def test_completion_sync_marks_complete_luns_and_mapped_hosts_done():
    build = _run_completion_sync(_completion_build())

    assert [lun["done"] for lun in build["luns"]] == [True, True]
    assert build["hosts"][0]["done"] is True
    assert build["hosts"][1]["done"] is True


def test_completion_sync_reverses_lun_and_host_when_one_volume_is_incomplete():
    build = _completion_build()
    del build["plan_done"]["pconsps_root_2"]

    synced = _run_completion_sync(build)

    assert [lun["done"] for lun in synced["luns"]] == [False, True]
    assert synced["hosts"][0]["done"] is False
    assert synced["hosts"][1]["done"] is True


def test_plan_done_handler_synchronizes_before_rendering():
    handler = LUN_BUILDER_HTML.split(
        'document.getElementById("plan-body").addEventListener("change"', 1
    )[1].split(
        'document.getElementById("cli-checklist").addEventListener("change"', 1
    )[0]

    assert "syncCompletionFromPlan(build);" in handler
    assert "render();" in handler
    assert handler.index("syncCompletionFromPlan(build);") < handler.index("render();")


def test_lun_builder_path():
    assert LUN_BUILDER_PATH == "/lun-builder"


def test_lun_builder_section_header_counts():
    for text in (
        'id="hosts-heading"',
        'id="luns-heading"',
        "Hosts (0/0 done)",
        "LUN specs (0/0 done)",
        "updateSectionHeadings",
    ):
        assert text in LUN_BUILDER_HTML


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
