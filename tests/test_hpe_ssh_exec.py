"""HPE CLI runs as one SSH exec per command (no interactive shell bleed)."""

from launchpad import ssh_paramiko


def test_run_ssh_auth_hpe_commands_uses_exec_not_shell(monkeypatch):
    calls = {"exec": 0, "shell": 0}
    outputs = ["sys-out", "cpg-out", "host-out"]

    class FakeChannel:
        def recv_exit_status(self):
            return 0

    class FakeStdout:
        def __init__(self, text):
            self.channel = FakeChannel()
            self._text = text

        def read(self):
            return self._text.encode("utf-8")

    class FakeStderr:
        def read(self):
            return b""

    class FakeClient:
        def exec_command(self, command, timeout=40):
            calls["exec"] += 1
            text = outputs[calls["exec"] - 1]
            return None, FakeStdout(text), FakeStderr()

        def invoke_shell(self, *args, **kwargs):
            calls["shell"] += 1
            raise AssertionError("interactive shell should not be used for HPE health cmds")

        def close(self):
            return None

    class FakeCtx:
        def __enter__(self):
            return FakeClient()

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(ssh_paramiko, "ssh_auth_client", lambda *a, **k: FakeCtx())

    result = ssh_paramiko.run_ssh_auth_hpe_commands(
        "10.0.0.1",
        22,
        "3paradm",
        ["showsys -d", "showcpg", "showhost"],
        password="x",
    )
    assert result == outputs
    assert calls["exec"] == 3
    assert calls["shell"] == 0
