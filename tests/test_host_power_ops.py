import pytest

from launchpad.host_power_ops import (
    HOST_POWER_MODE_SHUTDOWN_ONLY,
    HOST_POWER_MODE_STOP_THEN_SHUTDOWN,
    HOST_POWER_MUTATE_SSH_TIMEOUT,
    HOST_POWER_MODES,
    HOST_POWER_PRECHECK_SSH_TIMEOUT,
    PRECHECK_LETTERS,
    POWER_LABEL_PREFIX,
    build_host_power_preview,
    extract_power_steps,
    host_power_precheck_catalog,
    host_power_precheck_catalog_payload,
    normalize_host_power_mode,
    normalize_precheck_letter,
    precheck_command_is_mutating,
    require_host_power_confirm,
    resolve_precheck_command,
    run_host_power_for_card,
    run_host_power_precheck_for_card,
    select_shutdown_power_step,
    steps_for_host_power_mode,
)


def test_host_power_mode_and_timeout_constants():
    assert HOST_POWER_MODE_STOP_THEN_SHUTDOWN == "stop_then_shutdown"
    assert HOST_POWER_MODE_SHUTDOWN_ONLY == "shutdown_only"
    assert HOST_POWER_MODES == {
        HOST_POWER_MODE_STOP_THEN_SHUTDOWN,
        HOST_POWER_MODE_SHUTDOWN_ONLY,
    }
    assert HOST_POWER_PRECHECK_SSH_TIMEOUT == 45
    assert HOST_POWER_MUTATE_SSH_TIMEOUT == 120


def test_normalize_host_power_mode():
    assert normalize_host_power_mode("stop_then_shutdown") == "stop_then_shutdown"
    assert normalize_host_power_mode(" SHUTDOWN_ONLY ") == "shutdown_only"
    with pytest.raises(ValueError, match="mode"):
        normalize_host_power_mode("")
    with pytest.raises(ValueError, match="mode"):
        normalize_host_power_mode("run")


def test_select_shutdown_power_step_prefers_last_match():
    steps = [
        {"label": "Power - Stop YARN", "command": "sudo systemctl stop yarn"},
        {"label": "Power - Halt extra", "command": "sudo halt"},
        {"label": "Power - OS Shutdown", "command": "sudo shutdown -h now"},
    ]
    assert select_shutdown_power_step(steps) == steps[2]
    assert select_shutdown_power_step(steps[:2]) == steps[1]
    assert select_shutdown_power_step(steps[:1]) is None


def test_steps_for_host_power_mode_filters():
    steps = [
        {"label": "Power - Stop YARN", "command": "sudo systemctl stop yarn"},
        {"label": "Power - OS Shutdown", "command": "sudo shutdown -h now"},
    ]
    assert steps_for_host_power_mode(steps, "stop_then_shutdown") == steps
    assert steps_for_host_power_mode(steps, "shutdown_only") == [steps[1]]
    assert steps_for_host_power_mode(steps[:1], "shutdown_only") == []


def test_preview_includes_both_step_lists_and_shutdown_warning():
    preview = build_host_power_preview(
        [
            {
                "id": 1,
                "name": "hn1",
                "host": "10.0.0.1",
                "commands": [
                    ("Power - Stop YARN", "sudo systemctl stop yarn"),
                    ("Power - OS Shutdown", "sudo shutdown -h now"),
                ],
            },
            {
                "id": 2,
                "name": "hn2",
                "host": "10.0.0.2",
                "commands": [("Power - Stop YARN", "sudo systemctl stop yarn")],
            },
        ]
    )
    assert preview["ok"] is True
    h1, h2 = preview["hosts"]
    assert h1["stop_then_shutdown"] == h1["steps"]
    assert h1["shutdown_only"] == [
        {"label": "Power - OS Shutdown", "command": "sudo shutdown -h now"}
    ]
    assert h2["shutdown_only"] == []
    assert any("hn2" in w and "shutdown" in w.lower() for w in preview["warnings"])


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


def test_precheck_catalog_is_a_through_f():
    catalog = host_power_precheck_catalog()
    assert [item.letter for item in catalog] == list(PRECHECK_LETTERS)
    by_letter = {item.letter: item for item in catalog}
    assert by_letter["A"].hint == "Uptime / load"
    assert by_letter["A"].command == "uptime; cat /proc/loadavg"
    assert by_letter["B"].command == "systemctl --failed --no-pager 2>/dev/null || true"
    assert by_letter["C"].command == (
        "systemctl list-units 'hadoop*' 'hdfs*' 'yarn*' --no-pager 2>/dev/null || true"
    )
    assert by_letter["D"].command == "hdfs dfsadmin -report 2>/dev/null | head -n 40 || true"
    assert by_letter["E"].command == "yarn node -list 2>/dev/null || true"
    assert by_letter["F"].command == "yarn application -list 2>/dev/null || true"
    assert by_letter["A"].label.startswith("Precheck - A")
    payload = host_power_precheck_catalog_payload()
    assert payload[0] == {
        "letter": "A",
        "label": by_letter["A"].label,
        "hint": "Uptime / load",
    }
    assert "command" not in payload[0]


def test_normalize_precheck_letter_accepts_a_through_f():
    assert normalize_precheck_letter("e") == "E"
    assert normalize_precheck_letter("A") == "A"
    with pytest.raises(ValueError):
        normalize_precheck_letter("G")
    with pytest.raises(ValueError):
        normalize_precheck_letter("")


def test_resolve_precheck_command_prefers_card_override():
    cmds = [
        ("Health - Uptime", "uptime"),
        ("Precheck - E YARN node list", "yarn node -list -showDetails"),
    ]
    assert resolve_precheck_command(cmds, "E") == "yarn node -list -showDetails"
    assert resolve_precheck_command(cmds, "A") == "uptime; cat /proc/loadavg"


def test_resolve_precheck_command_does_not_match_aa_as_a():
    cmds = [("Precheck - AA custom", "echo aa")]
    assert resolve_precheck_command(cmds, "A") == "uptime; cat /proc/loadavg"


def test_precheck_command_is_mutating_word_match():
    assert precheck_command_is_mutating("sudo shutdown -h now") is True
    assert precheck_command_is_mutating("yarn node -list") is False
    assert precheck_command_is_mutating("echo noshutdownhere") is False


def test_run_precheck_rejects_mutating_without_calling_runner():
    calls: list[str] = []

    def run_command(cmd: str) -> str:
        calls.append(cmd)
        return "ok"

    result = run_host_power_precheck_for_card(
        letter="A",
        commands=[("Precheck - A Uptime / load", "sudo shutdown -h now")],
        run_command=run_command,
    )
    assert result["ok"] is False
    assert "shutdown" in result["error"].lower()
    assert calls == []


def test_run_precheck_records_output_and_error_prefix():
    result_ok = run_host_power_precheck_for_card(
        letter="E",
        commands=[],
        run_command=lambda cmd: "node1 RUNNING",
    )
    assert result_ok["ok"] is True
    assert result_ok["letter"] == "E"
    assert result_ok["output"] == "node1 RUNNING"

    result_err = run_host_power_precheck_for_card(
        letter="E",
        commands=[],
        run_command=lambda cmd: "ERROR: yarn not in PATH",
    )
    assert result_err["ok"] is False
    assert result_err["error"] == "ERROR: yarn not in PATH"
