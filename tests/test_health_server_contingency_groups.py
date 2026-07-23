import json

import pytest

from launchpad.contingency_groups_data import CONTINGENCY_GROUPS_SETTING
from launchpad.health_server import HealthServer


def _settings_backend(initial: dict[str, str] | None = None):
    settings = dict(initial or {})

    def get_setting(key: str, default: str) -> str:
        return settings.get(key, default)

    def set_setting(key: str, value: str) -> None:
        settings[key] = value

    return settings, get_setting, set_setting


def test_get_contingency_groups_seeds_and_persists_when_empty():
    settings, getter, setter = _settings_backend()
    server = HealthServer()
    server.set_settings_backend(getter, setter)

    groups = server.get_contingency_groups()

    assert {group["id"] for group in groups} == {
        "hartford-ct",
        "houston-tx",
        "windsor",
    }
    assert json.loads(settings[CONTINGENCY_GROUPS_SETTING]) == groups


def test_contingency_groups_upsert_and_delete_persist():
    settings, getter, setter = _settings_backend()
    server = HealthServer()
    server.set_settings_backend(getter, setter)

    groups = server.upsert_contingency_group(
        {
            "id": "lab-1",
            "name": "Lab",
            "hosts": [],
            "volumes": [],
            "maps": [],
        }
    )
    groups = server.delete_contingency_group("lab-1")

    assert all(group["id"] != "lab-1" for group in groups)
    assert json.loads(settings[CONTINGENCY_GROUPS_SETTING]) == groups


def test_contingency_groups_require_settings_backend_for_writes():
    server = HealthServer()

    assert server.contingency_groups_persist_available() is False
    assert server.get_contingency_groups() == []
    with pytest.raises(
        RuntimeError,
        match="LaunchPad must be unlocked to save contingency groups.",
    ):
        server.set_contingency_groups([])


def test_ensure_contingency_groups_from_monitored_svc_cards():
    settings, getter, setter = _settings_backend()
    server = HealthServer()
    server.set_settings_backend(getter, setter)
    # seed three defaults via get
    server.get_contingency_groups()
    server.register_card(1, "Moreno Valley, CA", "10.0.0.1", 22, "u", "", device_profile="flashsystem_7200")
    server.register_card(2, "Other SSH", "10.0.0.2", 22, "u", "", device_profile="generic_ssh")
    server.set_monitor_enabled(card_id=1, enabled=True)
    server.set_monitor_enabled(card_id=2, enabled=True)
    groups = server.ensure_contingency_groups_from_cards()
    names = {g["name"] for g in groups}
    assert "Moreno Valley, CA" in names
    assert "Other SSH" not in names  # not SVC


def test_sync_contingency_inventory_updates_group_not_lun_build(monkeypatch):
    settings, getter, setter = _settings_backend()
    server = HealthServer()
    server.set_settings_backend(getter, setter)
    server.set_contingency_groups([{
        "id": "lab-1",
        "name": "Lab Site",
        "location": "Lab Site",
        "storage_hint": "Storage A",
        "notes": "keep-notes",
        "hosts": [],
        "volumes": [{"name": "stale", "role": "source"}],
        "maps": [],
    }])
    server.set_lun_builds([{
        "id": "b1",
        "name": "Build",
        "hosts": [{"lpar_name": "untouched"}],
        "luns": [],
    }])
    server.register_card(1, "Storage A", "array.example", 22, "operator", "", device_profile="flashsystem_5200")
    outputs = {
        "svcinfo lshost -delim :": "id:name:status:port_count\n0:host1:online:2\n",
        "svcinfo lshostvdiskmap -delim :": "host_name:vdisk_name:SCSI_id\nhost1:vol1:3\n",
        "svcinfo lsvdisk -delim :": (
            "id:name:status:mdisk_grp_name:capacity:vdisk_UID\n"
            "0:vol1:online:Pool0:10.00 GiB:UID1\n"
        ),
        "svcinfo lsfabric -delim :": "name:local_wwpn:remote_wwpn\nhost1:AA:BB\n",
    }
    monkeypatch.setattr(server, "_lun_run_command", lambda _card: lambda command: outputs[command])
    result = server.sync_contingency_inventory("lab-1")
    assert result["group"]["id"] == "lab-1"
    assert result["group"]["name"] == "Lab Site"
    assert result["group"]["notes"] == "keep-notes"
    assert result["group"]["storage_hint"] == "Storage A"
    assert "vol1" in {v["name"] for v in result["group"]["volumes"]}
    assert "stale" not in {v["name"] for v in result["group"]["volumes"]}
    builds = server.get_lun_builds()
    assert builds[0]["hosts"][0]["lpar_name"] == "untouched"


def test_sync_contingency_inventory_ssh_failure_leaves_group_unchanged(monkeypatch):
    settings, getter, setter = _settings_backend()
    server = HealthServer()
    server.set_settings_backend(getter, setter)
    server.set_contingency_groups([{
        "id": "lab-1",
        "name": "Lab Site",
        "location": "Lab Site",
        "storage_hint": "Storage A",
        "notes": "keep-notes",
        "hosts": [],
        "volumes": [{"name": "stale", "role": "source"}],
        "maps": [],
    }])
    server.register_card(1, "Storage A", "array.example", 22, "operator", "", device_profile="flashsystem_5200")

    def fail_on_maps(command):
        if "lshostvdiskmap" in command:
            raise RuntimeError("SSH failed")
        return "id:name\n0:host1\n"

    monkeypatch.setattr(server, "_lun_run_command", lambda _card: fail_on_maps)

    with pytest.raises(RuntimeError, match="SSH failed"):
        server.sync_contingency_inventory("lab-1")

    groups = server.get_contingency_groups()
    group = next(g for g in groups if g["id"] == "lab-1")
    assert {v["name"] for v in group["volumes"]} == {"stale"}
