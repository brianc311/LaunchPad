import io
import json

from launchpad.health_server import HealthCard, HealthServer, _HealthHandler


def _register(server: HealthServer, card_id: int, name: str, *, monitor_on: bool) -> None:
    server.register_card(card_id, name, f"10.0.0.{card_id}", 22, "user", "")
    server.set_monitor_enabled(card_id=card_id, enabled=monitor_on)


def test_export_bytes_are_xlsx_with_expected_filename(monkeypatch):
    server = HealthServer()
    _register(server, 1, "On", monitor_on=True)
    monkeypatch.setattr(
        server,
        "refresh_card",
        lambda card_id: server._cards[card_id],
    )

    body, filename = server.export_capacity_excel_bytes()

    assert body[:2] == b"PK"
    assert filename.startswith("Storage_Capacity_Report_")
    assert filename.endswith(".xlsx")


def test_export_excludes_monitor_off_cards_by_default(monkeypatch):
    server = HealthServer()
    _register(server, 1, "On", monitor_on=True)
    _register(server, 2, "Off", monitor_on=False)
    refreshed: list[int] = []

    def _fake_refresh(card_id: int) -> HealthCard:
        refreshed.append(card_id)
        return server._cards[card_id]

    monkeypatch.setattr(server, "refresh_card", _fake_refresh)

    server.export_capacity_excel_bytes(include_monitor_off=False)

    assert refreshed == [1]


def test_export_includes_monitor_off_cards_when_requested(monkeypatch):
    server = HealthServer()
    _register(server, 1, "On", monitor_on=True)
    _register(server, 2, "Off", monitor_on=False)
    refreshed: list[int] = []

    def _fake_refresh(card_id: int) -> HealthCard:
        refreshed.append(card_id)
        return server._cards[card_id]

    monkeypatch.setattr(server, "refresh_card", _fake_refresh)

    server.export_capacity_excel_bytes(include_monitor_off=True)

    assert refreshed == [1, 2]


def test_export_keeps_going_when_refresh_card_raises(monkeypatch):
    server = HealthServer()
    _register(server, 1, "Flaky", monitor_on=True)

    def _raise(card_id: int) -> HealthCard:
        raise RuntimeError("SSH connection refused")

    monkeypatch.setattr(server, "refresh_card", _raise)

    body, filename = server.export_capacity_excel_bytes()

    assert body[:2] == b"PK"
    assert filename.startswith("Storage_Capacity_Report_")


def _call_capacity_export_api(
    monkeypatch,
    server: HealthServer,
    query: str = "",
):
    handler = object.__new__(_HealthHandler)
    handler.path = f"/api/capacity-export{query}"
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


def test_get_capacity_export_route_syncs_from_app(monkeypatch):
    server = HealthServer()
    _register(server, 1, "On", monitor_on=True)
    monkeypatch.setattr(server, "refresh_card", lambda card_id: server._cards[card_id])
    synced = {"called": False}

    def _sync_from_app():
        synced["called"] = True
        return 0

    monkeypatch.setattr(server, "sync_from_app", _sync_from_app)

    _call_capacity_export_api(monkeypatch, server, "?include_off=0&open=0")

    assert synced["called"] is True


def test_get_capacity_export_route_sends_xlsx_bytes(monkeypatch):
    server = HealthServer()
    _register(server, 1, "On", monitor_on=True)
    monkeypatch.setattr(server, "refresh_card", lambda card_id: server._cards[card_id])
    monkeypatch.setattr(server, "sync_from_app", lambda: 0)

    sent = _call_capacity_export_api(monkeypatch, server, "?include_off=0&open=0")

    assert sent["status"] == 200
    assert sent["body"][:2] == b"PK"
    assert sent["content_type"] == (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert sent["filename"].startswith("Storage_Capacity_Report_")


def test_get_capacity_export_route_opens_workbook_when_requested(monkeypatch):
    server = HealthServer()
    _register(server, 1, "On", monitor_on=True)
    monkeypatch.setattr(server, "refresh_card", lambda card_id: server._cards[card_id])
    monkeypatch.setattr(server, "sync_from_app", lambda: 0)
    opened: list[str] = []
    monkeypatch.setattr(
        "launchpad.capacity_export.open_exported_workbook",
        lambda path: opened.append(str(path)),
    )

    sent = _call_capacity_export_api(monkeypatch, server, "?open=1")

    assert sent["status"] == 200
    assert len(opened) == 1
    assert opened[0].endswith(".xlsx")


def test_health_handler_declares_capacity_export_route():
    import inspect

    source = inspect.getsource(_HealthHandler.do_GET)

    assert "/api/capacity-export" in source


def test_capacity_report_html_has_export_and_include_off():
    from launchpad.capacity_report import CAPACITY_REPORT_HTML

    assert "Export Excel" in CAPACITY_REPORT_HTML
    assert "Include monitoring-off sites" in CAPACITY_REPORT_HTML
    assert 'id="excel-btn"' in CAPACITY_REPORT_HTML
    assert 'id="include-off-toggle"' in CAPACITY_REPORT_HTML
