from launchpad.flashsystem_fc import parse_lsconsistgrp
from launchpad.site_lookup_data import (
    filter_svc_cards,
    match_contingency_groups,
    payload_from_card_cache,
    payload_from_ssh,
)

SAMPLE_LSCONSISTGRP = """id:name:type:status
0:cg_app:flash:empty
1:cg_db:flash:empty
"""


def test_parse_lsconsistgrp():
    rows = parse_lsconsistgrp(SAMPLE_LSCONSISTGRP)
    assert [r["name"] for r in rows] == ["cg_app", "cg_db"]
    assert rows[0]["status"] == "empty"


def test_filter_svc_cards_keeps_flashsystem_only():
    cards = [
        {"id": 1, "name": "and", "device_profile": "flashsystem_7200"},
        {"id": 2, "name": "3par", "device_profile": "hp_3par_7200"},
    ]
    out = filter_svc_cards(cards)
    assert [c["id"] for c in out] == [1]


def test_match_contingency_groups_by_name_or_hint():
    groups = [
        {"id": "a", "name": "Anderson", "location": "IN", "storage_hint": "v7kand-g3v1", "hosts": [], "volumes": [], "maps": []},
        {"id": "b", "name": "Other", "location": "X", "storage_hint": "other", "hosts": [], "volumes": [], "maps": []},
    ]
    matched = match_contingency_groups(groups, card_name="v7kand-g3v1")
    assert [g["id"] for g in matched] == ["a"]


def test_payload_from_card_cache_uses_fc_and_cg_fallback():
    card = {
        "id": 9,
        "name": "v7kand-g3v1",
        "host": "10.0.0.1",
        "model": "IBM FlashSystem 7200",
        "device_profile": "flashsystem_7200",
        "serial_number": "78E31NF",
        "fc_hosts": [{"host_name": "h1", "status": "online", "port_count": "2"}],
        "fc_mappings": [
            {"host_name": "h1", "vdisk_name": "vol1", "scsi_id": "0", "io_group_name": "io_grp0"}
        ],
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
    assert payload["stats"]["mappings"] == 1
    assert payload["stats"]["cgs"] == 1
    assert payload["source"] == "cache"
    assert payload["volumes"]  # derived from mappings and/or CG volumes
    assert payload["error"] is None


def test_payload_from_ssh_prefers_live_cgs():
    card = {"id": 1, "name": "site", "host": "1.2.3.4", "model": "FS", "device_profile": "flashsystem_5200"}
    payload = payload_from_ssh(
        card=card,
        hosts=[{"host_name": "h1", "status": "online", "port_count": "2"}],
        volumes=[{"name": "v1", "uid": "U1", "capacity": "10GB", "pool": "P0", "status": "online"}],
        maps=[{"host_name": "h1", "vdisk_name": "v1", "scsi_id": "0", "io_group_name": "io_grp0"}],
        consist_groups=[{"id": "1", "name": "cg_live", "status": "empty"}],
        contingency_groups=[{"id": "x", "name": "site", "location": "", "storage_hint": "site", "hosts": [], "volumes": [], "maps": []}],
        refreshed_at="2026-07-22T12:00:00Z",
    )
    assert payload["source"] == "ssh"
    assert payload["stats"]["cgs"] == 1
    assert payload["consistency_groups"][0]["name"] == "cg_live"


def test_payload_from_ssh_falls_back_to_contingency_groups():
    card = {"id": 1, "name": "site", "host": "1.2.3.4", "model": "FS", "device_profile": "flashsystem_5200"}
    payload = payload_from_ssh(
        card=card,
        hosts=[],
        volumes=[],
        maps=[],
        consist_groups=[],
        contingency_groups=[{"id": "x", "name": "site", "location": "L", "storage_hint": "site", "hosts": [], "volumes": [], "maps": []}],
        refreshed_at="2026-07-22T12:00:00Z",
    )
    assert payload["source"] == "ssh+cg_fallback"
    assert payload["stats"]["cgs"] == 1
