import json

from launchpad.contingency_groups_data import CONTINGENCY_GROUPS_SETTING
from launchpad.health_server import HealthServer
from launchpad.snapshot_schedule_overrides import SNAPSHOT_OVERRIDES_SETTING

CG_SAMPLE = """id:name:status:FC_mapping_count
0:AWD1_AS400_CG:idle_or_copied:6
1:empty_cg:empty:0
"""

MAP_SAMPLE = """id:name:source_vdisk_name:target_vdisk_name:status:progress:group_name
0:fcmap0:AWD1_AS400_1:AWD1_AS400_1_Snap1:copied:100:AWD1_AS400_CG
1:fcmap1:AWD1_AS400_2:AWD1_AS400_2_Snap2:copied:100:AWD1_AS400_CG
2:standalone1:VOL_A:VOL_A_snap:idle_or_copied:0:
"""

_INVENTORY_GROUPS = [
    {
        "id": "0",
        "name": "AWD1_AS400_CG",
        "status": "idle_or_copied",
        "map_count": 2,
        "policy": "",
    },
    {"id": "1", "name": "empty_cg", "status": "empty", "map_count": 0, "policy": ""},
]

_INVENTORY_MAPS = [
    {
        "id": "0",
        "name": "fcmap0",
        "source": "AWD1_AS400_1",
        "target": "AWD1_AS400_1_Snap1",
        "status": "copied",
        "progress": "100",
        "consistgrp": "AWD1_AS400_CG",
    },
    {
        "id": "2",
        "name": "standalone1",
        "source": "VOL_A",
        "target": "VOL_A_snap",
        "status": "idle_or_copied",
        "progress": "0",
        "consistgrp": "",
    },
]


def _settings_backend(initial: dict[str, str] | None = None):
    settings = dict(initial or {})

    def get_setting(key: str, default: str) -> str:
        return settings.get(key, default)

    def set_setting(key: str, value: str) -> None:
        settings[key] = value

    return settings, get_setting, set_setting


def _server_with_card() -> HealthServer:
    server = HealthServer()
    server.register_card(
        card_id=1,
        name="array1",
        host="fake.example",
        port=22,
        username="admin",
        key_path="/dev/null",
        device_profile="flashsystem_5200",
    )
    return server


def _fake_run_cmd(outputs: dict[str, str]):
    def run_cmd(command: str) -> str:
        if "lsfcconsistgrp" in command:
            return outputs.get("groups", "")
        if "lsfcmap" in command:
            return outputs.get("maps", "")
        if "lshostvdiskmap" in command:
            return outputs.get("host_maps", "")
        raise AssertionError(f"Unexpected command: {command}")

    return run_cmd


def _patch_inventory(
    monkeypatch, server: HealthServer, *, host_maps=None, host_warn=None
):
    monkeypatch.setattr(
        "launchpad.health_server.collect_fc_consistgrp_inventory",
        lambda run_cmd: (_INVENTORY_GROUPS, _INVENTORY_MAPS),
    )
    maps = host_maps if host_maps is not None else []
    warn = host_warn

    def _fake_host_maps(self, _card):
        return maps, warn

    monkeypatch.setattr(
        HealthServer,
        "_fc_host_lun_maps",
        _fake_host_maps,
        raising=False,
    )


def test_fc_consistgrp_cards_lists_registered_cards():
    server = _server_with_card()

    cards = server.fc_consistgrp_cards()

    assert cards == [{"id": 1, "name": "array1", "host": "fake.example", "url": ""}]


def test_fc_consistgrp_inventory_unknown_card():
    server = HealthServer()

    result = server.fc_consistgrp_inventory(999)

    assert result["ok"] is False
    assert any("999" in warning for warning in result["warnings"])


