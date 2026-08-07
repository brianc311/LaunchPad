from launchpad.storage_presets import HP_3PAR_COMMANDS, HPE_PRIMERA_COMMANDS, preset_commands_for_profile
from launchpad.volume_find import (
    ANDERSON_DEFAULT_HOST,
    ANDERSON_TARGET_NAME,
    anderson_rename_plan,
    find_hosts_in_cards,
    find_volumes_in_cards,
    host_name_matches,
    hosts_from_card,
    is_volume_find_eligible,
    is_williamston_anderson_name,
    normalize_site_host,
    parse_showhost_hosts,
    parse_showvv_volumes,
    site_ip_href,
    vendor_for_profile,
    volume_name_matches,
    volumes_from_command_results,
)


def test_normalize_site_host():
    assert normalize_site_host("  https://10.244.25.158/  ") == "10.244.25.158"
    assert normalize_site_host("http://host.example") == "host.example"
    assert normalize_site_host("10.1.2.3") == "10.1.2.3"
    assert normalize_site_host("   ") == ""


def test_site_ip_href():
    assert site_ip_href("10.244.25.158") == "https://10.244.25.158"
    assert site_ip_href("") == ""


def test_williamston_anderson_name_match():
    assert is_williamston_anderson_name("WILLIAMSTON (ANDERSON) SC") is True
    assert is_williamston_anderson_name("WILLIAMSTON  (ANDERSON)  SC") is True
    assert is_williamston_anderson_name("Anderson, SC") is False


def test_anderson_rename_plan_sets_default_host_when_empty():
    plan = anderson_rename_plan(
        [{"id": 11, "name": "WILLIAMSTON (ANDERSON) SC", "host": ""}]
    )
    assert plan == {
        "card_id": 11,
        "new_name": ANDERSON_TARGET_NAME,
        "new_host": ANDERSON_DEFAULT_HOST,
    }


def test_anderson_rename_plan_keeps_host_and_skips_conflict():
    assert anderson_rename_plan(
        [{"id": 11, "name": "WILLIAMSTON (ANDERSON) SC", "host": "10.9.9.9"}]
    )["new_host"] == "10.9.9.9"
    assert (
        anderson_rename_plan(
            [
                {"id": 1, "name": "Anderson, SC", "host": "1.1.1.1"},
                {"id": 11, "name": "WILLIAMSTON (ANDERSON) SC", "host": ""},
            ]
        )
        is None
    )
    assert anderson_rename_plan([{"id": 11, "name": "Anderson, SC", "host": "x"}]) is None


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
    # Ownership-only tables have no State; status stays empty (Volume Find still works).
    assert all(not (v.get("status") or "") for v in vols)


def test_parse_showvv_volumes_prefers_state_over_mstr():
    output = (
        "Id,Name,Rd,Mstr,State,UsrCPG\n"
        "0,vv_bad,rw,---,degraded,SSD_r5\n"
        "1,vv_ok,rw,3/1/0,normal,FC_r1\n"
    )
    vols = parse_showvv_volumes(output)
    by_name = {v["name"]: v for v in vols}
    assert by_name["vv_bad"]["status"] == "degraded"
    assert by_name["vv_bad"]["mstr"] == "---"
    assert by_name["vv_ok"]["status"] == "normal"


def test_parse_showvv_volumes_whitespace_table():
    output = (
        "Id Name     Rd   Mstr   HostDisp VV_WWN   Prov Type CopyOf BsId UsrCPG SnpCPG\n"
        "0  vv_data_1 ---- normal 0        5000ABCD full base --     0    SSD_r5 -\n"
        "1  vv_data_2 ---- normal 0        5000ABCE full base --     0    FC_r1  -\n"
    )
    vols = parse_showvv_volumes(output)
    by_name = {v["name"]: v for v in vols}
    assert "vv_data_1" in by_name
    assert "vv_data_2" in by_name
    assert by_name["vv_data_1"]["pool_or_cpg"] == "SSD_r5"
    assert by_name["vv_data_2"]["pool_or_cpg"] == "FC_r1"


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


def test_hpe_presets_include_showvv():
    assert any("showvv" in cmd for _, cmd in HP_3PAR_COMMANDS)
    assert any("showvv" in cmd for _, cmd in HPE_PRIMERA_COMMANDS)
    cmds = preset_commands_for_profile("hpe_3par_8450")
    assert any("showvv" in cmd for _, cmd in cmds)


