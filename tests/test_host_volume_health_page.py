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
