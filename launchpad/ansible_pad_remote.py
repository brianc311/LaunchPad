"""Remote SCP sync and ansible-playbook command helpers for Ansible Pad."""

from __future__ import annotations

import io
import shlex
from typing import Any, Callable


def build_ansible_playbook_argv(
    *,
    playbook: str,
    inventory: str | None,
    check: bool,
) -> list[str]:
    """Build argv for ansible-playbook on the control host."""
    argv = ["ansible-playbook"]
    if inventory:
        argv.extend(["-i", inventory])
    argv.append(playbook)
    if check:
        argv.append("--check")
    return argv


def require_confirm_for_mutate(*, check: bool, confirm: bool) -> None:
    """Raise ValueError when a mutating run lacks explicit confirm."""
    if not check and not confirm:
        raise ValueError("confirm=true is required for mutating ansible-playbook runs")


def _ensure_remote_dir(sftp: Any, remote_path: str) -> None:
    normalized = remote_path.replace("\\", "/")
    if not normalized or normalized == "/":
        return

    is_absolute = normalized.startswith("/")
    parts = [part for part in normalized.split("/") if part]
    current = "/" if is_absolute else ""

    for part in parts:
        current = f"{current}/{part}" if current else part
        try:
            sftp.stat(current)
        except (FileNotFoundError, OSError, IOError):
            sftp.mkdir(current)


def sync_files_via_sftp(sftp: Any, remote_dir: str, files: dict[str, str]) -> None:
    """Upload package files to remote_dir via an injectable SFTP-like client."""
    base = remote_dir.replace("\\", "/").rstrip("/")
    if not base:
        raise ValueError("remote_dir is required")

    _ensure_remote_dir(sftp, base)

    for rel_path, content in files.items():
        normalized = rel_path.replace("\\", "/").lstrip("/")
        remote_path = f"{base}/{normalized}"
        parent = remote_path.rsplit("/", 1)[0]
        if parent:
            _ensure_remote_dir(sftp, parent)

        payload = io.BytesIO(content.encode("utf-8"))
        if hasattr(sftp, "putfo"):
            sftp.putfo(payload, remote_path)
            continue

        with sftp.open(remote_path, "w") as remote_file:
            remote_file.write(content)


def _normalize_exec_result(result: Any) -> dict:
    if isinstance(result, dict):
        return {
            "returncode": int(result.get("returncode", 0)),
            "stdout": str(result.get("stdout", "")),
            "stderr": str(result.get("stderr", "")),
        }

    returncode = getattr(result, "returncode", 0)
    stdout = getattr(result, "stdout", "")
    stderr = getattr(result, "stderr", "")
    if isinstance(stdout, bytes):
        stdout = stdout.decode("utf-8", errors="replace")
    if isinstance(stderr, bytes):
        stderr = stderr.decode("utf-8", errors="replace")
    return {
        "returncode": int(returncode),
        "stdout": str(stdout),
        "stderr": str(stderr),
    }


def run_remote_argv(
    exec_fn: Callable[[str], Any],
    argv: list[str],
    *,
    cwd: str | None = None,
) -> dict:
    """Run argv on the remote host via exec_fn; return returncode/stdout/stderr."""
    if not argv:
        raise ValueError("argv must not be empty")

    command = shlex.join(argv)
    if cwd:
        command = f"cd {shlex.quote(cwd)} && {command}"

    return _normalize_exec_result(exec_fn(command))
