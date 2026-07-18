"""Interactive SSH shell for password-authenticated sessions on Windows."""

from __future__ import annotations

import os
import shutil
import sys
import threading
import time
from pathlib import Path

import paramiko

from launchpad.config import TEMP_DIR

SECRET_FILE = TEMP_DIR / "ssh_askpass.secret"


def _read_password() -> str:
    if not SECRET_FILE.exists():
        raise ValueError(f"SSH password secret file not found: {SECRET_FILE}")
    return SECRET_FILE.read_text(encoding="utf-8")


def _set_console_title(title: str) -> None:
    if os.name != "nt":
        return
    safe = title.replace('"', "'")
    os.system(f'title "{safe}"')
    os.system("color 0A")


def run_interactive_shell(
    host: str,
    port: int,
    username: str,
    password: str,
    *,
    title: str = "LaunchPad SSH",
) -> int:
    _set_console_title(title)

    print("=" * 60)
    print(f" LaunchPad SSH - {title}")
    print(f" Connecting to {username}@{host}:{port}")
    print("=" * 60)
    print()
    print("Signing in with saved password...")
    print()

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        client.connect(
            hostname=host,
            port=port,
            username=username,
            password=password,
            allow_agent=False,
            look_for_keys=False,
            timeout=20,
            banner_timeout=20,
            auth_timeout=20,
        )
    except paramiko.AuthenticationException:
        print("Authentication failed. Check username and password in LaunchPad Admin.")
        return 1
    except Exception as exc:
        print(f"Connection failed: {exc}")
        return 1

    cols, rows = shutil.get_terminal_size(fallback=(120, 40))
    channel = client.invoke_shell(term="vt100", width=cols, height=rows)
    channel.settimeout(0.1)

    stop = threading.Event()

    def reader() -> None:
        while not stop.is_set():
            try:
                if channel.recv_ready():
                    data = channel.recv(4096)
                    if not data:
                        break
                    sys.stdout.buffer.write(data)
                    sys.stdout.buffer.flush()
                elif channel.exit_status_ready():
                    break
            except TimeoutError:
                continue
            except OSError:
                if stop.is_set():
                    break
            time.sleep(0.01)

    reader_thread = threading.Thread(target=reader, daemon=True)
    reader_thread.start()

    try:
        import msvcrt

        while not channel.exit_status_ready():
            if msvcrt.kbhit():
                char = msvcrt.getch()
                if char == b"\x03":
                    channel.send(char)
                    continue
                if char in (b"\r", b"\n"):
                    channel.send(b"\r")
                else:
                    channel.send(char)
            time.sleep(0.02)
    except KeyboardInterrupt:
        channel.send(b"\x03")
    finally:
        stop.set()
        reader_thread.join(timeout=1)
        client.close()

    return 0


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if len(argv) < 3:
        print("Usage: ssh_interactive <host> <port> <username> [title]")
        return 2

    host = argv[0]
    port = int(argv[1])
    username = argv[2]
    title = argv[3] if len(argv) > 3 else f"LaunchPad SSH - {host}"

    try:
        password = _read_password()
    except ValueError as exc:
        print(exc)
        return 1

    return run_interactive_shell(host, port, username, password, title=title)


if __name__ == "__main__":
    raise SystemExit(main())
