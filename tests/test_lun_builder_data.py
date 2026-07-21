from launchpad.lun_builder_data import (
    LUN_BUILDS_SETTING,
    expand_lun_batch,
    normalize_build,
    seed_lun_builder_templates,
    supports_live_run,
    validate_build_for_preview,
)


def test_setting_key():
    assert LUN_BUILDS_SETTING == "lun_builds"


def test_expand_lun_batch_names():
    rows = expand_lun_batch(
        {
            "purpose": "ora1vg",
            "count": 3,
            "size": "100GB",
            "pool_or_cpg": "P0",
            "storage_profile": "flashsystem_5200",
            "host_names": ["h1"],
            "shared": True,
        }
    )
    assert [r["name"] for r in rows] == ["ora1vg_1", "ora1vg_2", "ora1vg_3"]


def test_expand_single_keeps_purpose_name():
    rows = expand_lun_batch(
        {
            "purpose": "caavg_private",
            "count": 1,
            "size": "10GB",
            "pool_or_cpg": "P0",
            "storage_profile": "flashsystem_5200",
        }
    )
    assert rows[0]["name"] == "caavg_private"


def test_expand_single_host_keeps_explicit_live_name():
    rows = expand_lun_batch(
        {
            "purpose": "pandap01_0",
            "count": 1,
            "size": "70GB",
            "pool_or_cpg": "G3_AND_Pool",
            "storage_profile": "flashsystem_7200",
            "host_names": ["pandap01"],
            "shared": False,
            "name_prefix": "",
        }
    )
    assert rows[0]["name"] == "pandap01_0"


def test_expand_single_host_keeps_arbitrary_exact_live_name():
    rows = expand_lun_batch(
        {
            "purpose": "pconbt1_2_archive_dt1",
            "count": 1,
            "size": "100GB",
            "pool_or_cpg": "G3_AND_Pool",
            "storage_profile": "flashsystem_7200",
            "host_names": ["tconbt20"],
            "shared": False,
            "name_prefix": "",
        }
    )
    assert rows[0]["name"] == "pconbt1_2_archive_dt1"


def test_expand_infers_pcon_prefix_from_host():
    rows = expand_lun_batch(
        {
            "purpose": "root",
            "count": 3,
            "size": "50GB",
            "pool_or_cpg": "P0",
            "storage_profile": "flashsystem_5200",
            "host_names": ["pconsps3"],
            "shared": False,
            "cluster": "SPS",
        }
    )
    assert [r["name"] for r in rows] == [
        "pconsps3_root_1",
        "pconsps3_root_2",
        "pconsps3_root_3",
    ]


def test_expand_prefixed_host_root_names():
    rows = expand_lun_batch(
        {
            "purpose": "root",
            "count": 3,
            "size": "50GB",
            "pool_or_cpg": "P0",
            "storage_profile": "flashsystem_5200",
            "host_names": ["pconsps3"],
            "shared": False,
            "cluster": "SPS",
            "name_prefix": "pcon",
        }
    )
    assert [r["name"] for r in rows] == [
        "pconsps3_root_1",
        "pconsps3_root_2",
        "pconsps3_root_3",
    ]


def test_expand_prefixed_shared_cluster_names():
    rows = expand_lun_batch(
        {
            "purpose": "ora1vg",
            "count": 2,
            "size": "100GB",
            "pool_or_cpg": "P0",
            "storage_profile": "flashsystem_5200",
            "host_names": ["pconsps3", "pconsps4"],
            "shared": True,
            "cluster": "SPS",
            "name_prefix": "pcon",
        }
    )
    assert [r["name"] for r in rows] == ["pconsps_ora1vg_1", "pconsps_ora1vg_2"]


def test_supports_live_run_families():
    assert supports_live_run("flashsystem_5200") is True
    assert supports_live_run("hpe_3par_8200") is True
    assert supports_live_run("ibm_ds8884") is False
    assert supports_live_run("ibm_xiv_gen3") is False


