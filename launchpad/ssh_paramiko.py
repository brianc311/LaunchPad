"""Password SSH command execution via Paramiko (non-interactive)."""

from __future__ import annotations

import re
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import paramiko

CONNECT_TIMEOUT = 15
COMMAND_TIMEOUT = 40
HPE_CLI_BUSY_TIMEOUT = 90

_lock_guard = threading.Lock()
_hpe_host_locks: dict[str, threading.Lock] = {}


def _host_lock_key(host: str, port: int | None) -> str:
    return f"{host}:{port or 22}"


def _hpe_host_lock(host: str, port: int | None) -> threading.Lock:
    key = _host_lock_key(host, port)
    with _lock_guard:
        lock = _hpe_host_locks.get(key)
        if lock is None:
            lock = threading.Lock()
            _hpe_host_locks[key] = lock
        return lock


@contextmanager
def _acquire_hpe_cli_lock(host: str, port: int | None) -> Iterator[None]:
    lock = _hpe_host_lock(host, port)
    acquired = lock.acquire(timeout=HPE_CLI_BUSY_TIMEOUT)
    if not acquired:
        raise ValueError(
            f"Storage CLI session to {host} is busy. "
            "Wait for the current stats refresh to finish, then try again."
        )
    try:
        yield
    finally:
        lock.release()


def _load_private_key(key_path: str, passphrase: str | None) -> paramiko.PKey:
    path = Path(key_path)
    if not path.is_file():
        raise ValueError(f"SSH key file not found:\n{key_path}")

    try:
        key_text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise ValueError(f"Cannot read SSH key file:\n{exc}") from exc

    if "ENCRYPTED" in key_text and not (passphrase or "").strip():
        raise ValueError("SSH key is encrypted. Enter the key passphrase in Admin.")

    errors: list[str] = []
    for key_cls in (paramiko.Ed25519Key, paramiko.ECDSAKey, paramiko.RSAKey):
        try:
            return key_cls.from_private_key_file(str(path), password=passphrase or None)
        except paramiko.PasswordRequiredException as exc:
            raise ValueError("SSH key is encrypted. Enter the key passphrase in Admin.") from exc
        except Exception as exc:
            errors.append(str(exc))

    detail = errors[0] if errors else "unsupported key format"
    raise ValueError(f"Could not load SSH private key: {detail}")


@contextmanager
def password_ssh_client(
    host: str,
    port: int | None,
    username: str,
    password: str,
) -> Iterator[paramiko.SSHClient]:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(
            hostname=host,
            port=port or 22,
            username=username,
            password=password,
            allow_agent=False,
            look_for_keys=False,
            timeout=CONNECT_TIMEOUT,
            banner_timeout=CONNECT_TIMEOUT,
            auth_timeout=CONNECT_TIMEOUT,
        )
        yield client
    finally:
        try:
            client.close()
        except OSError:
            pass


@contextmanager
def key_ssh_client(
    host: str,
    port: int | None,
    username: str,
    key_path: str,
    key_passphrase: str = "",
) -> Iterator[paramiko.SSHClient]:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    pkey = _load_private_key(key_path, key_passphrase or None)
    try:
        client.connect(
            hostname=host,
            port=port or 22,
            username=username,
            pkey=pkey,
            allow_agent=False,
            look_for_keys=False,
            timeout=CONNECT_TIMEOUT,
            banner_timeout=CONNECT_TIMEOUT,
            auth_timeout=CONNECT_TIMEOUT,
        )
        yield client
    finally:
        try:
            client.close()
        except OSError:
            pass


@contextmanager
def ssh_auth_client(
    host: str,
    port: int | None,
    username: str,
    *,
    password: str = "",
    key_path: str = "",
    key_passphrase: str = "",
) -> Iterator[paramiko.SSHClient]:
    if password:
        with password_ssh_client(host, port, username, password) as client:
            yield client
        return
    if key_path:
        with key_ssh_client(host, port, username, key_path, key_passphrase) as client:
            yield client
        return
    raise ValueError("SSH password or private key is required.")


def _read_command_output(stdout, stderr, *, exit_status: int) -> str:
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    if exit_status != 0:
        detail = err or out or "Unknown SSH error"
        raise ValueError(detail)
    if err and not out:
        return err
    if err and out:
        return f"{out}\n\n{err}".strip()
    return out


def run_ssh_command(
    host: str,
    port: int | None,
    username: str,
    password: str,
    command: str,
    *,
    timeout: int = COMMAND_TIMEOUT,
) -> str:
    with password_ssh_client(host, port, username, password) as client:
        _, stdout, stderr = client.exec_command(command, timeout=timeout)
        exit_status = stdout.channel.recv_exit_status()
        return _read_command_output(stdout, stderr, exit_status=exit_status)


def run_ssh_auth_command(
    host: str,
    port: int | None,
    username: str,
    command: str,
    *,
    password: str = "",
    key_path: str = "",
    key_passphrase: str = "",
    timeout: int = COMMAND_TIMEOUT,
) -> str:
    with ssh_auth_client(
        host,
        port,
        username,
        password=password,
        key_path=key_path,
        key_passphrase=key_passphrase,
    ) as client:
        _, stdout, stderr = client.exec_command(command, timeout=timeout)
        exit_status = stdout.channel.recv_exit_status()
        return _read_command_output(stdout, stderr, exit_status=exit_status)


