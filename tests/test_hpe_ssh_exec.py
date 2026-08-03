"""HPE interactive CLI prompt detection and shell helpers."""

from launchpad.ssh_paramiko import _extract_hpe_command_output, _looks_like_hpe_prompt


def test_hpe_prompt_accepts_cli_style_not_percent_values():
    assert _looks_like_hpe_prompt("cli%")
    assert _looks_like_hpe_prompt("3paradm%")
    assert _looks_like_hpe_prompt("user@array%")
    assert not _looks_like_hpe_prompt("98.5%")
    assert not _looks_like_hpe_prompt("50%")
    assert not _looks_like_hpe_prompt("Warn%")
    assert not _looks_like_hpe_prompt("Used 12.0%")
    assert not _looks_like_hpe_prompt("CPG_DATA01: 98.9% used")


def test_extract_hpe_stops_at_cli_prompt_not_percent_row():
    raw = """cli% showcpg
Id,Name,Warn%,Usr_Used_Perc
0,SSD_r5,0,50.0
cli%
"""
    body = _extract_hpe_command_output(raw, "showcpg")
    assert "SSD_r5" in body
    assert "cli%" not in body
    assert body.strip().endswith("50.0")