def test_validate_build_requires_lun_fields():
    build = normalize_build(
        {
            "id": "x",
            "name": "Lab",
            "hosts": [],
            "luns": [{"purpose": "", "count": 1, "size": "", "pool_or_cpg": ""}],
        }
    )
    assert validate_build_for_preview(build)


def test_normalize_build_keeps_default_fields():
    build = normalize_build(
        {
            "id": "lab",
            "name": "Lab",
            "default_storage_profile": "flashsystem_5200",
            "default_pool_or_cpg": "Pool0",
            "default_card_hint": "cardA",
            "hosts": [],
            "luns": [],
        }
    )
    assert build["default_storage_profile"] == "flashsystem_5200"
    assert build["default_pool_or_cpg"] == "Pool0"
    assert build["default_card_hint"] == "cardA"


def test_normalize_keeps_done_flags():
    build = normalize_build(
        {
            "id": "lab",
            "name": "Lab",
            "hosts": [{"lpar_name": "h1", "done": True}],
            "luns": [{"purpose": "root", "count": 1, "size": "50GB", "done": True}],
        }
    )
    assert build["hosts"][0]["done"] is True
    assert build["luns"][0]["done"] is True


def test_normalize_keeps_plan_done_map():
    build = normalize_build(
        {
            "id": "lab",
            "name": "Lab",
            "hosts": [],
            "luns": [],
            "plan_done": {"pconsps3_root_1": True, "pconsps3_root_2": False, "": True},
        }
    )
    assert build["plan_done"] == {"pconsps3_root_1": True}


def test_normalize_keeps_command_done_map():
    build = normalize_build(
        {
            "id": "lab",
            "name": "Lab",
            "hosts": [],
            "luns": [],
            "command_done": {
                "vol_a\ncmd1\ncmd2": True,
                "stale\ncmd": False,
                "": True,
            },
        }
    )
    assert build["command_done"] == {"vol_a\ncmd1\ncmd2": True}


def test_hartford_template_identity():
    templates = seed_lun_builder_templates()
    assert len(templates) == 6
    hartford = next(t for t in templates if t["id"] == "template-hartford-ct")
    assert hartford["id"] == "template-hartford-ct"
    assert hartford["name"] == "Hartford, CT (Template)"
    assert hartford["is_template"] is True
    assert hartford["location"] == "Hartford, CT"
    assert normalize_build(hartford)["is_template"] is True


def test_hartford_hosts_cover_six_lpars():
    templates = seed_lun_builder_templates()
    hartford = next(t for t in templates if t["id"] == "template-hartford-ct")
    names = {h["lpar_name"] for h in hartford["hosts"]}
    assert names == {
        "pconsps3",
        "pconsps4",
        "pconmfs3",
        "pconmfs4",
        "pconbt3",
        "pconbt4",
    }
    assert len(hartford["hosts"]) == 24
    first = next(h for h in hartford["hosts"] if h["lpar_name"] == "pconsps3")
    assert first["wwpn1"].lower().startswith("c05076")
    assert first["remote_lpar"].startswith("pconvio")


def test_hartford_lun_batches_and_blank_profile_pool():
    templates = seed_lun_builder_templates()
    hartford = next(t for t in templates if t["id"] == "template-hartford-ct")
    luns = hartford["luns"]
    assert len(luns) == 21  # 6 root batches + 15 shared batches
    assert all(not str(lun.get("storage_profile") or "").strip() for lun in luns)
    assert all(not str(lun.get("pool_or_cpg") or "").strip() for lun in luns)
    assert all(lun.get("name_prefix") == "pcon" for lun in luns)
    ora = [lun for lun in luns if lun["purpose"] == "ora1vg"]
    assert {lun["cluster"]: lun["count"] for lun in ora} == {
        "SPS": 7,
        "MFS": 7,
        "BT": 14,
    }
    expanded = [name for lun in luns for name in (r["name"] for r in expand_lun_batch(lun))]
    assert len(expanded) == len(set(expanded))
    assert "pconsps3_root_1" in expanded
    assert "pconsps_ora1vg_1" in expanded
    assert "pconmfs_ora1vg_1" in expanded
    assert "pconbt_ora1vg_1" in expanded


