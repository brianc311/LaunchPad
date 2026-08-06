import io
from types import SimpleNamespace

import launchpad.health_server as health_server_module
import launchpad.monitor as monitor_module
from launchpad.health_server import HealthCard, HealthServer, _HealthHandler
from launchpad.monitor import HealthDashboardEntry
from launchpad.ssh_utils import SshMetricsAuth


def _card(**kwargs):
    defaults = dict(
        card_id=1,
        name="site-a",
        host="10.0.0.1",
        port=22,
        username="user",
        password="x",
        key_path="",
        key_passphrase="",
        device_profile="flashsystem_5200",
        custom_commands="",
        serial_number="serial-1",
        category="",
    )
    defaults.update(kwargs)
    return HealthCard(**defaults)


def test_refresh_site_lookup_success(monkeypatch):
    server = HealthServer()
    server._cards[1] = _card()

    def fake_refresh(self, card_id, **kwargs):
        card = self._cards[card_id]
        card.command_results = [
            {
                "label": "FC - Hosts",
                "command": "svcinfo lshost -delim :",
                "output": "id:name:status:port_count\n1:h1:online:2\n",
                "error": None,
            },
            {
                "label": "Memory - Volumes %",
                "command": "svcinfo lsvdisk -delim :",
                "output": (
                    "id:name:capacity:mdisk_grp_name:vdisk_UID:status\n"
                    "1:v1:10GB:P0:U1:online\n"
                ),
                "error": None,
            },
            {
                "label": "FC - Host LUN Maps",
                "command": "svcinfo lshostvdiskmap -delim :",
                "output": "id:name:SCSI_id:host_id:host_name:vdisk_UID\n0:v1:0:1:h1:U1\n",
                "error": None,
            },
            {
                "label": "Capacity - Pools %",
                "command": "svcinfo lsmdiskgrp -delim :",
                "output": "id:name:capacity:free_capacity:used_capacity\n0:P0:100:50:50\n",
                "error": None,
            },
        ]
        card.error = None
        return card

    monkeypatch.setattr(HealthServer, "refresh_card", fake_refresh)

    def fake_run(card):
        def _run(command: str) -> str:
            if "lsconsistgrp" in command:
                return "id:name:status\n1:cg_live:empty\n"
            raise AssertionError(f"unexpected command {command}")

        return _run

    monkeypatch.setattr(HealthServer, "_lun_run_command", staticmethod(fake_run))
    monkeypatch.setattr(server, "get_contingency_groups", lambda: [])

    payload = server.refresh_site_lookup(1)

    assert payload["error"] is None
    assert payload["stats"]["hosts"] >= 1
    assert payload["stats"]["pools"] >= 1
    assert payload["consistency_groups"][0]["name"] == "cg_live"
    assert payload["source"] == "ssh"
    assert payload["card"]["serial"] == "serial-1"


def test_refresh_site_lookup_missing_card():
    server = HealthServer()

    try:
        server.refresh_site_lookup(999)
        assert False, "expected KeyError"
    except KeyError:
        pass


def test_site_lookup_cache_includes_contingency_group_fallback(monkeypatch):
    server = HealthServer()
    server._cards[1] = _card(name="site-a")
    monkeypatch.setattr(
        server,
        "get_contingency_groups",
        lambda: [
            {
                "id": "cg-1",
                "name": "site-a",
                "location": "DC1",
                "storage_hint": "site-a",
                "hosts": [],
                "volumes": [{"name": "vol-a"}],
                "maps": [],
            }
        ],
    )

    payload = server.site_lookup_cache(1)

    assert payload["source"] == "cache"
    assert payload["consistency_groups"][0]["id"] == "cg-1"
    assert payload["volumes"][0]["name"] == "vol-a"


def test_site_lookup_cache_get_maps_errors(monkeypatch):
    class FakeServer:
        def site_lookup_cache(self, card_id):
            if card_id == 404:
                raise KeyError(card_id)
            return {"card": {"id": card_id}, "source": "cache"}

    monkeypatch.setattr(health_server_module, "get_health_server", lambda: FakeServer())

    def get(path):
        handler = _HealthHandler.__new__(_HealthHandler)
        handler.path = path
        sent = {}
        handler._send_json = lambda payload, status=200: sent.update(
            payload=payload, status=status
        )
        handler.do_GET()
        return sent

    assert get("/api/site-lookup/cache")["status"] == 400
    assert get("/api/site-lookup/cache?card_id=nope")["status"] == 400
    assert get("/api/site-lookup/cache?card_id=404")["status"] == 404
    assert get("/api/site-lookup/cache?card_id=1") == {
        "payload": {"card": {"id": 1}, "source": "cache"},
        "status": 200,
    }


def test_site_lookup_refresh_post_maps_errors(monkeypatch):
    class FakeServer:
        def refresh_site_lookup(self, card_id):
            if card_id == 404:
                raise KeyError(card_id)
            if card_id == 502:
                raise RuntimeError("SSH unavailable")
            return {"card": {"id": card_id}, "error": None}

    monkeypatch.setattr(health_server_module, "get_health_server", lambda: FakeServer())

    def post(card_id):
        body = f'{{"card_id": "{card_id}"}}'.encode()
        handler = _HealthHandler.__new__(_HealthHandler)
        handler.path = "/api/site-lookup/refresh"
        handler.headers = {"Content-Length": str(len(body))}
        handler.rfile = io.BytesIO(body)
        sent = {}
        handler._send_json = lambda payload, status=200: sent.update(
            payload=payload, status=status
        )
        handler.do_POST()
        return sent

    assert post(1) == {"payload": {"card": {"id": 1}, "error": None}, "status": 200}
    assert post(404)["status"] == 404
    assert post(502) == {"payload": {"error": "SSH unavailable"}, "status": 502}


def test_site_lookup_open_helpers_register_cards(monkeypatch):
    server = SimpleNamespace(
        ensure_running=lambda: None,
        register_card=lambda *args: registered.append(args),
        open_site_lookup=lambda: "http://127.0.0.1:18765/site-lookup",
    )
    registered = []
    entry = HealthDashboardEntry(
        card_id=1,
        name="site-a",
        host="10.0.0.1",
        port=22,
        username="user",
        auth=SshMetricsAuth(key_path="", key_passphrase="", password="x"),
    )
    monkeypatch.setattr(monitor_module, "get_health_server", lambda: server)

    assert (
        monitor_module.open_site_lookup_for_cards([entry])
        == "http://127.0.0.1:18765/site-lookup"
    )
    assert registered[0][0] == 1


def test_open_site_lookup_opens_browser(monkeypatch):
    server = HealthServer()
    opened = []
    monkeypatch.setattr(server, "ensure_running", lambda: None)
    monkeypatch.setattr(health_server_module.webbrowser, "open", opened.append)

    url = server.open_site_lookup()

    assert url == "http://127.0.0.1:18765/site-lookup"
    assert opened == [url]


def test_site_lookup_get_serves_stub(monkeypatch):
    monkeypatch.setattr(
        health_server_module, "get_health_server", lambda: SimpleNamespace()
    )
    handler = _HealthHandler.__new__(_HealthHandler)
    handler.path = "/site-lookup"
    sent = []
    handler._send_html = sent.append

    handler.do_GET()

    assert "Site Lookup" in sent[0]
