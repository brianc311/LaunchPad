from launchpad.firmware_catalog import (
    eligible_firmware_profiles,
    latest_in_catalog,
    normalize_catalog,
    versions_behind,
    versions_behind_list,
)


def test_versions_behind_counts_entries_after_current():
    catalog = ["8.5.0", "8.6.0", "8.6.1", "8.6.2"]
    assert versions_behind("8.6.0", catalog) == "2"
    assert versions_behind("8.6.2", catalog) == "0"
    assert versions_behind("8.7.0", catalog) == "unknown"
    assert versions_behind("8.6.0", []) == "unknown"
    assert versions_behind("", catalog) == "unknown"


def test_versions_behind_list_returns_entries_after_current():
    catalog = ["8.5.0", "8.6.0", "8.6.1", "8.6.2"]
    assert versions_behind_list("8.6.0", catalog) == ["8.6.1", "8.6.2"]
    assert versions_behind_list("8.6.2", catalog) == []
    assert versions_behind_list("8.7.0", catalog) == []
    assert versions_behind_list("", catalog) == []


def test_latest_in_catalog():
    assert latest_in_catalog(["8.5.0", "8.6.2"]) == "8.6.2"
    assert latest_in_catalog([]) == ""


def test_normalize_catalog_drops_blanks_and_dupes_keeps_order():
    raw = {"flashsystem_7300": ["8.5.0", "", "8.6.0", "8.5.0", "8.6.1"]}
    assert normalize_catalog(raw) == {
        "flashsystem_7300": ["8.5.0", "8.6.0", "8.6.1"]
    }


def test_eligible_firmware_profiles_includes_svc_hpe_ds():
    profiles = eligible_firmware_profiles()
    assert "flashsystem_7300" in profiles
    assert "ibm_ds8884" in profiles
    assert profiles == sorted(profiles)