def _jupiter_template() -> dict:
    return next(
        t for t in seed_lun_builder_templates() if t["id"] == "template-jupiter-fl"
    )


def test_jupiter_template_identity_and_defaults():
    jup = _jupiter_template()
    assert jup["name"] == "Jupiter, FL (Template)"
    assert jup["location"] == "Jupiter, FL"
    assert jup["is_template"] is True
    assert jup["default_storage_profile"] == "flashsystem_5200"
    assert jup["default_pool_or_cpg"] == "JUP_G3_Pool"
    assert jup["default_card_hint"] == "Jupiter, FL"
    assert normalize_build(jup)["is_template"] is True


def test_jupiter_hosts_blank_wwpns():
    jup = _jupiter_template()
    names = {h["lpar_name"] for h in jup["hosts"]}
    assert names == {
        "pjupvio01a",
        "pjupvio01b",
        "pjupvio02a",
        "pjupvio02b",
        "pjupvio03a",
        "pjupvio03b",
        "pjupvio04a",
        "pjupvio04b",
        "pjupmhcdb2",
        "pjupmhcdg2",
        "pjupres01",
    }
    assert len(jup["hosts"]) == 11
    assert all(h.get("wwpn1") == "" and h.get("wwpn2") == "" for h in jup["hosts"])
    assert all(h.get("type") == "Generic" for h in jup["hosts"])


def test_jupiter_lun_batches_profile_and_names():
    jup = _jupiter_template()
    luns = jup["luns"]
    # 8 vio root + 2 db root + 2 db data + 1 res data = 13
    assert len(luns) == 13
    assert all(lun.get("name_prefix") == "pjup" for lun in luns)
    assert all(lun.get("storage_profile") == "flashsystem_5200" for lun in luns)
    assert all(lun.get("pool_or_cpg") == "JUP_G3_Pool" for lun in luns)
    assert all(lun.get("card_hint") == "Jupiter, FL" for lun in luns)

    vio_roots = [
        lun
        for lun in luns
        if lun["purpose"] == "root" and lun["host_names"][0].startswith("pjupvio")
    ]
    assert len(vio_roots) == 8
    assert all(lun["count"] == 2 and lun["size"] == "100GB" for lun in vio_roots)

    db2_root = next(
        lun
        for lun in luns
        if lun["purpose"] == "root" and lun["host_names"] == ["pjupmhcdb2"]
    )
    assert db2_root["count"] == 3 and db2_root["size"] == "50GB"
    db2_data = next(
        lun
        for lun in luns
        if lun["purpose"] == "data" and lun["host_names"] == ["pjupmhcdb2"]
    )
    assert db2_data["count"] == 9 and db2_data["size"] == "100GB"

    res = next(lun for lun in luns if lun["host_names"] == ["pjupres01"])
    assert res["purpose"] == "data" and res["count"] == 5 and res["size"] == "100GB"

    expanded = [
        name for lun in luns for name in (r["name"] for r in expand_lun_batch(lun))
    ]
    assert len(expanded) == len(set(expanded))
    assert "pjupvio01a_root_1" in expanded
    assert "pjupmhcdb2_root_1" in expanded
    assert "pjupmhcdb2_data_1" in expanded
    assert "pjupres01_data_1" in expanded


def _pendergrass_template() -> dict:
    return next(
        t for t in seed_lun_builder_templates() if t["id"] == "template-pendergrass-ga"
    )


