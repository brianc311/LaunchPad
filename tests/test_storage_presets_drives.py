from launchpad.storage_presets import SVC_COMMANDS


def test_svc_commands_include_lsdrive_and_lsnodecanister():
    cmds = {label: cmd for label, cmd in SVC_COMMANDS}
    assert "lsdrive" in cmds["Health - Drives"]
    assert "lsnodecanister" in cmds["Health - Controllers"]
