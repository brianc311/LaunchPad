"""Rewrite DSCLI command strings for remote SSH execution."""

from __future__ import annotations


def _is_dscli_invocation(command: str) -> bool:
    parts = command.strip().split(None, 1)
    if not parts:
        return False
    token = parts[0].strip('"').lower().replace("\\", "/")
    base = token.rsplit("/", 1)[-1]
    return base in {"dscli", "dscli.bat", "dscli.exe"} or base.endswith("/dscli")


def _quote_exe(path: str) -> str:
    path = path.strip()
    if not path:
        return "dscli"
    if path.startswith('"') and path.endswith('"'):
        return path
    if any(ch in path for ch in (" ", "\t")):
        return f'"{path}"'
    return path


def wrap_dscli_command(
    command: str,
    *,
    dscli_path: str = "",
    hmc_host: str = "",
    username: str = "",
    password: str = "",
) -> str:
    raw = (command or "").strip()
    if not raw or not _is_dscli_invocation(raw):
        return raw
    parts = raw.split(None, 1)
    rest = parts[1] if len(parts) > 1 else ""
    exe = _quote_exe(dscli_path) if dscli_path.strip() else parts[0]
    flags: list[str] = []
    hmc = (hmc_host or "").strip()
    if hmc:
        flags.extend(["-hmc1", hmc])
        user = (username or "").strip()
        pwd = password or ""
        if pwd:
            if user:
                flags.extend(["-user", user])
            flags.extend(["-passwd", pwd])
    mid = " ".join(flags)
    if mid and rest:
        return f"{exe} {mid} {rest}"
    if mid:
        return f"{exe} {mid}"
    if rest:
        return f"{exe} {rest}"
    return exe


def wrap_dscli_command_list(
    commands: list[str],
    *,
    dscli_path: str = "",
    hmc_host: str = "",
    username: str = "",
    password: str = "",
) -> list[str]:
    return [
        wrap_dscli_command(
            cmd,
            dscli_path=dscli_path,
            hmc_host=hmc_host,
            username=username,
            password=password,
        )
        for cmd in commands
    ]


def wrap_dscli_labeled_commands(
    commands: list[tuple[str, str]],
    *,
    dscli_path: str = "",
    hmc_host: str = "",
    username: str = "",
    password: str = "",
) -> list[tuple[str, str]]:
    return [
        (
            label,
            wrap_dscli_command(
                cmd,
                dscli_path=dscli_path,
                hmc_host=hmc_host,
                username=username,
                password=password,
            ),
        )
        for label, cmd in commands
    ]
