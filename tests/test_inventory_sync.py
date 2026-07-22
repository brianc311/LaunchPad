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


def test_build_inventory_sync_replaces_shaped_lun_and_cg():
    from launchpad.inventory_sync import build_inventory_sync
    from launchpad.lun_builder_data import expand_lun_batch

    hosts = [
        {"host_name": "esx1", "status": "online", "port_count": "2", "wwpns": "AA;BB"},
        {"host_name": "esx2", "status": "online", "port_count": "2", "wwpns": "CC;DD"},
    ]
    volumes = [
        {"name": "ADC-Data01", "capacity": "1.00TB", "pool": "G3_AND_Pool", "uid": "6005AAA", "status": "online"},
        {"name": "vol_a_snap", "capacity": "100.00GB", "pool": "G3_AND_Pool", "uid": "6005BBB", "status": "online"},
        {"name": "solo_data", "capacity": "50.00GB", "pool": "G3_AND_Pool", "uid": "6005CCC", "status": "online"},
    ]
    maps = [
        {"host_name": "esx1", "vdisk_name": "ADC-Data01", "scsi_id": "0"},
        {"host_name": "esx2", "vdisk_name": "ADC-Data01", "scsi_id": "0"},
        {"host_name": "esx1", "vdisk_name": "solo_data", "scsi_id": "1"},
        {"host_name": "esx1", "vdisk_name": "vol_a_snap", "scsi_id": "2"},
    ]
    result = build_inventory_sync(
        hosts=hosts,
        volumes=volumes,
        maps=maps,
        card_name="Williamston (Anderson)",
        storage_profile="flashsystem_7200",
        storage_hint="v7kand-g3v1",
    )
    assert result["pulled"]["skipped_snaps"] == 1
    assert result["defaults"]["default_pool_or_cpg"] == "G3_AND_Pool"
    assert result["defaults"]["default_card_hint"] == "Williamston (Anderson)"
    names = [expand_lun_batch(lun)[0]["name"] for lun in result["luns"]]
    assert "ADC-Data01" in names
    assert "solo_data" in names
    assert "vol_a_snap" not in names
    adc = next(lun for lun in result["luns"] if expand_lun_batch(lun)[0]["name"] == "ADC-Data01")
    assert set(adc["host_names"]) == {"esx1", "esx2"}
    assert adc["shared"] is True

    group = result["group"]
    assert group["name"] == "Williamston (Anderson)"
    assert group["storage_hint"] == "v7kand-g3v1"
    sources = [v for v in group["volumes"] if v.get("role") != "snap"]
    snaps = [v for v in group["volumes"] if v.get("role") == "snap"]
    assert {v["name"] for v in sources} == {"ADC-Data01", "solo_data"}
    assert len(snaps) == 2
    adc_maps = [m for m in group["maps"] if m["volume"] == "ADC-Data01" and m.get("role") != "snap"]
    assert {m["host"] for m in adc_maps} == {"esx1", "esx2"}
    assert all(m["scsi_id"] == "0" for m in adc_maps)


def test_build_inventory_sync_packs_multi_wwpn_host_rows():
    from launchpad.inventory_sync import build_inventory_sync

    hosts = [
        {"host_name": "AAN1", "status": "online", "port_count": "8", "wwpns": "W1;W2;W3;W4"},
    ]
    result = build_inventory_sync(
        hosts=hosts,
        volumes=[],
        maps=[],
        card_name="Site",
        storage_profile="flashsystem_7200",
        storage_hint="hint",
        allow_empty=True,
    )
    rows = [h for h in result["hosts"] if h["lpar_name"] == "AAN1"]
    assert len(rows) == 2
    assert rows[0]["wwpn1"] == "W1" and rows[0]["wwpn2"] == "W2"
    assert rows[1]["wwpn1"] == "W3" and rows[1]["wwpn2"] == "W4"
