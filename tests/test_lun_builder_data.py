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


def test_hartford_template_identity():
    templates = seed_lun_builder_templates()
    assert len(templates) == 1
    hartford = templates[0]
    assert hartford["id"] == "template-hartford-ct"
    assert hartford["name"] == "Hartford, CT (Template)"
    assert hartford["is_template"] is True
    assert hartford["location"] == "Hartford, CT"
    assert normalize_build(hartford)["is_template"] is True


def test_hartford_hosts_cover_six_lpars():
    hartford = seed_lun_builder_templates()[0]
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
    hartford = seed_lun_builder_templates()[0]
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
