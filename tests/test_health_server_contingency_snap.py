import json

import pytest

from launchpad.contingency_groups_data import CONTINGENCY_GROUPS_SETTING, seed_contingency_groups
from launchpad.health_server import HealthServer


def _settings_backend(initial: dict[str, str] | None = None):
    settings = dict(initial or {})

    def get_setting(key: str, default: str) -> str:
        return settings.get(key, default)

    def set_setting(key: str, value: str) -> None:
        settings[key] = value

    return get_setting, set_setting


def _group() -> dict:
    return {
        "id": "lab-1",
        "name": "Lab",
        "storage_hint": "missing-array",
        "hosts": [],
        "volumes": [{"name": "source", "role": "source", "pool": "pool", "capacity": "1 GB"}],
        "maps": [],
    }


def test_generate_contingency_snaps_succeeds_without_storage_card():
    getter, setter = _settings_backend(
        {CONTINGENCY_GROUPS_SETTING: json.dumps(seed_contingency_groups())}
    )
    server = HealthServer()
    server.set_settings_backend(getter, setter)

    result = server.generate_contingency_snaps("hartford-ct")

    assert result["ok"] is True
    assert result["group"]["id"] == "hartford-ct"
    assert result["group"]["storage_hint"] == ""


def test_preview_contingency_snaps_blocks_when_storage_card_missing():
    getter, setter = _settings_backend(
        {CONTINGENCY_GROUPS_SETTING: json.dumps([_group()])}
    )
    server = HealthServer()
    server.set_settings_backend(getter, setter)

    result = server.preview_contingency_snaps("lab-1")

    assert result["ok"] is False
    assert any("missing-array" in warning for warning in result["warnings"])


def _group_with_incomplete_snap_rows() -> dict:
    return {
        "id": "lab-1",
        "name": "Lab",
        "storage_hint": "array1",
        "hosts": [],
        "volumes": [
            {"name": "V1", "role": "source", "pool": "P0", "capacity": "4.00 TiB"},
            {
                "name": "V1_snap",
                "role": "snap",
                "source_volume": "V1",
                "pool": "",
                "capacity": "",
            },
        ],
        "maps": [
            {"volume": "V1_snap", "host": "h1", "scsi_id": "0", "role": "snap"},
        ],
    }


def _server_with_group_and_card(group: dict) -> HealthServer:
    getter, setter = _settings_backend(
        {CONTINGENCY_GROUPS_SETTING: json.dumps([group])}
    )
    server = HealthServer()
    server.set_settings_backend(getter, setter)
    server.register_card(
        card_id=1,
        name=str(group["storage_hint"]),
        host="fake.example",
        port=22,
        username="admin",
        key_path="/dev/null",
    )
    return server


def test_create_contingency_snaps_rejects_confirm_false():
    server = _server_with_group_and_card(_group())

    result = server.create_contingency_snaps("lab-1", confirm=False)

    assert result["ok"] is False
    assert any("confirm" in warning.lower() for warning in result["warnings"])


def test_create_contingency_snaps_requires_confirm_argument():
    server = HealthServer()

    with pytest.raises(TypeError):
        server.create_contingency_snaps("lab-1")


def test_preview_contingency_snaps_returns_resolved_card(monkeypatch):
    group = {
        "id": "lab-1",
        "name": "Lab",
        "storage_hint": "array1",
        "hosts": [],
        "volumes": [
            {"name": "V1", "role": "source", "pool": "P0", "capacity": "4.00 TiB"},
            {
                "name": "V1_snap",
                "role": "snap",
                "source_volume": "V1",
                "pool": "P0",
                "capacity": "4.00 TiB",
            },
        ],
        "maps": [],
    }
    server = _server_with_group_and_card(group)
    inventory = {"vdisks": {"V1"}, "fcmaps": set(), "hostmaps": set()}
    monkeypatch.setattr(
        "launchpad.health_server.collect_inventory",
        lambda run_cmd: inventory,
    )

    result = server.preview_contingency_snaps("lab-1")

    assert result["card"] == {
        "id": 1,
        "name": "array1",
        "host": "fake.example",
    }


def test_create_contingency_snaps_blocks_on_blocking_warnings(monkeypatch):
    server = _server_with_group_and_card(_group_with_incomplete_snap_rows())
    inventory = {"vdisks": {"V1"}, "fcmaps": set(), "hostmaps": set()}
    monkeypatch.setattr(
        "launchpad.health_server.collect_inventory",
        lambda run_cmd: inventory,
    )
    run_calls: list[tuple] = []

    def fake_run_snap_steps(steps, run_cmd):
        run_calls.append((steps, run_cmd))
        return {"ok": True, "log": []}

    monkeypatch.setattr("launchpad.health_server.run_snap_steps", fake_run_snap_steps)

    result = server.create_contingency_snaps("lab-1", confirm=True)

    assert result["ok"] is False
    assert any(
        "pool" in warning.lower()
        or "size" in warning.lower()
        or "capacity" in warning.lower()
        for warning in result["warnings"]
    )
    assert run_calls == []
