import json

import pytest

from launchpad.health_server import HealthServer
from launchpad.snapshot_schedule_overrides import SNAPSHOT_OVERRIDES_SETTING


def _settings_backend(initial: dict[str, str] | None = None):
    settings = dict(initial or {})

    def get_setting(key: str, default: str) -> str:
        return settings.get(key, default)

    def set_setting(key: str, value: str) -> None:
        settings[key] = value

    return settings, get_setting, set_setting


def test_snapshot_overrides_are_normalized_and_persisted():
    settings, getter, setter = _settings_backend()
    server = HealthServer()
    server.set_settings_backend(getter, setter)

    overrides = server.set_snapshot_override(
        42,
        {
            "mode": "CUSTOM",
            "held": 0,
            "interval_days": 7,
            "start_date": "2026-07-20",
            "time": "2:00",
            "one_offs": [],
        },
    )

    assert overrides["42"]["mode"] == "custom"
    assert overrides["42"]["time"] == "02:00"
    assert json.loads(settings[SNAPSHOT_OVERRIDES_SETTING]) == overrides
    assert server.get_snapshot_overrides() == overrides


def test_snapshot_override_bulk_save_discards_invalid_entries():
    settings, getter, setter = _settings_backend()
    server = HealthServer()
    server.set_settings_backend(getter, setter)

    overrides = server.set_snapshot_overrides(
        {
            42: {"mode": "auto", "held": False},
            43: "invalid",
        }
    )

    assert list(overrides) == ["42"]
    assert json.loads(settings[SNAPSHOT_OVERRIDES_SETTING]) == overrides


def test_snapshot_override_save_requires_unlocked_settings_backend():
    with pytest.raises(
        RuntimeError,
        match="LaunchPad must be unlocked to save schedule overrides.",
    ):
        HealthServer().set_snapshot_override(42, {"mode": "auto"})


def test_get_snapshot_overrides_empty_without_settings_backend():
    server = HealthServer()
    assert server.get_snapshot_overrides() == {}
    assert server.snapshot_schedule_persist_available() is False


def test_snapshot_schedule_persist_available_when_backend_set():
    _, getter, setter = _settings_backend()
    server = HealthServer()
    server.set_settings_backend(getter, setter)
    assert server.snapshot_schedule_persist_available() is True
    assert server.get_snapshot_overrides() == {}
