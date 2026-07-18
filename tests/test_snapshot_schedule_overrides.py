from datetime import date

from launchpad.snapshot_schedule_overrides import (
    DEFAULT_CUSTOM_TIME,
    format_one_offs_summary,
    normalize_override,
    normalize_overrides_map,
    parse_date_yyyy_mm_dd,
    parse_time_hhmm,
)


def test_normalize_override_defaults_and_cleans():
    out = normalize_override(
        {
            "mode": "CUSTOM",
            "held": 1,
            "interval_days": 7,
            "start_date": "2026-07-20",
            "time": "2:00",
            "one_offs": [
                {"date": "2026-08-01", "time": "14:30", "label": " Change window "},
                {"date": "bad", "time": "99:99"},
            ],
        }
    )
    assert out is not None
    assert out["mode"] == "custom"
    assert out["held"] is True
    assert out["interval_days"] == 7
    assert out["start_date"] == "2026-07-20"
    assert out["time"] == "02:00"
    assert out["one_offs"] == [
        {"date": "2026-08-01", "time": "14:30", "label": "Change window"}
    ]


def test_normalize_override_rejects_garbage():
    assert normalize_override(None) is None
    assert normalize_override("nope") is None


def test_normalize_overrides_map_keys_as_strings():
    mapping = normalize_overrides_map({42: {"mode": "auto", "held": False}})
    assert "42" in mapping
    assert mapping["42"]["mode"] == "auto"


def test_parse_helpers():
    assert parse_time_hhmm("02:00") == (2, 0)
    assert parse_time_hhmm("2:5") == (2, 5)
    assert parse_time_hhmm("25:00") is None
    assert parse_date_yyyy_mm_dd("2026-07-20") == date(2026, 7, 20)
    assert parse_date_yyyy_mm_dd("2026-13-01") is None


def test_format_one_offs_summary():
    text = format_one_offs_summary(
        [
            {"date": "2026-08-01", "time": "14:30", "label": "Window"},
            {"date": "2026-08-02", "time": "09:00"},
        ]
    )
    assert "2026-08-01 14:30 Window" in text
    assert "2026-08-02 09:00" in text
    assert DEFAULT_CUSTOM_TIME == "02:00"
