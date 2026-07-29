from launchpad.firmware_catalog import (
    merge_seed_into_catalog,
    normalize_hpe_firmware_version,
    version_sort_key,
)
from launchpad.firmware_catalog_seed import (
    FLASHSYSTEM_SEED_VERSIONS,
    HPE_SEED_VERSION,
    recommended_firmware_seed,
)
from launchpad.storage_presets import HPE_SHELL_PROFILES, SVC_PROFILES


def test_flashsystem_seed_contains_spec_union():
    required = {
        "7.8.1.8",
        "7.8.1.16",
        "8.2.1.11",
        "8.4.0.20",
        "8.6.0.2",
        "8.6.0.7",
        "8.6.0.9",
        "8.6.0.11",
        "8.6.1.0",
        "8.6.2.1",
        "8.6.3.0",
        "8.7.0.3",
        "8.7.0.13",
    }
    assert required.issubset(set(FLASHSYSTEM_SEED_VERSIONS))
    assert list(FLASHSYSTEM_SEED_VERSIONS) == sorted(
        FLASHSYSTEM_SEED_VERSIONS,
        key=version_sort_key,
    )


def test_recommended_seed_covers_svc_and_hpe_profiles():
    seed = recommended_firmware_seed()
    for profile in SVC_PROFILES:
        assert seed[profile] == list(FLASHSYSTEM_SEED_VERSIONS)
    for profile in HPE_SHELL_PROFILES:
        assert seed[profile] == [HPE_SEED_VERSION]
    assert "ibm_ds8884" not in seed


def test_normalize_hpe_firmware_version_strips_patches():
    assert (
        normalize_hpe_firmware_version(
            "3.3.1.648 (MU5)+P126,P132,P135,P140,P146,P150,P151,P155,P156"
        )
        == "3.3.1.648 (MU5)"
    )
    assert normalize_hpe_firmware_version("3.3.1.648 (MU5)") == "3.3.1.648 (MU5)"
    assert normalize_hpe_firmware_version("") == ""


def test_merge_seed_inserts_missing_only():
    catalog = {"flashsystem_7300": ["8.6.0.11", "9.9.9.9"]}
    seed = {"flashsystem_7300": ["8.6.0.11", "8.7.0.13"]}
    updated, n = merge_seed_into_catalog(catalog, seed)
    assert n == 1
    assert "8.7.0.13" in updated["flashsystem_7300"]
    assert "9.9.9.9" in updated["flashsystem_7300"]
    _, n2 = merge_seed_into_catalog(updated, seed)
    assert n2 == 0
