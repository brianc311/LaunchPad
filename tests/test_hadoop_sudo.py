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


def test_prepare_feeds_stdin_or_errors():
    cmd, payload = prepare_hadoop_sudo_command("sudo shutdown -h now", sudo_password="secret")
    assert cmd == "sudo -S shutdown -h now"
    assert payload == "secret\n"
    cmd2, payload2 = prepare_hadoop_sudo_command("uptime", sudo_password="secret")
    assert cmd2 == "uptime"
    assert payload2 is None
    with pytest.raises(ValueError, match=SUDO_PASSWORD_REQUIRED):
        prepare_hadoop_sudo_command("sudo true", sudo_password="")
