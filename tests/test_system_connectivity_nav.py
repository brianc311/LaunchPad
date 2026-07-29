from pathlib import Path

from launchpad.capacity_report import CAPACITY_REPORT_HTML
from launchpad.fc_consistgrp import FC_CONSISTGRP_HTML
from launchpad.fc_wwpn_report import FC_WWPN_REPORT_HTML
from launchpad.health_server import DASHBOARD_HTML, HealthServer
from launchpad.host_volume_health_page import HOST_VOLUME_HEALTH_HTML
from launchpad.system_connectivity_page import SYSTEM_CONNECTIVITY_PATH
from launchpad.volume_find_page import VOLUME_FIND_HTML


def test_dashboard_view_exposes_system_connectivity_button():
    source = (
        Path(__file__).parents[1] / "launchpad" / "ui" / "dashboard_view.py"
    ).read_text(encoding="utf-8")

    assert '"System Connectivity"' in source
    assert "command=self._open_system_connectivity" in source or (
        "self._open_system_connectivity" in source
    )
    assert "def _open_system_connectivity" in source


def test_health_dashboard_links_to_system_connectivity():
    assert f'href="{SYSTEM_CONNECTIVITY_PATH}"' in DASHBOARD_HTML
    assert "System Connectivity" in DASHBOARD_HTML


def test_open_system_connectivity_opens_browser(monkeypatch):
    server = HealthServer()
    opened: list[str] = []

    monkeypatch.setattr(server, "ensure_running", lambda: None)
    monkeypatch.setattr(
        "launchpad.health_server.webbrowser.open",
        lambda url: opened.append(url),
    )

    url = server.open_system_connectivity()

    assert url.endswith(SYSTEM_CONNECTIVITY_PATH)
    assert opened == [url]


def test_peer_pages_link_to_system_connectivity():
    link = f'href="{SYSTEM_CONNECTIVITY_PATH}">System Connectivity</a>'
    for html in (
        CAPACITY_REPORT_HTML,
        FC_WWPN_REPORT_HTML,
        VOLUME_FIND_HTML,
        FC_CONSISTGRP_HTML,
        HOST_VOLUME_HEALTH_HTML,
    ):
        assert link in html
