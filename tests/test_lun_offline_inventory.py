from launchpad.lun_offline_inventory import (
    is_lun_offline_inventory_eligible,
    normalize_store,
    record_snapshot_error,
    snapshot_from_command_results,
    upsert_snapshot,
)


def test_eligible_requires_monitor_and_svc_profile():
    assert is_lun_offline_inventory_eligible(
        {"device_profile": "flashsystem_7200"}, monitor_on=True
    )
    assert not is_lun_offline_inventory_eligible(
        {"device_profile": "flashsystem_7200"}, monitor_on=False
    )
    assert not is_lun_offline_inventory_eligible(
        {"device_profile": "hpe_3par_8200"}, monitor_on=True
    )


def test_snapshot_host_lookup_skips_lshostvdiskmap_before_lshost():
    results = [
        {
            "label": "FC - Host LUN Maps",
            "command": "svcinfo lshostvdiskmap -delim :",
            "output": "host_name:vdisk_name:SCSI_id\nwronghost:vol1:3",
        },
        {
            "label": "FC - Hosts",
            "command": "svcinfo lshost -delim :",
            "output": "id:name:port_count:iogrp_count:status:WWPN\n0:esx01:1:1:online:AABBCCDDEEFF0011",
        },
    ]
    snap = snapshot_from_command_results(
        card_id=8,
        site_name="Test Site",
        host="10.0.0.8",
        device_profile="flashsystem_5200",
        command_results=results,
    )
    lpar_names = [h.get("lpar_name") for h in snap["hosts"]]
    assert "esx01" in lpar_names
    assert "wronghost" not in lpar_names


def test_snapshot_from_command_results_parses_hosts_and_volumes():
    results = [
        {
            "label": "FC - Hosts",
            "command": "svcinfo lshost -delim :",
            "output": "id:name:port_count:iogrp_count:status:WWPN\n0:esx01:1:1:online:AABBCCDDEEFF0011",
        },
        {
            "label": "Memory - Volumes %",
            "command": "svcinfo lsvdisk -delim :",
            "output": "id:name:IO_group_id:IO_group_name:status:mdisk_grp_name:capacity\n0:vol1:0:io_grp0:online:Pool1:10.00GB",
        },
    ]
    snap = snapshot_from_command_results(
        card_id=7,
        site_name="Pendergrass, GA",
        host="10.0.0.7",
        device_profile="flashsystem_5200",
        command_results=results,
        updated_at="2026-07-30T12:00:00+00:00",
    )
    assert snap["card_id"] == 7
    assert snap["site_name"] == "Pendergrass, GA"
    assert snap["updated_at"] == "2026-07-30T12:00:00+00:00"
    assert snap["last_error"] in (None, "")
    assert any(h.get("lpar_name") == "esx01" for h in snap["hosts"])
    assert any(v.get("name") == "vol1" for v in snap["volumes"])


def test_failed_refresh_keeps_prior_hosts():
    store = upsert_snapshot(
        {},
        {
            "card_id": 1,
            "site_name": "Hartford, CT",
            "host": "10.0.0.1",
            "device_profile": "flashsystem_7200",
            "updated_at": "2026-07-30T10:00:00+00:00",
            "hosts": [{"lpar_name": "keepme", "wwpn1": "", "wwpn2": ""}],
            "volumes": [{"name": "v1", "pool": "P", "capacity": "1GB", "status": "online"}],
            "last_error": None,
            "last_error_at": None,
        },
    )
    store = record_snapshot_error(
        store, card_id=1, error="SSH timed out", site_name="Hartford, CT"
    )
    row = store["1"]
    assert row["hosts"][0]["lpar_name"] == "keepme"
    assert row["volumes"][0]["name"] == "v1"
    assert row["updated_at"] == "2026-07-30T10:00:00+00:00"
    assert "timed out" in row["last_error"].lower()
    assert row["last_error_at"]


def test_upsert_replaces_same_card():
    store = upsert_snapshot({}, {"card_id": 2, "site_name": "A", "hosts": [], "volumes": []})
    store = upsert_snapshot(
        store,
        {
            "card_id": 2,
            "site_name": "Windsor, WI",
            "hosts": [{"lpar_name": "h1"}],
            "volumes": [],
            "updated_at": "2026-07-30T11:00:00+00:00",
        },
    )
    assert list(store.keys()) == ["2"]
    assert store["2"]["site_name"] == "Windsor, WI"
    assert store["2"]["hosts"][0]["lpar_name"] == "h1"


def test_normalize_store_accepts_list_or_map():
    assert normalize_store({"3": {"card_id": 3, "hosts": [], "volumes": []}})["3"]["card_id"] == 3
    assert normalize_store([{"card_id": 4, "hosts": [], "volumes": []}])["4"]["card_id"] == 4
