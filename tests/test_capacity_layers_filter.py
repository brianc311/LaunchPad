"""Task 3: include_pools filter for capacity-focus refresh."""

import json

from launchpad.command_format import filter_capacity_focus_commands
from launchpad.health_server import HealthCard, HealthServer, _HealthHandler


def test_filter_capacity_focus_keeps_showsys_space_when_pools_off():
    commands = [
        ("Capacity - System", "showsys -d"),
        ("Capacity - Raw", "showsys -space"),
        ("Capacity - CPG %", "showcpg"),
    ]
    focused = filter_capacity_focus_commands(commands, include_pools=False)
    assert focused == [
        ("Capacity - System", "showsys -d"),
        ("Capacity - Raw", "showsys -space"),
    ]


def test_filter_capacity_focus_keeps_pools_by_default():
    commands = [
        ("Capacity - System", "showsys -d"),
        ("Capacity - CPG %", "showcpg"),
        ("Capacity - Pools %", "lssystem"),
    ]
    focused = filter_capacity_focus_commands(commands)
    assert ("Capacity - CPG %", "showcpg") in focused
    assert ("Capacity - System", "showsys -d") in focused


def test_filter_capacity_focus_pool_only_returns_empty_when_include_pools_false():
    commands = [("Capacity - CPG", "showcpg")]
    focused = filter_capacity_focus_commands(commands, include_pools=False)
    assert focused == []


def test_filter_capacity_focus_keeps_lssystem_when_pools_off():
    commands = [
        ("Capacity - System", "lssystem"),
        ("Capacity - Pools %", "svcinfo lsmdiskgrp -delim :"),
    ]
    focused = filter_capacity_focus_commands(commands, include_pools=False)
    assert focused == [("Capacity - System", "lssystem")]


def _call_refresh_api(monkeypatch, server: HealthServer, card_id: int, query: str = ""):
    handler = object.__new__(_HealthHandler)
    handler.path = f"/api/refresh/{card_id}{query}"
    sent: dict = {}

    def _send_json(data, status=200):
        sent["json"] = data
        sent["status"] = status

    handler._send_json = _send_json
    monkeypatch.setattr("launchpad.health_server.get_health_server", lambda: server)
    handler.do_POST()
    return sent


def test_refresh_api_passes_include_pools_to_refresh_card(monkeypatch):
    server = HealthServer()
    server.register_card(1, "Site", "10.0.0.1", 22, "user", "")
    calls: list[dict] = []

    def _spy(card_id: int, *, focus: str = "", include_pools: bool = True) -> HealthCard:
        calls.append({"card_id": card_id, "focus": focus, "include_pools": include_pools})
        return server._cards[card_id]

    monkeypatch.setattr(server, "refresh_card", _spy)

    sent = _call_refresh_api(
        monkeypatch, server, 1, "?focus=capacity&include_pools=0"
    )
    assert sent["status"] == 200
    assert calls == [{"card_id": 1, "focus": "capacity", "include_pools": False}]


def test_refresh_card_applies_include_pools_filter(monkeypatch):
    server = HealthServer()
    server.register_card(1, "HPE", "10.0.0.1", 22, "user", "", device_profile="HPE-WAG")
    filtered: list[bool] = []

    def _track_filter(commands, *, include_pools=True):
        filtered.append(include_pools)
        return filter_capacity_focus_commands(commands, include_pools=include_pools)

    monkeypatch.setattr(
        "launchpad.command_format.filter_capacity_focus_commands",
        _track_filter,
    )
    monkeypatch.setattr(
        "launchpad.health_server.resolve_card_commands",
        lambda *a, **k: [
            ("Capacity - System", "showsys -d"),
            ("Capacity - CPG %", "showcpg"),
        ],
    )
    monkeypatch.setattr(
        "launchpad.health_server.run_remote_command_suite",
        lambda *a, **k: [{"label": "Capacity - System", "command": "showsys -d", "output": ""}],
    )

    server.refresh_card(1, focus="capacity", include_pools=False)
    assert filtered == [False]


def test_refresh_card_drops_stale_showcpg_when_include_pools_false(monkeypatch):
    server = HealthServer()
    server.register_card(1, "HPE", "10.0.0.1", 22, "user", "", device_profile="hpe_3par_8400")
    showcpg = """Id,Name,Warn%,VVs,Usr_Used_MB,Usr_Total_MB
0,CPG_DATA01,0,7,13600000,13842640
"""
    server._cards[1].command_results = [
        {
            "label": "Capacity - System",
            "command": "showsys -d",
            "output": "System Name : A\nTotal Capacity : --",
            "error": None,
        },
        {
            "label": "Capacity - CPG %",
            "command": "showcpg",
            "output": showcpg,
            "error": None,
        },
        {
            "label": "Health - Alerts",
            "command": "showalert",
            "output": "No alerts",
            "error": None,
        },
    ]
    monkeypatch.setattr(
        "launchpad.health_server.resolve_card_commands",
        lambda *a, **k: [
            ("Capacity - System", "showsys -d"),
            ("Capacity - Raw", "showsys -space"),
            ("Capacity - CPG %", "showcpg"),
        ],
    )
    monkeypatch.setattr(
        "launchpad.health_server.run_remote_command_suite",
        lambda *a, **k: [
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
                "output": (
                    "Total Capacity : 57184000\n"
                    "Allocated Capacity : 41181000\n"
                    "Free Capacity : 16003000\n"
                ),
                "error": None,
            },
        ],
    )

    card = server.refresh_card(1, focus="capacity", include_pools=False)
    cmds = [f"{i.get('label')}|{i.get('command')}" for i in (card.command_results or [])]
    assert not any("showcpg" in c for c in cmds)
    assert any("showalert" in c for c in cmds)
    html = card.to_api().get("capacity_popup_html") or ""
    assert "All CPGs" not in html
    assert "System utilization" in html
    assert "Raw utilization" in html
    pool_issues = [
        i
        for i in (card.to_api().get("health_issues") or [])
        if "Pool " in str(i.get("message") or "")
    ]
    assert not pool_issues


def test_to_api_includes_raw_capacity_summary():
    card = HealthCard(
        card_id=1,
        name="HPE",
        host="10.0.0.1",
        port=22,
        username="user",
        key_path="",
        device_profile="HPE-WAG",
        command_results=[
            {
                "label": "Capacity - System",
                "command": "showsys -d",
                "output": """-----System Capacity (MB)-----
Total Capacity : 1000000
Allocated Capacity : 270000
Free Capacity : 730000
Raw Capacity : 1200000
Raw Free Capacity : 930000
""",
            },
        ],
    )
    api = card.to_api()
    raw = api.get("raw_capacity_summary")
    assert raw is not None
    assert raw["total_bytes"] == 1200000 * 1024**2
