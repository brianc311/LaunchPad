"""Tests for HPE 3PAR/Primera capacity CLI parsing (CSV + Usr_*_MB columns)."""

from launchpad.flashsystem_health import analyze_health, format_capacity_report_html
from launchpad.flashsystem_parse import (
    parse_pool_capacity_rows,
    summarize_command_output,
)


SAMPLE_SHOWCPG_CSV = """Id,Name,Warn%,VVs,TPVVs,TDVVs,Usr_RawRsvd_MB,Usr_Rsvd_MB,Usr_Used_MB,Usr_Total_MB,Usr_Used_Perc
0,SSD_r5,0,12,12,0,0,204800,102400,204800,50.0
1,NL_r6,0,4,4,0,0,512000,128000,512000,25.0
"""

SAMPLE_SHOWCPG_SPACE = """
Id Name   Warn% VVs Usr_Used_MB Usr_Total_MB
0  SSD_r5 0     12  102400      204800
"""


def test_parse_pool_capacity_rows_hpe_showcpg_csv():
    pools = parse_pool_capacity_rows(SAMPLE_SHOWCPG_CSV)
    assert len(pools) == 2
    by_name = {p["name"]: p for p in pools}
    ssd = by_name["SSD_r5"]
    assert ssd["total_bytes"] == 204800 * 1024**2
    assert ssd["used_bytes"] == 102400 * 1024**2
    assert ssd["used_pct"] == 50.0
    assert by_name["NL_r6"]["used_pct"] == 25.0


def test_parse_pool_capacity_rows_hpe_showcpg_space_table():
    pools = parse_pool_capacity_rows(SAMPLE_SHOWCPG_SPACE)
    assert len(pools) >= 1
    assert pools[0]["name"] == "SSD_r5"
    assert pools[0]["total_bytes"] == 204800 * 1024**2


def test_summarize_showcpg_csv_not_empty_cpg_rows():
    summary = summarize_command_output(
        "Capacity - CPG %", "showcpg", SAMPLE_SHOWCPG_CSV
    )
    assert "no CPG" not in summary.lower()
    assert "SSD_r5" in summary or "%" in summary


def test_analyze_health_builds_capacity_popup_from_showcpg():
    results = [
        {
            "label": "Capacity - System",
            "command": "showsys -d",
            "output": "System Name : ARRAY1\nTotal Capacity : --",
            "error": None,
        },
        {
            "label": "Capacity - CPG %",
            "command": "showcpg",
            "output": SAMPLE_SHOWCPG_CSV,
            "error": None,
        },
    ]
    analysis = analyze_health("HPE-WAG", results, None)
    assert analysis["capacity_popup_html"]
    assert "SSD_r5" in analysis["capacity_popup_html"] or "capacity" in analysis[
        "capacity_popup_html"
    ].lower()
    assert analysis["pools"]
    assert any(p["name"] == "SSD_r5" for p in analysis["pools"])


def test_format_capacity_report_html_from_pools_output():
    html = format_capacity_report_html(None, SAMPLE_SHOWCPG_CSV)
    assert html
    assert "SSD_r5" in html or "capacity-pool" in html


SAMPLE_SHOWCPG_NEAR_FULL = """Id,Name,Warn%,VVs,TPVVs,TDVVs,Usr,Snp,Base,Free,Total
3,CPG_DATA01,-,7,7,0,7,7,13680640,162000,13842640
"""

SAMPLE_SHOWCPG_WARN_BAND = """Id,Name,Warn%,VVs,TPVVs,TDVVs,Usr_RawRsvd_MB,Usr_Rsvd_MB,Usr_Used_MB,Usr_Total_MB,Usr_Used_Perc
0,CPG_DATA01,-,4,4,0,0,1000000,820000,1000000,82.0
"""


def test_analyze_health_raises_critical_for_near_full_hpe_pool():
    results = [
        {
            "label": "Capacity - CPG %",
            "command": "showcpg",
            "output": SAMPLE_SHOWCPG_NEAR_FULL,
            "error": None,
        },
    ]
    analysis = analyze_health("HPE-WAG", results, None)
    issues = analysis["health_issues"]
    capacity_issues = [i for i in issues if i.get("category") == "capacity"]
    assert capacity_issues
    assert any(i["severity"] == "critical" for i in capacity_issues)
    assert any("CPG_DATA01" in i["message"] or "Running at" in i["message"] for i in capacity_issues)


def test_analyze_health_raises_warn_between_80_and_90():
    results = [
        {
            "label": "Capacity - CPG %",
            "command": "showcpg",
            "output": SAMPLE_SHOWCPG_WARN_BAND,
            "error": None,
        },
    ]
    analysis = analyze_health("HPE-WAG", results, None)
    capacity_issues = [
        i for i in analysis["health_issues"] if i.get("category") == "capacity"
    ]
    assert capacity_issues
    assert any(i["severity"] == "warn" for i in capacity_issues)
    assert not any(
        i["severity"] == "critical" and "Pool" in i["message"] for i in capacity_issues
    )


def test_capacity_detail_hides_empty_warn_percent():
    html = format_capacity_report_html(None, SAMPLE_SHOWCPG_NEAR_FULL)
    assert html
    assert "Warn%" not in html or "Warn%</th><td>-</td>" not in html
