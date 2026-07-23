from launchpad.volume_find import (
    find_volumes_in_cards,
    is_volume_find_eligible,
    parse_showvv_volumes,
    vendor_for_profile,
    volume_name_matches,
    volumes_from_command_results,
)


def test_volume_name_matches_substring_case_insensitive():
    assert volume_name_matches("pconsps_archvg_1", "ARCHVG") is True
    assert volume_name_matches("pconsps_archvg_1", "nope") is False
    assert volume_name_matches("", "x") is False


def test_eligibility_requires_monitor_ssh_and_profile():
    ibm = {"id": 1, "card_type": "ssh", "device_profile": "flashsystem_7200", "name": "Hartford"}
    assert is_volume_find_eligible(ibm, monitor_on=True) is True
    assert is_volume_find_eligible(ibm, monitor_on=False) is False
    hpe = {"id": 2, "card_type": "ssh", "device_profile": "hpe_3par_8450", "name": "3PAR"}
    assert is_volume_find_eligible(hpe, monitor_on=True) is True
    web = {"id": 3, "card_type": "web", "device_profile": "flashsystem_7200", "name": "Web"}
    assert is_volume_find_eligible(web, monitor_on=True) is False


def test_vendor_for_profile():
    assert vendor_for_profile("flashsystem_7200") == "ibm"
    assert vendor_for_profile("hpe_3par_8450") == "hpe"
    assert vendor_for_profile("hpe_primera_600") == "hpe"


def test_parse_showvv_volumes_basic():
    output = (
        "Id,Name,Rd,Mstr,HostDisp,VV_WWN,Prov,Type,CopyOf,BsId,UsrCPG,SnpCPG\n"
        "0,vv_data_1,----,normal,0,5000ABCD,full,base,--,0,SSD_r5,-\n"
        "1,vv_data_2,----,normal,0,5000ABCE,full,base,--,0,FC_r1,-\n"
    )
    vols = parse_showvv_volumes(output)
    names = {v["name"] for v in vols}
    assert "vv_data_1" in names
    assert "vv_data_2" in names
    assert any(v.get("pool_or_cpg") == "SSD_r5" for v in vols if v["name"] == "vv_data_1")


def test_volumes_from_command_results_ibm_lsvdisk():
    results = [
        {
            "label": "Memory - Volumes %",
            "command": "svcinfo lsvdisk -delim :",
            "output": "id:name:IO_group_id:IO_group_name:status:mdisk_grp_id:mdisk_grp_name:capacity\n"
            "0:pconsps_archvg_1:0:io_grp0:online:0:Pool0:200.00GB\n",
        }
    ]
    vols = volumes_from_command_results(results, "flashsystem_7200")
    assert any(v["name"] == "pconsps_archvg_1" for v in vols)


def test_find_volumes_in_cards_sorted():
    cards = [
        {
            "id": 2,
            "name": "Zebra",
            "card_type": "ssh",
            "device_profile": "flashsystem_7200",
            "command_results": [
                {
                    "command": "svcinfo lsvdisk -delim :",
                    "output": "id:name:mdisk_grp_name\n0:vol_b:Pool0\n1:vol_a:Pool0\n",
                }
            ],
        },
        {
            "id": 1,
            "name": "Alpha",
            "card_type": "ssh",
            "device_profile": "flashsystem_7200",
            "command_results": [
                {
                    "command": "svcinfo lsvdisk -delim :",
                    "output": "id:name:mdisk_grp_name\n0:vol_a:Pool1\n",
                }
            ],
        },
    ]
    monitor = {1: True, 2: True}
    found = find_volumes_in_cards(cards, "vol_", monitor_enabled=monitor, source="cache")
    assert [(m["card_name"], m["volume"]) for m in found] == [
        ("Alpha", "vol_a"),
        ("Zebra", "vol_a"),
        ("Zebra", "vol_b"),
    ]
