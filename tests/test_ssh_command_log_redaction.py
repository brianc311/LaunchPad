from launchpad.ssh_commands import run_remote_ssh_command


def test_run_remote_ssh_command_logs_masked_smtp_password(monkeypatch):
    logged: list[str] = []
    ssh_cmds: list[str] = []

    monkeypatch.setattr("launchpad.ssh_commands._log", logged.append)

    def fake_run_ssh_command(host, port, username, password, remote_command, **kwargs):
        ssh_cmds.append(remote_command)
        return "ok"

    monkeypatch.setattr("launchpad.ssh_commands.run_ssh_command", fake_run_ssh_command)

    cmd = "svctask mkemailserver -ip 1.2.3.4 -port 25 -username user -password s3cret"
    run_remote_ssh_command(
        "array.example",
        22,
        "superuser",
        cmd,
        password="ssh-secret",
    )

    assert logged
    joined = "\n".join(logged)
    assert "********" in joined
    assert "s3cret" not in joined
    assert ssh_cmds == [cmd]