def test_pendergrass_template_identity_and_defaults():
    pen = _pendergrass_template()
    assert pen["name"] == "Pendergrass, GA (Template)"
    assert pen["location"] == "Pendergrass, GA"
    assert pen["is_template"] is True
    assert pen["default_storage_profile"] == "flashsystem_5200"
    assert pen["default_pool_or_cpg"] == "G3_PEN_Pool1"
    assert pen["default_card_hint"] == "Pendergrass, GA"
    assert normalize_build(pen)["is_template"] is True


def test_pendergrass_hosts_blank_wwpns():
    pen = _pendergrass_template()
    names = {h["lpar_name"] for h in pen["hosts"]}
    assert names == {"pen_penesx_vm05", "pen_penesx_vm06"}
    assert len(pen["hosts"]) == 2
    assert all(h.get("wwpn1") == "" and h.get("wwpn2") == "" for h in pen["hosts"])
    assert all(h.get("type") == "Generic" for h in pen["hosts"])


def test_pendergrass_lun_batches_shared_and_names():
    pen = _pendergrass_template()
    luns = pen["luns"]
    both = ["pen_penesx_vm05", "pen_penesx_vm06"]
    assert len(luns) == 3
    assert all(lun.get("name_prefix") == "PEN" for lun in luns)
    assert all(lun.get("storage_profile") == "flashsystem_5200" for lun in luns)
    assert all(lun.get("pool_or_cpg") == "G3_PEN_Pool1" for lun in luns)
    assert all(lun.get("card_hint") == "Pendergrass, GA" for lun in luns)
    assert all(lun.get("shared") is True for lun in luns)
    assert all(lun.get("cluster") == "esx" for lun in luns)
    assert all(lun.get("host_names") == both for lun in luns)

    vol_2tb = next(
        lun for lun in luns if lun["purpose"] == "ESX_VOL" and lun["size"] == "2TB"
    )
    assert vol_2tb["count"] == 3
    vol_4tb = next(
        lun for lun in luns if lun["purpose"] == "ESX_VOL" and lun["size"] == "4TB"
    )
    assert vol_4tb["count"] == 1
    coredump = next(lun for lun in luns if lun["purpose"] == "ESX_VOL_COREDUMP")
    assert coredump["count"] == 1 and coredump["size"] == "100GB"

    expanded = [
        name for lun in luns for name in (r["name"] for r in expand_lun_batch(lun))
    ]
    assert len(expanded) == 5
    assert len(expanded) == len(set(expanded))
    assert "PENesx_ESX_VOL_1" in expanded
    assert "PENesx_ESX_VOL_2" in expanded
    assert "PENesx_ESX_VOL_3" in expanded
    assert "PENesx_ESX_VOL" in expanded  # single 4TB batch (count==1 uses base only)
    assert "PENesx_ESX_VOL_COREDUMP" in expanded


def _mount_vernon_template() -> dict:
    return next(
        t for t in seed_lun_builder_templates() if t["id"] == "template-mount-vernon-il"
    )


def test_mount_vernon_template_identity_and_defaults():
    mtv = _mount_vernon_template()
    assert mtv["name"] == "Mount Vernon, IL (Template)"
    assert mtv["location"] == "Mount Vernon, IL"
    assert mtv["is_template"] is True
    assert mtv["default_storage_profile"] == "flashsystem_5200"
    assert mtv["default_pool_or_cpg"] == "MtVerno_Pool1"
    assert mtv["default_card_hint"] == "Mount Vernon, IL"
    assert normalize_build(mtv)["is_template"] is True


