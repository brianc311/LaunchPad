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
        "woodland-hills-ca",
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
