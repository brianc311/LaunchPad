import io
import json

from cryptography.fernet import Fernet

import launchpad.health_server as health_server_module
from launchpad.crypto import decrypt_text
from launchpad.health_server import HealthServer, _HealthHandler
from launchpad.vcenters import VCENTERS_PATH
from launchpad.vcenters_directory import (
    SETTING_VCENTERS_DIRECTORY,
    VCENTER_PASSWORD_PLACEHOLDER,
)


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
    server.set_settings_backend(getter, setter, crypto_key=Fernet.generate_key())
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


def test_vcenter_get_hides_password_and_keeps_placeholder(monkeypatch):
    server = HealthServer()
    settings, getter, setter = _settings_backend()
    key = Fernet.generate_key()
    server.set_settings_backend(getter, setter, crypto_key=key)
    saved = _post(
        "/api/vcenters",
        {
            "name": "remvcenter101",
            "address": "172.31.198.193",
            "use_vsphere_client": True,
            "username": "admin",
            "password": "s3cret",
        },
        monkeypatch,
        server,
    )
    row = saved["payload"]["vcenters"][0]
    assert row["password"] == VCENTER_PASSWORD_PLACEHOLDER
    assert "password_encrypted" not in row
    stored = json.loads(settings[SETTING_VCENTERS_DIRECTORY])[0]
    assert decrypt_text(key, stored["password_encrypted"]) == "s3cret"
    again = _post(
        "/api/vcenters",
        {
            "id": row["id"],
            "name": "remvcenter101",
            "address": "172.31.198.193",
            "use_vsphere_client": True,
            "username": "admin",
            "password": VCENTER_PASSWORD_PLACEHOLDER,
        },
        monkeypatch,
        server,
    )
    assert again["status"] == 200
    stored2 = json.loads(settings[SETTING_VCENTERS_DIRECTORY])[0]
    assert stored2["password_encrypted"] == stored["password_encrypted"]
    got = _get("/api/vcenters", monkeypatch, server)
    assert got["json"]["vcenters"][0]["password"] == VCENTER_PASSWORD_PLACEHOLDER


def test_launch_vcenter_client_requires_unlock_and_checkbox(monkeypatch):
    locked = _post("/api/vcenters/launch", {"id": "x"}, monkeypatch, HealthServer())
    assert locked["status"] == 503
    server = HealthServer()
    _settings, getter, setter = _settings_backend()
    key = Fernet.generate_key()
    server.set_settings_backend(getter, setter, crypto_key=key)
    created = _post(
        "/api/vcenters",
        {"name": "WebOnly", "address": "10.0.0.1", "use_vsphere_client": False},
        monkeypatch,
        server,
    )
    vid = created["payload"]["vcenters"][0]["id"]
    denied = _post("/api/vcenters/launch", {"id": vid}, monkeypatch, server)
    assert denied["status"] == 400
    missing = _post("/api/vcenters/launch", {"id": "nope"}, monkeypatch, server)
    assert missing["status"] == 400


def test_launch_vcenter_client_starts_process(monkeypatch, tmp_path):
    server = HealthServer()
    _settings, getter, setter = _settings_backend()
    key = Fernet.generate_key()
    server.set_settings_backend(getter, setter, crypto_key=key)
    created = _post(
        "/api/vcenters",
        {
            "name": "remvcenter101",
            "address": "172.31.198.193",
            "use_vsphere_client": True,
            "username": "admin",
            "password": "s3cret",
        },
        monkeypatch,
        server,
    )
    vid = created["payload"]["vcenters"][0]["id"]
    fake_exe = tmp_path / "vpxclient.exe"
    fake_exe.write_text("stub")
    monkeypatch.setattr(
        "launchpad.health_server.VPXCLIENT_PATH", fake_exe
    )
    monkeypatch.setattr(
        "launchpad.vcenters_directory.VPXCLIENT_PATH", fake_exe
    )
    started = []

    def fake_popen(cmd, **kwargs):
        started.append((cmd, kwargs))
        return object()

    monkeypatch.setattr("launchpad.health_server.subprocess.Popen", fake_popen)
    result = _post("/api/vcenters/launch", {"id": vid}, monkeypatch, server)
    assert result["status"] == 200
    assert result["payload"]["ok"] is True
    cmd, kwargs = started[0]
    assert cmd[0] == str(fake_exe)
    assert cmd[1:5] == ["-s", "172.31.198.193", "-u", "admin"]
    assert "-p" in cmd and "s3cret" in cmd
    assert kwargs.get("cwd") == str(fake_exe.parent)
