from cryptography.fernet import Fernet

from launchpad.crypto import encrypt_text
from launchpad.database import Database
from launchpad.ssh_utils import resolve_sudo_password


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
    from pathlib import Path

    text = Path("launchpad/ui/admin_view.py").read_text(encoding="utf-8")

    assert "sudo_password" in text
    assert "Sudo password" in text
