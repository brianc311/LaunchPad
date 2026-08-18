import os
from typing import Any

from launchpad.call_home_cli_ops import mask_password_in_cmd
from launchpad.flashsystem_parse import format_command_output_html
from launchpad.flashsystem_health import format_command_detail_html
from launchpad.hadoop_sudo import prepare_hadoop_sudo_command
from launchpad.ssh_launcher import _log, _ssh_executable
from launchpad.ssh_paramiko import (
    run_ssh_auth_command,
    run_ssh_auth_hpe_commands,
    run_ssh_command,
    run_ssh_commands,
)
from launchpad.ssh_passphrase import askpass_env
from launchpad.storage_presets import uses_hpe_shell_cli
from launchpad.subprocess_utils import run_hidden

CONTROLLER_FALLBACK_COMMAND = "svcinfo lsnode -delim :"

_FC_EMPTY_FALLBACKS = (
    ("lsportfc", ("lsportfc -delim :", "svcinfo lsportfc -delim :")),
    ("lshostvdiskmap", ("lshostvdiskmap -delim :", "svcinfo lshostvdiskmap -delim :")),
    ("lsfabric", ("lsfabric -delim :", "svcinfo lsfabric -delim :")),
    ("lshost", ("lshost -delim :", "svcinfo lshost -delim :")),
)


def _needs_controller_fallback(label: str, command: str, output: str) -> bool:
    if (output or "").strip():
        return False
    label_lower = label.lower()
    command_lower = command.lower()
    return (
        "health - controllers" in label_lower
        or "lsnodecanister" in command_lower
        or "lscontroller" in command_lower
    )


def _fc_fallback_commands(label: str, command: str, output: str) -> tuple[str, ...]:
    """When an FC inventory command returns empty, try bare / svcinfo variants."""
    if (output or "").strip():
        return ()
    haystack = f"{label} {command}".lower()
    if "fc -" not in haystack and not any(
        token in haystack for token in ("lsportfc", "lshost", "lsfabric")
    ):
        return ()
    for needle, variants in _FC_EMPTY_FALLBACKS:
        if needle == "lshost" and "lshostvdiskmap" in haystack:
            continue
        if needle not in haystack:
            continue
        return tuple(variant for variant in variants if variant != command.strip())
    return ()


def run_remote_ssh_command(
    host: str,
    port: int | None,
    username: str,
    remote_command: str,
    key_path: str = "",
    key_passphrase: str = "",
    password: str = "",
    *,
    timeout: int = 45,
    device_profile: str = "",
    sudo_password: str = "",
) -> str:
    if not remote_command.strip():
        raise ValueError("SSH command is empty.")

    use_password_auth = bool(password)
    if use_password_auth:
        key_path = ""
    if not key_path and not password:
        raise ValueError("SSH password or key is required to run commands.")

    stdin_data = None
    if device_profile == "hadoop_linux":
        remote_command, stdin_data = prepare_hadoop_sudo_command(
            remote_command,
            sudo_password=sudo_password,
        )
    target = f"{username}@{host}" if username else host
    _log(f"SSH command on {target}: {mask_password_in_cmd(remote_command)}")

    if use_password_auth:
        return run_ssh_command(
            host,
            port,
            username,
            password,
            remote_command,
            timeout=timeout,
            stdin_data=stdin_data,
        )

    if stdin_data:
        return run_ssh_auth_command(
            host,
            port,
            username,
            remote_command,
            key_path=key_path,
            key_passphrase=key_passphrase,
            timeout=timeout,
            stdin_data=stdin_data,
        )

    ssh = _ssh_executable()
    args = [
        ssh,
        "-o",
        "StrictHostKeyChecking=accept-new",
        "-o",
        "ConnectTimeout=12",
    ]
    args.extend(
        [
            "-i",
            key_path,
            "-o",
            "IdentitiesOnly=yes",
            "-o",
            "BatchMode=yes" if not key_passphrase else "BatchMode=no",
        ]
    )
    env = {**os.environ, **askpass_env(key_passphrase)}
    if port:
        args.extend(["-p", str(port)])
    args.extend([target, remote_command])

    result = run_hidden(args, capture_output=True, text=True, timeout=timeout, check=False, env=env)
    output = (result.stdout or "").strip()
    error = (result.stderr or "").strip()
    if result.returncode != 0:
        detail = error or output or "Unknown SSH error"
        raise ValueError(detail)
    if error and not output:
        return error
    if error:
        return f"{output}\n\n{error}".strip() if output else error
    return output


