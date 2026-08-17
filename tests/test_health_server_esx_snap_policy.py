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
0:esx_snap
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
    assert windsor["default_vg_name"] == "Windsor_esx_snap"


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
        "policy_name": "esx_snap",
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

    def bind_host(card, **kwargs):
        def run_cmd(command: str) -> str:
            return ""
        return run_cmd

    monkeypatch.setattr(HealthServer, "_snap_run_command", staticmethod(bind_host))
    payload = {
        "start_time": "02:00",
        "policy_name": "esx_snap",
        "arrays": [
            {"card_id": 1, "vg_name": "Windsor_ESX-snap", "volume_names": ["VOL_A"]},
            {"card_id": 2, "vg_name": "Hartford_ESX-snap", "volume_names": ["VOL_B"]},
        ],
    }
    result = server.preview_esx_snap_policy(payload)
    assert result["ok"] is True
    assert result["policy_name"] == "esx_snap"
    assert result["preview_hash"] == preview_hash(
        "02:00", list(payload["arrays"]), payload["policy_name"]
    )
    by_id = {row["card_id"]: row for row in result["arrays"]}
    assert by_id[1]["runnable"] is False
    assert by_id[2]["runnable"] is True


def test_run_recheck_skips_mutate_when_policy_appears(monkeypatch):
    server = _server_two_cards()
    mutate_cmds: list[str] = []
    inv_calls = {"n": 0}

    def inventory(self, card):
        inv_calls["n"] += 1
        policies = set() if inv_calls["n"] == 1 else {"esx_snap"}
        return {
            "ok": True,
            "error": "",
            "policies": policies,
            "volume_groups": set(),
            "volumes": parse_lsvdisk_membership(VDISK_SAMPLE),
        }

    def bind_host(card, **kwargs):
        def run_cmd(command: str) -> str:
            if str(command).startswith("svctask"):
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
        "policy_name": "esx_snap",
        "arrays": arrays,
        "preview_hash": preview_hash("02:00", arrays, "esx_snap"),
    }
    result = server.run_esx_snap_policy(payload, confirm=True)
    assert result["ok"] is False
    assert result["policy_name"] == "esx_snap"
    assert mutate_cmds == []
    assert any(not row["ok"] for row in result["arrays"])
    joined = " ".join(w for row in result["arrays"] for w in row["warnings"])
    assert "esx_snap" in joined
    assert "delete esx_snap" in joined
    assert "delete ESX-snap" not in joined


def test_preview_uses_typed_policy_name_in_hash_and_steps(monkeypatch):
    server = _server_two_cards()

    def inventory(self, card):
        return {
            "ok": True,
            "error": "",
            "policies": set(),
            "volume_groups": set(),
            "volumes": parse_lsvdisk_membership(VDISK_SAMPLE),
        }

    monkeypatch.setattr(HealthServer, "_esx_snap_inventory", inventory)

    def bind_host(card, **kwargs):
        def run_cmd(command: str) -> str:
            return ""
        return run_cmd

    monkeypatch.setattr(HealthServer, "_snap_run_command", staticmethod(bind_host))
    arrays = [
        {"card_id": 2, "vg_name": "Hartford_esx_snap", "volume_names": ["VOL_A"]},
    ]
    payload = {
        "start_time": "02:00",
        "policy_name": "siteA_esx",
        "arrays": arrays,
    }
    result = server.preview_esx_snap_policy(payload)
    assert result["policy_name"] == "siteA_esx"
    assert result["preview_hash"] == preview_hash("02:00", arrays, "siteA_esx")
    cmds = [step["cmd"] for row in result["arrays"] for step in row["steps"]]
    assert any("siteA_esx" in cmd for cmd in cmds)


def test_preview_applies_checked_volume_details(monkeypatch):
    server = _server_two_cards()

    def inventory(self, card):
        return {
            "ok": True,
            "error": "",
            "policies": set(),
            "volume_groups": set(),
            "volumes": [
                {"name": "VOL_A", "capacity": "1.00TB", "volume_group": ""},
            ],
        }

    def bind_host(card, **kwargs):
        def run_cmd(command: str) -> str:
            if "lsvdisk" in command and "VOL_A" in command:
                return "id:0\nname:VOL_A\nvolume_group_name:Hidden_VG\n"
            return ""
        return run_cmd

    monkeypatch.setattr(HealthServer, "_esx_snap_inventory", inventory)
    monkeypatch.setattr(HealthServer, "_snap_run_command", staticmethod(bind_host))
    payload = {
        "start_time": "02:00",
        "policy_name": "esx_snap",
        "arrays": [
            {"card_id": 2, "vg_name": "Hartford_esx_snap", "volume_names": ["VOL_A"]},
        ],
    }
    result = server.preview_esx_snap_policy(payload)
    by_id = {row["card_id"]: row for row in result["arrays"]}
    assert by_id[2]["runnable"] is False
    assert any("Hidden_VG" in w for w in by_id[2]["warnings"])
