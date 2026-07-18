from launchpad.snapshot_schedule_export import SCHEDULE_HEADERS, build_schedule_rows


def _card(card_id: int, used_pct: float = 40.0) -> dict:
    return {
        "id": card_id,
        "name": f"Site{card_id}",
        "category": "Lab",
        "host": "10.0.0.1",
        "device_profile": "ibm_flashsystem",
        "model": "FS7300",
        "pools": [
            {
                "name": "Pool0",
                "used_pct": used_pct,
                "free_bytes": 1000,
            }
        ],
    }


def test_headers_include_override_columns():
    assert "Mode" in SCHEDULE_HEADERS
    assert "Time" in SCHEDULE_HEADERS
    assert "Held" in SCHEDULE_HEADERS
    assert "One-offs" in SCHEDULE_HEADERS


def test_custom_override_controls_frequency_and_starts():
    cards = [_card(1, used_pct=40.0)]
    overrides = {
        "1": {
            "mode": "custom",
            "held": False,
            "interval_days": 7,
            "start_date": "2026-07-20",
            "time": "02:00",
            "one_offs": [{"date": "2026-08-01", "time": "14:30", "label": "Window"}],
        }
    }
    rows = build_schedule_rows(cards, {}, threshold=80.0, overrides=overrides)
    assert len(rows) == 1
    row = rows[0]
    headers = list(SCHEDULE_HEADERS)
    assert row[headers.index("Frequency")] == "WEEKLY"
    assert row[headers.index("Interval Days")] == 7
    assert "Jul 20, 2026" in str(row[headers.index("Starts")])
    assert row[headers.index("Mode")] == "custom"
    assert row[headers.index("Time")] == "02:00"
    assert row[headers.index("Held")] == "No"
    assert "2026-08-01 14:30 Window" in str(row[headers.index("One-offs")])


def test_manual_hold_overrides_capacity_hold():
    cards = [_card(1, used_pct=40.0)]
    overrides = {
        "1": {
            "mode": "auto",
            "held": True,
            "interval_days": 7,
            "start_date": "",
            "time": "02:00",
            "one_offs": [],
        }
    }
    rows = build_schedule_rows(cards, {}, threshold=80.0, overrides=overrides)
    assert rows[0][list(SCHEDULE_HEADERS).index("Status")] == "Flagged / Hold"
    assert rows[0][list(SCHEDULE_HEADERS).index("Held")] == "Yes"
