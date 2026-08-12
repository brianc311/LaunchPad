from launchpad.command_format import resolve_card_commands


def test_resolve_ds8884_applies_hmc_wrap():
    cmds = resolve_card_commands(
        "ibm_ds8884",
        "",
        dscli_path="dscli.bat",
        dscli_hmc="10.9.9.9",
        username="admin",
        password="pw",
    )
    assert cmds
    joined = " ".join(c for _, c in cmds)
    assert "10.9.9.9" in joined
    assert "dscli.bat" in joined or '"dscli.bat"' in joined
