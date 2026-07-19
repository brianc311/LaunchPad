from launchpad.lun_builder_data import (
    LUN_BUILDS_SETTING,
    expand_lun_batch,
    normalize_build,
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
