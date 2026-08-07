import pytest
from launchpad.hadoop_sudo import (
    SUDO_PASSWORD_REQUIRED,
    command_needs_sudo,
    ensure_sudo_dash_s,
    prepare_hadoop_sudo_command,
)


def test_command_needs_sudo_token():
    assert command_needs_sudo("sudo shutdown -h now")
    assert command_needs_sudo("sudo -n true")
    assert not command_needs_sudo("uptime")
    assert not command_needs_sudo("echo sudoish")


def test_ensure_sudo_dash_s():
    assert ensure_sudo_dash_s("sudo shutdown -h now") == "sudo -S shutdown -h now"
    assert ensure_sudo_dash_s("sudo -S shutdown -h now") == "sudo -S shutdown -h now"
    assert ensure_sudo_dash_s("uptime") == "uptime"


def test_ensure_sudo_dash_s_no_duplicate_when_s_present():
    assert ensure_sudo_dash_s("sudo -n -S id") == "sudo -n -S id"
    assert ensure_sudo_dash_s("sudo -nS id") == "sudo -nS id"
    assert ensure_sudo_dash_s("sudo -u root -S id") == "sudo -u root -S id"
    assert ensure_sudo_dash_s("sudo --user root -S id") == "sudo --user root -S id"


def test_ensure_sudo_dash_s_inserts_after_option_args():
    assert ensure_sudo_dash_s("sudo -u root id") == "sudo -S -u root id"
    assert ensure_sudo_dash_s("sudo --user=root id") == "sudo -S --user=root id"


def test_ensure_sudo_dash_s_respects_double_dash():
    assert ensure_sudo_dash_s("sudo -- -S") == "sudo -S -- -S"
    assert ensure_sudo_dash_s("sudo -S -- -S") == "sudo -S -- -S"


def test_prepare_feeds_stdin_or_errors():
    cmd, payload = prepare_hadoop_sudo_command("sudo shutdown -h now", sudo_password="secret")
    assert cmd == "sudo -S shutdown -h now"
    assert payload == "secret\n"
    cmd2, payload2 = prepare_hadoop_sudo_command("uptime", sudo_password="secret")
    assert cmd2 == "uptime"
    assert payload2 is None
    with pytest.raises(ValueError, match=SUDO_PASSWORD_REQUIRED):
        prepare_hadoop_sudo_command("sudo true", sudo_password="")
