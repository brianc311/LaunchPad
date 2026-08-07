"""Host Power preview and run helpers.

Step failure is defined by ``run_command`` raising an exception or returning
a string that starts with ``ERROR:``. Successful steps record the returned
string as output.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

POWER_LABEL_PREFIX = "Power -"


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
