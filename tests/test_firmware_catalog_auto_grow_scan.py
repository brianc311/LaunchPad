from launchpad.firmware_catalog import (
    grow_catalog_from_currents,
    load_firmware_auto_add,
    load_firmware_catalog,
    save_firmware_auto_add,
    save_firmware_catalog,
    versions_behind,
)
from launchpad.health_server import HealthCard, HealthServer
from launchpad.system_connectivity_page import SYSTEM_CONNECTIVITY_HTML


class _FakeDB:
    def __init__(self):
        self._s = {}

    def get_setting(self, key, default=""):
        return self._s.get(key, default)

    def set_setting(self, key, value):
        self._s[key] = value


def test_page_mentions_catalog_updated_status_handling():
    assert "catalog_updates" in SYSTEM_CONNECTIVITY_HTML or "Catalog updated:" in SYSTEM_CONNECTIVITY_HTML


def test_grow_then_behind_uses_new_entry():
    catalog = {"flashsystem_7300": ["8.5.0"]}
    updated, n = grow_catalog_from_currents(
        catalog, [("flashsystem_7300", "8.6.0")]
    )
    assert n == 1
    assert versions_behind("8.5.0", updated["flashsystem_7300"]) == "1"


def test_scan_live_grows_catalog_when_auto_add_on(monkeypatch):
    db = _FakeDB()
    save_firmware_catalog(db, {"flashsystem_7300": ["8.5.0"]})
    save_firmware_auto_add(db, True)

    server = HealthServer()
    server.set_settings_backend(db.get_setting, db.set_setting)
    card = HealthCard(
        card_id=1,
        name="Hartford",
        host="10.0.0.1",
        port=22,
        username="u",
        key_path="/tmp/key",
        device_profile="flashsystem_7300",
    )
    server._cards[1] = card
    server.set_monitor_enabled(card_id=1, enabled=True)
    monkeypatch.setattr(server, "sync_from_app", lambda: 0)

    def _runner(_card):
        def run(command):
            if "lscloudcallhome" in command:
                return "id:status\n0:enabled\n"
            if "lsdnsserver" in command:
                return "id:name:IP_address\n0:dns1:10.1.1.1\n"
            if "lssnmpserver" in command:
                return "id:IP:port\n0:10.2.2.2:162\n"
            if "lssystem" in command:
                return (
                    "name:c1\n"
                    "cluster_ntp_IP_address:10.3.3.3\n"
                    "code_level:8.6.0.0 (build 152.24.2403051134)\n"
                )
            return ""

        return run

    monkeypatch.setattr(server, "_lun_run_command", _runner)
    result = server.scan_system_connectivity_live()

    assert result.get("catalog_updates") == 1
    fw = result["firmware"][0]
    assert fw["current"] == "8.6.0.0"
    assert fw["versions_behind"] == "0"
    assert fw["latest"] == "8.6.0.0"
    saved = load_firmware_catalog(db)
    assert saved["flashsystem_7300"] == ["8.5.0", "8.6.0.0"]


def test_scan_live_skips_grow_when_auto_add_off(monkeypatch):
    db = _FakeDB()
    save_firmware_catalog(db, {"flashsystem_7300": ["8.5.0"]})
    assert load_firmware_auto_add(db) is False

    server = HealthServer()
    server.set_settings_backend(db.get_setting, db.set_setting)
    card = HealthCard(
        card_id=1,
        name="Hartford",
        host="10.0.0.1",
        port=22,
        username="u",
        key_path="/tmp/key",
        device_profile="flashsystem_7300",
    )
    server._cards[1] = card
    server.set_monitor_enabled(card_id=1, enabled=True)
    monkeypatch.setattr(server, "sync_from_app", lambda: 0)

    def _runner(_card):
        def run(command):
            if "lssystem" in command:
                return (
                    "name:c1\n"
                    "cluster_ntp_IP_address:10.3.3.3\n"
                    "code_level:8.6.0.0 (build 1)\n"
                )
            if "lscloudcallhome" in command:
                return "id:status\n0:enabled\n"
            if "lsdnsserver" in command:
                return "id:name:IP_address\n0:dns1:10.1.1.1\n"
            if "lssnmpserver" in command:
                return "id:IP:port\n0:10.2.2.2:162\n"
            return ""

        return run

    monkeypatch.setattr(server, "_lun_run_command", _runner)
    result = server.scan_system_connectivity_live()

    assert "catalog_updates" not in result or result.get("catalog_updates") in (0, None)
    assert result["firmware"][0]["versions_behind"] == "unknown"
    assert load_firmware_catalog(db) == {"flashsystem_7300": ["8.5.0"]}
