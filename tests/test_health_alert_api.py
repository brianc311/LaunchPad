import io
import json

import pytest

from launchpad.health_alert_state import HEALTH_ALERT_SETTING, issue_fingerprint
from launchpad.health_server import HealthServer, _HealthHandler


def _settings_backend(initial: dict[str, str] | None = None):
    settings = dict(initial or {})

    def get_setting(key: str, default: str) -> str:
        return settings.get(key, default)

    def set_setting(key: str, value: str) -> None:
        settings[key] = value

    return settings, get_setting, set_setting


def _register(server: HealthServer, card_id: int, name: str, *, monitor_on: bool) -> None:
    server.register_card(card_id, name, f"10.0.0.{card_id}", 22, "user", "")
    server.set_monitor_enabled(card_id=card_id, enabled=monitor_on)


def _critical_card(
    card_id: int = 1,
    name: str = "Site A",
    *,
    message: str = "Node n1 is offline",
    category: str = "node",
):
    return {
        "id": card_id,
        "name": name,
        "error": None,
        "metrics": {},
        "health_issues": [
            {
                "severity": "critical",
                "category": category,
                "message": message,
                "server": name,
            }
        ],
    }


def _patch_cards(monkeypatch, server: HealthServer, cards: list[dict]):
    monkeypatch.setattr(
        server,
        "list_cards",
        lambda *, allow_sync=True: cards,
    )


def _call_get(monkeypatch, server: HealthServer, path: str):
    handler = object.__new__(_HealthHandler)
    handler.path = path
    sent: dict = {}

    def _send_json(data, status=200):
        sent["json"] = data
        sent["status"] = status

    def _send_bytes(body, *, content_type, filename=None, status=200):
        sent["body"] = body
        sent["content_type"] = content_type
        sent["filename"] = filename
        sent["status"] = status

    handler._send_json = _send_json
    handler._send_bytes = _send_bytes
    handler.send_error = lambda status: sent.update(status=status)
    monkeypatch.setattr("launchpad.health_server.get_health_server", lambda: server)
    handler.do_GET()
    return sent


def _call_get_health_alerts(monkeypatch, server: HealthServer):
    return _call_get(monkeypatch, server, "/api/health-alerts")


def _call_post_health_alert(monkeypatch, server: HealthServer, path: str, payload: dict):
    handler = object.__new__(_HealthHandler)
    handler.path = path
    body = json.dumps(payload).encode("utf-8")
    handler.headers = {"Content-Length": str(len(body))}
    handler.rfile = io.BytesIO(body)
    sent: dict = {}

    def _send_json(data, status=200):
        sent["json"] = data
        sent["status"] = status

    handler._send_json = _send_json
    monkeypatch.setattr("launchpad.health_server.get_health_server", lambda: server)
    handler.do_POST()
    return sent


def test_get_health_alerts_returns_critical_popup(monkeypatch):
    _, getter, setter = _settings_backend()
    server = HealthServer()
    server.set_settings_backend(getter, setter)
    _register(server, 1, "Site A", monitor_on=True)
    _patch_cards(monkeypatch, server, [_critical_card()])

    payload = server.get_health_alerts()

    assert len(payload["alerts"]) == 1
    assert payload["alerts"][0]["card_name"] == "Site A"
    assert payload["cards"]["1"]["alarm_muted"] is False
    assert payload["cards"]["1"]["paused_until"] is None


def test_get_health_alerts_includes_art_url_when_card_art_exists(monkeypatch, tmp_path):
    _, getter, setter = _settings_backend()
    server = HealthServer()
    server.set_settings_backend(getter, setter)
    _register(server, 1, "Site A", monitor_on=True)
    _patch_cards(monkeypatch, server, [_critical_card()])
    art_path = tmp_path / "SITE_A.png"
    art_path.write_bytes(b"\x89PNG\r\n\x1a\n")
    monkeypatch.setattr(
        "launchpad.health_server.resolve_health_alert_art",
        lambda card_name: art_path if card_name == "Site A" else None,
    )

    payload = server.get_health_alerts()

    assert payload["alerts"][0]["art_url"] == "/api/health-alerts/art?card_id=1"
    assert payload["cards"]["1"]["art_url"] == "/api/health-alerts/art?card_id=1"


