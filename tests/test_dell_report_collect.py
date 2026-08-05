from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from launchpad.capacity_export import ExportSite
from launchpad.dell_report_export import (
    collect_dell_report_rows,
    maybe_upsert_dell_snapshot_for_card,
)
from launchpad.dell_report_snapshots import upsert_week_snapshot


def _site(
    *,
    card_id: int = 1,
    name: str = "WAG1_FS9200_1",
    device_profile: str = "flashsystem_9500",
    used_bytes: int = 60 * 1024**3,
    total_bytes: int = 100 * 1024**3,
) -> ExportSite:
    used_pct = (used_bytes / total_bytes * 100.0) if total_bytes else 0.0
    return ExportSite(
        card_id=card_id,
        name=name,
        host="10.0.0.1",
        serial_number="SN1",
        category="storage",
        device_profile=device_profile,
        capacity_summary={
            "name": "FlashSystem 9200",
            "used_bytes": used_bytes,
            "total_bytes": total_bytes,
            "free_bytes": total_bytes - used_bytes,
            "used_pct": used_pct,
        },
        pools=[],
        error=None,
    )


def test_collect_splits_ibm_and_hp_rows():
    ibm_site = _site(card_id=1, name="WAG1_FS9200_1", device_profile="flashsystem_9500")
    hp_site = _site(
        card_id=2,
        name="HPE-3PAR-site",
        device_profile="hpe_3par_8450",
        used_bytes=30 * 1024**3,
        total_bytes=80 * 1024**3,
    )
    other_site = _site(card_id=3, name="PowerMax", device_profile="dell_powermax")

    ibm_rows, hp_rows, store = collect_dell_report_rows(
        [ibm_site, hp_site, other_site],
        snapshot_store={},
        now=datetime(2026, 8, 4, tzinfo=timezone.utc),
    )

    assert len(ibm_rows) == 1
    assert len(hp_rows) == 1
    assert ibm_rows[0]["array_name"] == "FlashSystem 9200"
    assert hp_rows[0]["array_name"] == "FlashSystem 9200"
    assert ibm_rows[0]["facility"] == "Data center -WAG1"
    assert ibm_rows[0]["model"] == "IBM FlashSystem 9500"
    assert ibm_rows[0]["card_id"] == 1
    assert has_week(store, 1, "2026-W32")
    assert has_week(store, 2, "2026-W32")
    assert "3" not in store


def test_collect_uses_raw_when_include_pools_false():
    sites = [
        {
            "card_id": 5,
            "name": "Primera Remote",
            "device_profile": "hpe_primera_600",
            "capacity_summary": None,
            "raw_capacity_summary": {
                "name": "Vdiprimera101",
                "total_bytes": 200 * 1024**3,
                "used_bytes": 50 * 1024**3,
                "used_pct": 25.0,
            },
            "pools": [],
        }
    ]
    ibm, hp, store = collect_dell_report_rows(
        sites,
        snapshot_store={},
        include_pools=False,
        now=datetime(2026, 8, 5, tzinfo=timezone.utc),
    )
    assert ibm == []
    assert len(hp) == 1
    assert hp[0]["array_name"] == "Vdiprimera101"
    assert hp[0]["facility"] == "Remote"
    assert hp[0]["model"] == "HPE Primera 600 4-way"
    assert has_week(store, 5, "2026-W32")


