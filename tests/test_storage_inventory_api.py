from io import BytesIO

from openpyxl import load_workbook

from launchpad.health_server import HealthCard, HealthServer
from launchpad.storage_inventory_page import STORAGE_INVENTORY_PATH


def _unlock(server: HealthServer) -> None:
    server.set_settings_backend(lambda _key, default: default, lambda _key, _value: None)


def test_storage_inventory_page_route_constant():
    assert STORAGE_INVENTORY_PATH == "/storage-inventory"


def test_scan_storage_inventory_requires_unlock(monkeypatch):
    server = HealthServer()
    monkeypatch.setattr(server, "is_unlocked", lambda: False)
    try:
        server.scan_storage_inventory_live()
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "unlock" in str(exc).lower()


def test_scan_storage_inventory_svc_happy_path(monkeypatch):
    server = HealthServer()
    _unlock(server)
    card = HealthCard(
        card_id=1,
        name="Hartford",
        host="10.0.0.1",
        port=22,
        username="u",
        key_path="/tmp/key",
        device_profile="flashsystem_7200",
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
            if "lsemailserver" in command:
                return "id:name:IP_address:port\n0:smtp1:172.29.62.98:25\n"
            if "lsrcrelationship" in command:
                return "id:name:master_cluster_id\n0:rel1:1\n"
            if "lssystem" in command:
                return (
                    "id:78E37V9\nname:v7kcon-g3v1\n"
                    "product_name:IBM FlashSystem 7200\n"
                    "cluster_ntp_IP_address:10.3.3.3\n"
                )
            return ""

        return run

    monkeypatch.setattr(server, "_lun_run_command", _runner)
    result = server.scan_storage_inventory_live()
    assert result["errors"] == []
    assert len(result["rows"]) == 1
    row = result["rows"][0]
    assert row["ip"] == "10.0.0.1"
    assert "7200" in row["model"]
    assert row["serial"] == "78E37V9"
    assert "172.29.62.98" in row["smtp"]
    assert row["data_protection"].lower().startswith("yes")
    cached = server.get_storage_inventory_cache()
    assert cached is not None
    assert len(cached["rows"]) == 1


def test_export_storage_inventory_uses_cache_without_unlock(monkeypatch):
    server = HealthServer()
    monkeypatch.setattr(server, "is_unlocked", lambda: False)
    server.set_storage_inventory_cache(
        {
            "generated_at": "2026-08-10T12:00:00",
            "rows": [
                {
                    "site": "Hartford",
                    "host": "Hartford",
                    "ip": "10.0.0.1",
                    "model": "IBM FlashSystem 7200",
                    "serial": "ABC",
                    "location": "Hartford",
                    "phone_home": "Yes — IBM",
                    "data_protection": "Yes",
                    "smtp": "172.29.62.98",
                    "issues": "",
                },
                {
                    "site": "Bad",
                    "host": "Bad",
                    "ip": "10.0.0.2",
                    "model": "IBM FlashSystem 7200",
                    "serial": "DEF",
                    "location": "Bad",
                    "phone_home": "No — Not configured",
                    "data_protection": "No — Not configured",
                    "smtp": "No IP — Not configured",
                    "issues": "Phone Home not configured",
                },
            ],
            "errors": [],
            "total_devices": 2,
            "devices_with_issues": 1,
        }
    )
    body, filename, content_type = server.export_storage_inventory_bytes()
    assert filename.endswith(".xlsx")
    assert "sheet" in content_type or "spreadsheet" in content_type or "octet" in content_type
    wb = load_workbook(BytesIO(body))
    assert wb.sheetnames == ["Inventory", "Issues Summary"]