def test_get_health_alerts_excludes_warn_issues(monkeypatch):
    _, getter, setter = _settings_backend()
    server = HealthServer()
    server.set_settings_backend(getter, setter)
    _register(server, 1, "Site A", monitor_on=True)
    _patch_cards(
        monkeypatch,
        server,
        [
            {
                "id": 1,
                "name": "Site A",
                "error": None,
                "metrics": {},
                "health_issues": [
                    {
                        "severity": "warn",
                        "category": "capacity",
                        "message": "Pool X is 81% full",
                        "server": "Site A",
                    }
                ],
            }
        ],
    )

    payload = server.get_health_alerts()

    assert payload["alerts"] == []


def test_unreachable_card_is_connectivity_alert(monkeypatch):
    _, getter, setter = _settings_backend()
    server = HealthServer()
    server.set_settings_backend(getter, setter)
    _register(server, 2, "Valparaiso, IN", monitor_on=True)
    _patch_cards(
        monkeypatch,
        server,
        [
            {
                "id": 2,
                "name": "Valparaiso, IN",
                "error": "Connection refused",
                "metrics": None,
                "health_issues": [
                    {
                        "severity": "critical",
                        "category": "command",
                        "message": "Health - Nodes failed",
                        "server": "Valparaiso, IN",
                    },
                    {
                        "severity": "critical",
                        "category": "command",
                        "message": "Health - Alerts failed",
                        "server": "Valparaiso, IN",
                    },
                ],
            }
        ],
    )

    payload = server.get_health_alerts()

    assert len(payload["alerts"]) == 1
    assert payload["alerts"][0]["category"] == "connectivity"
    assert "Valparaiso" in payload["alerts"][0]["card_name"]


def test_acknowledge_health_alert_suppresses_popup(monkeypatch):
    settings, getter, setter = _settings_backend()
    server = HealthServer()
    server.set_settings_backend(getter, setter)
    _register(server, 1, "Site A", monitor_on=True)
    _patch_cards(monkeypatch, server, [_critical_card()])
    fp = issue_fingerprint(1, "node", "Node n1 is offline")

    open_before = server.get_health_alerts()
    assert len(open_before["alerts"]) == 1

    result = server.acknowledge_health_alert(fp)

    assert result["alerts"] == []
    stored = json.loads(settings[HEALTH_ALERT_SETTING])
    assert fp in stored["acknowledged"]
    assert server.get_health_alerts()["alerts"] == []


def test_acknowledge_health_alerts_batch(monkeypatch):
    settings, getter, setter = _settings_backend()
    server = HealthServer()
    server.set_settings_backend(getter, setter)
    _register(server, 1, "A", monitor_on=True)
    _register(server, 2, "B", monitor_on=True)
    _patch_cards(
        monkeypatch,
        server,
        [
            _critical_card(1, "A", message="Node a offline"),
            _critical_card(2, "B", message="Node b offline"),
        ],
    )
    fps = [
        issue_fingerprint(1, "node", "Node a offline"),
        issue_fingerprint(2, "node", "Node b offline"),
    ]

    server.acknowledge_health_alerts(fps)

    stored = json.loads(settings[HEALTH_ALERT_SETTING])
    assert set(stored["acknowledged"]) == set(fps)
    assert server.get_health_alerts()["alerts"] == []


def test_get_prunes_stale_acknowledgements(monkeypatch):
    stale = issue_fingerprint(1, "node", "Old issue")
    settings, getter, setter = _settings_backend(
        {
            HEALTH_ALERT_SETTING: json.dumps(
                {
                    "acknowledged": [stale],
                    "alarm_muted": {},
                    "paused_until": {},
                }
            )
        }
    )
    server = HealthServer()
    server.set_settings_backend(getter, setter)
    _register(server, 1, "Site A", monitor_on=True)
    _patch_cards(
        monkeypatch,
        server,
        [{"id": 1, "name": "Site A", "error": None, "metrics": {}, "health_issues": []}],
    )

    server.get_health_alerts()

    stored = json.loads(settings[HEALTH_ALERT_SETTING])
    assert stored["acknowledged"] == []


def test_pause_health_alert_hides_popup_until_expiry(monkeypatch):
    settings, getter, setter = _settings_backend()
    server = HealthServer()
    server.set_settings_backend(getter, setter)
    _register(server, 3, "Site B", monitor_on=True)
    _patch_cards(monkeypatch, server, [_critical_card(3, "Site B")])
    fixed_now = 1_000_000.0
    monkeypatch.setattr("launchpad.health_server.time.time", lambda: fixed_now)

    paused = server.pause_health_alert(3, 10)

    assert paused["alerts"] == []
    assert paused["cards"]["3"]["paused_until"] == fixed_now + 10 * 60
    stored = json.loads(settings[HEALTH_ALERT_SETTING])
    assert stored["paused_until"]["3"] == fixed_now + 10 * 60


