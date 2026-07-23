from launchpad.capacity_email_settings import (
    CAPACITY_EMAIL_SETTING,
    get_gmail_password,
    normalize_capacity_email_settings,
    parse_address_list,
    set_gmail_password,
    validate_for_send,
)
from launchpad.crypto import derive_key, generate_salt


def test_setting_key():
    assert CAPACITY_EMAIL_SETTING == "capacity_email_settings"


def test_parse_address_list_splits_comma_semicolon_and_strips():
    assert parse_address_list(" a@x.com, b@y.com;c@z.com ,,") == [
        "a@x.com",
        "b@y.com",
        "c@z.com",
    ]


def test_normalize_defaults_and_clamps():
    s = normalize_capacity_email_settings({})
    assert s["enabled"] is False
    assert s["provider"] == "gmail"
    assert s["mode"] == "weekly"
    assert s["time_local"] == "08:00"
    assert s["weekday"] == 0
    assert s["every_n_days"] == 7
    assert s["to"] == []
    bad = normalize_capacity_email_settings(
        {"provider": "nope", "mode": "hourly", "weekday": 99, "every_n_days": 0, "time_local": "25:99"}
    )
    assert bad["provider"] == "gmail"
    assert bad["mode"] == "weekly"
    assert bad["weekday"] == 0
    assert bad["every_n_days"] == 1
    assert bad["time_local"] == "08:00"


def test_gmail_password_roundtrip_and_validate():
    key = derive_key("secret", generate_salt())
    s = normalize_capacity_email_settings(
        {"provider": "gmail", "gmail_address": "ops@gmail.com", "to": ["a@b.com"]}
    )
    assert validate_for_send(s, crypto_key=key)
    s = set_gmail_password(s, key, "app-pass-here")
    assert get_gmail_password(s, key) == "app-pass-here"
    assert validate_for_send(s, crypto_key=key) == []
    outlook = normalize_capacity_email_settings(
        {"provider": "outlook", "to": ["a@b.com"]}
    )
    assert validate_for_send(outlook, crypto_key=key) == []