def test_mount_vernon_hosts_and_active_wwpns():
    mtv = _mount_vernon_template()
    hosts = mtv["hosts"]
    assert len(hosts) == 11
    names = [h["lpar_name"] for h in hosts]
    assert names.count("amv1_as400") == 2
    assert names.count("tmtvtst1") == 2
    assert set(names) == {
        "amv1_as400",
        "pen-mtvesx-vm01",
        "pen-mtvesx-vm02",
        "pen-mtvesx-vm03",
        "pmtvvio01a",
        "pmtvvio01b",
        "pmtvvio02a",
        "pmtvvio02b",
        "tmtvtst1",
    }
    assert all(h.get("type") == "Generic" for h in hosts)

    as400_rows = [h for h in hosts if h["lpar_name"] == "amv1_as400"]
    assert {(r["wwpn1"], r["wwpn2"]) for r in as400_rows} == {
        ("C050760B552B0004", "C050760B552B0006"),
        ("C050760B552B0010", ""),
    }
    tst_rows = [h for h in hosts if h["lpar_name"] == "tmtvtst1"]
    assert {(r["wwpn1"], r["wwpn2"]) for r in tst_rows} == {
        ("C050760B20CA0008", "C050760B20CA000A"),
        ("C050760B20CA000C", "C050760B20CA000E"),
    }
    esx01 = next(h for h in hosts if h["lpar_name"] == "pen-mtvesx-vm01")
    assert esx01["wwpn1"] == "51402EC012434DDC"
    assert esx01["wwpn2"] == "51402EC012434DDE"
    vio01a = next(h for h in hosts if h["lpar_name"] == "pmtvvio01a")
    assert vio01a["wwpn1"] == "21000024FF85BB40"
    assert vio01a["wwpn2"] == "21000024FF85BB41"


def test_mount_vernon_lun_batches_and_names():
    mtv = _mount_vernon_template()
    luns = mtv["luns"]
    # 1 AS400 + 1 ESX + 4 VIO + 1 test = 7
    assert len(luns) == 7
    assert all(lun.get("storage_profile") == "flashsystem_5200" for lun in luns)
    assert all(lun.get("pool_or_cpg") == "MtVerno_Pool1" for lun in luns)
    assert all(lun.get("card_hint") == "Mount Vernon, IL" for lun in luns)

    as400 = next(lun for lun in luns if lun["purpose"] == "AS400")
    assert as400["count"] == 10 and as400["size"] == "500GB"
    assert as400["shared"] is True
    assert as400["name_prefix"] == "AVM1"
    assert as400["host_names"] == ["amv1_as400"]

    esx = next(lun for lun in luns if lun["purpose"] == "ESXI_DS")
    assert esx["count"] == 4 and esx["size"] == "4TB"
    assert esx["shared"] is True
    assert esx["name_prefix"] == "MTV"
    assert esx["host_names"] == [
        "pen-mtvesx-vm01",
        "pen-mtvesx-vm02",
        "pen-mtvesx-vm03",
    ]

    vio = [
        lun
        for lun in luns
        if lun["purpose"] == "root" and lun["host_names"][0].startswith("pmtvvio")
    ]
    assert len(vio) == 4
    assert all(lun["count"] == 2 and lun["size"] == "100GB" for lun in vio)
    assert all(lun["name_prefix"] == "pmtv" for lun in vio)

    tst = next(lun for lun in luns if lun["host_names"] == ["tmtvtst1"])
    assert tst["purpose"] == "root" and tst["count"] == 3 and tst["size"] == "100GB"
    assert tst["name_prefix"] == ""

    expanded = [
        name for lun in luns for name in (r["name"] for r in expand_lun_batch(lun))
    ]
    assert "AVM1_AS400_1" in expanded
    assert "AVM1_AS400_10" in expanded
    assert "MTV_ESXI_DS_1" in expanded
    assert "MTV_ESXI_DS_4" in expanded
    assert "pmtvvio01a_root_1" in expanded
    assert "pmtvvio02b_root_2" in expanded
    assert "tmtvtst1_root_1" in expanded
    assert "tmtvtst1_root_3" in expanded
    assert len(expanded) == len(set(expanded))
    # 10 + 4 + 8 + 3 = 25
    assert len(expanded) == 25


