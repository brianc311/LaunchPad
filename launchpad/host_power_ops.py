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

        host_entry: dict[str, Any] = {
            "card_id": card_id,
            "name": name,
            "host": host,
            "steps": steps,
        }
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
