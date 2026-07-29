from launchpad.health_server import HealthServer


class _FakeDB:
    def __init__(self):
        self._s = {}

    def get_setting(self, key, default=""):
        return self._s.get(key, default)

    def set_setting(self, key, value):
        self._s[key] = value


def test_scan_payload_includes_license_key_key(monkeypatch):
    server = HealthServer()

    # Minimal: set_system_connectivity_cache round-trip includes license_key
    server.set_system_connectivity_cache(
        {
            "call_home": [],
            "dns": [],
            "snmp": [],
            "ntp": [],
            "firmware": [],
            "license_key": [
                {
                    "card_name": "A",
                    "feature": "3PAR OS Suite",
                    "key_generation_date": "Tue Sep 19 10:37:04 2017",
                }
            ],
            "errors": [],
        }
    )
    cached = server.get_system_connectivity_cache()
    assert "license_key" in cached
    assert isinstance(cached["license_key"], list)
    assert cached["license_key"][0]["feature"] == "3PAR OS Suite"