def test_fc_consistgrp_inventory_returns_groups_maps_stand_alone(monkeypatch):
    server = _server_with_card()
    _patch_inventory(monkeypatch, server)

    result = server.fc_consistgrp_inventory(1)

    assert result["ok"] is True
    assert result["warnings"] == []
    assert result["card"] == {"id": 1, "name": "array1", "host": "fake.example"}
    assert [g["name"] for g in result["groups"]] == ["AWD1_AS400_CG", "empty_cg"]
    assert [m["name"] for m in result["maps"]] == ["fcmap0", "standalone1"]
    assert [m["name"] for m in result["stand_alone"]] == ["standalone1"]
    assert "summaries" in result
    assert isinstance(result["summaries"], list)
    assert len(result["summaries"]) == 2
    assert result["summaries"][0]["name"] == "AWD1_AS400_CG"
    assert result["summaries"][0]["fc_map_count"] == 1
    assert "host_map_count" in result["summaries"][0]
    assert "snaps_per_week" in result["summaries"][0]
    assert "snaps_source" in result["summaries"][0]


def test_fc_consistgrp_inventory_collect_failure(monkeypatch):
    server = _server_with_card()

    def boom(run_cmd):
        raise RuntimeError("ssh unreachable")

    monkeypatch.setattr(
        "launchpad.health_server.collect_fc_consistgrp_inventory", boom
    )
    monkeypatch.setattr(
        HealthServer,
        "_fc_host_lun_maps",
        lambda self, _card: ([], None),
        raising=False,
    )

    result = server.fc_consistgrp_inventory(1)

    assert result["ok"] is False
    assert any("ssh unreachable" in warning for warning in result["warnings"])


def test_fc_consistgrp_inventory_host_map_failure_warns(monkeypatch):
    server = _server_with_card()
    _patch_inventory(
        monkeypatch,
        server,
        host_maps=[],
        host_warn="Unable to collect host maps: ssh timeout",
    )

    result = server.fc_consistgrp_inventory(1)

    assert result["ok"] is True
    assert any(
        "Unable to collect host maps" in warning for warning in result["warnings"]
    )
    assert result["summaries"]
    assert all(row["host_map_count"] == 0 for row in result["summaries"])


def test_fc_consistgrp_inventory_skips_host_maps_without_summaries(monkeypatch):
    server = _server_with_card()
    host_calls: list[object] = []

    monkeypatch.setattr(
        "launchpad.health_server.collect_fc_consistgrp_inventory",
        lambda run_cmd: (_INVENTORY_GROUPS, _INVENTORY_MAPS),
    )

    def _track_host_maps(self, _card):
        host_calls.append(_card)
        return [], None

    monkeypatch.setattr(
        HealthServer,
        "_fc_host_lun_maps",
        _track_host_maps,
        raising=False,
    )

    result = server.fc_consistgrp_inventory(1, include_summaries=False)

    assert result["ok"] is True
    assert result["summaries"] == []
    assert result["host_maps"] == []
    assert host_calls == []


def test_preview_fc_consistgrp_skips_host_map_collection(monkeypatch):
    server = _server_with_card()
    host_calls: list[object] = []

    monkeypatch.setattr(
        "launchpad.health_server.collect_fc_consistgrp_inventory",
        lambda run_cmd: (_INVENTORY_GROUPS, _INVENTORY_MAPS),
    )

    def _track_host_maps(self, _card):
        host_calls.append(_card)
        return [], None

    monkeypatch.setattr(
        HealthServer,
        "_fc_host_lun_maps",
        _track_host_maps,
        raising=False,
    )

    result = server.preview_fc_consistgrp(1, "create_group", {"name": "New_CG"})

    assert result["ok"] is True
    assert host_calls == []


def test_contingency_fc_cg_summary_unknown_group():
    server = HealthServer()

    result = server.contingency_fc_cg_summary("missing-group")

    assert result["ok"] is False
    assert result["summaries"] == []
    assert any("missing-group" in warning for warning in result["warnings"])


def test_contingency_fc_cg_summary_resolves_card(monkeypatch):
    settings, getter, setter = _settings_backend(
        {
            CONTINGENCY_GROUPS_SETTING: json.dumps(
                [
                    {
                        "id": "lab-1",
                        "name": "Lab Site",
                        "storage_hint": "array1",
                        "hosts": [],
                        "volumes": [],
                        "maps": [],
                    }
                ]
            ),
            SNAPSHOT_OVERRIDES_SETTING: "{}",
        }
    )
    server = _server_with_card()
    server.set_settings_backend(getter, setter)
    _patch_inventory(
        monkeypatch,
        server,
        host_maps=[{"vdisk_name": "AWD1_AS400_1_Snap1", "host_name": "h1"}],
    )

    result = server.contingency_fc_cg_summary("lab-1")

    assert result["ok"] is True
    assert result["card"] == {"id": 1, "name": "array1", "host": "fake.example"}
    assert len(result["summaries"]) == 2
    assert result["summaries"][0]["host_map_count"] == 1
    assert result["warnings"] == []


