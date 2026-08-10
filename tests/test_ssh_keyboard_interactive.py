"""Password SSH with keyboard-interactive support (e.g. IBM DS8884)."""

from __future__ import annotations

from unittest.mock import MagicMock

import paramiko

from launchpad.ssh_paramiko import authenticate_with_password


def test_authenticate_prefers_password_when_server_offers_it():
    transport = MagicMock()
    transport.auth_none.side_effect = paramiko.BadAuthenticationType(
        "Bad authentication type",
        ["password", "publickey"],
    )
    authenticate_with_password(transport, "admin", "secret")
    transport.auth_password.assert_called_once_with("admin", "secret")
    transport.auth_interactive.assert_not_called()


def test_authenticate_uses_keyboard_interactive_when_password_not_allowed():
    transport = MagicMock()
    transport.auth_none.side_effect = paramiko.BadAuthenticationType(
        "Bad authentication type",
        ["publickey", "keyboard-interactive"],
    )
    authenticate_with_password(transport, "admin", "secret")
    transport.auth_password.assert_not_called()
    transport.auth_interactive.assert_called_once()
    username, handler = transport.auth_interactive.call_args[0]
    assert username == "admin"
    assert handler(None, None, [("Password:", False)]) == ["secret"]


def test_authenticate_falls_back_to_keyboard_interactive_when_none_lists_nothing():
    transport = MagicMock()
    transport.auth_none.side_effect = paramiko.AuthenticationException("fail")
    transport.auth_password.side_effect = paramiko.BadAuthenticationType(
        "Bad authentication type",
        ["keyboard-interactive"],
    )
    authenticate_with_password(transport, "admin", "secret")
    transport.auth_interactive.assert_called_once()
