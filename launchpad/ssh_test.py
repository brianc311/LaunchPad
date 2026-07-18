"""Non-interactive SSH login test for Admin."""

from __future__ import annotations

from pathlib import Path

from launchpad.config import TEMP_DIR
from launchpad.ssh_keys import write_secure_private_key
from launchpad.ssh_paramiko import run_ssh_auth_command
from launchpad.ssh_utils import normalize_key_file_path

# Restricted shells (e.g. IBM FlashSystem rbash) often lack hostname/whoami in PATH.
_TEST_COMMAND = "echo LaunchPad-SSH-OK"
_TEST_TIMEOUT = 20


def resolve_test_key_path(
    key_file_path: str,
    ssh_key_text: str,
    *,
    temp_name: str = "admin_ssh_test_key",
) -> str:
    configured = normalize_key_file_path(key_file_path)
    if configured:
        path = Path(configured).expanduser()
        if path.is_file():
            return str(path)

    key_text = (ssh_key_text or "").strip()
    if key_text:
        return str(write_secure_private_key(TEMP_DIR / temp_name, key_text))

    return ""


def test_ssh_login(
    host: str,
    port: int | None,
    username: str,
    *,
    password: str = "",
    key_file_path: str = "",
    key_passphrase: str = "",
    ssh_key_text: str = "",
) -> str:
    host = host.strip()
    username = username.strip()
    if not host:
        raise ValueError("Host is required.")
    if not username:
        raise ValueError("Username is required.")

    password = password or ""
    key_passphrase = key_passphrase or ""
    key_path = resolve_test_key_path(key_file_path, ssh_key_text)

    if not password and not key_path:
        raise ValueError("Set SSH Password or an SSH key file / private key to test login.")

    if key_file_path.strip() and not key_path and not password:
        path = Path(normalize_key_file_path(key_file_path)).expanduser()
        raise ValueError(f"SSH key file not found:\n{path}")

    output = run_ssh_auth_command(
        host,
        port,
        username,
        _TEST_COMMAND,
        password=password,
        key_path=key_path if not password else "",
        key_passphrase=key_passphrase,
        timeout=_TEST_TIMEOUT,
    )

    port_label = f":{port}" if port else ""
    target = f"{username}@{host}{port_label}"
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    detail = "\n".join(lines) if lines else output.strip() or "Login succeeded."
    return f"Connected to {target}\n\n{detail}"


def probe_ssh_login_for_card(card, crypto_key: bytes) -> tuple[str, str]:
    """Return (status, message) for dashboard LED: ok, fail, or nocreds."""
    from launchpad.ssh_utils import resolve_ssh_metrics_auth, ssh_stats_prereq_message

    reason = ssh_stats_prereq_message(card, crypto_key)
    if reason:
        return "nocreds", reason.replace("\n", " ")

    auth = resolve_ssh_metrics_auth(card, crypto_key)
    try:
        run_ssh_auth_command(
            card.host,
            card.port,
            card.username,
            _TEST_COMMAND,
            password=auth.password,
            key_path=auth.key_path if not auth.password else "",
            key_passphrase=auth.key_passphrase,
            timeout=12,
        )
        return "ok", ""
    except Exception as exc:
        message = str(exc).splitlines()[0][:72]
        return "fail", message