def test_contingency_fc_cg_summary_locked_returns_clear_error(monkeypatch):
    server = _server_with_card()
    assert server.is_unlocked() is False
    monkeypatch.setattr(
        server,
        "_contingency_group_by_id",
        lambda _gid: {
            "id": "lab-1",
            "name": "Lab Site",
            "storage_hint": "array1",
        },
    )

    result = server.contingency_fc_cg_summary("lab-1")

    assert result["ok"] is False
    assert any("unlock" in warning.lower() for warning in result["warnings"])


def _server_with_inventory(monkeypatch) -> HealthServer:
    server = _server_with_card()
    _patch_inventory(monkeypatch, server)
    return server


def test_preview_fc_consistgrp_create_group_returns_mkfcconsistgrp_step(monkeypatch):
    server = _server_with_inventory(monkeypatch)

    result = server.preview_fc_consistgrp(1, "create_group", {"name": "New_CG"})

    assert result["ok"] is True
    assert any("mkfcconsistgrp" in step["cmd"] for step in result["steps"])


def test_preview_fc_consistgrp_delete_non_empty_blocks(monkeypatch):
    server = _server_with_inventory(monkeypatch)

    result = server.preview_fc_consistgrp(
        1, "delete_group", {"group_name": "AWD1_AS400_CG"}
    )

    assert result["ok"] is False
    assert any(w.startswith("ERROR:") for w in result["warnings"])
    assert result["steps"] == []


def test_run_fc_consistgrp_rejects_confirm_false(monkeypatch):
    server = _server_with_inventory(monkeypatch)

    result = server.run_fc_consistgrp(1, "create_group", {"name": "New_CG"}, confirm=False)

    assert result["ok"] is False
    assert any("confirm" in warning.lower() for warning in result["warnings"])


def test_run_fc_consistgrp_requires_confirm_argument():
    server = HealthServer()

    try:
        server.run_fc_consistgrp(1, "create_group", {"name": "New_CG"})
    except TypeError:
        pass
    else:
        raise AssertionError("Expected TypeError when confirm is omitted")


def test_run_fc_consistgrp_blocks_when_preview_blocks(monkeypatch):
    server = _server_with_inventory(monkeypatch)

    result = server.run_fc_consistgrp(
        1, "delete_group", {"group_name": "AWD1_AS400_CG"}, confirm=True
    )

    assert result["ok"] is False
    assert any(w.startswith("ERROR:") for w in result["warnings"])


def test_run_fc_consistgrp_executes_steps_when_confirmed(monkeypatch):
    server = _server_with_inventory(monkeypatch)
    run_calls: list[tuple] = []

    def fake_run_snap_steps(steps, run_cmd):
        run_calls.append((steps, run_cmd))
        return {"ok": True, "log": [{"kind": s.kind, "cmd": s.cmd} for s in steps]}

    monkeypatch.setattr("launchpad.health_server.run_snap_steps", fake_run_snap_steps)

    result = server.run_fc_consistgrp(1, "create_group", {"name": "New_CG"}, confirm=True)

    assert result["ok"] is True
    assert len(run_calls) == 1
    assert result["warnings"] == []


def test_open_fc_consistgrp_url_includes_card_id(monkeypatch):
    server = HealthServer()
    opened: list[str] = []

    monkeypatch.setattr(server, "ensure_running", lambda: None)
    monkeypatch.setattr(
        "launchpad.health_server.webbrowser.open",
        lambda url: opened.append(url),
    )

    url = server.open_fc_consistgrp(card_id=42)

    assert "?card=42" in url
    assert url.endswith("/fc-consistgrp?card=42")
    assert opened == [url]
