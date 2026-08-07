from unittest.mock import MagicMock, patch

import pytest

from launchpad.hadoop_sudo import (
    SUDO_PASSWORD_REQUIRED,
    command_needs_sudo,
    ensure_sudo_dash_s,
    prepare_hadoop_sudo_command,
)
from launchpad.ssh_commands import run_remote_command_suite, run_remote_ssh_command
from launchpad.ssh_paramiko import run_ssh_auth_command, run_ssh_command


def test_command_needs_sudo_token():
    assert command_needs_sudo("sudo shutdown -h now")
    assert command_needs_sudo("sudo -n true")
    assert command_needs_sudo("uptime && sudo -n true")
    assert not command_needs_sudo("uptime")
    assert not command_needs_sudo("echo sudoish")
    assert not command_needs_sudo("grep sudo /var/log/messages")
    assert not command_needs_sudo("id | grep sudo")


def test_ensure_sudo_dash_s():
    assert ensure_sudo_dash_s("sudo shutdown -h now") == "sudo -S -p '' shutdown -h now"
    assert ensure_sudo_dash_s("sudo -S shutdown -h now") == "sudo -p '' -S shutdown -h now"
    assert ensure_sudo_dash_s("uptime") == "uptime"
    assert ensure_sudo_dash_s("id | grep sudo") == "id | grep sudo"


def test_ensure_sudo_dash_s_no_duplicate_when_s_present():
    assert ensure_sudo_dash_s("sudo -n -S id") == "sudo -p '' -n -S id"
    assert ensure_sudo_dash_s("sudo -nS id") == "sudo -p '' -nS id"
    assert ensure_sudo_dash_s("sudo -u root -S id") == "sudo -p '' -u root -S id"
    assert ensure_sudo_dash_s("sudo --user root -S id") == "sudo -p '' --user root -S id"


def test_ensure_sudo_dash_s_inserts_after_option_args():
    assert ensure_sudo_dash_s("sudo -u root id") == "sudo -S -p '' -u root id"
    assert ensure_sudo_dash_s("sudo --user=root id") == "sudo -S -p '' --user=root id"
    assert ensure_sudo_dash_s("sudo -uS id") == "sudo -S -p '' -uS id"


def test_ensure_sudo_dash_s_respects_double_dash():
    assert ensure_sudo_dash_s("sudo -- -S") == "sudo -S -p '' -- -S"
    assert ensure_sudo_dash_s("sudo -S -- -S") == "sudo -p '' -S -- -S"


def test_prepare_feeds_stdin_or_errors():
    cmd, payload = prepare_hadoop_sudo_command("sudo shutdown -h now", sudo_password="secret")
    assert cmd == "sudo -S -p '' shutdown -h now"
    assert payload == "secret\n"
    cmd2, payload2 = prepare_hadoop_sudo_command("uptime", sudo_password="secret")
    assert cmd2 == "uptime"
    assert payload2 is None
    with pytest.raises(ValueError, match=SUDO_PASSWORD_REQUIRED):
        prepare_hadoop_sudo_command("sudo true", sudo_password="")


def test_run_remote_feeds_stdin_for_sudo(monkeypatch):
    seen = {}

    def fake_run_ssh_command(
        host, port, username, password, command, *, timeout=45, stdin_data=None
    ):
        seen["command"] = command
        seen["stdin_data"] = stdin_data
        return "ok"

    monkeypatch.setattr("launchpad.ssh_commands.run_ssh_command", fake_run_ssh_command)

    output = run_remote_ssh_command(
        "10.0.0.1",
        22,
        "user",
        "sudo shutdown -h now",
        password="ssh-pass",
        device_profile="hadoop_linux",
        sudo_password="sudo-pass",
    )

    assert output == "ok"
    assert seen == {
        "command": "sudo -S -p '' shutdown -h now",
        "stdin_data": "sudo-pass\n",
    }


def test_run_remote_errors_without_sudo_password():
    with pytest.raises(ValueError, match=SUDO_PASSWORD_REQUIRED):
        run_remote_ssh_command(
            "10.0.0.1",
            22,
            "user",
            "sudo true",
            password="ssh-pass",
            device_profile="hadoop_linux",
            sudo_password="",
        )