def test_find_volumes_in_cards_sorted():
    cards = [
        {
            "id": 2,
            "name": "Zebra",
            "host": "10.0.0.2",
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
            "host": "10.0.0.1",
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
    assert all(m["host"] == "10.0.0.1" for m in found if m["card_name"] == "Alpha")
    assert all(m["host"] == "10.0.0.2" for m in found if m["card_name"] == "Zebra")


def test_host_name_matches_substring_case_insensitive():
    assert host_name_matches("woo_esx_cluster", "ESX") is True
    assert host_name_matches("woo_esx_cluster", "nope") is False


def test_parse_showhost_hosts_basic():
    output = (
        "Id,Name,Persona,Port_WWN\n"
        "0,woo_esx_cluster,Generic,-,\n"
        "1,other_host,Generic,100000109BEE31E2,\n"
    )
    rows = parse_showhost_hosts(output)
    names = {r["host_name"] for r in rows}
    assert "woo_esx_cluster" in names
    assert "other_host" in names
    other = next(r for r in rows if r["host_name"] == "other_host")
    assert other["type"] == "Generic"
    assert other["port_count"] == "1"


def test_parse_showhost_hosts_skips_preamble_and_composite_wwn_column():
    output = (
        "--------------- Hosts ---------------\n"
        "Id,Name,Persona,Port_WWN/iSCSI_Name/IPAddr\n"
        "0,ESX_hpew202sms01,Generic-ALUA,100000051EC2AAAA\n"
        "0,ESX_hpew202sms01,Generic-ALUA,100000051EC2BBBB\n"
    )
    rows = parse_showhost_hosts(output)
    assert len(rows) == 1
    assert rows[0]["host_name"] == "ESX_hpew202sms01"
    assert rows[0]["type"] == "Generic-ALUA"
    assert rows[0]["port_count"] == "2"
    assert "100000051EC2AAAA" in rows[0]["wwpns"]
    assert "100000051EC2BBBB" in rows[0]["wwpns"]


def test_parse_showvv_volumes_dashed_headers_and_preamble():
    output = (
        "---- Virtual Volumes ----\n"
        "Id,-Name-,-State-,-UsrCPG-,-VSize_MB-\n"
        "1,vv_prod,normal,cpg_a,10240\n"
    )
    vols = parse_showvv_volumes(output)
    assert vols[0]["name"] == "vv_prod"
    assert vols[0]["pool_or_cpg"] == "cpg_a"
    assert vols[0]["status"] == "normal"
    assert "10240" in vols[0]["capacity"]


def test_parse_showhost_pathsum_derives_online_offline_degraded():
    from launchpad.volume_find import (
        apply_pathsum_status_to_hosts,
        parse_showhost_pathsum_status,
    )

    output = (
        "Id,Name,Persona,Host_WWN,Port,Host_Paths\n"
        "0,esx_online,VMware,10000000AAAA,1:2:1,1--- ----\n"
        "0,esx_online,VMware,10000000BBBB,0:2:1,1--- ----\n"
        "1,esx_degraded,VMware,10000000CCCC,1:2:2,1--- ----\n"
        "1,esx_degraded,VMware,10000000DDDD,---,---- ----\n"
        "2,esx_offline,Generic,10000000EEEE,---,---- ----\n"
    )
    status_by_host = parse_showhost_pathsum_status(output)
    assert status_by_host["esx_online"] == "online"
    assert status_by_host["esx_degraded"] == "degraded"
    assert status_by_host["esx_offline"] == "offline"

    hosts = [
        {"host_name": "esx_online", "status": "", "type": "VMware"},
        {"host_name": "esx_degraded", "status": "", "type": "VMware"},
        {"host_name": "esx_offline", "status": "", "type": "Generic"},
        {"host_name": "other", "status": "kept", "type": "X"},
    ]
    apply_pathsum_status_to_hosts(hosts, status_by_host)
    assert hosts[0]["status"] == "online"
    assert hosts[1]["status"] == "degraded"
    assert hosts[2]["status"] == "offline"
    assert hosts[3]["status"] == "kept"


def test_hosts_from_card_ibm_fc_hosts():
    card = {
        "id": 1,
        "name": "Woodland Hills, CA",
        "card_type": "ssh",
        "device_profile": "flashsystem_9500",
        "host": "10.244.66.227",
        "fc_hosts": [
            {"host_name": "woo_esx_cluster", "wwpns": "100000109BEE31E2"},
        ],
        "command_results": [],
    }
    hosts = hosts_from_card(card)
    assert hosts[0]["host_name"] == "woo_esx_cluster"
    assert "100000109BEE31E2" in hosts[0]["wwpns"]


def test_find_hosts_in_cards_sorted():
    cards = [
        {
            "id": 2,
            "name": "Zebra",
            "card_type": "ssh",
            "device_profile": "flashsystem_7200",
            "host": "1.1.1.1",
            "fc_hosts": [{"host_name": "b_host", "wwpns": ""}],
        },
        {
            "id": 1,
            "name": "Alpha",
            "card_type": "ssh",
            "device_profile": "flashsystem_7200",
            "host": "2.2.2.2",
            "fc_hosts": [{"host_name": "a_host", "wwpns": ""}],
        },
    ]
    monitor = {1: True, 2: True}
    found = find_hosts_in_cards(cards, "host", monitor_enabled=monitor, source="cache")
    assert [m["card_name"] for m in found] == ["Alpha", "Zebra"]
    assert found[0]["host_name"] == "a_host"
