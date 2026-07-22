import io
import json

import pytest

from launchpad import monitor
from launchpad.health_server import HealthServer, _HealthHandler


def _call_site_lookup_api(
    monkeypatch,
    server: HealthServer,
    payload: dict | None = None,
) -> tuple[int, dict]:
    body = json.dumps(payload or {}).encode()
    handler = object.__new__(_HealthHandler)
    handler.path = "/api/site-lookup/refresh"
    handler.headers = {"Content-Length": str(len(body))}
    handler.rfile = io.BytesIO(body)
    responses: list[tuple[int, dict]] = []
    handler._send_json = lambda data, status=200: responses.append((status, data))
    monkeypatch.setattr(
        "launchpad.health_server.get_health_server",
        lambda: server,
    )

    handler.do_POST()

    return responses[0]


def _registered_svc_server() -> HealthServer:
    server = HealthServer()
    server.register_card(
        1,
        "Storage A",
        "array.example",
        22,
        "operator",
        "",
        device_profile="flashsystem_5200",
        serial_number="SN123",
    )
    return server


def test_refresh_site_lookup_returns_live_inventory_payload(monkeypatch):
    server = _registered_svc_server()
    outputs = {
        "svcinfo lshost -delim :": "id:name:status:port_count\n0:host1:online:2\n",
        "svcinfo lshostvdiskmap -delim :": (
            "host_name:vdisk_name:SCSI_id\nhost1:vol1:3\n"
        ),
        "svcinfo lsvdisk -delim :": (
            "id:name:status:mdisk_grp_name:capacity:vdisk_UID\n"
            "0:vol1:online:Pool0:10.00 GiB:UID1\n"
        ),
        "svcinfo lsconsistgrp -delim :": "id:name:status:type\n0:cg_app:empty:master\n",
    }
    monkeypatch.setattr(
        server,
        "_lun_run_command",
        lambda _card: lambda command: outputs[command],
    )

    result = server.refresh_site_lookup(1)

    assert result["stats"] == {
        "hosts": 1,
        "volumes": 1,
        "mappings": 1,
        "cgs": 1,
    }
    assert result["source"] == "ssh"
    assert result["card"]["serial"] == "SN123"
    assert result["error"] is None


def test_site_lookup_refresh_api_rejects_unknown_card(monkeypatch):
    status, payload = _call_site_lookup_api(monkeypatch, HealthServer(), {"card_id": 99})

    assert status == 404
    assert payload == {"error": "Unknown card id 99"}


def test_site_lookup_refresh_api_reports_ssh_failure(monkeypatch):
    server = _registered_svc_server()
    monkeypatch.setattr(
        server,
        "_lun_run_command",
        lambda _card: lambda _command: (_ for _ in ()).throw(RuntimeError("SSH failed")),
    )

    status, payload = _call_site_lookup_api(monkeypatch, server, {"card_id": 1})

    assert status == 502
    assert payload == {"ok": False, "error": "SSH failed"}


def test_site_lookup_refresh_api_requires_card_id(monkeypatch):
    status, payload = _call_site_lookup_api(monkeypatch, HealthServer(), {})

    assert status == 400
    assert payload == {"error": "card_id required"}


def test_site_lookup_refresh_rejects_non_svc_card():
    server = HealthServer()
    server.register_card(
        1,
        "Primera",
        "array.example",
        22,
        "operator",
        "",
        device_profile="hpe_primera_600",
    )

    with pytest.raises(ValueError, match="FlashSystem / SVC"):
        server.refresh_site_lookup(1)


def test_health_card_api_includes_serial_number():
    server = _registered_svc_server()

    assert server.list_cards(allow_sync=False)[0]["serial_number"] == "SN123"


def test_open_site_lookup_for_cards_registers_cards_and_opens(monkeypatch):
    server = HealthServer()
    entries = [
        monitor.HealthDashboardEntry(
            card_id=1,
            name="Storage A",
            host="array.example",
            port=22,
            username="operator",
            auth=monitor.SshMetricsAuth(
                password="secret",
                key_path="",
                key_passphrase="",
            ),
            device_profile="flashsystem_5200",
        )
    ]
    monkeypatch.setattr(monitor, "get_health_server", lambda: server)
    opened: list[str] = []
    monkeypatch.setattr("launchpad.health_server.webbrowser.open", opened.append)

    url = monitor.open_site_lookup_for_cards(entries)

    assert url.endswith("/site-lookup")
    assert opened == [url]
    assert server.list_cards(allow_sync=False)[0]["name"] == "Storage A"
