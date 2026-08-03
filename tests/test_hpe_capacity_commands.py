"""HPE capacity CLI commands, MB parsing, and shell output extraction."""

from launchpad.flashsystem_health import (
    analyze_health,
    format_capacity_report_html,
    pool_capacity_from_commands,
)
from launchpad.flashsystem_parse import parse_capacity_summary, parse_pool_capacity_rows
from launchpad.ssh_paramiko import _extract_hpe_command_output
from launchpad.storage_presets import HP_3PAR_COMMANDS, HPE_PRIMERA_COMMANDS


SAMPLE_SHOWYS_D = """------------General-------------
System Name : S424
System Model : InServ E200
-----System Capacity (MB)-----
Total Capacity : 6277120
Allocated Capacity : 687872
Free Capacity : 5589248
Failed Capacity : 0
"""

SAMPLE_SHOWCPG = """Id,Name,Warn%,VVs,TPVVs,Usr,Snp,Usr_Total_MB,Usr_Used_MB,Snp_Total_MB,Snp_Used_MB
0,SSD_r5,0,12,12,12,0,204800,102400,0,0
1,NL_r6,0,4,4,4,0,512000,128000,0,0
"""


def test_hpe_presets_use_showcpg_not_sdg_or_bare_showspace_cpg():
    assert ("Capacity - CPG %", "showcpg") in HP_3PAR_COMMANDS
    assert ("Capacity - CPG %", "showcpg -sdg") not in HP_3PAR_COMMANDS
    assert ("Capacity - CPG %", "showcpg") in HPE_PRIMERA_COMMANDS
    assert ("Capacity - CPG %", "showspace -cpg") not in HPE_PRIMERA_COMMANDS
    assert ("Capacity - System", "showsys -d") in HP_3PAR_COMMANDS
    assert ("Capacity - System", "showsys -d") in HPE_PRIMERA_COMMANDS
    assert HP_3PAR_COMMANDS[0][1] == "showsys -d"
    assert HP_3PAR_COMMANDS[1][1] == "showcpg"


def test_ensure_hpe_capacity_rewrites_legacy_custom_commands():
    from launchpad.command_format import resolve_card_commands

    custom = "\n".join(
        [
            "Health - Overall|checkhealth",
            "Capacity - System|showspace",
            "Capacity - CPG %|showcpg -sdg",
            "Capacity - Free|showspace -cpg",
        ]
    )
    commands = resolve_card_commands("hpe_3par_8450", custom)
    assert commands[0][1] == "showsys -d"
    assert ("Capacity - CPG %", "showcpg") in commands
    assert ("Capacity - Free", "showcpg") in commands
    assert not any(cmd == "showcpg -sdg" for _, cmd in commands)
    assert not any(cmd == "showspace -cpg" for _, cmd in commands)
    assert not any(cmd == "showspace" for _, cmd in commands)


def test_parse_showsys_d_treats_bare_numbers_as_mb():
    capacity = parse_capacity_summary(SAMPLE_SHOWYS_D)
    assert capacity is not None
    assert capacity["total_bytes"] == 6277120 * 1024**2
    assert capacity["free_bytes"] == 5589248 * 1024**2
    assert capacity["used_bytes"] == 687872 * 1024**2


def test_pool_capacity_prefers_showcpg_over_system_showspace():
    results = [
        {
            "label": "Capacity - System %",
            "command": "showspace",
            "output": "--Estimated(MiB)--,RawFree,UsableFree\n0,0",
            "error": None,
        },
        {
            "label": "Capacity - CPG %",
            "command": "showcpg",
            "output": SAMPLE_SHOWCPG,
            "error": None,
        },
    ]
    pools = pool_capacity_from_commands(results)
    assert len(pools) == 2
    assert pools[0]["name"] == "SSD_r5"


def test_analyze_health_showsys_and_showcpg_build_popup():
    results = [
        {
            "label": "Capacity - System",
            "command": "showsys -d",
            "output": SAMPLE_SHOWYS_D,
            "error": None,
        },
        {
            "label": "Capacity - CPG %",
            "command": "showcpg",
            "output": SAMPLE_SHOWCPG,
            "error": None,
        },
    ]
    analysis = analyze_health("HPE-WAG", results, None)
    assert analysis["capacity_summary"]
    assert analysis["capacity_summary"]["total_bytes"] == 6277120 * 1024**2
    assert analysis["capacity_popup_html"]
    assert "SSD_r5" in analysis["capacity_popup_html"]
    assert analysis["pools"]


def test_extract_hpe_ignores_checkhealth_leftover_before_showsys():
    raw = """Checking date
OK
cli% showsys -d
------------General-------------
System Name : S424
Total Capacity : 6277120
Free Capacity : 5589248
cli%
"""
    body = _extract_hpe_command_output(raw, "showsys -d")
    assert "Checking date" not in body
    assert "Total Capacity" in body
    assert parse_capacity_summary(body) is not None


def test_parse_showcpg_default_csv_has_usr_mb_columns():
    pools = parse_pool_capacity_rows(SAMPLE_SHOWCPG)
    assert len(pools) == 2
    assert pools[0]["total_bytes"] == 204800 * 1024**2


def test_parse_showcpg_mib_preamble_free_total_columns():
    cpg = """---------------(MiB)---------------
Id,Name,Warn%,VVs,TPVVs,TDVVs,Usr,Snp,Base,Free,Total
0,SSD_r6,-,237,237,0,237,0,237,981632,30387200
1,NL_r5,-,10,10,0,10,0,10,5000,100000
2,total,-,247,247,0,247,0,247,986632,30487200
"""
    pools = parse_pool_capacity_rows(cpg)
    assert len(pools) == 2
    by_name = {p["name"]: p for p in pools}
    assert "total" not in by_name
    ssd = by_name["SSD_r6"]
    assert ssd["total_bytes"] == 30387200 * 1024**2
    assert ssd["free_bytes"] == 981632 * 1024**2
    assert ssd["used_pct"] == round((30387200 - 981632) / 30387200 * 100, 1)
    html = format_capacity_report_html(None, cpg)
    assert html
    assert "SSD_r6" in html


def test_analyze_health_ignores_checkhealth_bleed_for_capacity():
    results = [
        {
            "label": "Capacity - System",
            "command": "showsys -d",
            "output": "Checking date\nOK",
            "error": None,
        },
        {
            "label": "Capacity - CPG %",
            "command": "showcpg",
            "output": SAMPLE_SHOWCPG,
            "error": None,
        },
    ]
    analysis = analyze_health("HPE-WAG", results, None)
    assert analysis["pools"]
    assert analysis["capacity_popup_html"]
    assert "Checking" not in analysis["capacity_popup_html"]
