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


def _token_has_dash_s(token: str) -> bool:
    return token == "-S" or (
        token.startswith("-")
        and len(token) > 1
        and token[1] != "-"
        and "S" in token[1:]
    )


def _sudo_option_consumes_next_token(token: str) -> bool:
    if token.startswith("--"):
        name = token[2:]
        if "=" in name:
            return False
        return name in _SUDO_LONG_OPTS_WITH_ARG
    if token.startswith("-") and len(token) > 1:
        if len(token) == 2:
            return token[1] in _SUDO_SHORT_OPTS_WITH_ARG
        return token[-1] in _SUDO_SHORT_OPTS_WITH_ARG
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