def _windsor_template() -> dict:
    return next(
        t for t in seed_lun_builder_templates() if t["id"] == "template-windsor-wi"
    )


def test_windsor_template_identity_and_defaults():
    win = _windsor_template()
    assert win["name"] == "Windsor, WI (Template)"
    assert win["location"] == "Windsor, WI"
    assert win["is_template"] is True
    assert win["default_storage_profile"] == "flashsystem_5200"
    assert win["default_pool_or_cpg"] == "Windsor_G3_Pool0"
    assert win["default_card_hint"] == "Windsor, WI"
    assert normalize_build(win)["is_template"] is True


def test_windsor_hosts_and_active_wwpns():
    win = _windsor_template()
    hosts = win["hosts"]
    assert len(hosts) == 14
    names = [h["lpar_name"] for h in hosts]
    assert names.count("AWN1") == 2
    assert names.count("pwinmq01") == 2
    assert names.count("pwinvio01b") == 2
    assert names.count("pwinvio02b") == 2
    assert set(names) == {
        "AWN1",
        "PEN_WINESX_VM01",
        "PEN_WINESX_VM02",
        "PEN_WINESX_VM03",
        "pwinap01",
        "pwinmq01",
        "pwinvio01a",
        "pwinvio01b",
        "pwinvio02a",
        "pwinvio02b",
    }
    assert all(h.get("type") == "Generic" for h in hosts)

    ap01 = next(h for h in hosts if h["lpar_name"] == "pwinap01")
    assert ap01["wwpn1"] == "" and ap01["wwpn2"] == ""

    awn_rows = [h for h in hosts if h["lpar_name"] == "AWN1"]
    assert {(r["wwpn1"], r["wwpn2"]) for r in awn_rows} == {
        ("C050760B518B0000", "C050760B518B0002"),
        ("C050760B518B0004", "C050760B518B0006"),
    }
    mq_rows = [h for h in hosts if h["lpar_name"] == "pwinmq01"]
    assert {(r["wwpn1"], r["wwpn2"]) for r in mq_rows} == {
        ("C050760B53990018", "C050760B5399001A"),
        ("C050760B5399001C", "C050760B5399001E"),
    }
    esx01 = next(h for h in hosts if h["lpar_name"] == "PEN_WINESX_VM01")
    assert esx01["wwpn1"] == "51402EC012CFD072"
    assert esx01["wwpn2"] == "51402EC012CFD2BE"
    vio01a = next(h for h in hosts if h["lpar_name"] == "pwinvio01a")
    assert vio01a["wwpn1"] == "21000024FF86027C"
    assert vio01a["wwpn2"] == "21000024FF86027D"


