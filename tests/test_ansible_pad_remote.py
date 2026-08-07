from launchpad.ansible_pad_remote import (
    build_ansible_playbook_argv,
    require_confirm_for_mutate,
)

def test_check_mode_argv():
    argv = build_ansible_playbook_argv(
        playbook="playbooks/start_fc_consistgrp.yml",
        inventory="inventory/hosts.yml",
        check=True,
    )
    assert argv[0] == "ansible-playbook"
    assert "--check" in argv

def test_mutate_requires_confirm():
    try:
        require_confirm_for_mutate(check=False, confirm=False)
        assert False, "expected ValueError"
    except ValueError:
        pass
    require_confirm_for_mutate(check=True, confirm=False)
    require_confirm_for_mutate(check=False, confirm=True)
