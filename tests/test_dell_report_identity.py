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
