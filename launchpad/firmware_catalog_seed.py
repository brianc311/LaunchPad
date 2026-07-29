from launchpad.storage_presets import HPE_SHELL_PROFILES, SVC_PROFILES

FLASHSYSTEM_SEED_VERSIONS: tuple[str, ...] = (
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
)
HPE_SEED_VERSION = "3.3.1.648 (MU5)"


def recommended_firmware_seed() -> dict[str, list[str]]:
    seed: dict[str, list[str]] = {}
    fs = list(FLASHSYSTEM_SEED_VERSIONS)
    for profile in SVC_PROFILES:
        seed[str(profile)] = list(fs)
    for profile in HPE_SHELL_PROFILES:
        seed[str(profile)] = [HPE_SEED_VERSION]
    return seed
