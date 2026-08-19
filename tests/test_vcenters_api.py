import io
import json

import launchpad.health_server as health_server_module
from launchpad.health_server import HealthServer, _HealthHandler
from launchpad.vcenters import VCENTERS_PATH
from launchpad.vcenters_directory import SETTING_VCENTERS_DIRECTORY


def _settings_backend(initial: dict[str, str] | None = None):
    settings = dict(initial or {})

    def get_setting(key: str, default: str) -> str:
        return settings.get(key, default)

    def set_setting(key: str, value: str) -> None:
        settings[key] = value

    return settings, get_setting, set_setting


def _get(path: str, monkeypatch, server: HealthServer) -> dict:
    handler = object.__new__(_HealthHandler)
    handler.path = path
    sent: dict = {}

    def _send_html(body, status=200):
        sent["html"] = body
        sent["status"] = status

    def _send_json(data, status=200):
        sent["json"] = data
        sent["status"] = status

    handler._send_html = _send_html
    handler._send_json = _send_json
    monkeypatch.setattr(health_server_module, "get_health_server", lambda: server)
    handler.do_GET()
    return sent


def _post(path: str, payload: dict, monkeypatch, server: HealthServer) -> dict:
    body = json.dumps(payload).encode()
    handler = object.__new__(_HealthHandler)
    handler.path = path
    handler.headers = {"Content-Length": str(len(body))}
    handler.rfile = io.BytesIO(body)
    sent: dict = {}

    def _send_json(response, status=200):
        sent.update(payload=response, status=status)

    handler._send_json = _send_json
    monkeypatch.setattr(health_server_module, "get_health_server", lambda: server)
    handler.do_POST()
    return sent


def test_get_vcenters_page_and_empty_list(monkeypatch):
    server = HealthServer()
    _settings, getter, setter = _settings_backend()
    server.set_settings_backend(getter, setter)
    page = _get(VCENTERS_PATH, monkeypatch, server)
    assert page["status"] == 200
    assert "vCenters" in page["html"]
    sent = _get("/api/vcenters", monkeypatch, server)
    assert sent["json"]["vcenters"] == []
    assert sent["json"]["unlocked"] is True


def test_post_vcenter_saves_and_locked_write_fails(monkeypatch):
    server = HealthServer()
    settings, getter, setter = _settings_backend()
    server.set_settings_backend(getter, setter)
    saved = _post(
        "/api/vcenters",
        {"name": "WAG VC", "address": "10.1.2.3", "location": "Wagga"},
        monkeypatch,
        server,
    )
    assert saved["status"] == 200
    rows = saved["payload"]["vcenters"]
    assert len(rows) == 1
    assert rows[0]["name"] == "WAG VC"
    assert json.loads(settings[SETTING_VCENTERS_DIRECTORY])
    locked = HealthServer()
    denied = _post(
        "/api/vcenters",
        {"name": "X", "address": "10.0.0.1"},
        monkeypatch,
        locked,
    )
    assert denied["status"] == 503
    assert "unlocked" in denied["payload"]["error"].lower()


def test_open_vcenters_opens_browser(monkeypatch):
    server = HealthServer()
    opened: list[str] = []
    monkeypatch.setattr(server, "ensure_running", lambda: None)
    monkeypatch.setattr(
        "launchpad.health_server.webbrowser.open",
        lambda url: opened.append(url),
    )
    url = server.open_vcenters()
    assert url.endswith(VCENTERS_PATH)
    assert opened == [url]
