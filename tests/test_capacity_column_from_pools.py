"""Excel Capacity column falls back to CPG/pool rollup when showsys is missing."""

from launchpad.capacity_export import format_capacity_text
from launchpad.flashsystem_health import analyze_health, capacity_summary_from_pools


SAMPLE_SHOWCPG = """Id,Name,Warn%,VVs,TPVVs,TDVVs,Usr,Snp,Base,Free,Total
0,CPG_DATA01,-,10,10,0,10,0,10,981632,14000000
1,CPG_MGT,-,2,2,0,2,0,2,50000,1900000
"""


def test_capacity_summary_from_pools_rolls_up_totals():
    pools = [
        {
            "name": "CPG_DATA01",
            "used_bytes": 100,
            "total_bytes": 200,
            "free_bytes": 100,
            "used_pct": 50.0,
        },
        {
            "name": "CPG_MGT",
            "used_bytes": 25,
            "total_bytes": 50,
            "free_bytes": 25,
            "used_pct": 50.0,
        },
        {
            "name": "total",
            "used_bytes": 999,
            "total_bytes": 999,
            "free_bytes": 0,
            "used_pct": 100.0,
        },
    ]
    summary = capacity_summary_from_pools(pools)
    assert summary is not None
    assert summary["total_bytes"] == 250
    assert summary["used_bytes"] == 125
    assert summary["used_pct"] == 50.0


def test_format_capacity_text_uses_pool_rollup_when_summary_missing():
    pools = [
        {
            "name": "CPG_DATA01",
            "used_bytes": 13_300_000_000_000,
            "total_bytes": 26_700_000_000_000,
            "free_bytes": 13_400_000_000_000,
            "used_pct": 49.8,
        }
    ]
    text = format_capacity_text(None, pools=pools)
    assert text
    assert "All CPGs" in text or "%" in text
    assert "TB" in text or "GB" in text


def test_analyze_health_fills_capacity_summary_from_showcpg_pools():
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
    assert analysis["capacity_summary"]
    assert analysis["capacity_summary"]["total_bytes"] > 0
    text = format_capacity_text(
        analysis["capacity_summary"],
        pools=analysis["pools"],
    )
    assert text
