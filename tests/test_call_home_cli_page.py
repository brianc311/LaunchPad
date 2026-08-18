from launchpad.call_home_cli import CALL_HOME_CLI_HTML, CALL_HOME_CLI_PATH
from launchpad.health_server import DASHBOARD_HTML


def test_path_title_and_actions():
    assert CALL_HOME_CLI_PATH == "/call-home-cli"
    html = CALL_HOME_CLI_HTML
    assert "Call Home CLI" in html
    assert "Preview Apply" in html
    assert "Run Apply" in html
    assert "Preview Remove SMTP" in html
    assert "Run Remove SMTP" in html
    assert "Load current" in html
    assert "Select all" in html
    assert "Select none" in html
    assert 'id="run-apply-btn"' in html
    assert 'id="run-remove-btn"' in html
    assert "disabled" in html


def test_api_paths_and_payload_fields():
    html = CALL_HOME_CLI_HTML
    assert "/api/call-home/cards" in html
    assert "/api/call-home/state" in html
    assert "/api/call-home/preview-apply" in html
    assert "/api/call-home/run-apply" in html
    assert "/api/call-home/preview-remove" in html
    assert "/api/call-home/run-remove" in html
    assert "preview_hash" in html
    assert "confirm" in html
    assert "contact" in html
    assert "smtp" in html
    assert "location" in html
    assert 'type="password"' in html


def test_array_host_is_https_link_outside_checkbox_label():
    html = CALL_HOME_CLI_HTML
    assert "function arrayHostLink" in html
    assert 'class="array-ip-link"' in html
    assert 'target="_blank"' in html
    assert 'rel="noopener"' in html
    assert '"https://"' in html
    assert html.find("</label>' + arrayHostLink") != -1
    assert html.find("<span class=\"hint\">' + (card.host") == -1


def test_fetch_catch_and_separate_run_kinds():
    html = CALL_HOME_CLI_HTML
    assert "invalidatePreview" in html
    assert "catch" in html
    load_at = html.find("async function loadCurrent")
    assert load_at != -1
    assert "catch" in html[load_at:load_at + 1600]
    assert 'id="run-apply-btn"' in html
    assert 'id="run-remove-btn"' in html
    apply_at = html.find('getElementById("run-apply-btn").onclick')
    remove_at = html.find('getElementById("run-remove-btn").onclick')
    assert apply_at != -1 and remove_at != -1
    assert html.find('runApplyBtn.disabled = true', apply_at) != -1
    assert html.find('runRemoveBtn.disabled = true', remove_at) != -1
    assert "/api/call-home/run-apply" in html[apply_at:apply_at + 1200]
    assert "/api/call-home/run-remove" in html[remove_at:remove_at + 1200]
    assert "no rollback" in html.lower()
    assert "cloud Call Home" in html or "Cloud Call Home" in html


def test_run_modal_renders_array_logs():
    html = CALL_HOME_CLI_HTML
    preview_at = html.find("function previewLines")
    assert preview_at != -1
    chunk = html[preview_at : preview_at + 900]
    assert "row.runnable" in chunk
    assert "row.steps" in chunk
    assert "row.ok" in chunk
    assert "row.log" in chunk
    assert "entry.cmd" in chunk
    assert "entry.error" in chunk
    assert "entry.output" in chunk
    apply_at = html.find('getElementById("run-apply-btn").onclick')
    remove_at = html.find('getElementById("run-remove-btn").onclick')
    assert apply_at != -1 and remove_at != -1
    apply_chunk = html[apply_at : apply_at + 1400]
    remove_chunk = html[remove_at : remove_at + 1400]
    assert "runHadArrayErrors" in apply_chunk
    assert "runHadArrayErrors" in remove_chunk
    assert "Apply finished with errors." in apply_chunk
    assert "Remove finished with errors." in remove_chunk


def test_health_dashboard_link():
    assert 'href="/call-home-cli"' in DASHBOARD_HTML
