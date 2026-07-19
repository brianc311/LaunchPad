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
    assert [r["name"] for r in rows] == ["ora1vg_01", "ora1vg_02", "ora1vg_03"]


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
    ora = [lun for lun in luns if lun["purpose"] == "ora1vg"]
    assert {lun["cluster"]: lun["count"] for lun in ora} == {
        "SPS": 7,
        "MFS": 7,
        "BT": 14,
    }
