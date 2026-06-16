import json
from datetime import datetime, timezone
from pathlib import Path

from launchpad.crypto import decrypt_text, encrypt_text

BACKUP_VERSION = 1


def export_backup(crypto_key: bytes, cards: list[dict]) -> str:
    payload = {
        "version": BACKUP_VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "cards": cards,
    }
    encrypted = encrypt_text(crypto_key, json.dumps(payload, indent=2))
    return json.dumps({"format": "launchpad-backup", "version": BACKUP_VERSION, "data": encrypted})


def parse_backup_file(content: str, crypto_key: bytes) -> list[dict]:
    wrapper = json.loads(content)
    if wrapper.get("format") != "launchpad-backup":
        raise ValueError("Not a valid LaunchPad backup file.")

    decrypted = decrypt_text(crypto_key, wrapper["data"])
    payload = json.loads(decrypted)

    if payload.get("version") != BACKUP_VERSION:
        raise ValueError("Unsupported backup version.")

    cards = payload.get("cards")
    if not isinstance(cards, list):
        raise ValueError("Backup file is missing card data.")

    return cards


def write_backup_file(path: str | Path, crypto_key: bytes, cards: list[dict]) -> None:
    Path(path).write_text(export_backup(crypto_key, cards), encoding="utf-8")


def read_backup_file(path: str | Path, crypto_key: bytes) -> list[dict]:
    return parse_backup_file(Path(path).read_text(encoding="utf-8"), crypto_key)
