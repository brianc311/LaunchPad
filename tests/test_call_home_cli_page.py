from launchpad.call_home_cli import CALL_HOME_CLI_HTML, CALL_HOME_CLI_PATH
from launchpad.health_server import DASHBOARD_HTML


def test_path_title_and_actions():
    assert CALL_HOME_CLI_PATH == "/call-home-cli"
    html = CALL_HOME_CLI_HTML
    assert "Call Home CLI" in html
    assert "Preview Contact" in html
    assert "Run Contact" in html
    assert "Preview SMTP" in html
    assert "Run SMTP" in html
    assert "Preview Users" in html
    assert "Run Users" in html
    assert "Preview Cloud" in html
    assert "Run Cloud" in html
    assert "Preview Remove SMTP" in html
    assert "Run Remove SMTP" in html
    assert 'id="smtp-ip"' not in html  # shared SMTP block removed
    assert "SMTP add (optional)" not in html


def test_api_paths_and_payload_fields():
    html = CALL_HOME_CLI_HTML
    for path in (
        "/api/call-home/cards",
        "/api/call-home/state",
        "/api/call-home/preview-apply",
        "/api/call-home/run-apply",
        "/api/call-home/preview-smtp",
        "/api/call-home/run-smtp",
        "/api/call-home/preview-users",
        "/api/call-home/run-users",
        "/api/call-home/preview-cloud",
        "/api/call-home/run-cloud",
        "/api/call-home/preview-remove",
        "/api/call-home/run-remove",
    ):
        assert path in html
    assert "remove_ids" in html
    assert "user_type" in html
    assert "requested" in html


def test_array_host_is_https_link_outside_checkbox_label():
    html = CALL_HOME_CLI_HTML
    assert html.find("</label>' + arrayHostLink") != -1
    assert 'target="_blank"' in html
    assert 'rel="noopener"' in html


def test_five_run_kinds_invalidate_and_catch():
    html = CALL_HOME_CLI_HTML
    assert "invalidatePreview" in html
    for key in ("apply", "smtp", "users", "cloud", "remove"):
        assert f"__{key}Ok" in html or f"window.__{key}Ok" in html
    assert "catch" in html
    assert "This writes Call Home contact/location" in html
    assert "optional SMTP add" not in html
    assert "This writes SMTP" in html
    assert "This writes Call Home email users" in html
    assert "This enables or disables Cloud Call Home" in html


def test_run_modal_renders_array_logs():
    html = CALL_HOME_CLI_HTML
    chunk = html[html.find("function previewLines") : html.find("function previewLines") + 900]
    assert "row.log" in chunk
    assert "entry.error" in chunk
    assert "runHadArrayErrors" in html
    assert "finished with errors" in html


def test_health_dashboard_link():
    assert 'href="/call-home-cli"' in DASHBOARD_HTML
