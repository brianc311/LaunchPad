"""Password SSH with keyboard-interactive support (e.g. IBM DS8884)."""

from __future__ import annotations

from unittest.mock import MagicMock

import paramiko
import pytest

from launchpad.ssh_paramiko import (
    authenticate_with_password,
    keyboard_interactive_answers,
)


def test_keyboard_answers_single_and_multi_field():
    assert keyboard_interactive_answers([], password="secret") == []
    assert keyboard_interactive_answers(
        [("Password:", False)],
        password="secret",
    ) == ["secret"]
    assert keyboard_interactive_answers(
        [("login:", True), ("Password:", False)],
        password="secret",
        username="admin",
    ) == ["admin", "secret"]


def test_keyboard_answers_single_username_prompt_uses_password():
    """SSH already sent the username; a lone login: field is the password challenge.

    IBM XIV rejects sending ``admin`` again (wrong keyboard-interactive auth).
    """
    assert keyboard_interactive_answers(
        [("login:", True)],
        password="secret",
        username="admin",
    ) == ["secret"]
    assert keyboard_interactive_answers(
        [("Username:", True)],
        password="secret",
        username="admin",
    ) == ["secret"]
    assert keyboard_interactive_answers(
        [("Password for user admin:", False)],
        password="secret",
        username="admin",
    ) == ["secret"]


def test_authenticate_sends_password_to_lone_login_prompt():
    transport = MagicMock()
    transport.auth_none.side_effect = paramiko.BadAuthenticationType(
        "Bad authentication type",
        ["publickey", "keyboard-interactive"],
    )
    authenticate_with_password(transport, "admin", "secret")
    _username, handler = transport.auth_interactive.call_args[0]
    assert handler(None, None, [("login:", True)]) == ["secret"]


def test_authenticate_uses_password_when_only_password_allowed():
    transport = MagicMock()
    transport.auth_none.side_effect = paramiko.BadAuthenticationType(
        "Bad authentication type",
        ["password", "publickey"],
    )
    authenticate_with_password(transport, "admin", "secret")
    transport.auth_password.assert_called_once_with(
        "admin", "secret", fallback=False
    )
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
    assert handler(None, None, [("User:", True), ("Password:", False)]) == [
        "admin",
        "secret",
    ]


def test_authenticate_includes_server_prompts_on_failure():
    transport = MagicMock()
    transport.auth_none.side_effect = paramiko.BadAuthenticationType(
        "Bad authentication type",
        ["keyboard-interactive"],
    )

    def fail_interactive(username, handler, *args, **kwargs):
        handler(None, None, [("Password:", False)])
        raise paramiko.AuthenticationException("Authentication failed.")

    transport.auth_interactive.side_effect = fail_interactive
    with pytest.raises(paramiko.AuthenticationException) as excinfo:
        authenticate_with_password(transport, "admin", "secret")
    assert "Server prompts: Password:" in str(excinfo.value)
