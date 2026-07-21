from launchpad.fc_consistgrp_ops import (
    ACTIONS,
    build_fc_consistgrp_steps,
    collect_fc_consistgrp_inventory,
    enrich_group_map_counts,
    parse_lsfcconsistgrp,
    parse_lsfcmap_rows,
    partition_maps,
    preview_ok,
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


def test_parse_lsfcconsistgrp():
    groups = parse_lsfcconsistgrp(CG_SAMPLE)
    assert groups[0]["name"] == "AWD1_AS400_CG"
    assert groups[0]["status"] == "idle_or_copied"
    assert int(groups[0]["map_count"]) == 6


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
    }
    calls: list[str] = []

    def run_cmd(cmd: str) -> str:
        calls.append(cmd)
        return responses.get(cmd, "")

    groups, maps = collect_fc_consistgrp_inventory(run_cmd)

    assert [g["name"] for g in groups] == ["AWD1_AS400_CG", "empty_cg"]
    assert groups[0]["map_count"] == 2
    assert [m["name"] for m in maps] == ["fcmap0", "fcmap1", "standalone1"]
    assert all(cmd.endswith("-delim :") for cmd in calls)
    assert calls == [
        "svcinfo lsfcconsistgrp -delim :",
        "svcinfo lsfcmap -delim :",
    ]


def test_collect_fc_consistgrp_inventory_falls_back_when_delimited_empty():
    responses = {
        "svcinfo lsfcconsistgrp -delim :": "",
        "svcinfo lsfcconsistgrp": CG_SAMPLE.strip(),
        "svcinfo lsfcmap -delim :": "   \n  ",
        "svcinfo lsfcmap": MAP_SAMPLE.strip(),
    }
    calls: list[str] = []

    def run_cmd(cmd: str) -> str:
        calls.append(cmd)
        return responses.get(cmd, "")

    groups, maps = collect_fc_consistgrp_inventory(run_cmd)

    assert [g["name"] for g in groups] == ["AWD1_AS400_CG", "empty_cg"]
    assert len(maps) == 3
    assert calls == [
        "svcinfo lsfcconsistgrp -delim :",
        "svcinfo lsfcconsistgrp",
        "svcinfo lsfcmap -delim :",
        "svcinfo lsfcmap",
    ]


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
