from pathlib import Path

from launchpad.esx_snap_policy import ESX_SNAP_POLICY_HTML, ESX_SNAP_POLICY_PATH
from launchpad.snapshot_schedule import SNAPSHOT_SCHEDULE_HTML


def test_path_and_title():
    assert ESX_SNAP_POLICY_PATH == "/esx-snap-policy"
    assert "ESX-snap Policy" in ESX_SNAP_POLICY_HTML


def test_preview_run_and_api_paths():
    html = ESX_SNAP_POLICY_HTML
    assert "Preview / Dry-run" in html
    assert "Run Create" in html
    assert "/api/esx-snap-policy/cards" in html
    assert "/api/esx-snap-policy/volumes" in html
    assert "/api/esx-snap-policy/preview" in html
    assert "/api/esx-snap-policy/run" in html
    assert 'id="run-btn"' in html
    assert "disabled" in html


def test_policy_copy_and_volume_picker():
    html = ESX_SNAP_POLICY_HTML
    assert "ESX-snap" in html
    assert "02:00" in html
    assert "Select all" in html
    assert "Select none" in html
    assert "Load volumes" in html
    assert "operator-initiated" in html.lower() or "does not create snapshots immediately" in html.lower()


def test_invalidate_preview_and_confirm():
    html = ESX_SNAP_POLICY_HTML
    assert "invalidatePreview" in html
    assert "confirm" in html
    assert "preview_hash" in html
    assert 'maxlength="63"' in html


def test_policy_name_input_and_payload():
    html = ESX_SNAP_POLICY_HTML
    assert 'id="policy-name"' in html
    assert 'value="esx_snap"' in html
    assert "policy_name" in html
    policy_at = html.find('id="policy-name"')
    max_at = html.find('maxlength="63"', policy_at)
    assert max_at != -1


def test_load_and_preview_fetch_catch_errors():
    html = ESX_SNAP_POLICY_HTML
    load_at = html.find("async function loadVolumes")
    preview_at = html.find('getElementById("preview-btn").onclick')
    assert "catch" in html[load_at:load_at + 1200]
    assert "catch" in html[preview_at:preview_at + 1500]


def test_run_disables_button_before_fetch():
    html = ESX_SNAP_POLICY_HTML
    run_at = html.find('getElementById("run-btn").onclick')
    fetch_at = html.find('fetch("/api/esx-snap-policy/run"')
    assert run_at != -1
    assert fetch_at != -1
    disable_at = html.find("runBtn.disabled = true", run_at)
    assert disable_at != -1
    assert disable_at < fetch_at


def test_volume_checks_survive_render():
    html = ESX_SNAP_POLICY_HTML
    assert "checkedByCard" in html
    inner_at = html.find("box.innerHTML = volumesByCard")
    assert inner_at != -1
    restore_at = html.find(".checked =", inner_at)
    assert restore_at != -1


def test_dashboard_tool_specs_includes_esx_snap_policy():
    source = Path("launchpad/ui/dashboard_view.py").read_text(encoding="utf-8")
    assert '"ESX-snap Policy"' in source or "'ESX-snap Policy'" in source
    assert "_open_esx_snap_policy" in source


def test_snapshot_schedule_links_here():
    assert "/esx-snap-policy" in SNAPSHOT_SCHEDULE_HTML


def test_health_dashboard_nav_includes_esx_snap_policy():
    source = Path("launchpad/health_server.py").read_text(encoding="utf-8")
    assert 'href="/esx-snap-policy"' in source
