import re

SUDO_PASSWORD_REQUIRED = "Sudo password required for this Hadoop command"

_SUDO_TOKEN = re.compile(r"\bsudo\b")


def command_needs_sudo(command: str) -> bool:
    return _SUDO_TOKEN.search(command) is not None


def _sudo_has_dash_s(command: str) -> bool:
    match = _SUDO_TOKEN.search(command)
    if match is None:
        return False
    rest = command[match.end() :].lstrip()
    while rest:
        if rest[0] != "-":
            break
        space_idx = rest.find(" ")
        if space_idx == -1:
            token = rest
            rest = ""
        else:
            token = rest[:space_idx]
            rest = rest[space_idx + 1 :].lstrip()
        if token == "-S" or (
            token.startswith("-") and len(token) > 1 and token[1] != "-" and "S" in token[1:]
        ):
            return True
    return False


def ensure_sudo_dash_s(command: str) -> str:
    if not command_needs_sudo(command):
        return command
    if _sudo_has_dash_s(command):
        return command
    return _SUDO_TOKEN.sub("sudo -S", command, count=1)


def prepare_hadoop_sudo_command(
    command: str, *, sudo_password: str
) -> tuple[str, str | None]:
    if not command_needs_sudo(command):
        return command, None
    if not sudo_password or not sudo_password.strip():
        raise ValueError(SUDO_PASSWORD_REQUIRED)
    return ensure_sudo_dash_s(command), sudo_password + "\n"
