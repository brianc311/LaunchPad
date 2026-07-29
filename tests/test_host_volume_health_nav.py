from pathlib import Path

from launchpad.capacity_report import CAPACITY_REPORT_HTML
from launchpad.fc_consistgrp import FC_CONSISTGRP_HTML
from launchpad.fc_wwpn_report import FC_WWPN_REPORT_HTML
from launchpad.health_server import DASHBOARD_HTML, HealthServer
from launchpad.host_volume_health_page import HOST_VOLUME_HEALTH_PATH
from launchpad.volume_find_page import VOLUME_FIND_HTML


def test_dashboard_view_exposes_hosts_volumes_button():
    source = (
        Path(__file__).parents[1] / "launchpad" / "ui" / "dashboard_view.py"
    ).read_text(encoding="utf-8")

    assert '"Hosts & Volumes"' in source
    assert "self._open_host_volume_health" in source


def test_health_dashboard_links_to_host_volume_health():
    assert f'href="{HOST_VOLUME_HEALTH_PATH}"' in DASHBOARD_HTML
    assert "Hosts & Volumes" in DASHBOARD_HTML


def test_open_host_volume_health_opens_browser(monkeypatch):
    server = HealthServer()
    opened: list[str] = []

    monkeypatch.setattr(server, "ensure_running", lambda: None)
    monkeypatch.setattr(
        "launchpad.health_server.webbrowser.open",
        lambda url: opened.append(url),
    )

    url = server.open_host_volume_health()

    assert url.endswith(HOST_VOLUME_HEALTH_PATH)
    assert opened == [url]


def test_peer_pages_link_to_host_volume_health():
    link = f'href="{HOST_VOLUME_HEALTH_PATH}">Hosts & Volumes</a>'
    for html in (
        CAPACITY_REPORT_HTML,
        FC_WWPN_REPORT_HTML,
        VOLUME_FIND_HTML,
        FC_CONSISTGRP_HTML,
    ):
        assert link in html