def test_set_health_alarm_mutes_card(monkeypatch):
    settings, getter, setter = _settings_backend()
    server = HealthServer()
    server.set_settings_backend(getter, setter)
    _register(server, 3, "Site B", monitor_on=True)
    _patch_cards(monkeypatch, server, [_critical_card(3, "Site B")])

    muted = server.set_health_alarm(3, True)

    assert muted["alerts"] == []
    assert muted["cards"]["3"]["alarm_muted"] is True
    stored = json.loads(settings[HEALTH_ALERT_SETTING])
    assert stored["alarm_muted"]["3"] is True

    restored = server.set_health_alarm(3, False)
    assert restored["cards"]["3"]["alarm_muted"] is False
    assert len(restored["alerts"]) == 1


def test_health_alert_writes_require_settings_backend():
    server = HealthServer()
    with pytest.raises(RuntimeError, match="unlocked"):
        server.acknowledge_health_alert("1:node:test")
    with pytest.raises(RuntimeError, match="unlocked"):
        server.pause_health_alert(1, 5)
    with pytest.raises(RuntimeError, match="unlocked"):
        server.set_health_alarm(1, True)


def test_get_health_alerts_route(monkeypatch):
    _, getter, setter = _settings_backend()
    server = HealthServer()
    server.set_settings_backend(getter, setter)
    _register(server, 1, "Site A", monitor_on=True)
    _patch_cards(monkeypatch, server, [_critical_card()])

    sent = _call_get_health_alerts(monkeypatch, server)

    assert sent["status"] == 200
    assert len(sent["json"]["alerts"]) == 1


def test_get_health_alert_art_route_returns_png(monkeypatch, tmp_path):
    server = HealthServer()
    _register(server, 7, "Site Art", monitor_on=True)
    art_path = tmp_path / "SITE_ART.png"
    png = b"\x89PNG\r\n\x1a\nart"
    art_path.write_bytes(png)
    monkeypatch.setattr(
        "launchpad.health_server.resolve_health_alert_art",
        lambda card_name: art_path if card_name == "Site Art" else None,
    )

    sent = _call_get(monkeypatch, server, "/api/health-alerts/art?card_id=7")

    assert sent["status"] == 200
    assert sent["body"] == png
    assert sent["content_type"] == "image/png"


def test_get_health_alert_art_route_returns_404_without_art(monkeypatch):
    server = HealthServer()
    _register(server, 8, "No Art", monitor_on=True)
    monkeypatch.setattr(
        "launchpad.health_server.resolve_health_alert_art",
        lambda _card_name: None,
    )

    sent = _call_get(monkeypatch, server, "/api/health-alerts/art?card_id=8")

    assert sent["status"] == 404


def test_post_acknowledge_route(monkeypatch):
    settings, getter, setter = _settings_backend()
    server = HealthServer()
    server.set_settings_backend(getter, setter)
    _register(server, 1, "Site A", monitor_on=True)
    _patch_cards(monkeypatch, server, [_critical_card()])
    fp = issue_fingerprint(1, "node", "Node n1 is offline")

    sent = _call_post_health_alert(
        monkeypatch,
        server,
        "/api/health-alerts/acknowledge",
        {"fingerprint": fp},
    )

    assert sent["status"] == 200
    assert sent["json"]["alerts"] == []
    assert fp in json.loads(settings[HEALTH_ALERT_SETTING])["acknowledged"]


def test_post_pause_invalid_minutes(monkeypatch):
    _, getter, setter = _settings_backend()
    server = HealthServer()
    server.set_settings_backend(getter, setter)

    sent = _call_post_health_alert(
        monkeypatch,
        server,
        "/api/health-alerts/pause",
        {"card_id": 1, "minutes": 7},
    )

    assert sent["status"] == 400


def test_post_alarm_route(monkeypatch):
    settings, getter, setter = _settings_backend()
    server = HealthServer()
    server.set_settings_backend(getter, setter)
    _register(server, 1, "Site A", monitor_on=True)
    _patch_cards(monkeypatch, server, [_critical_card()])

    sent = _call_post_health_alert(
        monkeypatch,
        server,
        "/api/health-alerts/alarm",
        {"card_id": 1, "muted": True},
    )

    assert sent["status"] == 200
    assert sent["json"]["cards"]["1"]["alarm_muted"] is True
    assert json.loads(settings[HEALTH_ALERT_SETTING])["alarm_muted"]["1"] is True
