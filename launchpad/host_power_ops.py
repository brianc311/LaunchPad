"""Host Power preview and run helpers.

Step failure is defined by ``run_command`` raising an exception or returning
a string that starts with ``ERROR:``. Successful steps record the returned
string as output.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

POWER_LABEL_PREFIX = "Power -"
PRECHECK_LABEL_PREFIX = "Precheck -"
PRECHECK_LETTERS = ("A", "B", "C", "D", "E", "F")

_PRECHECK_MUTATE_RE = re.compile(r"\b(shutdown|reboot|halt|poweroff)\b", re.IGNORECASE)

HOST_POWER_MODE_STOP_THEN_SHUTDOWN = "stop_then_shutdown"
HOST_POWER_MODE_SHUTDOWN_ONLY = "shutdown_only"
HOST_POWER_MODES = frozenset(
    {HOST_POWER_MODE_STOP_THEN_SHUTDOWN, HOST_POWER_MODE_SHUTDOWN_ONLY}
)
HOST_POWER_PRECHECK_SSH_TIMEOUT = 45
HOST_POWER_MUTATE_SSH_TIMEOUT = 120
OS_SHUTDOWN_POWER_LABEL = "Power - OS Shutdown"


@dataclass(frozen=True)
class HostPowerPrecheck:
    letter: str
    hint: str
    label: str
    command: str


def host_power_precheck_catalog() -> list[HostPowerPrecheck]:
    rows = (
        ("A", "Uptime / load", "uptime; cat /proc/loadavg"),
        ("B", "Failed systemd units", "systemctl --failed --no-pager 2>/dev/null || true"),
        (
            "C",
            "Hadoop / HDFS / YARN units",
            "systemctl list-units 'hadoop*' 'hdfs*' 'yarn*' --no-pager 2>/dev/null || true",
        ),
        (
            "D",
            "HDFS dfsadmin report",
            "hdfs dfsadmin -report 2>/dev/null | head -n 40 || true",
        ),
        ("E", "YARN node list", "yarn node -list 2>/dev/null || true"),
        ("F", "YARN running apps", "yarn application -list 2>/dev/null || true"),
    )
    return [
        HostPowerPrecheck(
            letter=letter,
            hint=hint,
            label=f"Precheck - {letter} {hint}",
            command=command,
        )
        for letter, hint, command in rows
    ]


def host_power_precheck_catalog_payload() -> list[dict[str, str]]:
    return [
        {"letter": item.letter, "label": item.label, "hint": item.hint}
        for item in host_power_precheck_catalog()
    ]


def normalize_precheck_letter(letter: str) -> str:
    value = str(letter or "").strip().upper()
    if value not in PRECHECK_LETTERS:
        raise ValueError("Precheck letter must be A–F")
    return value


def _label_matches_precheck_letter(label: str, letter: str) -> bool:
    prefix = f"{PRECHECK_LABEL_PREFIX} {letter}"
    text = str(label or "")
    return text == prefix or text.startswith(prefix + " ")


def precheck_letter_from_label(label: str) -> str | None:
    text = str(label or "")
    for letter in PRECHECK_LETTERS:
        if _label_matches_precheck_letter(text, letter):
            return letter
    return None


def resolve_precheck_command(commands: list[tuple[str, str]], letter: str) -> str:
    letter_n = normalize_precheck_letter(letter)
    for label, command in commands:
        command_s = str(command or "").strip()
        if command_s and _label_matches_precheck_letter(label, letter_n):
            return command_s
    catalog = {item.letter: item for item in host_power_precheck_catalog()}
    return catalog[letter_n].command


def precheck_command_is_mutating(command: str) -> bool:
    return bool(_PRECHECK_MUTATE_RE.search(str(command or "")))


def run_host_power_precheck_for_card(
    *,
    letter: str,
    commands: list[tuple[str, str]],
    run_command: Callable[[str], str],
) -> dict[str, Any]:
    letter_n = normalize_precheck_letter(letter)
    catalog = {item.letter: item for item in host_power_precheck_catalog()}
    item = catalog[letter_n]
    command = resolve_precheck_command(commands, letter_n)
    label = next(
        (
            lbl
            for lbl, cmd in commands
            if str(cmd or "").strip() == command and _label_matches_precheck_letter(lbl, letter_n)
        ),
        item.label,
    )
    if precheck_command_is_mutating(command):
        return {
            "ok": False,
            "letter": letter_n,
            "label": label,
            "command": command,
            "error": "Precheck commands cannot include shutdown/reboot/halt/poweroff",
        }
    try:
        output = run_command(command)
    except Exception as exc:
        return {
            "ok": False,
            "letter": letter_n,
            "label": label,
            "command": command,
            "error": str(exc),
        }
    if str(output).startswith("ERROR:"):
        return {
            "ok": False,
            "letter": letter_n,
            "label": label,
            "command": command,
            "error": str(output),
        }
    return {
        "ok": True,
        "letter": letter_n,
        "label": label,
        "command": command,
        "output": output,
    }


def extract_power_steps(commands: list[tuple[str, str]]) -> list[dict[str, str]]:
    steps: list[dict[str, str]] = []
    for label, command in commands:
        label_s = str(label or "")
        command_s = str(command or "").strip()
        if label_s.startswith(POWER_LABEL_PREFIX) and command_s:
            steps.append({"label": label_s, "command": command_s})
    return steps


def normalize_host_power_mode(mode: str) -> str:
    value = str(mode or "").strip().lower()
    if value not in HOST_POWER_MODES:
        raise ValueError(
            "Host Power mode must be stop_then_shutdown or shutdown_only"
        )
    return value


def select_shutdown_power_step(steps: list[dict[str, str]]) -> dict[str, str] | None:
    matched: dict[str, str] | None = None
    for step in steps:
        label = str(step.get("label") or "")
        command = str(step.get("command") or "")
        if label == OS_SHUTDOWN_POWER_LABEL or _PRECHECK_MUTATE_RE.search(command):
            matched = step
    return matched


def steps_for_host_power_mode(
    steps: list[dict[str, str]],
    mode: str,
) -> list[dict[str, str]]:
    mode_n = normalize_host_power_mode(mode)
    if mode_n == HOST_POWER_MODE_STOP_THEN_SHUTDOWN:
        return list(steps)
    shutdown = select_shutdown_power_step(steps)
    return [shutdown] if shutdown else []


def coerce_card_ids(raw_ids: list[Any]) -> tuple[list[int], list[str]]:
    """Parse JSON card_ids entries to int, skipping invalid values."""
    parsed: list[int] = []
    warnings: list[str] = []
    for raw_id in raw_ids:
        try:
            parsed.append(int(raw_id))
        except (TypeError, ValueError):
            warnings.append(f"Ignored invalid card_id: {raw_id!r}")
    return parsed, warnings


def build_host_power_preview(cards: list[dict[str, Any]]) -> dict[str, Any]:
    if not cards:
        return {"ok": False, "warnings": ["No eligible hosts to preview"], "hosts": []}

    warnings: list[str] = []
    hosts: list[dict[str, Any]] = []
    ok = True

    for card in cards:
        card_id = card.get("id")
        name = str(card.get("name") or card_id or "unknown")
        host = str(card.get("host") or "").strip()
        commands = card.get("commands") or []
        host_warnings: list[str] = []

        steps = extract_power_steps(commands)

        if not host:
            msg = f"{name}: missing host"
            host_warnings.append(msg)
            warnings.append(msg)
            ok = False

        if not steps:
            msg = f"{name}: no Power - commands configured"
            host_warnings.append(msg)
            warnings.append(msg)
            ok = False

        shutdown_steps = steps_for_host_power_mode(
            steps, HOST_POWER_MODE_SHUTDOWN_ONLY
        )
        host_entry: dict[str, Any] = {
            "card_id": card_id,
            "name": name,
            "host": host,
            "steps": steps,
            "stop_then_shutdown": steps,
            "shutdown_only": shutdown_steps,
        }
        if steps and not shutdown_steps:
            msg = f"{name}: no OS shutdown Power - step"
            host_warnings.append(msg)
            warnings.append(msg)
        if host_warnings:
            host_entry["warnings"] = host_warnings
        hosts.append(host_entry)

    return {"ok": ok, "warnings": warnings, "hosts": hosts}


def require_host_power_confirm(confirm: bool) -> None:
    if not confirm:
        raise ValueError("Host Power requires explicit confirm=True")


def run_host_power_for_card(
    *,
    steps: list[dict[str, str]],
    run_command: Callable[[str], str],
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    aborted = False

    for step in steps:
        label = step["label"]
        command = step["command"]
        try:
            output = run_command(command)
        except Exception as exc:
            results.append(
                {
                    "label": label,
                    "command": command,
                    "ok": False,
                    "error": str(exc),
                }
            )
            aborted = True
            break

        if str(output).startswith("ERROR:"):
            results.append(
                {
                    "label": label,
                    "command": command,
                    "ok": False,
                    "error": str(output),
                }
            )
            aborted = True
            break

        results.append(
            {
                "label": label,
                "command": command,
                "ok": True,
                "output": output,
            }
        )

    all_ok = bool(results) and all(r["ok"] for r in results) and not aborted
    return {"ok": all_ok, "results": results, "aborted": aborted}
