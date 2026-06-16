import os
from pathlib import Path

from launchpad.config import TEMP_DIR
from launchpad.subprocess_utils import run_hidden

_SECURED_PATHS: set[str] = set()


def _is_managed_key_path(path: Path) -> bool:
    try:
        return path.resolve().is_relative_to(TEMP_DIR.resolve())
    except AttributeError:
        temp_root = str(TEMP_DIR.resolve()).lower()
        return str(path.resolve()).lower().startswith(temp_root)


def _allow_key_file_rewrite(path: Path) -> None:
    path = Path(path)
    if not path.exists():
        return

    if os.name == "nt":
        username = os.environ.get("USERNAME", "")
        run_hidden(
            ["icacls", str(path), "/inheritance:e"],
            check=False,
            capture_output=True,
        )
        if username:
            run_hidden(
                ["icacls", str(path), "/grant", f"{username}:(F)"],
                check=False,
                capture_output=True,
            )
    else:
        path.chmod(0o600)


def secure_private_key_file(path: Path) -> None:
    path = Path(path)
    if not path.exists():
        return

    if os.name == "nt" and not _is_managed_key_path(path):
        return

    cache_key = str(path.resolve())
    if cache_key in _SECURED_PATHS:
        return

    if os.name == "nt":
        username = os.environ.get("USERNAME", "")
        run_hidden(
            ["icacls", str(path), "/inheritance:r"],
            check=False,
            capture_output=True,
        )
        if username:
            run_hidden(
                ["icacls", str(path), "/grant:r", f"{username}:(R)"],
                check=False,
                capture_output=True,
            )
        for principal in ("Everyone", "Users", "Authenticated Users", "BUILTIN\\Users"):
            run_hidden(
                ["icacls", str(path), "/remove", principal],
                check=False,
                capture_output=True,
            )
    else:
        path.chmod(0o600)

    _SECURED_PATHS.add(cache_key)


def prepare_writable_file(path: Path) -> None:
    _allow_key_file_rewrite(path)
    _SECURED_PATHS.discard(str(path.resolve()))


def write_secure_private_key(path: Path, key_text: str) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = key_text.strip() + "\n"
    if path.exists():
        try:
            if path.read_text(encoding="utf-8") == normalized:
                return path
        except OSError:
            pass

    _SECURED_PATHS.discard(str(path.resolve()))
    _allow_key_file_rewrite(path)
    path.write_text(normalized, encoding="utf-8")
    secure_private_key_file(path)
    return path
