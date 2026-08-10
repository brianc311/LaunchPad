"""Password SSH command execution via Paramiko (non-interactive)."""

from __future__ import annotations

import re
import socket
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import paramiko

CONNECT_TIMEOUT = 15
COMMAND_TIMEOUT = 40
HPE_CLI_BUSY_TIMEOUT = 90


def keyboard_interactive_answers(
    prompt_list: list,
    *,
    password: str,
    username: str = "",
) -> list[str]:
    """Answer keyboard-interactive prompts without logging secrets.

    Matches Paramiko's password-fallback rules for 0/1 fields, and for multiple
    fields fills username prompts with ``username`` and others with ``password``.
    """
    fields = list(prompt_list or [])
    if not fields:
        return []
    if len(fields) == 1:
        return [password]
    answers: list[str] = []
    for prompt, _echo in fields:
        label = str(prompt or "").strip().lower()
        if "user" in label or "login" in label or "account" in label:
            answers.append(username)
        else:
            answers.append(password)
    return answers


def _prompt_labels(prompt_list: list) -> list[str]:
    labels: list[str] = []
    for item in prompt_list or []:
        if isinstance(item, (tuple, list)) and item:
            labels.append(str(item[0] or "").strip())
        else:
            labels.append(str(item or "").strip())
    return [label for label in labels if label]


def authenticate_with_password(
    transport: paramiko.Transport,
    username: str,
    password: str,
) -> None:
    """Authenticate using password and/or keyboard-interactive.

    IBM DS8884 (and similar) often advertise only ``publickey`` +
    ``keyboard-interactive``. Paramiko's built-in password→interactive fallback
    rejects challenges with more than one field; we answer those explicitly.
    """
    allowed: list[str] = []
    try:
        transport.auth_none(username)
    except paramiko.BadAuthenticationType as exc:
        allowed = [str(item) for item in (exc.allowed_types or [])]
    except paramiko.AuthenticationException:
        allowed = []

    seen_prompts: list[str] = []

    def keyboard_handler(
        _title: str,
        _instructions: str,
        prompt_list: list,
    ) -> list[str]:
        seen_prompts.extend(_prompt_labels(prompt_list))
        return keyboard_interactive_answers(
            prompt_list,
            password=password,
            username=username,
        )

    def raise_auth_failed(exc: Exception) -> None:
        detail = str(exc).strip() or "Authentication failed."
        if seen_prompts:
            joined = "; ".join(seen_prompts[:6])
            raise paramiko.AuthenticationException(
                f"{detail} Server prompts: {joined}"
            ) from exc
        raise paramiko.AuthenticationException(
            f"{detail} Check username/password for keyboard-interactive SSH "
            "(common on IBM DS8884)."
        ) from exc

    # Prefer plain password when offered without keyboard-interactive.
    if "password" in allowed and "keyboard-interactive" not in allowed:
        transport.auth_password(username, password, fallback=False)
        return

    # Prefer our multi-prompt keyboard-interactive handler when advertised.
    if "keyboard-interactive" in allowed:
        try:
            transport.auth_interactive(username, keyboard_handler)
            return
        except paramiko.AuthenticationException as exc:
            if "password" in allowed:
                try:
                    transport.auth_password(username, password, fallback=False)
                    return
                except paramiko.AuthenticationException as pwd_exc:
                    raise_auth_failed(pwd_exc)
                    return
            raise_auth_failed(exc)
            return

    if "password" in allowed:
        transport.auth_password(username, password, fallback=False)
        return

    # Unknown allowed set — try password with Paramiko fallback, then interactive.
    try:
        transport.auth_password(username, password, fallback=True)
        return
    except (paramiko.BadAuthenticationType, paramiko.AuthenticationException):
        pass
    try:
        transport.auth_interactive(username, keyboard_handler)
    except paramiko.AuthenticationException as exc:
        raise_auth_failed(exc)


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
    sock: socket.socket | None = None
    transport: paramiko.Transport | None = None
    try:
        sock = socket.create_connection((host, port or 22), timeout=CONNECT_TIMEOUT)
        transport = paramiko.Transport(sock)
        transport.banner_timeout = CONNECT_TIMEOUT
        transport.auth_timeout = CONNECT_TIMEOUT
        transport.start_client(timeout=CONNECT_TIMEOUT)
        # Trailing newlines from paste/forms break some keyboard-interactive hosts.
        authenticate_with_password(transport, username, (password or "").rstrip("\r\n"))
        client._transport = transport
        yield client
    finally:
        try:
            client.close()
        except OSError:
            pass
        if transport is not None:
            try:
                transport.close()
            except OSError:
                pass
        if sock is not None:
            try:
                sock.close()
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
    stdin_data: str | None = None,
) -> str:
    with password_ssh_client(host, port, username, password) as client:
        stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
        if stdin_data:
            try:
                stdin.write(stdin_data)
                stdin.flush()
                stdin.channel.shutdown_write()
            except OSError:
                pass
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
    stdin_data: str | None = None,
) -> str:
    with ssh_auth_client(
        host,
        port,
        username,
        password=password,
        key_path=key_path,
        key_passphrase=key_passphrase,
    ) as client:
        stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
        if stdin_data:
            try:
                stdin.write(stdin_data)
                stdin.flush()
                stdin.channel.shutdown_write()
            except OSError:
                pass
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
# Bare ``cli%`` / ``user%``. Real arrays often show ``HOSTNAME cli%``.
_HPE_PROMPT_RE = re.compile(r"^(?:cli|[A-Za-z0-9][\w.@\\-]*)\s*%\s*$")
_HPE_HOST_CLI_PROMPT_RE = re.compile(r"(?:^|\s)cli\s*%\s*$", re.IGNORECASE)


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
    """True for ``cli%`` / ``HOST cli%`` — false for capacity percents like ``98.5%``."""
    stripped = (line or "").strip()
    if not stripped:
        return False
    # Reject numeric percents: "98.5%", "50%", "Used 12.0%"
    if re.search(r"[\d.]\s*%\s*$", stripped):
        return False
    lowered = stripped.lower()
    if lowered in {"warn%", "used%", "use%", "%"}:
        return False
    # Most common production prompt: "ARRAYNAME cli%"
    if _HPE_HOST_CLI_PROMPT_RE.search(stripped):
        return True
    if _HPE_PROMPT_RE.match(stripped):
        return True
    if stripped == ">":
        return True
    return bool(re.match(r"^[\w.@\\-]+>\s*$", stripped)) and len(stripped) < 40


