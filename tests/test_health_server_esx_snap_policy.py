from launchpad.esx_snap_policy_ops import (
    parse_lsvdisk_membership,
    parse_named_objects,
    preview_hash,
)
from launchpad.health_server import HealthServer

POLICY_SAMPLE = """id:name
0:keep-me
"""
VG_SAMPLE = """id:name
0:Other_VG
"""
VDISK_SAMPLE = """id:name:capacity:volume_group
0:VOL_A:1.00TB:
1:VOL_B:2.00TB:
"""
EXISTING_POLICY = """id:name
0:ESX-snap
"""


def _server_two_cards() -> HealthServer:
    server = HealthServer()
    server.register_card(
        card_id=1,
        name="Windsor",
        host="win.example",
        port=22,
        username="admin",
        key_path="/dev/null",
        device_profile="flashsystem_9200",
    )
    server.register_card(
        card_id=2,
        name="Hartford",
        host="hart.example",
        port=22,
        username="admin",
        key_path="/dev/null",
        device_profile="flashsystem_9200",
    )
    server.register_card(
        card_id=3,
        name="HPE box",
        host="hpe.example",
        port=22,
        username="3paradm",
        key_path="/dev/null",
        device_profile="hpe_3par_8450",
    )
    return server


def test_cards_are_ibm_only_with_default_vg():
    server = _server_two_cards()
    cards = server.esx_snap_policy_cards()
    names = {row["name"] for row in cards}
    assert names == {"Windsor", "Hartford"}
    windsor = next(row for row in cards if row["name"] == "Windsor")
    assert windsor["default_vg_name"] == "Windsor_ESX-snap"


def test_run_without_confirm_or_bad_hash_does_not_mutate(monkeypatch):
    server = _server_two_cards()
    calls: list[str] = []

    def bind_host(card, **kwargs):
        def run_cmd(command: str) -> str:
            calls.append(command)
            return ""
        return run_cmd

    monkeypatch.setattr(HealthServer, "_snap_run_command", staticmethod(bind_host))
    payload = {
        "start_time": "02:00",
        "arrays": [
            {"card_id": 2, "vg_name": "Hartford_ESX-snap", "volume_names": ["VOL_A"]},
        ],
        "preview_hash": "deadbeef",
    }
    denied = server.run_esx_snap_policy(payload, confirm=False)
    assert denied["ok"] is False
    assert calls == []
    denied_hash = server.run_esx_snap_policy(payload, confirm=True)
    assert denied_hash["ok"] is False
    assert calls == []


def test_preview_many_one_blocked_still_ok(monkeypatch):
    server = _server_two_cards()

    def inventory(self, card):
        if card.card_id == 1:
            return {
                "ok": True,
                "error": "",
                "policies": parse_named_objects(EXISTING_POLICY),
                "volume_groups": set(),
                "volumes": parse_lsvdisk_membership(VDISK_SAMPLE),
            }
        return {
            "ok": True,
            "error": "",
            "policies": parse_named_objects(POLICY_SAMPLE),
            "volume_groups": parse_named_objects(VG_SAMPLE),
            "volumes": parse_lsvdisk_membership(VDISK_SAMPLE),
        }

    monkeypatch.setattr(HealthServer, "_esx_snap_inventory", inventory)
    payload = {
        "start_time": "02:00",
        "arrays": [
            {"card_id": 1, "vg_name": "Windsor_ESX-snap", "volume_names": ["VOL_A"]},
            {"card_id": 2, "vg_name": "Hartford_ESX-snap", "volume_names": ["VOL_B"]},
        ],
    }
    result = server.preview_esx_snap_policy(payload)
    assert result["ok"] is True
    by_id = {row["card_id"]: row for row in result["arrays"]}
    assert by_id[1]["runnable"] is False
    assert by_id[2]["runnable"] is True


def test_run_recheck_skips_mutate_when_policy_appears(monkeypatch):
    server = _server_two_cards()
    mutate_cmds: list[str] = []

    def inventory(self, card):
        return {
            "ok": True,
            "error": "",
            "policies": {"ESX-snap"},
            "volume_groups": set(),
            "volumes": parse_lsvdisk_membership(VDISK_SAMPLE),
        }

    def bind_host(card, **kwargs):
        def run_cmd(command: str) -> str:
            mutate_cmds.append(command)
            return "ok"
        return run_cmd

    monkeypatch.setattr(HealthServer, "_esx_snap_inventory", inventory)
    monkeypatch.setattr(HealthServer, "_snap_run_command", staticmethod(bind_host))
    arrays = [
        {"card_id": 2, "vg_name": "Hartford_ESX-snap", "volume_names": ["VOL_A"]},
    ]
    payload = {
        "start_time": "02:00",
        "arrays": arrays,
        "preview_hash": preview_hash("02:00", arrays),
    }
    result = server.run_esx_snap_policy(payload, confirm=True)
    assert result["ok"] is False
    assert mutate_cmds == []
    assert any(not row["ok"] for row in result["arrays"])
