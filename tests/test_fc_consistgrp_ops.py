from launchpad.fc_consistgrp_ops import (
    enrich_group_map_counts,
    parse_lsfcconsistgrp,
    parse_lsfcmap_rows,
    partition_maps,
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
