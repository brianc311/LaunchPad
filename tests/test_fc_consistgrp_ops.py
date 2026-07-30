from types import SimpleNamespace

from launchpad.fc_consistgrp_ops import (
    ACTIONS,
    build_fc_consistgrp_steps,
    collect_fc_consistgrp_inventory,
    enrich_group_map_counts,
    enrich_maps_with_source_size,
    format_cg_total_size,
    is_fc_consistgrp_status_eligible,
    normalize_fc_cg_status_bucket,
    parse_lsfcconsistgrp,
    parse_lsfcmap_rows,
    partition_maps,
    preview_ok,
    sum_source_size_bytes,
    volume_capacity_index,
)

CG_SAMPLE = """id:name:status:FC_mapping_count
0:AWD1_AS400_CG:idle_or_copied:6
1:empty_cg:empty:0
"""

MAP_SAMPLE = """id:name:source_vdisk_name:target_vdisk_name:status:progress:group_name
0:fcmap0:AWD1_AS400_1:AWD1_AS400_1_Snap1:copied:100:AWD1_AS400_CG
1:fcmap1:AWD1_AS400_2:AWD1_AS400_2_Snap2:copied:100:AWD1_AS400_CG
2:standalone1:VOL_A:VOL_A_snap:idle_or_copied:0:
"""

LSVDISK_SAMPLE = """id:name:capacity:mdisk_grp_name
0:AWD1_AS400_1:100.00GB:Pool0
1:AWD1_AS400_2:200.00GB:Pool0
2:VOL_A:50.00GB:Pool0
"""


def test_parse_lsfcconsistgrp():
    groups = parse_lsfcconsistgrp(CG_SAMPLE)
    assert groups[0]["name"] == "AWD1_AS400_CG"
    assert groups[0]["status"] == "idle_or_copied"
    assert int(groups[0]["map_count"]) == 6


def test_parse_lsfcconsistgrp_policy_fields():
    sample = """id:name:status:copy_rate:autodelete
0:cg_with_policy:idle:50:enabled
1:cg_no_policy:empty::
"""
    groups = parse_lsfcconsistgrp(sample)
    by_name = {g["name"]: g for g in groups}
    assert by_name["cg_with_policy"]["policy"] == "50 · enabled"
    assert by_name["cg_no_policy"]["policy"] == ""


def test_parse_lsfcmap_rows_and_partition():
    maps = parse_lsfcmap_rows(MAP_SAMPLE)
    assert maps[0]["source"] == "AWD1_AS400_1"
    assert maps[0]["consistgrp"] == "AWD1_AS400_CG"
    in_g, alone = partition_maps(maps)
    assert {m["name"] for m in alone} == {"standalone1"}
    assert len(in_g) == 2


def test_enrich_group_map_counts():
    groups = parse_lsfcconsistgrp(CG_SAMPLE)
    maps = parse_lsfcmap_rows(MAP_SAMPLE)
    enriched = enrich_group_map_counts(groups, maps)
    awd = next(g for g in enriched if g["name"] == "AWD1_AS400_CG")
    assert awd["map_count"] == 2  # from membership in sample


def test_collect_fc_consistgrp_inventory_parses_delimited_tables():
    responses = {
        "svcinfo lsfcconsistgrp -delim :": CG_SAMPLE.strip(),
        "svcinfo lsfcmap -delim :": MAP_SAMPLE.strip(),
        "svcinfo lsvdisk -delim :": LSVDISK_SAMPLE.strip(),
    }
    calls: list[str] = []

    def run_cmd(cmd: str) -> str:
        calls.append(cmd)
        if cmd in responses:
            return responses[cmd]
        return ""

    groups, maps = collect_fc_consistgrp_inventory(run_cmd)

    assert [g["name"] for g in groups] == ["AWD1_AS400_CG", "empty_cg"]
    assert groups[0]["map_count"] == 2
    assert [m["name"] for m in maps] == ["fcmap0", "fcmap1", "standalone1"]
    by_name = {m["name"]: m for m in maps}
    assert by_name["fcmap0"]["source_size"] == "100.00GB"
    assert by_name["fcmap0"]["source_size_bytes"] == int(100 * (1024**3))
    assert calls[0] == "svcinfo lsfcconsistgrp -delim :"
    assert "svcinfo lsfcmap -delim :" in calls
    assert "svcinfo lsvdisk -delim :" in calls
    assert any("AWD1_AS400_CG" in cmd for cmd in calls)
    assert any("empty_cg" in cmd for cmd in calls)

