from launchpad.health_server import DASHBOARD_HTML, HealthServer, _HealthHandler
from launchpad.mouse_jiggler import SETTING_MOUSE_JIGGLER


def test_dashboard_has_jiggler_status_markup():
    html = DASHBOARD_HTML
    for text in (
        'id="jiggler-status"',
        "Mouse jiggler: Off",
        "/api/mouse-jiggler",
    ):
        assert text in html


def _call_mouse_jiggler_api(monkeypatch, server: HealthServer):
    handler = object.__new__(_HealthHandler)
    handler.path = "/api/mouse-jiggler"
    sent: dict = {}

    def _send_json(data, status=200):
        sent["json"] = data
        sent["status"] = status

    handler._send_json = _send_json
    monkeypatch.setattr("launchpad.health_server.get_health_server", lambda: server)

    handler.do_GET()

    return sent


def test_get_mouse_jiggler_api_returns_enabled_from_setting(monkeypatch):
    server = HealthServer()
    settings = {SETTING_MOUSE_JIGGLER: "true"}

    server.set_settings_backend(
        lambda key, default="": settings.get(key, default),
        lambda key, value: settings.__setitem__(key, value),
    )

    sent = _call_mouse_jiggler_api(monkeypatch, server)

    assert sent["status"] == 200
    assert sent["json"] == {"enabled": True}


def test_get_mouse_jiggler_api_false_when_no_getter(monkeypatch):
    server = HealthServer()

    sent = _call_mouse_jiggler_api(monkeypatch, server)

    assert sent["status"] == 200
    assert sent["json"] == {"enabled": False}
