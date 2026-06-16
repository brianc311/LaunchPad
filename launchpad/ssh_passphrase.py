import os
import shutil
import sys
from pathlib import Path

from launchpad.config import TEMP_DIR
from launchpad.ssh_keys import prepare_writable_file


def _bundled_askpass_exe() -> Path:
    candidates: list[Path] = []
    if getattr(sys, "frozen", False):
        candidates.extend(
            [
                Path(sys.executable).with_name("ssh_askpass.exe"),
                Path(getattr(sys, "_MEIPASS", "")) / "ssh_askpass.exe",
            ]
        )
    else:
        root = Path(__file__).resolve().parents[1]
        candidates.extend(
            [
                root / "dist_new" / "ssh_askpass.exe",
                root / "dist" / "ssh_askpass.exe",
            ]
        )

    for candidate in candidates:
        if candidate.exists():
            return candidate

    raise FileNotFoundError(
        "ssh_askpass.exe was not found. Rebuild LaunchPad to include the hidden askpass helper."
    )


def write_askpass_helper(passphrase: str) -> Path:
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    askpass_exe = TEMP_DIR / "ssh_askpass.exe"
    secret_file = TEMP_DIR / "ssh_askpass.secret"

    bundled = _bundled_askpass_exe()
    if not askpass_exe.exists() or bundled.stat().st_mtime > askpass_exe.stat().st_mtime:
        shutil.copy2(bundled, askpass_exe)

    prepare_writable_file(secret_file)
    secret_file.write_text(passphrase, encoding="utf-8")

    for legacy in (
        TEMP_DIR / "ssh_askpass.cmd",
        TEMP_DIR / "ssh_askpass.vbs",
        TEMP_DIR / "ssh_askpass.pyw",
    ):
        if legacy.exists():
            legacy.unlink(missing_ok=True)

    return askpass_exe


def askpass_env(passphrase: str) -> dict[str, str]:
    if not passphrase:
        return {}
    helper = write_askpass_helper(passphrase)
    return {
        "SSH_ASKPASS": str(helper),
        "SSH_ASKPASS_REQUIRE": "force",
        "DISPLAY": "launchpad",
    }
