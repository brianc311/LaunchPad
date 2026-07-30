import inspect
import json

from launchpad.health_server import HealthCard, HealthServer, _HealthHandler


def _unlock(server: HealthServer) -> None:
    store: dict[str, str] = {}

    def get_setting(key: str, default: str = "") -> str:
        return store.get(key, default)

    def set_setting(key: str, value: str) -> None:
        store[key] = value

    server.set_settings_backend(get_setting, set_setting)


def _card(**kwargs) -> HealthCard:
    base = dict(
        card_id=1,
        name="Pendergrass, GA",
        host="10.0.0.9",
        port=22,
        username="user",
        key_path="/tmp/key",
        device_profile="flashsystem_5200",
    )
    base.update(kwargs)
    return HealthCard(**base)


def test_upsert_persists_and_replaces(monkeypatch):
    server = HealthServer()
    _unlock(server)
    server._cards[1] = _card()
    server.set_monitor_enabled(card_id=1, enabled=True)
    card = server._cards[1]
    card.command_results = [
        {
            "label": "FC - Hosts",
            "command": "svcinfo lshost -delim :",
            "output": "id:name:WWPN\n0:esx01:AA",
        }
    ]
    card.error = None
    server.upsert_lun_offline_inventory_from_card(card)
    store = server.get_lun_offline_inventory()
    assert "1" in store
    assert store["1"]["site_name"] == "Pendergrass, GA"


def test_failed_refresh_preserves_hosts():
    server = HealthServer()
    _unlock(server)
    server._cards[1] = _card()
    server.set_monitor_enabled(card_id=1, enabled=True)
    card = server._cards[1]
    card.command_results = [
        {"label": "FC - Hosts", "command": "svcinfo lshost -delim :", "output": "id:name:WWPN\n0:keep:AA"}
    ]
    card.error = None
    server.upsert_lun_offline_inventory_from_card(card)
    card.command_results = None
    card.error = "SSH failed"
    server.upsert_lun_offline_inventory_from_card(card)
    row = server.get_lun_offline_inventory()["1"]
    assert any(h.get("lpar_name") == "keep" for h in row["hosts"])
    assert "ssh" in (row.get("last_error") or "").lower()


def test_skips_monitor_off():
    server = HealthServer()
    _unlock(server)
    server._cards[1] = _card()
    server.set_monitor_enabled(card_id=1, enabled=False)
    card = server._cards[1]
    card.command_results = [{"label": "FC - Hosts", "command": "svcinfo lshost", "output": "x"}]
    server.upsert_lun_offline_inventory_from_card(card)
    assert server.get_lun_offline_inventory() == {}


def test_api_route_declared():
    assert "/api/lun-offline-inventory" in inspect.getsource(_HealthHandler.do_GET)


def test_refresh_card_calls_upsert(monkeypatch):
    server = HealthServer()
    _unlock(server)
    called = {}

    def fake_upsert(card, **kwargs):
        called["id"] = card.card_id

    monkeypatch.setattr(server, "upsert_lun_offline_inventory_from_card", fake_upsert)
    monkeypatch.setattr(
        "launchpad.health_server.run_remote_command_suite",
        lambda *a, **k: [{"label": "FC - Hosts", "command": "svcinfo lshost", "output": "id:name\n0:h1"}],
    )
    monkeypatch.setattr(
        "launchpad.health_server.resolve_card_commands",
        lambda *a, **k: [("FC - Hosts", "svcinfo lshost -delim :")],
    )
    server._cards[1] = _card()
    server.set_monitor_enabled(card_id=1, enabled=True)
    server.refresh_card(1)
    assert called.get("id") == 1