def test_collect_fc_consistgrp_inventory_falls_back_when_delimited_empty():
    responses = {
        "svcinfo lsfcconsistgrp -delim :": "",
        "svcinfo lsfcconsistgrp": CG_SAMPLE.strip(),
        "svcinfo lsfcmap -delim :": "   \n  ",
        "svcinfo lsfcmap": MAP_SAMPLE.strip(),
        "svcinfo lsvdisk -delim :": "",
        "svcinfo lsvdisk": LSVDISK_SAMPLE.strip(),
    }
    calls: list[str] = []

    def run_cmd(cmd: str) -> str:
        calls.append(cmd)
        if cmd in responses:
            return responses[cmd]
        return ""

    groups, maps = collect_fc_consistgrp_inventory(run_cmd)

    assert [g["name"] for g in groups] == ["AWD1_AS400_CG", "empty_cg"]
    assert len(maps) == 3
    by_name = {m["name"]: m for m in maps}
    assert by_name["fcmap1"]["source_size"] == "200.00GB"
    assert calls[0:4] == [
        "svcinfo lsfcconsistgrp -delim :",
        "svcinfo lsfcconsistgrp",
        "svcinfo lsfcmap -delim :",
        "svcinfo lsfcmap",
    ]
    assert "svcinfo lsvdisk -delim :" in calls
    assert "svcinfo lsvdisk" in calls
    assert any("AWD1_AS400_CG" in cmd for cmd in calls)

def test_collect_inventory_lsvdisk_failure_still_returns_maps():
    def run_cmd(cmd: str) -> str:
        if "lsfcconsistgrp" in cmd:
            return CG_SAMPLE
        if "lsfcmap" in cmd:
            return MAP_SAMPLE
        if "lsvdisk" in cmd:
            raise RuntimeError("ssh failed")
        return ""

    groups, maps = collect_fc_consistgrp_inventory(run_cmd)
    assert groups and maps
    assert not maps[0].get("source_size")


def _inv():
    return parse_lsfcconsistgrp(CG_SAMPLE), parse_lsfcmap_rows(MAP_SAMPLE)


def test_create_group_skips_existing():
    groups, maps = _inv()
    steps, warnings = build_fc_consistgrp_steps(
        "create_group", {"name": "AWD1_AS400_CG"}, groups=groups, maps=maps
    )
    assert len(steps) == 1 and steps[0].skip
    assert "mkfcconsistgrp" in steps[0].cmd


def test_assign_and_remove_and_start():
    groups, maps = _inv()
    steps, _ = build_fc_consistgrp_steps(
        "assign_maps",
        {"group_name": "AWD1_AS400_CG", "map_names": ["standalone1"]},
        groups=groups,
        maps=maps,
    )
    assert any("chfcmap -consistgrp AWD1_AS400_CG standalone1" in s.cmd for s in steps)
    steps, _ = build_fc_consistgrp_steps(
        "remove_maps", {"map_names": ["fcmap0"]}, groups=groups, maps=maps
    )
    assert any("chfcmap -consistgrp null fcmap0" in s.cmd for s in steps)
    steps, _ = build_fc_consistgrp_steps(
        "start_group", {"group_name": "AWD1_AS400_CG"}, groups=groups, maps=maps
    )
    assert [s.kind for s in steps] == ["prestartfcconsistgrp", "startfcconsistgrp"]


def test_delete_non_empty_refused():
    groups, maps = _inv()
    steps, warnings = build_fc_consistgrp_steps(
        "delete_group", {"group_name": "AWD1_AS400_CG"}, groups=groups, maps=maps
    )
    assert steps == []
    assert any(w.startswith("ERROR:") for w in warnings)
    assert not preview_ok(steps, warnings)


def test_delete_empty_ok():
    groups, maps = _inv()
    steps, warnings = build_fc_consistgrp_steps(
        "delete_group", {"group_name": "empty_cg"}, groups=groups, maps=maps
    )
    assert len(steps) == 1 and "rmfcconsistgrp empty_cg" in steps[0].cmd
    assert not any(w.startswith("ERROR:") for w in warnings)
    assert preview_ok(steps, warnings)


def test_actions_constant():
    assert ACTIONS == frozenset(
        {"create_group", "assign_maps", "remove_maps", "start_group", "delete_group"}
    )


def test_volume_capacity_index():
    idx = volume_capacity_index(LSVDISK_SAMPLE)
    assert idx["AWD1_AS400_1"]["capacity"] == "100.00GB"
    assert idx["AWD1_AS400_1"]["bytes"] == int(100 * (1024**3))


def test_enrich_maps_with_source_size():
    maps = parse_lsfcmap_rows(MAP_SAMPLE)
    idx = volume_capacity_index(LSVDISK_SAMPLE)
    enriched = enrich_maps_with_source_size(maps, idx)
    by_name = {m["name"]: m for m in enriched}
    assert by_name["fcmap0"]["source_size"] == "100.00GB"
    assert by_name["standalone1"]["source_size"] == "50.00GB"
    assert by_name["fcmap0"]["source_size_bytes"] == int(100 * (1024**3))


