import inspect
import json

from launchpad.dell_report_settings import DELL_REPORT_SETTING
from launchpad.health_server import HealthServer, _HealthHandler


def _register(server: HealthServer, card_id: int, name: str, *, monitor_on: bool) -> None:
    server.register_card(card_id, name, f"10.0.0.{card_id}", 22, "user", "")
    server.set_monitor_enabled(card_id=card_id, enabled=monitor_on)


def _call_dell_report_export_api(
    monkeypatch,
    server: HealthServer,
    query: str = "",
):
    handler = object.__new__(_HealthHandler)
    handler.path = f"/api/dell-report-export{query}"
    sent: dict = {}

    def _send_bytes(body, *, content_type, filename, status=200):
        sent["body"] = body
        sent["content_type"] = content_type
        sent["filename"] = filename
        sent["status"] = status

    def _send_json(data, status=200):
        sent["json"] = data
        sent["status"] = status

    handler._send_bytes = _send_bytes
    handler._send_json = _send_json
    monkeypatch.setattr("launchpad.health_server.get_health_server", lambda: server)

    handler.do_GET()

    return sent


def test_health_handler_declares_dell_report_export_route():
    source = inspect.getsource(_HealthHandler.do_GET)

    assert "/api/dell-report-export" in source


def test_dell_report_export_disabled_returns_403(monkeypatch):
    server = HealthServer()

    def _get_setting(key: str, default: str = "") -> str:
        if key == DELL_REPORT_SETTING:
            return json.dumps({"enabled": False})
        return default

    server.set_settings_backend(_get_setting, lambda key, value: None)

    sent = _call_dell_report_export_api(monkeypatch, server)

    assert sent["status"] == 403
    assert sent["json"] == {"error": "Dell Report is disabled in Admin."}


def test_dell_report_export_sends_xlsx_when_enabled(monkeypatch):
    server = HealthServer()
    server.register_card(
        1,
        "WAG1_FS9200_1",
        "10.0.0.1",
        22,
        "user",
        "",
        device_profile="flashsystem_9500",
    )
    server.set_monitor_enabled(card_id=1, enabled=True)
    monkeypatch.setattr(server, "sync_from_app", lambda: 0)
    monkeypatch.setattr(
        server,
        "refresh_card",
        lambda card_id: server._cards[card_id],
    )
    monkeypatch.setattr(
        "launchpad.flashsystem_health.analyze_health",
        lambda name, command_results, metrics: {
            "health_issues": [],
            "capacity_summary": {
                "name": "FlashSystem 9200",
                "used_bytes": 60 * 1024**3,
                "total_bytes": 100 * 1024**3,
                "free_bytes": 40 * 1024**3,
                "used_pct": 60.0,
            },
            "pools": [],
        },
    )

    sent = _call_dell_report_export_api(monkeypatch, server, "?include_off=0&open=0")

    assert sent["status"] == 200
    assert sent["body"][:2] == b"PK"
    assert sent["content_type"] == (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert sent["filename"].startswith("Dell_Capacity_Report_")
    assert sent["filename"].endswith(".xlsx")
