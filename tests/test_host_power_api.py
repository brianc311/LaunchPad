import io
import json

import launchpad.health_server as health_server_module
from launchpad.health_server import HealthCard, HealthServer, _HealthHandler


def _card(
    card_id: int,
    *,
    name: str = "Hadoop node",
    host: str = "10.0.0.1",
    profile: str = "hadoop_linux",
    custom_commands: str = "",
) -> HealthCard:
    return HealthCard(
        card_id=card_id,
        name=name,
        host=host,
        port=22,
        username="hadoop",
        password="secret",
        key_path="",
        device_profile=profile,
        custom_commands=custom_commands,
    )


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


def test_host_power_cards_filters_profile_and_missing_host():
    server = HealthServer()
    server._cards[1] = _card(1, name="Hadoop A")
    server._cards[2] = _card(2, name="Array A", profile="flashsystem_5200")
    server._cards[3] = _card(3, name="Hadoop B", host="")

    assert server.host_power_cards() == [
        {
            "id": 1,
            "name": "Hadoop A",
            "host": "10.0.0.1",
            "device_profile": "hadoop_linux",
        }
    ]


def test_host_power_run_requires_confirm(monkeypatch):
    server = HealthServer()
    server._cards[1] = _card(1)

    response = _post(
        "/api/host-power/run",
        {"card_ids": [1], "confirm": False},
        monkeypatch,
        server,
    )

    assert response["status"] == 400
    assert response["payload"]["error"] == "Host Power requires explicit confirm=True"


def test_host_power_run_skips_shutdown_after_stop_failure(monkeypatch):
    server = HealthServer()
    server._cards[1] = _card(
        1,
        custom_commands=(
            "Power - Stop Hadoop|sudo systemctl stop hadoop\n"
            "Power - OS Shutdown|sudo shutdown -h now"
        ),
    )
    commands: list[str] = []

    def run_command(command: str) -> str:
        commands.append(command)
        return "ERROR: unable to stop"

    monkeypatch.setattr(
        HealthServer,
        "_snap_run_command",
        staticmethod(lambda _card: run_command),
    )

    result = server.host_power_run([1], confirm=True)

    assert result["ok"] is False
    assert commands == ["sudo systemctl stop hadoop"]
    assert result["hosts"][0]["aborted"] is True


def test_host_power_run_continues_after_other_host_fails(monkeypatch):
    server = HealthServer()
    server._cards[1] = _card(1, name="Failed host")
    server._cards[2] = _card(2, name="Healthy host", host="10.0.0.2")
    seen: list[tuple[str, str]] = []

    def runner_for(card: HealthCard):
        def run_command(command: str) -> str:
            seen.append((card.name, command))
            return "ERROR: refused" if card.card_id == 1 else "ok"

        return run_command

    monkeypatch.setattr(
        HealthServer,
        "_snap_run_command",
        staticmethod(runner_for),
    )

    result = server.host_power_run([1, 2], confirm=True)

    assert result["ok"] is False
    assert [host["card_id"] for host in result["hosts"]] == [1, 2]
    assert any(name == "Healthy host" for name, _command in seen)


def test_host_power_run_empty_selection_not_ok():
    server = HealthServer()
    result = server.host_power_run([], confirm=True)
    assert result["ok"] is False
    assert result["hosts"] == []
    assert "No hosts selected" in result["warnings"]


def test_host_power_run_unmatched_ids_not_ok():
    server = HealthServer()
    server._cards[1] = _card(1, profile="flashsystem_5200")
    result = server.host_power_run([1], confirm=True)
    assert result["ok"] is False
    assert result["hosts"] == []
    assert "No eligible Hadoop hosts matched the selection" in result["warnings"]


def test_host_power_run_coerces_string_ids(monkeypatch):
    server = HealthServer()
    server._cards[1] = _card(1)
    commands: list[str] = []

    def run_command(command: str) -> str:
        commands.append(command)
        return "ok"

    monkeypatch.setattr(
        HealthServer,
        "_snap_run_command",
        staticmethod(lambda _card: run_command),
    )

    result = server.host_power_run(["1"], confirm=True)

    assert result["ok"] is True
    assert len(result["hosts"]) == 1


def test_host_power_run_rejects_invalid_ids():
    server = HealthServer()
    result = server.host_power_run(["not-an-id"], confirm=True)
    assert result["ok"] is False
    assert any("Ignored invalid card_id" in w for w in result["warnings"])


def test_host_power_preview_empty_selection_not_ok():
    server = HealthServer()
    result = server.host_power_preview([])
    assert result["ok"] is False
    assert result["hosts"] == []
    assert "No hosts selected" in result["warnings"]


def test_host_power_preview_coerces_string_ids():
    server = HealthServer()
    server._cards[1] = _card(1)
    result = server.host_power_preview(["1"])
    assert result["ok"] is True
    assert len(result["hosts"]) == 1


def test_host_power_api_empty_selection_not_ok(monkeypatch):
    server = HealthServer()

    preview = _post(
        "/api/host-power/preview",
        {"card_ids": []},
        monkeypatch,
        server,
    )
    assert preview["status"] == 200
    assert preview["payload"]["ok"] is False
    assert "No hosts selected" in preview["payload"]["warnings"]

    run = _post(
        "/api/host-power/run",
        {"card_ids": [], "confirm": True},
        monkeypatch,
        server,
    )
    assert run["status"] == 200
    assert run["payload"]["ok"] is False
    assert "No hosts selected" in run["payload"]["warnings"]
