from launchpad.flashsystem_fc import parse_lsvdisk_volumes
from launchpad.inventory_sync import is_flashcopy_target_name


LSVDISK_SAMPLE = """id:name:IO_group_id:IO_group_name:status:mdisk_grp_id:mdisk_grp_name:capacity:type:FC_id:FC_name:RC_id:RC_name:vdisk_UID:fc_map_count:copy_count:fast_write_state:se_copy_count:RC_change
0:ADC-Data01:0:io_grp0:online:0:G3_AND_Pool:1.00TB:striped:::::60050764008101A45800000000000B90:0:1:empty:0:no
1:vol_a_snap:0:io_grp0:online:0:G3_AND_Pool:100.00GB:striped:::::60050764008101A45800000000000B91:1:1:empty:0:no
2:host1_data:0:io_grp0:online:0:G3_AND_Pool:50.00GB:striped:::::60050764008101A45800000000000B92:0:1:empty:0:no
"""


def test_parse_lsvdisk_volumes_extracts_fields():
    rows = parse_lsvdisk_volumes(LSVDISK_SAMPLE)
    by_name = {r["name"]: r for r in rows}
    assert by_name["ADC-Data01"]["pool"] == "G3_AND_Pool"
    assert by_name["ADC-Data01"]["uid"].startswith("60050764")
    assert by_name["ADC-Data01"]["capacity"]
    assert by_name["ADC-Data01"]["status"] == "online"


def test_is_flashcopy_target_name():
    assert is_flashcopy_target_name("vol_a_snap") is True
    assert is_flashcopy_target_name("VOL_A_SNAP") is True
    assert is_flashcopy_target_name("foo_Snap1") is True
    assert is_flashcopy_target_name("ADC-Data01") is False
    assert is_flashcopy_target_name("host1_data") is False