def run_ssh_commands(
    host: str,
    port: int | None,
    username: str,
    password: str,
    commands: list[str],
    *,
    timeout: int = COMMAND_TIMEOUT,
) -> list[str]:
    outputs: list[str] = []
    with password_ssh_client(host, port, username, password) as client:
        for command in commands:
            _, stdout, stderr = client.exec_command(command, timeout=timeout)
            exit_status = stdout.channel.recv_exit_status()
            outputs.append(_read_command_output(stdout, stderr, exit_status=exit_status))
    return outputs


_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9?]*[ -/]*[@-~]")


def _clean_shell_text(raw: str) -> str:
    return _ANSI_ESCAPE_RE.sub("", raw.replace("\r\n", "\n").replace("\r", "\n"))


def _recv_shell(channel, *, timeout: float, idle_seconds: float = 0.35) -> str:
    deadline = time.monotonic() + timeout
    chunks: list[bytes] = []
    last_data = time.monotonic()
    while time.monotonic() < deadline:
        if channel.recv_ready():
            chunk = channel.recv(65536)
            if not chunk:
                break
            chunks.append(chunk)
            last_data = time.monotonic()
            continue
        if chunks and (time.monotonic() - last_data) >= idle_seconds:
            break
        if channel.exit_status_ready() and not channel.recv_ready():
            break
        time.sleep(0.02)
    return b"".join(chunks).decode("utf-8", errors="replace")


def _looks_like_hpe_prompt(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if stripped in {"%", ">"}:
        return True
    return stripped.endswith("%") or stripped.endswith(">")


def _recv_hpe_command_output(
    channel,
    command: str,
    *,
    timeout: float,
    idle_seconds: float = 0.45,
) -> str:
    """Read until the CLI prompt returns after ``command`` (avoids checkhealth bleed)."""
    channel.send(f"{command}\r\n")
    deadline = time.monotonic() + timeout
    chunks: list[bytes] = []
    last_data = time.monotonic()
    cmd = command.strip()
    saw_echo = False
    while time.monotonic() < deadline:
        if channel.recv_ready():
            chunk = channel.recv(65536)
            if not chunk:
                break
            chunks.append(chunk)
            last_data = time.monotonic()
            text = _clean_shell_text(b"".join(chunks).decode("utf-8", errors="replace"))
            if cmd and cmd in text:
                saw_echo = True
            lines = [line for line in text.split("\n") if line.strip()]
            if saw_echo and lines and _looks_like_hpe_prompt(lines[-1]):
                # Brief settle so trailing bytes after the prompt are included.
                if (time.monotonic() - last_data) >= 0.12:
                    break
            continue
        if chunks and (time.monotonic() - last_data) >= idle_seconds:
            text = _clean_shell_text(b"".join(chunks).decode("utf-8", errors="replace"))
            if saw_echo or (cmd and cmd in text) or _looks_like_hpe_prompt(
                text.splitlines()[-1] if text.splitlines() else ""
            ):
                break
            # Leftover from a prior command — keep waiting for this command's echo.
            continue
        if channel.exit_status_ready() and not channel.recv_ready():
            break
        time.sleep(0.02)
    return b"".join(chunks).decode("utf-8", errors="replace")


def _extract_hpe_command_output(raw: str, command: str) -> str:
    lines = _clean_shell_text(raw).split("\n")
    cmd = command.strip()
    start: int | None = None
    for idx, line in enumerate(lines):
        if cmd in line and "setclienv" not in line.lower():
            start = idx + 1
            break
    if start is None:
        for idx, line in enumerate(lines):
            if "setclienv" in line.lower():
                start = idx + 1
                break
    if start is None:
        # Prefer content after the last checkhealth-style noise when echo was missed.
        start = 0
        for idx, line in enumerate(lines):
            lowered = line.strip().lower()
            if lowered.startswith("checking ") or lowered in {"ok", "passed"}:
                start = idx + 1

    end = len(lines)
    for idx in range(len(lines) - 1, start - 1, -1):
        stripped = lines[idx].strip()
        if not stripped:
            end = idx
            continue
        if stripped == "exit" or _looks_like_hpe_prompt(stripped):
            end = idx
            continue
        break

    body = [line for line in lines[start:end] if line.strip() and line.strip() != "exit"]
    return "\n".join(body).strip()


def run_ssh_auth_hpe_commands(
    host: str,
    port: int | None,
    username: str,
    commands: list[str],
    *,
    password: str = "",
    key_path: str = "",
    key_passphrase: str = "",
    timeout: int = COMMAND_TIMEOUT,
) -> list[str]:
    if not commands:
        return []

    outputs: list[str] = []
    with _acquire_hpe_cli_lock(host, port):
        with ssh_auth_client(
            host,
            port,
            username,
            password=password,
            key_path=key_path,
            key_passphrase=key_passphrase,
        ) as client:
            channel = client.invoke_shell(term="vt100", width=220, height=48)
            channel.settimeout(0.1)
            try:
                _recv_shell(channel, timeout=8)
                channel.send("setclienv csvtable 1\r\n")
                _recv_shell(channel, timeout=8, idle_seconds=0.5)

                for command in commands:
                    raw = _recv_hpe_command_output(
                        channel,
                        command,
                        timeout=float(timeout),
                    )
                    outputs.append(_extract_hpe_command_output(raw, command))

                channel.send("exit\r\n")
            finally:
                channel.close()

    return outputs
