import io
import json

from launchpad.fc_consistgrp import FC_CONSISTGRP_HTML
from launchpad.health_server import HealthServer, _HealthHandler


def _unlock(server: HealthServer) -> None:
    server.set_settings_backend(lambda _key, default: default, lambda _key, _value: None)


def _call_fc_api(
    monkeypatch,
    server: HealthServer,
    path: str,
    payload: dict,
) -> tuple[int, dict]:
    body = json.dumps(payload).encode()
    handler = object.__new__(_HealthHandler)
    handler.path = path
    handler.headers = {"Content-Length": str(len(body))}
    handler.rfile = io.BytesIO(body)
    responses: list[tuple[int, dict]] = []
    handler._send_json = lambda data, status=200: responses.append((status, data))
    monkeypatch.setattr("launchpad.health_server.get_health_server", lambda: server)
    handler.do_POST()
    return responses[0]


def test_fc_consistgrp_html_has_connect_and_open_gui_buttons():
    assert 'id="connect-btn"' in FC_CONSISTGRP_HTML
    assert 'id="open-gui-btn"' in FC_CONSISTGRP_HTML
    assert "/api/fc-consistgrp/connect" in FC_CONSISTGRP_HTML
    assert "/api/fc-consistgrp/open-gui" in FC_CONSISTGRP_HTML


def test_fc_consistgrp_cards_include_url():
    server = HealthServer()
    server.register_card(
        card_id=1,
        name="array1",
        host="fake.example",
        port=22,
        username="admin",
        key_path="/dev/null",
        url="https://array.example",
    )

    cards = server.fc_consistgrp_cards()

    assert cards == [
        {
            "id": 1,
            "name": "array1",
            "host": "fake.example",
            "url": "https://array.example",
        }
    ]


def test_connect_api_requires_unlock(monkeypatch):
    server = HealthServer()

    status, data = _call_fc_api(
        monkeypatch, server, "/api/fc-consistgrp/connect", {"card_id": 1}
    )

    assert status == 403
    assert data["ok"] is False


def test_open_gui_api_requires_unlock(monkeypatch):
    server = HealthServer()

    status, data = _call_fc_api(
        monkeypatch, server, "/api/fc-consistgrp/open-gui", {"card_id": 1}
    )

    assert status == 403
    assert data["ok"] is False


def test_open_gui_api_400_when_no_url(monkeypatch):
    server = HealthServer()
    _unlock(server)
    server.register_card(
        card_id=1,
        name="array1",
        host="fake.example",
        port=22,
        username="admin",
        key_path="/dev/null",
    )
    server.set_card_launch_backend(
        lambda _card_id: "SSH session started",
        lambda card_id: (_ for _ in ()).throw(
            ValueError("No GUI URL on this card — set URL in Admin.")
        ),
    )

    status, data = _call_fc_api(
        monkeypatch, server, "/api/fc-consistgrp/open-gui", {"card_id": 1}
    )

    assert status == 400
    assert "url" in data["error"].lower()


def test_connect_api_success(monkeypatch):
    server = HealthServer()
    _unlock(server)
    server.register_card(
        card_id=1,
        name="array1",
        host="fake.example",
        port=22,
        username="admin",
        key_path="/dev/null",
    )
    calls: list[int] = []
    server.set_card_launch_backend(
        lambda card_id: calls.append(card_id) or "SSH session started",
        lambda _card_id: "Opened GUI",
    )

    status, data = _call_fc_api(
        monkeypatch, server, "/api/fc-consistgrp/connect", {"card_id": 1}
    )

    assert status == 200
    assert data == {"ok": True, "message": "SSH session started"}
    assert calls == [1]


def test_open_gui_api_success(monkeypatch):
    server = HealthServer()
    _unlock(server)
    server.register_card(
        card_id=1,
        name="array1",
        host="fake.example",
        port=22,
        username="admin",
        key_path="/dev/null",
        url="10.1.2.3",
    )
    calls: list[int] = []
    server.set_card_launch_backend(
        lambda _card_id: "SSH session started",
        lambda card_id: calls.append(card_id) or "Opened GUI",
    )

    status, data = _call_fc_api(
        monkeypatch, server, "/api/fc-consistgrp/open-gui", {"card_id": 1}
    )

    assert status == 200
    assert data == {"ok": True, "message": "Opened GUI"}
    assert calls == [1]
