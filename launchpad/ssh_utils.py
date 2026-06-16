import re
from pathlib import Path

from launchpad.config import TEMP_DIR
from launchpad.crypto import decrypt_text
from launchpad.database import Card
from launchpad.ssh_keys import write_secure_private_key

_WINDOWS_PATH_START = re.compile(r"[A-Za-z]:\\")


def normalize_key_file_path(value: str) -> str:
    raw = value.strip().strip('"')
    if not raw:
        return ""

    starts = [match.start() for match in _WINDOWS_PATH_START.finditer(raw)]
    if not starts:
        return raw

    candidates: list[str] = []
    for index, start in enumerate(starts):
        end = starts[index + 1] if index + 1 < len(starts) else len(raw)
        candidates.append(raw[start:end].strip())

    file_matches = [candidate for candidate in reversed(candidates) if Path(candidate).expanduser().is_file()]
    if file_matches:
        return str(Path(file_matches[0]).expanduser())

    for candidate in reversed(candidates):
        path = Path(candidate).expanduser()
        if path.exists():
            return str(path)

    ssh_matches = [candidate for candidate in sorted(candidates, key=len, reverse=True) if ".ssh" in candidate.lower()]
    if ssh_matches:
        return str(Path(ssh_matches[0]).expanduser())

    return str(Path(candidates[-1]).expanduser())


def resolve_ssh_key(card: Card, crypto_key: bytes) -> str:
    configured_raw = getattr(card, "key_file_path", "") or ""
    if configured_raw.strip():
        configured = Path(normalize_key_file_path(configured_raw)).expanduser()
        if configured.exists():
            return str(configured)

    key_text = decrypt_text(crypto_key, card.encrypted_key)
    if key_text.strip():
        key_path = write_secure_private_key(TEMP_DIR / f"card_{card.id}_key", key_text)
        return str(key_path)

    return ""
