import pytest

from launchpad.host_power_ops import (
    POWER_LABEL_PREFIX,
    build_host_power_preview,
    extract_power_steps,
    require_host_power_confirm,
    run_host_power_for_card,
)


def test_extract_power_steps_filters_and_orders():
    cmds = [
        ("Health - Uptime", "uptime"),
        ("Power - Stop YARN", "sudo systemctl stop yarn"),
        ("Capacity - Root", "df -h /"),
        ("Power - OS Shutdown", "sudo shutdown -h now"),
    ]
    steps = extract_power_steps(cmds)
    assert [s["label"] for s in steps] == [
        "Power - Stop YARN",
        "Power - OS Shutdown",
    ]
    assert all(s["label"].startswith(POWER_LABEL_PREFIX) for s in steps)


def test_preview_blocks_when_no_power_steps():
    preview = build_host_power_preview(
        [
            {
                "id": 1,
                "name": "hn1",
                "host": "10.0.0.1",
                "commands": [("Health - Uptime", "uptime")],
            }
        ]
    )
    assert preview["ok"] is False
    assert preview["warnings"]


def test_require_confirm():
    with pytest.raises(ValueError, match="confirm"):
        require_host_power_confirm(False)
    require_host_power_confirm(True)


def test_run_aborts_remaining_after_stop_failure():
    calls: list[str] = []

    def run_command(cmd: str) -> str:
        calls.append(cmd)
        if "stop" in cmd:
            raise RuntimeError("unit not found")
        return "ok"

    result = run_host_power_for_card(
        steps=[
            {"label": "Power - Stop YARN", "command": "sudo systemctl stop yarn"},
            {"label": "Power - OS Shutdown", "command": "sudo shutdown -h now"},
        ],
        run_command=run_command,
    )
    assert result["ok"] is False
    assert result["aborted"] is True
    assert calls == ["sudo systemctl stop yarn"]
    assert "shutdown" not in "".join(calls)


def test_run_aborts_remaining_after_error_string():
    calls: list[str] = []

    def run_command(cmd: str) -> str:
        calls.append(cmd)
        if "stop" in cmd:
            return "ERROR: unit not found"
        return "ok"

    result = run_host_power_for_card(
        steps=[
            {"label": "Power - Stop YARN", "command": "sudo systemctl stop yarn"},
            {"label": "Power - OS Shutdown", "command": "sudo shutdown -h now"},
        ],
        run_command=run_command,
    )
    assert result["ok"] is False
    assert result["aborted"] is True
    assert result["results"][0]["ok"] is False
    assert result["results"][0]["error"] == "ERROR: unit not found"
    assert calls == ["sudo systemctl stop yarn"]
    assert "shutdown" not in "".join(calls)
