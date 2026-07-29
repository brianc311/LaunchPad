from launchpad.health_server import HealthServer
from launchpad.firmware_catalog import save_firmware_catalog


class _FakeDB:
    def __init__(self):
        self._s = {}

    def get_setting(self, key, default=""):
        return self._s.get(key, default)

    def set_setting(self, key, value):
        self._s[key] = value


def test_scan_payload_includes_firmware_key(monkeypatch):
    server = HealthServer()
    db = _FakeDB()
    save_firmware_catalog(db, {"flashsystem_7300": ["8.5.0", "8.6.0"]})

    # Minimal: set_system_connectivity_cache round-trip includes firmware
    server.set_system_connectivity_cache(
        {
            "call_home": [],
            "dns": [],
            "snmp": [],
            "ntp": [],
            "firmware": [{"card_name": "A", "current": "8.5.0", "versions_behind": "1"}],
            "errors": [],
        }
    )
    cached = server.get_system_connectivity_cache()
    assert "firmware" in cached
    assert cached["firmware"][0]["versions_behind"] == "1"