def test_windsor_lun_batches_and_names():
    win = _windsor_template()
    luns = win["luns"]
    # 1 AS400 + 1 ESX + 2 ap + 1 mq + 3 vio(01a/02a/02b) + 1 vio01b = 9
    assert len(luns) == 9
    assert all(lun.get("storage_profile") == "flashsystem_5200" for lun in luns)
    assert all(lun.get("pool_or_cpg") == "Windsor_G3_Pool0" for lun in luns)
    assert all(lun.get("card_hint") == "Windsor, WI" for lun in luns)

    as400 = next(lun for lun in luns if lun["purpose"] == "AWN1")
    assert as400["count"] == 6 and as400["size"] == "500GB"
    assert as400["shared"] is True and as400["name_prefix"] == "AS400"
    assert as400["host_names"] == ["AWN1"]

    esx = next(lun for lun in luns if lun["purpose"] == "ESX_DataStore")
    assert esx["count"] == 3 and esx["size"] == "4TB"
    assert esx["shared"] is True and esx["name_prefix"] == "WIN"
    assert esx["host_names"] == [
        "PEN_WINESX_VM01",
        "PEN_WINESX_VM02",
        "PEN_WINESX_VM03",
    ]

    ap_root = next(
        lun
        for lun in luns
        if lun["host_names"] == ["pwinap01"] and lun["purpose"] == "root"
    )
    assert ap_root["count"] == 3 and ap_root["size"] == "50GB"
    ap_data = next(
        lun
        for lun in luns
        if lun["host_names"] == ["pwinap01"] and lun["purpose"] == "data"
    )
    assert ap_data["count"] == 2 and ap_data["size"] == "100GB"

    mq = next(lun for lun in luns if lun["host_names"] == ["pwinmq01"])
    assert mq["purpose"] == "root" and mq["count"] == 3 and mq["size"] == "50GB"

    vio01b = next(lun for lun in luns if lun["host_names"] == ["pwinvio01b"])
    assert vio01b["count"] == 5 and vio01b["size"] == "100GB"

    expanded = [
        name for lun in luns for name in (r["name"] for r in expand_lun_batch(lun))
    ]
    assert "AS400_AWN1_1" in expanded
    assert "AS400_AWN1_6" in expanded
    assert "WIN_ESX_DataStore_1" in expanded
    assert "WIN_ESX_DataStore_3" in expanded
    assert "pwinap01_root_1" in expanded
    assert "pwinap01_data_1" in expanded
    assert "pwinmq01_root_1" in expanded
    assert "pwinvio01a_root_1" in expanded
    assert "pwinvio01b_root_1" in expanded
    assert "pwinvio01b_root_5" in expanded
    assert "pwinvio02b_root_2" in expanded
    assert len(expanded) == len(set(expanded))
    # 6 + 3 + 3 + 2 + 3 + 2 + 2 + 2 + 5 = 28
    assert len(expanded) == 28


ANDERSON_REQUIRED_HOSTS = frozenset({
    "AAN1", "AAN1C", "FC_AAN1",
    "BIB_ADC_VM01", "BIB_ADC_VM02",
    "pen_andesx_vm03", "pen_andesx_vm04",
    "pla-wanoemcr01", "pla-wanoemcr02",
    "pandvio01a", "pandvio01b", "pandvio02a", "pandvio02b",
    "pandvio03a", "pandvio03b", "pandvio04a", "pandvio04b",
    "pandvio05a", "pandvio05b", "pandvio06a", "pandvio06b",
    "pandvio07a", "pandvio07b", "pandvio08a", "pandvio08b",
    "pandvio09a", "pandvio09b", "pandvio10a", "pandvio10b",
    "pandap01", "pandap02",
    "pandbt1", "pandbt2", "pandbt3", "pandbt4", "pandbtdg1",
    "panddb01", "panddb02",
    "pandmfs1", "pandmfs2", "pandmfs3", "pandmfs4", "pandmfs10", "pandmfsdg1",
    "pandnim01",
    "pandps1", "pandps2", "pandps3", "pandps4", "pandpspdg1",
    "pandpspa1", "pandpspa2",
    "dandmfs1",
    "tandbt1", "tandbt20",
    "tandmfs1", "tandmfs2", "tandmfs20",
    "tandsps1", "tandsps2", "tandsps20", "tandsps21",
    "tconbt20", "tconmfs20", "tconsps20", "tconsps21",
    "TLA_WANMFS01", "TLA_WANMFS02",
})


def _anderson_template() -> dict:
    return next(
        t
        for t in seed_lun_builder_templates()
        if t["id"] == "template-williamston-anderson"
    )


def test_anderson_template_identity_and_defaults():
    and_ = _anderson_template()
    assert and_["name"] == "Williamston (Anderson) (Template)"
    assert and_["location"] == "Williamston (Anderson)"
    assert and_["is_template"] is True
    assert and_["default_storage_profile"] == "flashsystem_7200"
    assert and_["default_pool_or_cpg"] == "G3_AND_Pool"
    assert and_["default_card_hint"] == "Williamston (Anderson)"
    assert normalize_build(and_)["is_template"] is True
    assert "flashsystem_7200" in and_["notes"]
    assert "G3_AND_Pool" in and_["notes"]