def test_non_hadoop_sudo_command_is_unchanged(monkeypatch):
    seen = {}

    def fake_run_ssh_command(
        host, port, username, password, command, *, timeout=45, stdin_data=None
    ):
        seen["command"] = command
        seen["stdin_data"] = stdin_data
        return "ok"

    monkeypatch.setattr("launchpad.ssh_commands.run_ssh_command", fake_run_ssh_command)

    assert (
        run_remote_ssh_command(
            "10.0.0.1",
            22,
            "user",
            "sudo systemctl status service",
            password="ssh-pass",
            device_profile="generic_ssh",
        )
        == "ok"
    )
    assert seen == {
        "command": "sudo systemctl status service",
        "stdin_data": None,
    }


@pytest.mark.parametrize("runner", [run_ssh_command, run_ssh_auth_command])
def test_paramiko_runner_writes_and_closes_stdin(runner):
    stdin = MagicMock()
    stdout = MagicMock()
    stderr = MagicMock()
    stdout.channel.recv_exit_status.return_value = 0
    stdout.read.return_value = b"ok"
    stderr.read.return_value = b""
    client = MagicMock()
    client.exec_command.return_value = (stdin, stdout, stderr)
    client_context = MagicMock()
    client_context.__enter__.return_value = client

    if runner is run_ssh_command:
        runner_patch = patch(
            "launchpad.ssh_paramiko.password_ssh_client",
            return_value=client_context,
        )
        args = ("10.0.0.1", 22, "user", "ssh-pass", "uptime")
        kwargs = {"stdin_data": "sudo-pass\n"}
    else:
        runner_patch = patch(
            "launchpad.ssh_paramiko.ssh_auth_client",
            return_value=client_context,
        )
        args = ("10.0.0.1", 22, "user", "uptime")
        kwargs = {"password": "ssh-pass", "stdin_data": "sudo-pass\n"}

    with runner_patch:
        assert runner(*args, **kwargs) == "ok"

    stdin.write.assert_called_once_with("sudo-pass\n")
    stdin.flush.assert_called_once_with()
    stdin.channel.shutdown_write.assert_called_once_with()


@pytest.mark.parametrize("runner", [run_ssh_command, run_ssh_auth_command])
def test_paramiko_runner_preserves_remote_error_when_stdin_is_closed(runner):
    stdin = MagicMock()
    stdin.write.side_effect = OSError("Socket is closed")
    stdout = MagicMock()
    stderr = MagicMock()
    stdout.channel.recv_exit_status.return_value = 1
    stdout.read.return_value = b""
    stderr.read.return_value = b"remote command failed"
    client = MagicMock()
    client.exec_command.return_value = (stdin, stdout, stderr)
    client_context = MagicMock()
    client_context.__enter__.return_value = client

    if runner is run_ssh_command:
        runner_patch = patch(
            "launchpad.ssh_paramiko.password_ssh_client",
            return_value=client_context,
        )
        args = ("10.0.0.1", 22, "user", "ssh-pass", "bad-command")
        kwargs = {"stdin_data": "sudo-pass\n"}
    else:
        runner_patch = patch(
            "launchpad.ssh_paramiko.ssh_auth_client",
            return_value=client_context,
        )
        args = ("10.0.0.1", 22, "user", "bad-command")
        kwargs = {"password": "ssh-pass", "stdin_data": "sudo-pass\n"}

    with runner_patch, pytest.raises(ValueError, match="remote command failed"):
        runner(*args, **kwargs)


def test_hadoop_suite_records_sudo_error_but_runs_non_sudo(monkeypatch):
    calls = []

    def fake_run_remote(*args, **kwargs):
        command = args[3]
        calls.append((command, kwargs["sudo_password"]))
        if command == "sudo true":
            raise ValueError(SUDO_PASSWORD_REQUIRED)
        return "up"

    monkeypatch.setattr("launchpad.ssh_commands.run_remote_ssh_command", fake_run_remote)

    results = run_remote_command_suite(
        "10.0.0.1",
        22,
        "user",
        [("Status", "uptime"), ("Privileged", "sudo true")],
        password="ssh-pass",
        device_profile="hadoop_linux",
    )

    assert calls == [("uptime", ""), ("sudo true", "")]
    assert results[0]["output"] == "up"
    assert results[0]["error"] is None
    assert results[1]["error"] == SUDO_PASSWORD_REQUIRED