def _recv_until_hpe_prompt(channel, *, timeout: float, idle_seconds: float = 0.5) -> str:
    """Drain shell output until a real CLI prompt (used after login / setclienv)."""
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
            text = _clean_shell_text(b"".join(chunks).decode("utf-8", errors="replace"))
            lines = [line for line in text.split("\n") if line.strip()]
            if lines and _looks_like_hpe_prompt(lines[-1]) and (
                time.monotonic() - last_data
            ) >= 0.12:
                break
            continue
        if chunks and (time.monotonic() - last_data) >= idle_seconds:
            text = _clean_shell_text(b"".join(chunks).decode("utf-8", errors="replace"))
            lines = [line for line in text.split("\n") if line.strip()]
            if lines and _looks_like_hpe_prompt(lines[-1]):
                break
            # Login banners can end without a matched prompt — stop on long idle.
            if (time.monotonic() - last_data) >= max(idle_seconds, 2.0):
                break
        if channel.exit_status_ready() and not channel.recv_ready():
            break
        time.sleep(0.02)
    return b"".join(chunks).decode("utf-8", errors="replace")


def _hpe_allows_idle_exit_without_prompt(command: str) -> bool:
    """checkhealth prints 'Checking …' with multi-second gaps; idle exit truncates it."""
    return "checkhealth" not in (command or "").lower()


def _recv_hpe_command_output(
    channel,
    command: str,
    *,
    timeout: float,
    idle_seconds: float = 0.6,
) -> str:
    """Read until the CLI prompt returns after ``command``."""
    channel.send(f"{command}\r\n")
    deadline = time.monotonic() + timeout
    chunks: list[bytes] = []
    last_data = time.monotonic()
    cmd = command.strip()
    saw_echo = False
    allow_idle_exit = _hpe_allows_idle_exit_without_prompt(cmd)
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
                if (time.monotonic() - last_data) >= 0.15:
                    break
            continue
        if chunks and (time.monotonic() - last_data) >= idle_seconds:
            text = _clean_shell_text(b"".join(chunks).decode("utf-8", errors="replace"))
            lines = [line for line in text.split("\n") if line.strip()]
            if saw_echo and lines and _looks_like_hpe_prompt(lines[-1]):
                break
            # Safety: after echo + sustained idle, accept output even if prompt
            # matching fails (some builds use unusual prompt text).
            # Never do this for checkhealth — pauses between "Checking X" lines
            # routinely exceed 2.5s and would truncate mid-run.
            if (
                allow_idle_exit
                and saw_echo
                and (time.monotonic() - last_data) >= max(idle_seconds, 2.5)
            ):
                break
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
    """Run HPE CLI over an interactive shell (3PAR/Primera reject bare SSH exec)."""
    if not commands:
        return []

    # checkhealth and large show* tables often exceed the default exec timeout.
    shell_timeout = max(float(timeout), 90.0)
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
                _recv_until_hpe_prompt(channel, timeout=20)
                channel.send("setclienv csvtable 1\r\n")
                _recv_until_hpe_prompt(channel, timeout=15)

                for command in commands:
                    cmd_timeout = shell_timeout
                    if "checkhealth" in command.lower():
                        # Full checkhealth can take several minutes on large arrays.
                        cmd_timeout = max(shell_timeout, 300.0)
                    raw = _recv_hpe_command_output(
                        channel,
                        command,
                        timeout=cmd_timeout,
                    )
                    outputs.append(_extract_hpe_command_output(raw, command))

                channel.send("exit\r\n")
            finally:
                channel.close()

    return outputs
