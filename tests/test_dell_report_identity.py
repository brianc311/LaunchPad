from launchpad.dell_report_identity import resolve_dell_identity


def test_defaults_array_from_summary_model_from_profile():
    ident = resolve_dell_identity(
        card_id=1,
        site_name="Carolina, PR - Remote",
        device_profile="hpe_primera_600",
        summary_name="Vdiprimera101",
        overrides={},
    )
    assert ident["facility"] == "Remote"
    assert ident["array_name"] == "Vdiprimera101"
    assert ident["model"] == "HPE Primera 600 4-way"


def test_override_wins():
    ident = resolve_dell_identity(
        card_id=9,
        site_name="Other site",
        device_profile="hpe_primera_600",
        summary_name="Vdiprimera101",
        overrides={"9": {"facility": "Data center -WAG2", "model": "Custom"}},
    )
    assert ident["facility"] == "Data center -WAG2"
    assert ident["array_name"] == "Vdiprimera101"
    assert ident["model"] == "Custom"


def test_rejects_all_cpgs_as_array_uses_site_and_facility_from_array():
    ident = resolve_dell_identity(
        card_id=3,
        site_name="HPE - VDIPRIMERA101 - WAG2",
        device_profile="hpe_primera_600",
        summary_name="All CPGs",
        overrides={},
    )
    assert ident["array_name"] == "HPE - VDIPRIMERA101 - WAG2"
    assert ident["model"] == "HPE Primera 600 4-way"
    assert ident["facility"] == "Data center -WAG2"


def test_facility_from_ibm_array_hostname_when_site_other():
    ident = resolve_dell_identity(
        card_id=4,
        site_name="Storage Card 12",
        device_profile="flashsystem_5200",
        summary_name="v5kPEN-g3v1",
        overrides={},
    )
    assert ident["facility"] == "Distribution center"
    assert ident["array_name"] == "v5kPEN-g3v1"