def test_enrich_unknown_source_leaves_empty():
    maps = [{"name": "x", "source": "missing_vol", "consistgrp": "g"}]
    enriched = enrich_maps_with_source_size(maps, {})
    assert enriched[0].get("source_size") in ("", None)
    assert not enriched[0].get("source_size_bytes")


def test_sum_and_format_cg_total():
    maps = [
        {"source_size_bytes": int(100 * (1024**3))},
        {"source_size_bytes": int(200 * (1024**3))},
        {"source_size": "?", "source_size_bytes": None},
    ]
    assert sum_source_size_bytes(maps) == int(300 * (1024**3))
    total = format_cg_total_size(maps)
    assert total  # non-empty formatted string from _format_bytes


def test_normalize_idle_or_copied_variants():
    assert normalize_fc_cg_status_bucket("idle_or_copied") == "idle_or_copied"
    assert normalize_fc_cg_status_bucket("Idle or Copied") == "idle_or_copied"


def test_normalize_stopped_and_copying():
    assert normalize_fc_cg_status_bucket("stopped") == "stopped"
    assert normalize_fc_cg_status_bucket("Copying") == "copying"


def test_normalize_unknown_empty():
    assert normalize_fc_cg_status_bucket("weird_state") == ""
    assert normalize_fc_cg_status_bucket("") == ""


def _eligible_card(**overrides):
    base = {
        "monitor_on": True,
        "card_type": "ssh",
        "device_profile": "flashsystem_7200",
    }
    base.update(overrides)
    return base


def test_status_eligible_monitor_on_svc_ssh():
    assert is_fc_consistgrp_status_eligible(_eligible_card()) is True


def test_status_eligible_rejects_monitor_off():
    assert is_fc_consistgrp_status_eligible(_eligible_card(monitor_on=False)) is False


def test_status_eligible_rejects_non_ssh():
    assert is_fc_consistgrp_status_eligible(_eligible_card(card_type="web")) is False


def test_status_eligible_rejects_hpe_profile():
    assert (
        is_fc_consistgrp_status_eligible(
            _eligible_card(device_profile="hpe_3par_8450")
        )
        is False
    )


def test_status_eligible_accepts_object_card():
    card = SimpleNamespace(
        monitor_on=True,
        card_type="ssh",
        device_profile="flashsystem_7200",
    )
    assert is_fc_consistgrp_status_eligible(card) is True


def test_parse_lsfcconsistgrp_flash_time_when_present():
    sample = """id:name:status:flash_time:FC_mapping_count
0:cg_with_flash:idle_or_copied:2026-07-29 120000:2
"""
    groups = parse_lsfcconsistgrp(sample)
    assert groups[0]["flash_time"] == "7/29/2026 12:00:00 PM"


def test_parse_lsfcconsistgrp_flash_time_blank_when_absent():
    groups = parse_lsfcconsistgrp(CG_SAMPLE)
    assert groups[0]["flash_time"] == ""


def test_format_flash_time_display_compact_yymmddhhmmss():
    from launchpad.fc_consistgrp_ops import format_flash_time_display

    assert format_flash_time_display("260502060129") == "5/2/2026 6:01:29 AM"
    assert format_flash_time_display("260502050129") == "5/2/2026 5:01:29 AM"
    assert format_flash_time_display("") == ""
    assert format_flash_time_display("not-a-time") == "not-a-time"


def test_enrich_groups_flash_time_from_detailed_view():
    from launchpad.fc_consistgrp_ops import enrich_groups_flash_time

    groups = [{"name": "CG1", "status": "idle_or_copied", "flash_time": ""}]
    maps: list[dict] = []

    def run_cmd(command: str) -> str:
        if "lsfcconsistgrp -delim : CG1" in command or command.endswith(" CG1"):
            return "id:1\nname:CG1\nstatus:idle_or_copied\nstart_time:210730:12:00:00\n"
        return ""

    enrich_groups_flash_time(groups, maps, run_cmd)
    assert groups[0]["flash_time"] == "7/30/2021 12:00:00 PM"


def test_enrich_groups_flash_time_from_map_start_time():
    from launchpad.fc_consistgrp_ops import enrich_groups_flash_time

    groups = [{"name": "CG1", "status": "copying", "flash_time": ""}]
    maps = [
        {"consistgrp": "CG1", "start_time": "210731120000"},
        {"consistgrp": "CG1", "start_time": "210730120000"},
    ]
    enrich_groups_flash_time(groups, maps, run_cmd=None)
    assert groups[0]["flash_time"] == "7/30/2021 12:00:00 PM"


def test_parse_lsfcmap_rows_includes_start_time():
    sample = """id:name:source_vdisk_name:target_vdisk_name:status:progress:group_name:start_time
0:m1:src:tgt:copying:50:CG1:210730120000
"""
    maps = parse_lsfcmap_rows(sample)
    assert maps[0]["start_time"] == "210730120000"
