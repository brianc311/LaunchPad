from launchpad.lun_builder_data import (
    expand_lun_batch,
    normalize_build,
    seed_lun_builder_templates,
)


EXPECTED = {
    "template-perrysburg-oh": (
        "Perrysburg, OH",
        "flashsystem_7200",
        "G3_PER_Pool",
        "Perrysburg, OH",
    ),
    "template-moreno-valley-ca": (
        "Moreno Valley, CA",
        "flashsystem_5200",
        "MOR_G3_Pool",
        "Moreno Valley, CA",
    ),
    "template-nazareth-pa": (
        "Nazareth, PA",
        "flashsystem_5200",
        "V5kNAZ_Pool1",
        "Nazareth, PA",
    ),
    "template-valparaiso-in": (
        "Valparaiso, IN",
        "flashsystem_7300",
        "VAL_POOL",
        "Valparaiso, IN",
    ),
    "template-waxahachie-tx": (
        "Waxahachie, TX",
        "flashsystem_5200",
        "Wax_Pool1",
        "Waxahachie, TX",
    ),
    "template-woodland-hills-ca": (
        "Woodland Hills, CA",
        "flashsystem_5200",
        "WOO_Pool1",
        "Woodland Hills, CA",
    ),
}


def test_six_site_templates_present_with_defaults():
    by_id = {template["id"]: template for template in seed_lun_builder_templates()}

    for template_id, (location, profile, pool, hint) in EXPECTED.items():
        template = by_id[template_id]
        assert template["location"] == location
        assert template["is_template"] is True
        assert template["default_storage_profile"] == profile
        assert template["default_pool_or_cpg"] == pool
        assert template["default_card_hint"] == hint
        assert len(template["hosts"]) >= 1
        assert len(template["luns"]) >= 1
        assert all(
            not (host.get("wwpn1") or host.get("wwpn2"))
            for host in template["hosts"]
        )
        assert normalize_build(template)["is_template"] is True


def test_six_site_luns_are_exact_name_singletons():
    by_id = {template["id"]: template for template in seed_lun_builder_templates()}

    for template_id in EXPECTED:
        for lun in by_id[template_id]["luns"]:
            assert lun.get("exact_name") is True
            assert int(lun.get("count") or 1) == 1
            rows = expand_lun_batch(lun)
            assert len(rows) == 1
            assert rows[0]["name"] == lun["purpose"]
