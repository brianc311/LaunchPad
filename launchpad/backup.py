import json
from datetime import datetime, timezone
from pathlib import Path

from launchpad.crypto import decrypt_text, derive_key, encrypt_text

BACKUP_VERSION = 1
SECRET_CARD_FIELDS = ("encrypted_password", "encrypted_key_passphrase", "encrypted_key")


class BackupDecryptError(ValueError):
    """Backup ciphertext could not be opened with the supplied vault key."""


def export_backup(crypto_key: bytes, cards: list[dict], *, master_salt: str = "") -> str:
    payload = {
        "version": BACKUP_VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "cards": cards,
    }
    encrypted = encrypt_text(crypto_key, json.dumps(payload, indent=2))
    wrapper: dict[str, object] = {
        "format": "launchpad-backup",
        "version": BACKUP_VERSION,
        "data": encrypted,
    }
    if master_salt:
        wrapper["master_salt"] = master_salt
    return json.dumps(wrapper)


def read_backup_wrapper(content: str) -> dict:
    wrapper = json.loads(content)
    if wrapper.get("format") != "launchpad-backup":
        raise ValueError("Not a valid LaunchPad backup file.")
    return wrapper


def parse_backup_file(content: str, crypto_key: bytes) -> list[dict]:
    wrapper = read_backup_wrapper(content)
    try:
        decrypted = decrypt_text(crypto_key, wrapper["data"])
    except ValueError as exc:
        raise BackupDecryptError(str(exc)) from exc

    payload = json.loads(decrypted)

    if payload.get("version") != BACKUP_VERSION:
        raise ValueError("Unsupported backup version.")

    cards = payload.get("cards")
    if not isinstance(cards, list):
        raise ValueError("Backup file is missing card data.")

    return cards


def migrate_card_secrets(cards: list[dict], from_key: bytes, to_key: bytes) -> list[dict]:
    if from_key == to_key:
        return cards

    migrated: list[dict] = []
    for entry in cards:
        copy = dict(entry)
        for field in SECRET_CARD_FIELDS:
            ciphertext = copy.get(field, "")
            if not ciphertext:
                continue
            plaintext = decrypt_text(from_key, ciphertext)
            copy[field] = encrypt_text(to_key, plaintext)
        migrated.append(copy)
    return migrated


def read_backup_file(
    path: str | Path,
    crypto_key: bytes,
    *,
    backup_password: str = "",
    backup_master_salt: str = "",
    vault_crypto_key: bytes | None = None,
) -> list[dict]:
    content = Path(path).read_text(encoding="utf-8")
    wrapper = read_backup_wrapper(content)
    salt = backup_master_salt or wrapper.get("master_salt", "")

    keys_to_try: list[bytes] = [crypto_key]
    if backup_password and salt:
        keys_to_try.insert(0, derive_key(backup_password, salt))

    last_error: BackupDecryptError | None = None
    for key in keys_to_try:
        try:
            cards = parse_backup_file(content, key)
            target_key = vault_crypto_key if vault_crypto_key is not None else crypto_key
            if key != target_key:
                return migrate_card_secrets(cards, key, target_key)
            return cards
        except BackupDecryptError as exc:
            last_error = exc

    if last_error:
        raise last_error
    raise BackupDecryptError("Unable to decrypt backup file.")


def write_backup_file(
    path: str | Path,
    crypto_key: bytes,
    cards: list[dict],
    *,
    master_salt: str = "",
) -> None:
    Path(path).write_text(export_backup(crypto_key, cards, master_salt=master_salt), encoding="utf-8")
