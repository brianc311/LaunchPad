from launchpad.storage_presets import HP_3PAR_COMMANDS, HPE_PRIMERA_COMMANDS


def test_hpe_presets_include_showhost():
    assert ("Hosts - host list", "showhost") in HP_3PAR_COMMANDS
    assert ("Hosts - host list", "showhost") in HPE_PRIMERA_COMMANDS
