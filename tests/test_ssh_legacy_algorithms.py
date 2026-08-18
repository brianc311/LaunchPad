"""IBM XIV and similar old OpenSSH need ssh-rsa host keys (Paramiko 5 dropped them)."""

from __future__ import annotations

from unittest.mock import MagicMock

import paramiko

from launchpad.ssh_paramiko import (
    enable_legacy_ssh_algorithms,
    key_ssh_client,
    legacy_ssh_transport_factory,
    password_ssh_client,
)


class _DummySock:
    def send(self, data: bytes) -> int:
        return len(data)

    def recv(self, _size: int) -> bytes:
        return b""

    def close(self) -> None:
        return None

    def settimeout(self, _timeout: float | None) -> None:
        return None


def test_paramiko_defaults_omit_ssh_rsa_host_key():
    transport = paramiko.Transport(_DummySock())
    try:
        assert "ssh-rsa" not in transport.preferred_keys
        assert "diffie-hellman-group14-sha1" not in transport.preferred_kex
    finally:
        transport.close()


def test_enable_legacy_ssh_algorithms_adds_xiv_host_key_and_kex():
    transport = paramiko.Transport(_DummySock())
    try:
        enable_legacy_ssh_algorithms(transport)
        assert "ssh-rsa" in transport.preferred_keys
        assert transport.preferred_keys.index("ssh-ed25519") < transport.preferred_keys.index(
            "ssh-rsa"
        )
        assert "diffie-hellman-group14-sha1" in transport.preferred_kex
        assert "diffie-hellman-group1-sha1" in transport.preferred_kex
    finally:
        transport.close()


def test_enable_legacy_registers_ssh_rsa_for_host_key_verify():
    """Paramiko 5 dropped ssh-rsa from _key_info; XIV still signs kex with it."""
    assert "ssh-rsa" not in paramiko.Transport._key_info
    transport = paramiko.Transport(_DummySock())
    try:
        enable_legacy_ssh_algorithms(transport)
        key_cls = transport._key_info["ssh-rsa"]
        assert "ssh-rsa" in key_cls.HASHES
        assert "ssh-rsa" not in paramiko.Transport._key_info
    finally:
        transport.close()


def test_legacy_ssh_transport_factory_enables_ssh_rsa():
    transport = legacy_ssh_transport_factory(_DummySock())
    try:
        assert "ssh-rsa" in transport.preferred_keys
    finally:
        transport.close()


def test_password_ssh_client_enables_legacy_algorithms(monkeypatch):
    configured: list[object] = []

    class FakeTransport:
        def __init__(self, sock):
            self.sock = sock
            self.banner_timeout = None
            self.auth_timeout = None

        def start_client(self, timeout=None):
            return None

        def close(self):
            return None

    def fake_enable(transport):
        configured.append(transport)
        return transport

    monkeypatch.setattr(
        "launchpad.ssh_paramiko.socket.create_connection",
        lambda *args, **kwargs: MagicMock(),
    )
    monkeypatch.setattr("launchpad.ssh_paramiko.paramiko.Transport", FakeTransport)
    monkeypatch.setattr(
        "launchpad.ssh_paramiko.enable_legacy_ssh_algorithms", fake_enable
    )
    monkeypatch.setattr(
        "launchpad.ssh_paramiko.authenticate_with_password", lambda *args, **kwargs: None
    )

    with password_ssh_client("10.246.85.1", 22, "admin", "secret"):
        pass

    assert configured
    assert isinstance(configured[0], FakeTransport)


def test_key_ssh_client_uses_legacy_transport_factory(monkeypatch):
    captured: dict[str, object] = {}

    class FakeClient:
        def set_missing_host_key_policy(self, _policy):
            return None

        def connect(self, **kwargs):
            captured.update(kwargs)

        def close(self):
            return None

    monkeypatch.setattr("launchpad.ssh_paramiko.paramiko.SSHClient", FakeClient)
    monkeypatch.setattr(
        "launchpad.ssh_paramiko._load_private_key", lambda *args, **kwargs: object()
    )

    with key_ssh_client("10.246.85.1", 22, "admin", "C:\\keys\\id_rsa"):
        pass

    assert captured["transport_factory"] is legacy_ssh_transport_factory


def test_interactive_shell_enables_legacy_algorithms():
    import inspect

    from launchpad import ssh_interactive

    source = inspect.getsource(ssh_interactive.run_interactive_shell)
    assert "enable_legacy_ssh_algorithms" in source
