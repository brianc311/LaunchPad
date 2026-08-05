"""Tests for analyze_health capacity layers (Task 2): system vs CPG, raw summary, HTML."""

from launchpad.flashsystem_health import analyze_health, format_capacity_report_html
from launchpad.flashsystem_parse import parse_raw_capacity_summary

HPE_SHOWSYS_WITH_RAW = """------------General-------------
System Name : ARRAY1
System Model : InServ E200
-----System Capacity (MB)-----
Total Capacity : 1000000
Allocated Capacity : 270000
Free Capacity : 730000
Failed Capacity : 0
Raw Capacity : 1200000
Raw Free Capacity : 930000
"""

SAMPLE_SHOWCPG_NEAR_FULL = """Id,Name,Warn%,VVs,TPVVs,TDVVs,Usr,Snp,Base,Free,Total
3,CPG_DATA01,-,7,7,0,7,7,13680640,162000,13842640
"""


def test_analyze_health_prefers_system_capacity_over_cpg_rollup():
    results = [
        {
            "label": "Capacity - System",
            "command": "showsys -d",
            "output": HPE_SHOWSYS_WITH_RAW,
            "error": None,
        },
        {
            "label": "Capacity - CPG %",
            "command": "showcpg",
            "output": SAMPLE_SHOWCPG_NEAR_FULL,
            "error": None,
        },
    ]
    analysis = analyze_health("HPE-WAG", results, None)
    summary = analysis["capacity_summary"]
    assert summary is not None
    assert summary["used_pct"] == 27.0
    assert summary["total_bytes"] == 1000000 * 1024**2
    pool_roll_pct = (13842640 - 162000) / 13842640 * 100
    assert pool_roll_pct > 95
    assert summary["used_pct"] != round(pool_roll_pct, 1)


def test_analyze_health_exposes_raw_capacity_summary():
    results = [
        {
            "label": "Capacity - System",
            "command": "showsys -d",
            "output": HPE_SHOWSYS_WITH_RAW,
            "error": None,
        },
        {
            "label": "Capacity - CPG %",
            "command": "showcpg",
            "output": SAMPLE_SHOWCPG_NEAR_FULL,
            "error": None,
        },
    ]
    analysis = analyze_health("HPE-WAG", results, None)
    raw = analysis["raw_capacity_summary"]
    assert raw is not None
    assert raw["total_bytes"] == 1200000 * 1024**2
    assert raw["used_pct"] == 22.5
    running_issues = [
        i
        for i in analysis["health_issues"]
        if i.get("category") == "capacity" and "Running at" in str(i.get("message"))
    ]
    assert not any("22.5" in i["message"] or "raw" in i["message"].lower() for i in running_issues)


def test_format_capacity_report_html_includes_raw_section():
    raw = parse_raw_capacity_summary(HPE_SHOWSYS_WITH_RAW)
    assert raw is not None
    html = format_capacity_report_html(None, "", raw_capacity=raw)
    assert "capacity-raw-wrap" in html
    assert "raw" in html.lower() or "physical" in html.lower()


def test_analyze_health_popup_html_includes_raw_wrap_when_physical_present():
    results = [
        {
            "label": "Capacity - System",
            "command": "showsys -d",
            "output": HPE_SHOWSYS_WITH_RAW,
            "error": None,
        },
    ]
    analysis = analyze_health("HPE-WAG", results, None)
    assert "capacity-raw-wrap" in analysis["capacity_popup_html"]


SHOWSYS_SPACE = """---------System Capacity---------
Total Capacity     :   57184000
Allocated Capacity :   41181000
Free Capacity      :   16003000
Failed Capacity    :          0
"""


def test_analyze_health_uses_showsys_space_for_raw_not_system():
    results = [
        {
            "label": "Capacity - System",
            "command": "showsys -d",
            "output": (
                "System Name : A\n"
                "Total Capacity : 1000000\n"
                "Allocated Capacity : 270000\n"
                "Free Capacity : 730000\n"
            ),
            "error": None,
        },
        {
            "label": "Capacity - Raw",
            "command": "showsys -space",
            "output": SHOWSYS_SPACE,
            "error": None,
        },
    ]
    analysis = analyze_health("HPE", results, None)
    assert analysis["capacity_summary"]["used_pct"] == 27.0
    assert analysis["raw_capacity_summary"]["total_bytes"] == 57184000 * 1024**2
    html = analysis["capacity_popup_html"] or ""
    assert "System utilization" in html
    assert "Raw utilization" in html


def test_analyze_health_no_all_cpgs_system_when_no_pools():
    results = [
        {
            "label": "Capacity - System",
            "command": "showsys -d",
            "output": "System Name : X\nTotal Capacity : --",
            "error": None,
        },
    ]
    analysis = analyze_health("HPE", results, None)
    html = analysis["capacity_popup_html"] or ""
    assert "All CPGs" not in html
    assert "System utilization" not in html


def test_analyze_health_system_bar_from_cpg_when_showsys_unparseable():
    """When showsys has no usable totals, still show System utilization from CPG rollup."""
    results = [
        {
            "label": "Capacity - System",
            "command": "showsys -d",
            "output": "System Name : HPEW101\nTotal Capacity : --",
            "error": None,
        },
        {
            "label": "Capacity - CPG %",
            "command": "showcpg",
            "output": SAMPLE_SHOWCPG_NEAR_FULL,
            "error": None,
        },
    ]
    analysis = analyze_health("HPE-WAG", results, None)
    html = analysis["capacity_popup_html"] or ""
    assert "System utilization" in html
    assert analysis["capacity_summary"] is not None
    assert analysis["capacity_summary"]["used_pct"] >= 80


def test_analyze_health_raw_from_total_raw_capacity_labels():
    showsys = """------------General-------------
System Name : HPEW101SSTOR01
-----System Capacity (MB)-----
Total Capacity : 25000000
Allocated Capacity : 24700000
Free Capacity : 300000
-----Raw Capacity (MB)-----
Total Raw Capacity : 34000000
Free Raw Capacity : 9000000
Allocated Raw Capacity : 25000000
"""
    results = [
        {
            "label": "Capacity - System",
            "command": "showsys -d",
            "output": showsys,
            "error": None,
        },
    ]
    analysis = analyze_health("HPE-WAG", results, None)
    html = analysis["capacity_popup_html"] or ""
    assert "System utilization" in html
    assert "Raw utilization" in html
    assert "capacity-raw-wrap" in html
    assert analysis["raw_capacity_summary"]["used_pct"] == 73.5
