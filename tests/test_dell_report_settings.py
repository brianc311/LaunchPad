import json

from launchpad.dell_report_settings import (
    DELL_REPORT_SETTING,
    is_dell_report_enabled,
    load_dell_report_settings,
    normalize_dell_report_settings,
    save_dell_report_settings,
)


class _FakeDb:
    def __init__(self):
        self.values = {}

    def get_setting(self, key, default=""):
        return self.values.get(key, default)

    def set_setting(self, key, value):
        self.values[key] = value


def test_setting_key():
    assert DELL_REPORT_SETTING == "dell_report_settings"


def test_normalize_defaults_enabled_true():
    assert normalize_dell_report_settings({}) == {
        "enabled": True,
        "card_overrides": {},
    }
    assert normalize_dell_report_settings(None) == {
        "enabled": True,
        "card_overrides": {},
    }
    assert normalize_dell_report_settings([]) == {
        "enabled": True,
        "card_overrides": {},
    }


def test_normalize_coerces_enabled():
    assert normalize_dell_report_settings({"enabled": False}) == {
        "enabled": False,
        "card_overrides": {},
    }
    assert normalize_dell_report_settings({"enabled": True}) == {
        "enabled": True,
        "card_overrides": {},
    }
    assert normalize_dell_report_settings({"enabled": "false"}) == {
        "enabled": False,
        "card_overrides": {},
    }
    assert normalize_dell_report_settings({"enabled": "true"}) == {
        "enabled": True,
        "card_overrides": {},
    }
    assert normalize_dell_report_settings({"enabled": 1}) == {
        "enabled": True,
        "card_overrides": {},
    }
    assert normalize_dell_report_settings({"enabled": 0}) == {
        "enabled": False,
        "card_overrides": {},
    }


def test_normalize_keeps_card_overrides():
    raw = {
        "enabled": True,
        "card_overrides": {
            "12": {"facility": "Data center -WAG2", "array_name": "Vdiprimera101"}
        },
    }
    out = normalize_dell_report_settings(raw)
    assert out["card_overrides"]["12"]["facility"] == "Data center -WAG2"
    assert out["card_overrides"]["12"]["array_name"] == "Vdiprimera101"
    assert "model" not in out["card_overrides"]["12"]


def test_normalize_drops_bad_overrides():
    out = normalize_dell_report_settings(
        {"card_overrides": {"x": "nope", "7": {"facility": 1}}}
    )
    assert out["card_overrides"] == {}


def test_load_empty_defaults_enabled_true():
    db = _FakeDb()
    assert load_dell_report_settings(db) == {"enabled": True, "card_overrides": {}}


def test_load_invalid_json_defaults_enabled_true():
    db = _FakeDb()
    db.values[DELL_REPORT_SETTING] = "not-json"
    assert load_dell_report_settings(db) == {"enabled": True, "card_overrides": {}}


def test_save_load_roundtrip():
    db = _FakeDb()
    saved = save_dell_report_settings(db, {"enabled": False})
    assert saved == {"enabled": False, "card_overrides": {}}
    assert json.loads(db.values[DELL_REPORT_SETTING]) == {
        "enabled": False,
        "card_overrides": {},
    }
    assert load_dell_report_settings(db) == {"enabled": False, "card_overrides": {}}


def test_is_dell_report_enabled():
    db = _FakeDb()
    assert is_dell_report_enabled(db) is True
    save_dell_report_settings(db, {"enabled": False})
    assert is_dell_report_enabled(db) is False
