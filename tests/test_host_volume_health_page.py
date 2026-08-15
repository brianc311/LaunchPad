from launchpad.host_volume_health_page import (
    HOST_VOLUME_HEALTH_HTML,
    HOST_VOLUME_HEALTH_PATH,
)


def test_host_volume_health_path_and_controls():
    assert HOST_VOLUME_HEALTH_PATH == "/host-volume-health"
    for text in (
        "Hosts & Volumes Health",
        'id="hv-site-select"',
        '<option value="">All servers</option>',
        'id="hv-refresh-btn"',
        'id="hv-export-xlsx-btn"',
        'id="hv-export-csv-btn"',
        "/api/host-volume-health/live",
        'id="hv-hosts-body"',
        'id="hv-volumes-body"',
        'id="hv-status"',
        'id="hv-errors"',
        "Site changed — click Refresh to scan again.",
    ):
        assert text in HOST_VOLUME_HEALTH_HTML


def test_host_volume_health_progress_markers():
    html = HOST_VOLUME_HEALTH_HTML
    script = html.split("<script>", 1)[1]
    assert 'id="hv-progress-wrap"' in html
    assert 'id="hv-progress-bar"' in html
    assert "/api/host-volume-health/progress" in script
    assert "progressActive" in script
    assert '"<div class="' not in script


def test_host_volume_health_progress_ignores_polls_after_hide():
    script = HOST_VOLUME_HEALTH_HTML.split("<script>", 1)[1]
    hide_fn = script.split("function hideProgress()", 1)[1].split("function applyProgress", 1)[0]
    apply_fn = script.split("function applyProgress(data)", 1)[1].split("async function pollProgress", 1)[0]
    poll_fn = script.split("async function pollProgress()", 1)[1].split("async function refreshLive", 1)[0]
    refresh_fn = script.split("async function refreshLive()", 1)[1].split("function exportUrl", 1)[0]
    assert "progressActive = false" in hide_fn
    assert "if (!progressActive)" in apply_fn
    assert poll_fn.count("if (!progressActive)") >= 2
    assert "progressActive = true" in refresh_fn
    assert "hideProgress()" in refresh_fn
