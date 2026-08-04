from launchpad.system_connectivity import (
    base_row,
    enrich_firmware_row,
    parse_ds_firmware,
    parse_hpe_showversion_firmware,
    parse_svc_firmware_from_lssystem,
    TOPICS,
)


def test_topics_include_firmware():
    assert "firmware" in TOPICS
    assert TOPICS.index("firmware") < TOPICS.index("license_key")
    assert "ntp" in TOPICS


def test_parse_svc_firmware_code_level():
    output = "id:1\nname:fs1\ncode_level:8.6.0.0 (build 152.24.2403051134)\n"
    configured, status, details, current = parse_svc_firmware_from_lssystem(output)
    assert configured == "yes"
    assert current == "8.6.0.0"
    assert "8.6.0.0" in details
    assert "build" not in current


def test_svc_normalized_current_matches_catalog():
    output = "id:1\nname:fs1\ncode_level:8.6.0.0 (build 152.24.2403051134)\n"
    configured, status, details, current = parse_svc_firmware_from_lssystem(output)
    row = base_row(
        card_name="SiteA", host="1.2.3.4", vendor="ibm", profile="flashsystem_7300"
    )
    out = enrich_firmware_row(
        row,
        current=current,
        catalog=["8.6.0.0", "8.6.1.0"],
        configured=configured,
        status=status,
        details=details,
    )
    assert out["current"] == "8.6.0.0"
    assert out["latest"] == "8.6.1.0"
    assert out["versions_behind"] == "1"


def test_enrich_firmware_row_behind_count():
    row = base_row(
        card_name="SiteA", host="1.2.3.4", vendor="ibm", profile="flashsystem_7300"
    )
    catalog = ["8.5.0", "8.6.0", "8.6.1"]
    out = enrich_firmware_row(
        row,
        current="8.6.0",
        catalog=catalog,
        configured="yes",
        status="behind",
        details="8.6.0 → 8.6.1",
    )
    assert out["current"] == "8.6.0"
    assert out["latest"] == "8.6.1"
    assert out["versions_behind"] == "1"


def test_enrich_firmware_unknown_when_current_missing_from_catalog():
    row = base_row(
        card_name="SiteA", host="1.2.3.4", vendor="ibm", profile="flashsystem_7300"
    )
    out = enrich_firmware_row(
        row, current="9.0.0", catalog=["8.5.0", "8.6.0"], configured="yes"
    )
    assert out["versions_behind"] == "unknown"
    assert out["latest"] == "8.6.0"


def test_parse_hpe_showversion_firmware():
    output = "System Name: array1\nVersion: 4.1.2\n"
    configured, status, details, current = parse_hpe_showversion_firmware(output)
    assert configured == "yes"
    assert current == "4.1.2"


def test_parse_hpe_showversion_release_version_no_colon():
    """Live 3PAR/Primera CLI uses 'Release version X' without a colon."""
    output = (
        "Release version 3.3.1.648 (MU5)\n"
        "Patches: P126,P132\n"
        "Component Name Version\n"
        "CLI Server 3.3.1.648 (MU5)\n"
    )
    configured, status, details, current = parse_hpe_showversion_firmware(output)
    assert configured == "yes"
    assert status == "configured"
    assert current == "3.3.1.648 (MU5)"
    assert "version=" in details


def test_hpe_showversion_normalizes_patch_suffix():
    output = "Version: 3.3.1.648 (MU5)+P126,P132\n"
    configured, status, details, current = parse_hpe_showversion_firmware(output)
    assert configured == "yes"
    assert current == "3.3.1.648 (MU5)"


def test_ds_firmware_na_preserves_status():
    configured, status, details, current = parse_ds_firmware("")
    row = base_row(
        card_name="DS1", host="1.2.3.4", vendor="ibm", profile="ibm_ds8884"
    )
    out = enrich_firmware_row(
        row,
        current=current,
        catalog=[],
        configured=configured,
        status=status,
        details=details,
    )
    assert configured == "n/a"
    assert out["status"] == "n/a"
    assert out["configured"] == "n/a"
    assert out["current"] == ""
