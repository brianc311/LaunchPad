import re
from dataclasses import dataclass
from pathlib import Path

from launchpad.config import TEMP_DIR
from launchpad.command_format import resolve_card_commands
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


def resolve_sudo_password(card: Card, crypto_key: bytes) -> str:
    encrypted_sudo_password = getattr(card, "encrypted_sudo_password", "") or ""
    try:
        return decrypt_text(crypto_key, encrypted_sudo_password)
    except ValueError:
        return ""


@dataclass(frozen=True)
class SshMetricsAuth:
    password: str
    key_path: str
    key_passphrase: str

    @property
    def is_valid(self) -> bool:
        return bool(self.password or self.key_path)


def resolve_ssh_metrics_auth(card: Card, crypto_key: bytes) -> SshMetricsAuth:
    try:
        password = decrypt_text(crypto_key, card.encrypted_password)
    except ValueError:
        password = ""
    try:
        key_passphrase = decrypt_text(crypto_key, card.encrypted_key_passphrase)
    except ValueError:
        key_passphrase = ""

    if password:
        return SshMetricsAuth(password=password, key_path="", key_passphrase="")

    try:
        key_path = resolve_ssh_key(card, crypto_key)
    except OSError:
        key_path = ""

    return SshMetricsAuth(password="", key_path=key_path, key_passphrase=key_passphrase)


def ssh_stats_prereq_message(card: Card, crypto_key: bytes) -> str | None:
    if resolve_card_commands(
        card.device_profile,
        card.custom_commands,
        instance_id=getattr(card, "serial_number", "") or "",
    ):
        auth = resolve_ssh_metrics_auth(card, crypto_key)
        if not auth.is_valid:
            return "Add SSH Password or key\nin Admin to view stats"
        return None

    auth = resolve_ssh_metrics_auth(card, crypto_key)
    if not auth.is_valid:
        return "Add SSH Password or key\nin Admin to view stats"

    if not auth.key_path:
        return None

    try:
        key_content = Path(auth.key_path).read_text(encoding="utf-8")
    except OSError as exc:
        return f"Cannot read SSH key:\n{exc}"

    if "ENCRYPTED" in key_content and not auth.key_passphrase:
        return "Add SSH key passphrase\nin Admin to view stats"

    return None
