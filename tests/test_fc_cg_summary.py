from launchpad.fc_cg_summary import (
    build_cg_summaries,
    count_host_maps_for_targets,
    schedule_interval_days,
    snaps_per_week_from_days,
)


def test_schedule_interval_and_snaps_week():
    assert schedule_interval_days(0, 80) == 2
    assert snaps_per_week_from_days(7) == 1.0
    assert snaps_per_week_from_days(14) == 0.5


def test_host_map_count_only_targets():
    host_maps = [
        {"volume": "vol_a_snap", "host": "h1"},
        {"volume": "other", "host": "h2"},
        {"volume": "vol_a_snap", "host": "h3"},
    ]
    assert count_host_maps_for_targets(host_maps, {"vol_a_snap"}) == 2


def test_build_cg_summaries_schedule_fallback():
    groups = [{"name": "CG1", "status": "empty", "policy": "", "map_count": 0}]
    maps = [
        {
            "name": "m1",
            "source": "src1",
            "target": "tgt1",
            "consistgrp": "CG1",
            "source_size": "10 GB",
            "source_size_bytes": 10 * (1024**3),
        }
    ]
    host_maps = [{"volume": "tgt1", "host": "h1"}]
    rows = build_cg_summaries(
        groups=groups,
        maps=maps,
        host_maps=host_maps,
        schedule={"days": 7, "held": False, "label": "WEEKLY"},
    )
    assert len(rows) == 1
    assert rows[0]["fc_map_count"] == 1
    assert rows[0]["host_map_count"] == 1
    assert rows[0]["snaps_per_week"] == 1.0
    assert rows[0]["snaps_source"] == "schedule"
