from launchpad.contingency_groups_data import (
    CONTINGENCY_GROUPS_SETTING,
    delete_group,
    filter_fc_card,
    group_matches_host,
    group_matches_volume,
    normalize_group,
    normalize_groups,
    new_group_id,
    seed_contingency_groups,
    upsert_group,
)


def test_setting_key():
    assert CONTINGENCY_GROUPS_SETTING == "contingency_groups"


def test_seeds_include_three_sites():
    seeds = seed_contingency_groups()
    ids = {g["id"] for g in seeds}
    assert ids == {"hartford-ct", "houston-tx", "windsor"}
    hartford = next(g for g in seeds if g["id"] == "hartford-ct")
    assert len(hartford["hosts"]) == 3
    assert len(hartford["volumes"]) == 3
    assert any(m["scsi_id"] == "0" for m in hartford["maps"])
    houston = next(g for g in seeds if g["id"] == "houston-tx")
    assert {h["name"] for h in houston["hosts"]} == {
        "pen-houesx-vm03",
        "pen-houesx-vm04",
    }
    assert len(houston["volumes"]) == 4
    assert all(volume["capacity"] == "" for volume in houston["volumes"])
    assert all(volume["pool"] == "" for volume in houston["volumes"])
    windsor = next(g for g in seeds if g["id"] == "windsor")
    vm01 = next(h for h in windsor["hosts"] if h["name"] == "PEN_WINESX_VM01")
    assert "51402EC012CFD072" in vm01["wwpns"]
    vol1 = next(v for v in windsor["volumes"] if v["name"] == "WIN_ESX_DataStore_1")
    assert vol1["uid"].startswith("60050768128000A758")


def test_normalize_strips_and_keeps_empty_wwpn_uid():
    g = normalize_group(
        {
            "id": "x",
            "name": " X ",
            "hosts": [{"name": "h1", "wwpns": ["", " AA "]}],
            "volumes": [{"name": "v1", "uid": ""}],
            "maps": [{"volume": "v1", "host": "h1", "scsi_id": 0}],
        }
    )
    assert g is not None
    assert g["name"] == "X"
    assert g["hosts"][0]["wwpns"] == ["AA"]
    assert g["volumes"][0]["uid"] == ""
    assert g["maps"][0]["scsi_id"] == "0"


def test_upsert_and_delete():
    groups = normalize_groups(seed_contingency_groups())
    extra = normalize_group(
        {
            "id": "lab-1",
            "name": "Lab",
            "hosts": [],
            "volumes": [],
            "maps": [],
        }
    )
    groups = upsert_group(groups, extra)
    assert any(g["id"] == "lab-1" for g in groups)
    groups = delete_group(groups, "lab-1")
    assert all(g["id"] != "lab-1" for g in groups)


def test_match_helpers():
    seeds = {g["id"]: g for g in seed_contingency_groups()}
    assert group_matches_host(seeds["houston-tx"], "PEN-HOUESX-VM03")
    assert group_matches_volume(seeds["houston-tx"], "houston_esx1_datastore_2")
    assert group_matches_host(
        seeds["windsor"], "other", wwpns_haystack="51402EC012CFD072"
    )
    assert not group_matches_host(seeds["houston-tx"], "nope")


def test_new_group_id_unique():
    existing = seed_contingency_groups()
    gid = new_group_id("Houston, TX", existing)
    assert gid != "houston-tx"
    assert gid


def test_filter_fc_card_keeps_mapping_when_host_matches_by_wwpn_only():
    group = {
        "id": "g1",
        "hosts": [{"name": "group-host", "wwpns": ["51402EC012CFD072"]}],
        "volumes": [],
    }
    card = {
        "fc_hosts": [],
        "fc_mappings": [
            {
                "host_name": "alias-not-in-group",
                "vdisk_name": "other_volume",
                "host_wwpns": "51402EC012CFD072",
            }
        ],
    }
    filtered = filter_fc_card(card, group)
    assert len(filtered["fc_mappings"]) == 1
    assert filtered["fc_mappings"][0]["host_name"] == "alias-not-in-group"