def _apply_command_fallbacks(
    *,
    label: str,
    command: str,
    output: str,
    run_command,
) -> str:
    if _needs_controller_fallback(label, command, output):
        _log(
            f"Controller query returned no output for {label!r}; "
            f"retrying {CONTROLLER_FALLBACK_COMMAND}"
        )
        output = run_command(CONTROLLER_FALLBACK_COMMAND)
    for fallback in _fc_fallback_commands(label, command, output):
        _log(f"FC query returned no output for {label!r}; retrying {fallback}")
        output = run_command(fallback)
        if (output or "").strip():
            break
    return output


def run_remote_command_suite(
    host: str,
    port: int | None,
    username: str,
    commands: list[tuple[str, str]],
    key_path: str = "",
    key_passphrase: str = "",
    password: str = "",
    *,
    device_profile: str = "",
    sudo_password: str = "",
) -> list[dict[str, Any]]:
    if uses_hpe_shell_cli(device_profile, commands):
        return _run_hpe_command_suite(
            host,
            port,
            username,
            commands,
            key_path,
            key_passphrase,
            password,
        )

    results: list[dict[str, Any]] = []
    use_password_auth = bool(password)

    if (
        use_password_auth
        and commands
        and not (sudo_password or device_profile == "hadoop_linux")
    ):
        remote_commands = [command for _, command in commands]
        try:
            outputs = run_ssh_commands(host, port, username, password, remote_commands)

            def run_password_command(remote_command: str) -> str:
                return run_ssh_command(
                    host,
                    port,
                    username,
                    password,
                    remote_command,
                )

            for (label, command), output in zip(commands, outputs, strict=True):
                output = _apply_command_fallbacks(
                    label=label,
                    command=command,
                    output=output,
                    run_command=run_password_command,
                )
                results.append(
                    {
                        "label": label,
                        "command": command,
                        "output": output,
                        "output_html": format_command_output_html(label, command, output),
                        "output_html_detail": format_command_detail_html(label, command, output),
                        "error": None,
                    }
                )
            return results
        except Exception as exc:
            message = str(exc)
            for label, command in commands:
                results.append(
                    {
                        "label": label,
                        "command": command,
                        "output": "",
                        "output_html": "",
                        "error": message,
                    }
                )
            return results

    for label, command in commands:
        try:
            def run_key_command(remote_command: str) -> str:
                return run_remote_ssh_command(
                    host,
                    port,
                    username,
                    remote_command,
                    key_path,
                    key_passphrase,
                    password,
                    device_profile=device_profile,
                    sudo_password=sudo_password,
                )

            output = run_remote_ssh_command(
                host,
                port,
                username,
                command,
                key_path,
                key_passphrase,
                password,
                device_profile=device_profile,
                sudo_password=sudo_password,
            )
            output = _apply_command_fallbacks(
                label=label,
                command=command,
                output=output,
                run_command=run_key_command,
            )
            results.append(
                {
                    "label": label,
                    "command": command,
                    "output": output,
                    "output_html": format_command_output_html(label, command, output),
                    "output_html_detail": format_command_detail_html(label, command, output),
                    "error": None,
                }
            )
        except Exception as exc:
            results.append(
                {
                    "label": label,
                    "command": command,
                    "output": "",
                    "output_html": "",
                    "error": str(exc),
                }
            )
    return results


def _run_hpe_command_suite(
    host: str,
    port: int | None,
    username: str,
    commands: list[tuple[str, str]],
    key_path: str = "",
    key_passphrase: str = "",
    password: str = "",
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    remote_commands = [command for _, command in commands]
    try:
        outputs = run_ssh_auth_hpe_commands(
            host,
            port,
            username,
            remote_commands,
            password=password,
            key_path=key_path,
            key_passphrase=key_passphrase,
        )
        for (label, command), output in zip(commands, outputs, strict=True):
            results.append(
                {
                    "label": label,
                    "command": command,
                    "output": output,
                    "output_html": format_command_output_html(label, command, output),
                    "output_html_detail": format_command_detail_html(label, command, output),
                    "error": None,
                }
            )
    except Exception as exc:
        message = str(exc)
        for label, command in commands:
            results.append(
                {
                    "label": label,
                    "command": command,
                    "output": "",
                    "output_html": "",
                    "error": message,
                }
            )
    return results