def test_collect_refreshes_stale_cpg_snapshot_with_raw():
    store = upsert_week_snapshot(
        {},
        card_id=5,
        week="2026-W32",
        usable_bytes=10 * 1024**3,
        used_bytes=9 * 1024**3,
        model="All CPGs",
        facility="Other",
        family="hp",
        array_name="old",
        captured_at="2026-08-05T01:00:00+00:00",
    )
    sites = [
        {
            "card_id": 5,
            "name": "HPE - VDIPRIMERA101 - WAG2",
            "device_profile": "hpe_primera_600",
            "capacity_summary": {
                "name": "All CPGs",
                "total_bytes": 10 * 1024**3,
                "used_bytes": 9 * 1024**3,
            },
            "raw_capacity_summary": {
                "name": "Vdiprimera101",
                "total_bytes": 200 * 1024**3,
                "used_bytes": 50 * 1024**3,
            },
            "pools": [],
        }
    ]
    _, hp, updated = collect_dell_report_rows(
        sites,
        snapshot_store=store,
        include_pools=False,
        now=datetime(2026, 8, 5, tzinfo=timezone.utc),
    )
    assert len(hp) == 1
    assert hp[0]["model"] == "HPE Primera 600 4-way"
    assert hp[0]["array_name"] == "Vdiprimera101"
    assert hp[0]["facility"] == "Data center -WAG2"
    assert hp[0]["curr_usable_gib"] == pytest.approx(200.0)
    assert updated["5"]["2026-W32"]["model"] == "HPE Primera 600 4-way"


def has_week(store, card_id, week):
    return week in store.get(str(card_id), {})


def test_collect_growth_with_two_weeks_in_store():
    store = upsert_week_snapshot(
        {},
        card_id=7,
        week="2026-W31",
        usable_bytes=200 * 1024**3,
        used_bytes=100 * 1024**3,
        model="FS9500",
        facility="Data center -WAG1",
        family="ibm",
        array_name="WAG1_FS9200_1",
        captured_at="2026-07-28T12:00:00+00:00",
    )
    site = _site(
        card_id=7,
        used_bytes=int(125 * 1024**3),
        total_bytes=int(200 * 1024**3),
    )

    ibm_rows, hp_rows, updated = collect_dell_report_rows(
        [site],
        snapshot_store=store,
        now=datetime(2026, 8, 4, tzinfo=timezone.utc),
    )

    assert hp_rows == []
    assert len(ibm_rows) == 1
    row = ibm_rows[0]
    assert row["prior_used_gib"] == pytest.approx(100.0)
    assert row["curr_used_gib"] == pytest.approx(125.0)
    assert row["weekly_growth"] == pytest.approx(0.25)
    assert has_week(updated, 7, "2026-W32")


def test_collect_one_week_prior_and_growth_blank():
    site = _site(card_id=5)

    ibm_rows, _, _ = collect_dell_report_rows(
        [site],
        snapshot_store={},
        now=datetime(2026, 8, 4, tzinfo=timezone.utc),
    )

    row = ibm_rows[0]
    assert row["prior_usable_gib"] is None
    assert row["prior_used_gib"] is None
    assert row["prior_util"] is None
    assert row["weekly_growth"] is None
    assert row["curr_used_gib"] == pytest.approx(60.0)


def test_maybe_upsert_creates_current_week_snapshot_when_missing(monkeypatch):
    card = SimpleNamespace(
        card_id=11,
        name="WAG1_FS9200_1",
        device_profile="flashsystem_9500",
        command_results={},
        metrics=None,
    )
    monkeypatch.setattr(
        "launchpad.flashsystem_health.analyze_health",
        lambda name, command_results, metrics: {
            "capacity_summary": {
                "name": "FlashSystem 9200",
                "used_bytes": 60 * 1024**3,
                "total_bytes": 100 * 1024**3,
            },
            "pools": [],
        },
    )

    store = maybe_upsert_dell_snapshot_for_card(
        card,
        snapshot_store={},
        now=datetime(2026, 8, 4, tzinfo=timezone.utc),
    )

    assert has_week(store, 11, "2026-W32")
    snap = store["11"]["2026-W32"]
    assert snap["used_bytes"] == 60 * 1024**3
    assert snap["usable_bytes"] == 100 * 1024**3
    assert snap["family"] == "ibm"
    assert snap["array_name"] == "FlashSystem 9200"
    assert snap["model"] == "IBM FlashSystem 9500"
