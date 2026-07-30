from launchpad.fc_cg_summary import (
    build_cg_summaries,
    compose_cg_policy_display,
    count_host_maps_for_targets,
    format_cg_policy,
    min_map_progress_pct,
    schedule_interval_days,
    snaps_per_week_from_days,
)


def test_compose_cg_policy_schedule_then_array():
    assert compose_cg_policy_display(
        array_policy="50 · enabled",
        schedule={"label": "WEEKLY"},
    ) == "WEEKLY · 50 · enabled"
    assert compose_cg_policy_display(array_policy="", schedule={"label": "WEEKLY"}) == "WEEKLY"
    assert compose_cg_policy_display(array_policy="50", schedule=None) == "50"
    assert compose_cg_policy_display() == ""


def test_build_cg_summaries_policy_includes_schedule_label():
    groups = [{"name": "CG1", "status": "idle_or_copied", "policy": "50"}]
    rows = build_cg_summaries(
        groups=groups, maps=[], host_maps=[],
        schedule={"days": 7, "held": False, "label": "WEEKLY"},
    )
    assert rows[0]["policy"] == "WEEKLY · 50"


def test_format_cg_policy_joins_and_empty():
    assert format_cg_policy({"copy_rate": "50", "autodelete": "enabled"}) == "50 · enabled"
    assert format_cg_policy({}) == ""
    assert format_cg_policy({"copy_rate": "", "autodelete": "  "}) == ""


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


def test_build_cg_summaries_flash_time_and_min_progress_while_copying():
    groups = [
        {
            "name": "CG1",
            "status": "copying",
            "policy": "",
            "flash_time": "2026-07-30 10:00:00",
        }
    ]
    maps = [
        {"name": "m1", "consistgrp": "CG1", "progress": "80%", "source": "s", "target": "t"},
        {"name": "m2", "consistgrp": "CG1", "progress": "40", "source": "s2", "target": "t2"},
        {"name": "m3", "consistgrp": "other", "progress": "10", "source": "s3", "target": "t3"},
    ]
    rows = build_cg_summaries(groups=groups, maps=maps, host_maps=[], schedule=None)
    assert rows[0]["flash_time"] == "2026-07-30 10:00:00"
    assert rows[0]["progress_pct"] == 40


def test_build_cg_summaries_progress_100_when_idle_or_copied():
    groups = [{"name": "CG1", "status": "idle_or_copied", "flash_time": "x"}]
    maps = [{"name": "m1", "consistgrp": "CG1", "progress": "", "source": "s", "target": "t"}]
    rows = build_cg_summaries(groups=groups, maps=maps, host_maps=[], schedule=None)
    assert rows[0]["progress_pct"] == 100


def test_build_cg_summaries_progress_min_when_stopped():
    groups = [{"name": "CG1", "status": "stopped", "flash_time": "x"}]
    maps = [
        {"name": "m1", "consistgrp": "CG1", "progress": "75", "source": "s", "target": "t"},
        {"name": "m2", "consistgrp": "CG1", "progress": "90", "source": "s2", "target": "t2"},
    ]
    rows = build_cg_summaries(groups=groups, maps=maps, host_maps=[], schedule=None)
    assert rows[0]["progress_pct"] == 75


def test_min_map_progress_pct_ignores_non_numeric():
    maps = [
        {"progress": "50%"},
        {"progress": "n/a"},
        {"progress": "30"},
    ]
    assert min_map_progress_pct(maps, status="copying") == 30


def test_min_map_progress_pct_copying_case_insensitive():
    maps = [{"progress": "75"}]
    assert min_map_progress_pct(maps, status="COPYING") == 75
    assert min_map_progress_pct(maps, status="Copying") == 75
