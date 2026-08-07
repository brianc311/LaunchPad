from launchpad.flashsystem_fc import parse_lsconsistgrp
from launchpad.site_lookup_data import (
    filter_lookup_cards,
    inventory_from_command_results,
    match_contingency_groups,
    payload_from_card_cache,
    payload_from_live,
)


def test_parse_lsconsistgrp_colon_table():
    out = "id:name:status\n1:cg_live:empty\n2:cg_b:stopped\n"
    rows = parse_lsconsistgrp(out)
    assert [r["name"] for r in rows] == ["cg_live", "cg_b"]
    assert rows[0]["status"] == "empty"


def test_filter_lookup_cards_keeps_all_named_ssh_cards():
    cards = [
        {"id": 1, "name": "and", "device_profile": "flashsystem_7200"},
        {"id": 2, "name": "3par", "device_profile": "hp_3par_7200"},
        {"id": 3, "name": "", "device_profile": "flashsystem_5200"},
    ]
    out = filter_lookup_cards(cards)
    assert [c["id"] for c in out] == [1, 2]


def test_match_contingency_groups_by_name_or_hint():
    groups = [
        {"id": "a", "name": "Anderson", "location": "IN", "storage_hint": "v7kand-g3v1", "hosts": [], "volumes": [], "maps": []},
        {"id": "b", "name": "Other", "location": "X", "storage_hint": "other", "hosts": [], "volumes": [], "maps": []},
    ]
    matched = match_contingency_groups(groups, card_name="v7kand-g3v1")
    assert [g["id"] for g in matched] == ["a"]


def test_payload_from_card_cache_uses_fc_pools_and_cg_fallback():
    card = {
        "id": 9,
        "name": "v7kand-g3v1",
        "host": "10.0.0.1",
        "model": "IBM FlashSystem 7200",
        "device_profile": "flashsystem_7200",
        "fc_hosts": [{"host_name": "h1", "status": "online", "port_count": "2"}],
        "fc_mappings": [
            {"host_name": "h1", "vdisk_name": "vol1", "scsi_id": "0", "io_group_name": "io_grp0"}
        ],
        "pools": [{"name": "P0", "total_bytes": 1000, "used_bytes": 400, "free_bytes": 600, "used_pct": 40.0}],
    }
    groups = [
        {
            "id": "cg1",
            "name": "v7kand-g3v1",
            "location": "Anderson",
            "storage_hint": "v7kand-g3v1",
            "hosts": [],
            "volumes": [{"name": "vol1"}],
            "maps": [],
        }
    ]
    payload = payload_from_card_cache(card, contingency_groups=groups)
    assert payload["stats"]["hosts"] == 1
    assert payload["stats"]["pools"] == 1
    assert payload["stats"]["consistency_groups"] == 1
    assert payload["pools"][0]["name"] == "P0"
    assert payload["source"] == "cache"
    assert payload["error"] is None


def test_payload_from_live_prefers_live_cgs():
    card = {"id": 1, "name": "site", "host": "1.2.3.4", "model": "FS", "device_profile": "flashsystem_5200"}
    payload = payload_from_live(
        card=card,
        hosts=[{"host_name": "h1", "status": "online", "port_count": "2"}],
        volumes=[{"name": "v1", "uid": "U1", "capacity": "10GB", "pool": "P0", "status": "online"}],
        maps=[{"host_name": "h1", "vdisk_name": "v1", "scsi_id": "0", "io_group_name": "io_grp0"}],
        consist_groups=[{"id": "1", "name": "cg_live", "status": "empty"}],
        pools=[{"name": "P0", "total_bytes": 100, "used_bytes": 50, "free_bytes": 50, "used_pct": 50.0}],
        contingency_groups=[{"id": "x", "name": "site", "location": "", "storage_hint": "site", "hosts": [], "volumes": [], "maps": []}],
        refreshed_at="2026-08-06T12:00:00Z",
    )
    assert payload["source"] == "ssh"
    assert payload["consistency_groups"][0]["name"] == "cg_live"
    assert payload["stats"]["pools"] == 1
    assert payload["refreshed_at"] == "2026-08-06T12:00:00Z"


def test_payload_from_live_falls_back_to_contingency_groups():
    card = {"id": 1, "name": "site", "host": "1.2.3.4", "model": "FS", "device_profile": "flashsystem_5200"}
    payload = payload_from_live(
        card=card,
        hosts=[],
        volumes=[],
        maps=[],
        consist_groups=[],
        pools=[],
        contingency_groups=[{"id": "x", "name": "site", "location": "L", "storage_hint": "site", "hosts": [], "volumes": [], "maps": []}],
        refreshed_at="2026-08-06T12:00:00Z",
    )
    assert payload["source"] == "ssh+cg_fallback"
    assert len(payload["consistency_groups"]) == 1


def test_inventory_from_command_results_parses_hpe_showhost_showvv():
    hosts, volumes, maps = inventory_from_command_results(
        [
            {
                "label": "Hosts - host list",
                "command": "showhost",
                "output": "Id,Name,Persona,Port_WWN\n0,host_a,Generic,10000000AAAA\n",
                "error": None,
            },
            {
                "label": "Volumes - VV list",
                "command": "showvv",
                "output": "Id,Name,State,UsrCPG\n1,vv_a,normal,cpg1\n",
                "error": None,
            },
        ],
        device_profile="hpe_3par_8450",
    )
    assert hosts[0]["host_name"] == "host_a"
    assert volumes[0]["name"] == "vv_a"
    assert volumes[0]["pool"] == "cpg1"
    assert maps == []


def test_payload_from_card_cache_uses_hpe_command_results():
    card = {
        "id": 3,
        "name": "HPE - PLN",
        "host": "10.0.0.2",
        "device_profile": "hpe_3par_8450",
        "fc_hosts": [],
        "fc_mappings": [],
        "pools": [{"name": "cpg1", "used_pct": 10}],
    }
    payload = payload_from_card_cache(
        card,
        command_results=[
            {
                "label": "Hosts - host list",
                "command": "showhost",
                "output": "Id,Name\n0,hpe_host\n",
                "error": None,
            },
            {
                "label": "Volumes - VV list",
                "command": "showvv",
                "output": "Id,Name,State,UsrCPG\n1,vv1,normal,cpg1\n",
                "error": None,
            },
        ],
    )
    assert payload["stats"]["hosts"] == 1
    assert payload["stats"]["volumes"] == 1
    assert payload["hosts"][0]["host_name"] == "hpe_host"
    assert payload["volumes"][0]["name"] == "vv1"