def test_anderson_hosts_cover_required_catalog():
    and_ = _anderson_template()
    names = {h["lpar_name"] for h in and_["hosts"]}
    assert names == ANDERSON_REQUIRED_HOSTS
    assert all(h.get("type") == "Generic" for h in and_["hosts"])
    # WWPNs left blank — set Port Definitions before create
    assert all(h.get("wwpn1") == "" and h.get("wwpn2") == "" for h in and_["hosts"])


def test_anderson_core_lun_families():
    luns = _anderson_template()["luns"]
    assert all(lun.get("storage_profile") == "flashsystem_7200" for lun in luns)
    assert all(lun.get("pool_or_cpg") == "G3_AND_Pool" for lun in luns)
    assert all(lun.get("card_hint") == "Williamston (Anderson)" for lun in luns)
    assert not any(lun.get("purpose") == "placeholder" for lun in luns)

    rows = [row for lun in luns for row in expand_lun_batch(lun)]
    by_name = {row["name"]: row for row in rows}
    assert len(rows) == len(by_name)
    assert not any("Snap" in name or name.lower().endswith("_snap") for name in by_name)

    esx_hosts = {"pen_andesx_vm03", "pen_andesx_vm04"}
    esx_sizes = {
        "ADC-Data01": "1023GB",
        "ADC-Data02": "4TB",
        "ADC-Data03": "4TB",
        "Andesx-DS01": "4TB",
        "Andesx-DS02": "4TB",
        "Andesx-DS03": "4TB",
        "RHEL-Networker01": "100GB",
    }
    for name, size in esx_sizes.items():
        assert by_name[name]["size"] == size
        assert set(by_name[name]["host_names"]) == esx_hosts
        assert by_name[name]["shared"] is True

    for prefix, count, size, host in (
        ("aan1_", 28, "120GB", "AAN1"),
        ("AAN1C_", 4, "125GB", "AAN1C"),
        ("FC_AAN1_", 28, "120GB", "FC_AAN1"),
    ):
        family = [row for row in rows if row["name"].startswith(prefix)]
        assert len(family) == count
        assert all(row["size"] == size and row["host_names"] == [host] for row in family)

    assert {by_name[f"pandap01_{index}"]["size"] for index in range(4)} == {"70GB"}
    assert by_name["pandap01_4"]["size"] == "50GB"
    assert all(by_name[f"pandap01_{index}"]["host_names"] == ["pandap01"] for index in range(5))

    oem = [row for row in rows if row["name"].startswith("pla-wanoemcr01_02_")]
    assert len(oem) == 61
    assert all(
        row["shared"] is True
        and set(row["host_names"]) == {"pla-wanoemcr01", "pla-wanoemcr02"}
        for row in oem
    )


def test_anderson_lun_inventory_covers_mapped_hosts():
    and_ = _anderson_template()
    luns = and_["luns"]
    hosts_with_luns = {
        host_name
        for lun in luns
        for host_name in (lun.get("host_names") or [])
    }
    configured_hosts = {host["lpar_name"] for host in and_["hosts"]}
    for required in (
        "AAN1",
        "AAN1C",
        "FC_AAN1",
        "pen_andesx_vm03",
        "pla-wanoemcr01",
        "pandap01",
        "pandvio08b",
        "tandbt1",
        "tandbt20",
        "tandmfs1",
        "tandmfs20",
        "tandsps1",
        "TLA_WANMFS01",
    ):
        assert required in hosts_with_luns or required in configured_hosts

    expanded = [
        row["name"]
        for lun in luns
        for row in expand_lun_batch(lun)
    ]
    assert len(expanded) >= 200
    assert len(expanded) == len(set(expanded))
    assert all(lun.get("pool_or_cpg") == "G3_AND_Pool" for lun in luns)
