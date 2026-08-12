from pathlib import Path

from cryptography.fernet import Fernet

from launchpad.config import APP_VERSION
from launchpad.crypto import encrypt_text
from launchpad.database import Database
from launchpad.ssh_utils import resolve_sudo_password
from launchpad.health_server import HealthCard, HealthServer


def test_card_persists_encrypted_sudo_password(tmp_path):
    db = Database(tmp_path / "launchpad.db")
    crypto_key = Fernet.generate_key()
    encrypted_sudo_password = encrypt_text(crypto_key, "sudo-secret")

    card_id = db.add_card(
        {
            "name": "Hadoop node",
            "card_type": "ssh",
            "device_profile": "hadoop_linux",
            "encrypted_sudo_password": encrypted_sudo_password,
        }
    )

    card = db.get_card(card_id)

    assert card is not None
    assert card.encrypted_sudo_password == encrypted_sudo_password
    assert resolve_sudo_password(card, crypto_key) == "sudo-secret"


def test_resolve_sudo_password_returns_empty_for_invalid_ciphertext(tmp_path):
    db = Database(tmp_path / "launchpad.db")
    card_id = db.add_card(
        {
            "name": "Hadoop node",
            "card_type": "ssh",
            "encrypted_sudo_password": "not-a-valid-token",
        }
    )
    card = db.get_card(card_id)

    assert card is not None
    assert resolve_sudo_password(card, Fernet.generate_key()) == ""


def test_admin_has_sudo_password_field_marker():
    text = Path("launchpad/ui/admin_view.py").read_text(encoding="utf-8")

    assert "sudo_password" in text
    assert "Sudo password" in text


def test_health_refresh_passes_sudo_password_for_hadoop(monkeypatch):
    server = HealthServer()
    server._cards[1] = HealthCard(
        card_id=1,
        name="Hadoop node",
        host="10.0.0.1",
        port=22,
        username="hadoop",
        key_path="",
        password="ssh-secret",
        device_profile="hadoop_linux",
        sudo_password="sudo-secret",
    )
    captured: dict = {}

    def run_suite(*args, **kwargs):
        captured.update(kwargs)
        return []

    monkeypatch.setattr("launchpad.health_server.run_remote_command_suite", run_suite)

    server.refresh_card(1)

    assert captured["sudo_password"] == "sudo-secret"


def test_host_power_runner_passes_sudo_password_for_hadoop(monkeypatch):
    card = HealthCard(
        card_id=1,
        name="Hadoop node",
        host="10.0.0.1",
        port=22,
        username="hadoop",
        key_path="",
        password="ssh-secret",
        device_profile="hadoop_linux",
        sudo_password="sudo-secret",
    )
    captured: dict = {}

    def run_command(*args, **kwargs):
        captured.update(kwargs)
        return "ok"

    monkeypatch.setattr("launchpad.health_server.run_remote_ssh_command", run_command)

    HealthServer._snap_run_command(card)("sudo shutdown -h now")

    assert captured["sudo_password"] == "sudo-secret"


def test_host_power_runner_ignores_sudo_password_for_non_hadoop(monkeypatch):
    card = HealthCard(
        card_id=1,
        name="Linux node",
        host="10.0.0.1",
        port=22,
        username="operator",
        key_path="",
        password="ssh-secret",
        device_profile="generic_ssh",
        sudo_password="sudo-secret",
    )
    captured: dict = {}

    def run_command(*args, **kwargs):
        captured.update(kwargs)
        return "ok"

    monkeypatch.setattr("launchpad.health_server.run_remote_ssh_command", run_command)

    HealthServer._snap_run_command(card)("sudo systemctl status service")

    assert captured["device_profile"] == "generic_ssh"
    assert captured["sudo_password"] == ""


def test_version_157():
    assert APP_VERSION == "1.6.157"
