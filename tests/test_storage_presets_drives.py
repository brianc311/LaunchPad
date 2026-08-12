from launchpad.storage_presets import SVC_COMMANDS, ensure_svc_health_commands


def test_svc_commands_include_lsdrive_and_lsnodecanister():
    cmds = {label: cmd for label, cmd in SVC_COMMANDS}
    assert "lsdrive" in cmds["Health - Drives"]
    assert "lsnodecanister" in cmds["Health - Controllers"]


def test_ensure_svc_health_commands_adds_lsdrive_to_legacy_customs():
    legacy = [
        ("Health - Nodes", "svcinfo lsnode -delim :"),
        ("Health - Controllers", "svcinfo lsnode -delim :"),
        ("Health - Alerts", "svcinfo lseventlog -alert yes -delim :"),
    ]
    merged = ensure_svc_health_commands("ibm_svc_2145", legacy)
    labels = [label for label, _ in merged]
    commands = {label: cmd for label, cmd in merged}
    assert "Health - Drives" in labels
    assert "lsdrive" in commands["Health - Drives"]
    assert "lsnodecanister" in commands["Health - Controllers"]
    assert labels[:3] == ["Health - Nodes", "Health - Controllers", "Health - Alerts"]


def test_ensure_svc_health_commands_skips_non_svc_profiles():
    legacy = [("Health - Nodes", "svcinfo lsnode -delim :")]
    assert ensure_svc_health_commands("hp_3par", legacy) == legacy


def test_resolve_card_commands_backfills_svc_health_commands():
    from launchpad.command_format import resolve_card_commands

    custom = "\n".join(
        [
            "Health - Nodes|svcinfo lsnode -delim :",
            "Health - Controllers|svcinfo lsnode -delim :",
            "Health - Alerts|svcinfo lseventlog -alert yes -delim :",
        ]
    )
    commands = resolve_card_commands("ibm_svc_2145", custom)
    labels = [label for label, _ in commands]
    by_label = {label: cmd for label, cmd in commands}
    assert "Health - Drives" in labels
    assert "lsdrive" in by_label["Health - Drives"]
    assert "lsnodecanister" in by_label["Health - Controllers"]
