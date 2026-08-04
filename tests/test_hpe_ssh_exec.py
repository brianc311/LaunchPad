"""HPE interactive CLI prompt detection and shell helpers."""

from launchpad.command_format import filter_capacity_focus_commands
from launchpad.flashsystem_parse import summarize_command_output
from launchpad.ssh_paramiko import (
    _extract_hpe_command_output,
    _hpe_allows_idle_exit_without_prompt,
    _looks_like_hpe_prompt,
)


def test_checkhealth_does_not_idle_exit_without_prompt():
    assert not _hpe_allows_idle_exit_without_prompt("checkhealth")
    assert not _hpe_allows_idle_exit_without_prompt("CHECKHEALTH")
    assert _hpe_allows_idle_exit_without_prompt("showcpg")
    assert _hpe_allows_idle_exit_without_prompt("showsys -d")


def test_summarize_checkhealth_incomplete_when_only_checking_lines():
    text = "\n".join(
        [
            "Checking alert",
            "Checking ao",
            "Checking cabling",
            "Checking cage",
            "Checking cert",
            "Checking dar",
            "Checking date",
        ]
    )
    summary = summarize_command_output("Health - Overall", "checkhealth", text)
    assert "incomplete" in summary.lower()
    assert "Checking alert" not in summary


def test_hpe_prompt_accepts_host_cli_style_not_percent_values():
    assert _looks_like_hpe_prompt("cli%")
    assert _looks_like_hpe_prompt("3paradm%")
    assert _looks_like_hpe_prompt("user@array%")
    assert _looks_like_hpe_prompt("BSA-3PAR01 cli%")
    assert _looks_like_hpe_prompt("HPEW101SSTOR01 cli%")
    assert not _looks_like_hpe_prompt("98.5%")
    assert not _looks_like_hpe_prompt("50%")
    assert not _looks_like_hpe_prompt("Warn%")
    assert not _looks_like_hpe_prompt("Used 12.0%")
    assert not _looks_like_hpe_prompt("CPG_DATA01: 98.9% used")


def test_extract_hpe_stops_at_host_cli_prompt_not_percent_row():
    raw = """HPEW101SSTOR01 cli% showcpg
Id,Name,Warn%,Usr_Used_Perc
0,SSD_r5,0,50.0
HPEW101SSTOR01 cli%
"""
    body = _extract_hpe_command_output(raw, "showcpg")
    assert "SSD_r5" in body
    assert "cli%" not in body
    assert body.strip().endswith("50.0")


def test_filter_capacity_focus_keeps_showsys_showcpg():
    commands = [
        ("Capacity - System", "showsys -d"),
        ("Capacity - CPG %", "showcpg"),
        ("Health - Overall", "checkhealth"),
        ("Hosts - host list", "showhost"),
    ]
    focused = filter_capacity_focus_commands(commands)
    assert focused == [
        ("Capacity - System", "showsys -d"),
        ("Capacity - CPG %", "showcpg"),
    ]
