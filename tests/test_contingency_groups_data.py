from launchpad.contingency_groups_data import (
    CONTINGENCY_GROUPS_SETTING,
    delete_group,
    filter_fc_card,
    generate_snap_rows,
    group_matches_host,
    group_matches_volume,
    normalize_group,
    normalize_groups,
    new_group_id,
    seed_contingency_groups,
    snap_pairs,
    snap_volume_name,
    source_volumes,
    upsert_group,
    validate_wizard_step1,
    validate_wizard_step2,
)


def test_setting_key():
    assert CONTINGENCY_GROUPS_SETTING == "contingency_groups"


def test_seeds_include_three_sites():
    seeds = seed_contingency_groups()
    ids = {g["id"] for g in seeds}
    assert ids == {"hartford-ct", "houston-tx", "windsor"}
    hartford = next(g for g in seeds if g["id"] == "hartford-ct")
    assert len(hartford["hosts"]) == 3
    hartford_sources = [v for v in hartford["volumes"] if v.get("role") != "snap"]
    assert len(hartford_sources) == 3
    assert len(hartford["volumes"]) == 6
    assert any(m["scsi_id"] == "0" for m in hartford["maps"])
    houston = next(g for g in seeds if g["id"] == "houston-tx")
    assert {h["name"] for h in houston["hosts"]} == {
        "pen-houesx-vm03",
        "pen-houesx-vm04",
    }
    assert len(houston["volumes"]) == 8
    houston_sources = [v for v in houston["volumes"] if v.get("role") != "snap"]
    assert len(houston_sources) == 4
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


def test_snap_volume_name():
    assert snap_volume_name("HRDC_ESXI_DS01") == "HRDC_ESXI_DS01_snap"
    assert snap_volume_name("HRDC_ESXI_DS01_snap") == "HRDC_ESXI_DS01_snap"


def test_generate_snap_rows_idempotent():
    group = normalize_group(
        {
            "id": "lab",
            "name": "Lab",
            "hosts": [{"name": "h1"}],
            "volumes": [{"name": "VOL1", "pool": "P0", "capacity": "4.00 TiB"}],
            "maps": [{"volume": "VOL1", "host": "h1", "scsi_id": "0"}],
        }
    )
    once = generate_snap_rows(group)
    twice = generate_snap_rows(once)
    snaps = [v for v in once["volumes"] if v.get("role") == "snap"]
    assert len(snaps) == 1
    assert snaps[0]["name"] == "VOL1_snap"
    assert snaps[0]["source_volume"] == "VOL1"
    assert snaps[0]["pool"] == "P0"
    assert len([v for v in twice["volumes"] if v.get("role") == "snap"]) == 1
    snap_maps = [m for m in once["maps"] if m.get("role") == "snap"]
    assert snap_maps == [
        {"volume": "VOL1_snap", "host": "h1", "scsi_id": "0", "role": "snap"}
    ]


def test_seeds_include_snap_rows():
    seeds = {g["id"]: g for g in seed_contingency_groups()}
    hartford = seeds["hartford-ct"]
    assert any(v["name"] == "HRDC_ESXI_DS01_snap" for v in hartford["volumes"])
    assert any(
        m.get("role") == "snap" and m["volume"] == "HRDC_ESXI_DS01_snap"
        for m in hartford["maps"]
    )
    houston = seeds["houston-tx"]
    assert any(v["name"].endswith("_snap") for v in houston["volumes"])


def test_source_volumes_exclude_snaps():
    hartford = next(g for g in seed_contingency_groups() if g["id"] == "hartford-ct")
    sources = source_volumes(hartford)
    assert sources
    assert all(not str(v["name"]).endswith("_snap") for v in sources)
    assert all(str(v.get("role") or "source") != "snap" for v in sources)


def test_snap_pairs_link_source_to_target():
    hartford = next(g for g in seed_contingency_groups() if g["id"] == "hartford-ct")
    pairs = snap_pairs(hartford)
    assert pairs
    for pair in pairs:
        assert pair["target"] is not None
        assert pair["target"]["name"] == f"{pair['source']['name']}_snap"


def test_validate_step1_requires_pool_capacity():
    group = {
        "volumes": [{"name": "V1", "role": "source", "pool": "", "capacity": ""}],
        "maps": [],
    }
    warnings = validate_wizard_step1(group)
    assert warnings


def test_validate_step2_requires_targets():
    group = {
        "volumes": [{"name": "V1", "role": "source", "pool": "P0", "capacity": "4.00 TiB"}],
        "maps": [],
    }
    assert validate_wizard_step2(group)


def test_generate_snap_rows_keeps_linked_live_snap_name():
    group = {
        "id": "lab",
        "name": "Lab",
        "location": "Lab",
        "storage_hint": "",
        "notes": "",
        "updated_at": "",
        "hosts": [{"name": "h1", "status": "Online", "host_type": "Generic", "port_count": 2, "protocol": "SCSI", "wwpns": []}],
        "volumes": [
            {
                "name": "volA",
                "capacity": "1.00TB",
                "pool": "Pool1",
                "uid": "UID-SRC",
                "protocol": "SCSI",
                "role": "source",
                "source_volume": "",
            },
            {
                "name": "volA_Snap1",
                "capacity": "1.00TB",
                "pool": "Pool1",
                "uid": "UID-LIVE",
                "protocol": "SCSI",
                "role": "snap",
                "source_volume": "volA",
            },
        ],
        "maps": [
            {"volume": "volA", "host": "h1", "scsi_id": "0", "role": "source"},
        ],
    }
    out = generate_snap_rows(group)
    snaps = [v for v in out["volumes"] if v.get("role") == "snap"]
    assert len(snaps) == 1
    assert snaps[0]["name"] == "volA_Snap1"
    assert snaps[0]["uid"] == "UID-LIVE"
    assert "volA_snap" not in {v["name"] for v in out["volumes"]}
    snap_maps = [m for m in out["maps"] if m.get("role") == "snap"]
    assert snap_maps
    assert all(m["volume"] == "volA_Snap1" for m in snap_maps)


def test_generate_snap_rows_still_creates_placeholder_when_no_live_snap():
    group = {
        "id": "lab",
        "name": "Lab",
        "location": "Lab",
        "storage_hint": "",
        "notes": "",
        "updated_at": "",
        "hosts": [],
        "volumes": [
            {
                "name": "solo",
                "capacity": "50GB",
                "pool": "P",
                "uid": "U1",
                "protocol": "SCSI",
                "role": "source",
                "source_volume": "",
            }
        ],
        "maps": [{"volume": "solo", "host": "h1", "scsi_id": "1", "role": "source"}],
    }
    out = generate_snap_rows(group)
    assert any(v["name"] == "solo_snap" and v.get("role") == "snap" for v in out["volumes"])


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
