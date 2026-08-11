from datetime import datetime, timezone
from pathlib import Path

import pytest

from launchpad.dell_report_snapshots import (
    DELL_SNAPSHOT_RETENTION_WEEKS,
    SNAPSHOT_LAYER_SYSTEM,
    has_week_snapshot,
    iso_week_key,
    load_dell_snapshots,
    prior_and_current_for_card,
    save_dell_snapshots,
    snapshots_allow_weekly_growth,
    upsert_week_snapshot,
    weekly_growth_fraction,
)


def _snap(
    week: str,
    *,
    used_bytes: float = 100.0,
    usable_bytes: float = 200.0,
) -> dict:
    return {
        "week": week,
        "usable_bytes": usable_bytes,
        "used_bytes": used_bytes,
        "model": "FS9500",
        "facility": "Data center -WAG1",
        "family": "ibm",
        "array_name": "site-a",
        "captured_at": f"{week}T12:00:00+00:00",
    }


def test_iso_week_key_utc():
    dt = datetime(2026, 8, 4, 15, 30, tzinfo=timezone.utc)
    assert iso_week_key(dt) == "2026-W32"


def test_iso_week_key_defaults_to_now(monkeypatch):
    fixed = datetime(2026, 1, 5, 0, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(
        "launchpad.dell_report_snapshots.datetime",
        type(
            "DT",
            (),
            {
                "now": staticmethod(lambda tz=None: fixed),
            },
        ),
    )
    assert iso_week_key() == "2026-W02"


def test_one_week_prior_is_none():
    store = upsert_week_snapshot(
        {},
        card_id=7,
        week="2026-W32",
        usable_bytes=200,
        used_bytes=100,
        model="FS9500",
        facility="Data center -WAG1",
        family="ibm",
        array_name="site-a",
        captured_at="2026-08-04T12:00:00+00:00",
    )
    prior, current = prior_and_current_for_card(store, 7)
    assert prior is None
    assert current is not None
    assert current["week"] == "2026-W32"
    assert current["used_bytes"] == 100


def test_two_weeks_growth_fraction():
    store = {}
    for week, used in [("2026-W31", 100.0), ("2026-W32", 125.0)]:
        store = upsert_week_snapshot(
            store,
            card_id=7,
            week=week,
            usable_bytes=200,
            used_bytes=used,
            model="FS9500",
            facility="Data center -WAG1",
            family="ibm",
            array_name="site-a",
            captured_at=f"{week}T12:00:00+00:00",
        )
    prior, current = prior_and_current_for_card(store, 7, current_week="2026-W32")
    assert prior["week"] == "2026-W31"
    assert current["week"] == "2026-W32"
    assert weekly_growth_fraction(prior["used_bytes"], current["used_bytes"]) == pytest.approx(0.25)


def test_weekly_growth_fraction_prior_zero_returns_none():
    assert weekly_growth_fraction(0, 100) is None


def test_retention_trims_older_than_twelve_weeks():
    store = {}
    for idx in range(14):
        week_num = idx + 1
        store = upsert_week_snapshot(
            store,
            card_id=1,
            week=f"2026-W{week_num:02d}",
            usable_bytes=1000,
            used_bytes=float(week_num),
            model="m",
            facility="Other",
            family="ibm",
            array_name="a",
            captured_at=f"2026-W{week_num:02d}T00:00:00+00:00",
        )
    weeks = sorted(store["1"].keys())
    assert len(weeks) == DELL_SNAPSHOT_RETENTION_WEEKS
    assert weeks[0] == "2026-W03"
    assert weeks[-1] == "2026-W14"


def test_upsert_replaces_same_card_and_week():
    store = upsert_week_snapshot(
        {},
        card_id="42",
        week="2026-W10",
        usable_bytes=100,
        used_bytes=50,
        model="m",
        facility="Other",
        family="hp",
        array_name="x",
        captured_at="t1",
    )
    store = upsert_week_snapshot(
        store,
        card_id=42,
        week="2026-W10",
        usable_bytes=100,
        used_bytes=75,
        model="m",
        facility="Other",
        family="hp",
        array_name="x",
        captured_at="t2",
    )
    assert store["42"]["2026-W10"]["used_bytes"] == 75
    assert store["42"]["2026-W10"]["captured_at"] == "t2"


def test_has_week_snapshot():
    store = upsert_week_snapshot(
        {},
        card_id=3,
        week="2026-W20",
        usable_bytes=1,
        used_bytes=1,
        model="m",
        facility="Other",
        family="ibm",
        array_name="a",
        captured_at="t",
    )
    assert has_week_snapshot(store, 3, "2026-W20")
    assert has_week_snapshot(store, "3", "2026-W20")
    assert not has_week_snapshot(store, 3, "2026-W21")
    assert not has_week_snapshot(store, 99, "2026-W20")


def test_load_save_roundtrip(tmp_path: Path):
    path = tmp_path / "dell_report_snapshots.json"
    store = upsert_week_snapshot(
        {},
        card_id=5,
        week="2026-W05",
        usable_bytes=500,
        used_bytes=250,
        model="3PAR",
        facility="Distribution center",
        family="hp",
        array_name="hp-site",
        captured_at="2026-02-01T08:00:00+00:00",
    )
    save_dell_snapshots(store, path)
    loaded = load_dell_snapshots(path)
    assert loaded == store


def test_load_missing_file_returns_empty_dict(tmp_path: Path):
    assert load_dell_snapshots(tmp_path / "missing.json") == {}


def test_upsert_stamps_layer_system():
    store = upsert_week_snapshot(
        {},
        card_id=7,
        week="2026-W32",
        usable_bytes=200,
        used_bytes=100,
        model="FS9500",
        facility="Data center -WAG1",
        family="ibm",
        array_name="site-a",
        captured_at="2026-08-04T12:00:00+00:00",
    )
    assert store["7"]["2026-W32"]["layer"] == SNAPSHOT_LAYER_SYSTEM


def test_growth_allowed_only_when_both_system():
    system = {"layer": SNAPSHOT_LAYER_SYSTEM, "used_bytes": 100}
    assert snapshots_allow_weekly_growth(system, system) is True
    assert snapshots_allow_weekly_growth({"used_bytes": 100}, system) is False
    assert snapshots_allow_weekly_growth(None, system) is False
