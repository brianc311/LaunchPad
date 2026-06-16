import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from launchpad.config import APP_DATA_DIR, TEMP_DIR
from launchpad.ssh_keys import secure_private_key_file
from launchpad.ssh_passphrase import write_askpass_helper

LOG_PATH = APP_DATA_DIR / "launch.log"
SSH_EXE = r"C:\Windows\System32\OpenSSH\ssh.exe"


def _log(message: str) -> None:
    APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(f"[{stamp}] {message}\n")


def _ssh_executable() -> str:
    return shutil.which("ssh") or SSH_EXE


def _validate_private_key(key_path: Path) -> None:
    if not key_path.exists():
        raise ValueError(f"SSH key file was not created: {key_path}")
    content = key_path.read_text(encoding="utf-8")
    if "PRIVATE KEY" not in content:
        raise ValueError(
            "Stored SSH key looks invalid. In Admin, paste your private key "
            "(id_ed25519), not the .pub file."
        )


def launch_ssh(
    host: str,
    port: int | None,
    username: str,
    password: str,
    key_path: str,
    card_name: str = "SSH",
    key_passphrase: str = "",
) -> str:
    if not host:
        raise ValueError("SSH host is required.")

    user_host = f"{username}@{host}" if username else host
    ssh_exe = _ssh_executable()
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    port_value = port or 22

    key_file = Path(key_path) if key_path else None
    use_password_auth = bool(password)

    if use_password_auth:
        key_file = None
    elif key_file:
        secure_private_key_file(key_file)
        _validate_private_key(key_file)

    if not key_file and not password:
        raise ValueError("This card has no SSH password or key. Add one in Admin.")

    bat_path = TEMP_DIR / "launch_ssh.bat"
    lines = [
        "@echo off",
        f"title LaunchPad - {card_name}",
        "color 0A",
        "echo ============================================================",
        f"echo  LaunchPad SSH - {card_name}",
        f"echo  Connecting to {user_host} on port {port_value}",
        "echo ============================================================",
        "echo.",
    ]

    if key_file:
        if key_passphrase:
            askpass_cmd = write_askpass_helper(key_passphrase)
            lines.extend(
                [
                    "echo Using saved SSH private key with stored passphrase.",
                    "echo.",
                    f'set "SSH_ASKPASS={askpass_cmd}"',
                    "set SSH_ASKPASS_REQUIRE=force",
                    "set DISPLAY=launchpad",
                    (
                        f'"{ssh_exe}" -i "{key_file}" '
                        f"-o IdentitiesOnly=yes "
                        f"-o PreferredAuthentications=publickey,keyboard-interactive "
                        f"-o StrictHostKeyChecking=accept-new "
                        f"-p {port_value} {user_host}"
                    ),
                ]
            )
        else:
            lines.extend(
                [
                    "echo Using saved SSH private key.",
                    "echo Enter your key PASSPHRASE when prompted below.",
                    "echo.",
                    (
                        f'"{ssh_exe}" -i "{key_file}" '
                        f"-o IdentitiesOnly=yes "
                        f"-o PreferredAuthentications=publickey,keyboard-interactive "
                        f"-o StrictHostKeyChecking=accept-new "
                        f"-p {port_value} {user_host}"
                    ),
                ]
            )
    else:
        askpass_cmd = write_askpass_helper(password)
        lines.extend(
            [
                "echo Using stored SSH password (key auth skipped).",
                "echo.",
                f'set "SSH_ASKPASS={askpass_cmd}"',
                "set SSH_ASKPASS_REQUIRE=force",
                "set DISPLAY=launchpad",
                (
                    f'"{ssh_exe}" -o PubkeyAuthentication=no '
                    f"-o PreferredAuthentications=password,keyboard-interactive "
                    f"-o StrictHostKeyChecking=accept-new "
                    f"-p {port_value} {user_host}"
                ),
            ]
        )

    lines.extend(
        [
            "echo.",
            "if %ERRORLEVEL% NEQ 0 (",
            "  echo.",
            "  echo CONNECTION FAILED.",
            "  echo.",
            "  echo Common fixes:",
            "  echo  1. Add your PUBLIC key to the server authorized_keys",
            "  echo     Server path: /root/.ssh/authorized_keys",
            "  echo  2. Confirm SSH Key File Path in LaunchPad Admin",
            "  echo  3. Enter your key PASSPHRASE when prompted",
            "  echo.",
            ")",
            "pause",
        ]
    )
    bat_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    bat_quoted = str(bat_path).replace('"', '""')
    cmd_line = f'cmd.exe /c start "LaunchPad - {card_name}" cmd.exe /k "{bat_quoted}"'
    _log(f"Card '{card_name}' -> {user_host}")
    _log(f"Launch command: {cmd_line}")
    if key_file:
        _log(f"Key file: {key_file}")

    try:
        process = subprocess.Popen(cmd_line, shell=True, cwd=str(TEMP_DIR))
        _log(f"Spawned PID {process.pid}")
    except OSError as exc:
        _log(f"Launch failed: {exc}")
        raise ValueError(f"Could not start SSH window: {exc}") from exc

    if key_file and key_passphrase:
        return f"SSH window opened for {user_host} using stored key passphrase."
    if password:
        return f"SSH window opened for {user_host} using stored password."
    if key_file:
        return f"SSH window opened for {user_host}. Enter key passphrase if asked."
    return f"SSH window opened for {user_host}."
