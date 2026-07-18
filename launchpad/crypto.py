import base64
import hashlib
import secrets

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


def generate_salt() -> str:
    return base64.b64encode(secrets.token_bytes(16)).decode("ascii")


def hash_password(password: str, salt_b64: str) -> str:
    salt = base64.b64decode(salt_b64.encode("ascii"))
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 600_000)
    return base64.b64encode(digest).decode("ascii")


def verify_password(password: str, salt_b64: str, expected_hash: str) -> bool:
    return secrets.compare_digest(hash_password(password, salt_b64), expected_hash)


def derive_key(password: str, salt_b64: str) -> bytes:
    salt = base64.b64decode(salt_b64.encode("ascii"))
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=600_000,
    )
    raw = kdf.derive(password.encode("utf-8"))
    return base64.urlsafe_b64encode(raw)


def encrypt_text(key: bytes, plaintext: str) -> str:
    if not plaintext:
        return ""
    token = Fernet(key).encrypt(plaintext.encode("utf-8"))
    return token.decode("ascii")


def decrypt_text(key: bytes, ciphertext: str) -> str:
    if not ciphertext:
        return ""
    try:
        return Fernet(key).decrypt(ciphertext.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError(
            "Unable to decrypt stored credentials. "
            "If you restored from backup, re-import using the export master password, "
            "or re-enter credentials in Admin and save the card."
        ) from exc
