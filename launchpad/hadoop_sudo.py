import re

SUDO_PASSWORD_REQUIRED = "Sudo password required for this Hadoop command"

_SUDO_TOKEN = re.compile(r"\bsudo\b")
_SUDO_SHORT_OPTS_WITH_ARG = frozenset("CDghprRtTUu")
_SUDO_LONG_OPTS_WITH_ARG = frozenset(
    {
        "chdir",
        "close-from",
        "command-timeout",
        "group",
        "host",
        "other-user",
        "prompt",
        "role",
        "type",
        "user",
    }
)


def command_needs_sudo(command: str) -> bool:
    return _SUDO_TOKEN.search(command) is not None


def _parse_sudo_short_option_token(token: str) -> tuple[bool, bool]:
    """Return (has_dash_s, consumes_next_token) for a combined short-option token."""
    has_dash_s = False
    index = 1
    while index < len(token):
        option = token[index]
        if option in _SUDO_SHORT_OPTS_WITH_ARG:
            if index + 1 < len(token):
                return has_dash_s, False
            return has_dash_s, True
        if option == "S":
            has_dash_s = True
        index += 1
    return has_dash_s, False


def _token_has_dash_s(token: str) -> bool:
    if token == "-S":
        return True
    if token.startswith("-") and len(token) > 1 and token[1] != "-":
        has_dash_s, _ = _parse_sudo_short_option_token(token)
        return has_dash_s
    return False


def _sudo_option_consumes_next_token(token: str) -> bool:
    if token.startswith("--"):
        name = token[2:]
        if "=" in name:
            return False
        return name in _SUDO_LONG_OPTS_WITH_ARG
    if token.startswith("-") and len(token) > 1 and token[1] != "-":
        _, consumes_next_token = _parse_sudo_short_option_token(token)
        return consumes_next_token
    return False


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
        if token == "--":
            break
        if _token_has_dash_s(token):
            return True
        if _sudo_option_consumes_next_token(token) and rest:
            space_idx = rest.find(" ")
            if space_idx == -1:
                rest = ""
            else:
                rest = rest[space_idx + 1 :].lstrip()
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
