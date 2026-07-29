import inspect
from io import BytesIO

from openpyxl import load_workbook

from launchpad.health_server import HealthCard, HealthServer, _HealthHandler


def _unlock(server: HealthServer) -> None:
    server.set_settings_backend(lambda _key, default: default, lambda _key, _value: None)


def _svc_card(
    card_id: int,
    name: str,
    host: str,
    *,
    category: str = "",
    device_profile: str = "flashsystem_7200",
) -> HealthCard:
    return HealthCard(
        card_id=card_id,
        name=name,
        host=host,
        port=22,
        username="user",
        key_path="/tmp/key",
        device_profile=device_profile,
        category=category,
    )


def _groups_output(*rows: tuple) -> str:
    lines = ["id:name:status:FC_mapping_count:flash_time"]
    for row in rows:
        row_id, name, status, map_count = row[:4]
        flash = row[4] if len(row) > 4 else ""
        lines.append(f"{row_id}:{name}:{status}:{map_count}:{flash}")
    return "\n".join(lines) + "\n"


def _snap_runner(outputs_by_card: dict[int, dict[str, str]]):
    def factory(card: HealthCard):
        outputs = outputs_by_card.get(card.card_id, {})

        def run(command: str) -> str:
            if "lsfcconsistgrp" in command:
                return outputs.get("groups", "")
            if "lsfcmap" in command:
                return outputs.get("maps", "id:name:source_vdisk_name:target_vdisk_name:status:progress:group_name\n")
            if "lsvdisk" in command:
                return outputs.get("volumes", "")
            return ""

        return run

    return factory


def test_live_scan_requires_unlock(monkeypatch):
    server = HealthServer()
    monkeypatch.setattr(server, "is_unlocked", lambda: False)
    try:
        server.scan_fc_consistgrp_status_live()
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "unlock" in str(exc).lower()


def test_live_scan_happy_path(monkeypatch):
    server = HealthServer()
    _unlock(server)
    card = _svc_card(1, "Hartford", "10.0.0.1", category="Hartford Site")
    server._cards[1] = card
    server.set_monitor_enabled(card_id=1, enabled=True)
    monkeypatch.setattr(server, "sync_from_app", lambda: 0)
    monkeypatch.setattr(
        server,
        "_snap_run_command",
        _snap_runner(
            {
                1: {
                    "groups": _groups_output(
                        ("0", "AWD1_AS400_CG", "idle_or_copied", "6", "2026-01-15_0830"),
                        ("1", "STOPPED_CG", "stopped", "0"),
                    )
                }
            }
        ),
    )

    result = server.scan_fc_consistgrp_status_live()
    assert result["errors"] == []
    assert len(result["rows"]) == 2
    by_name = {row["name"]: row for row in result["rows"]}
    idle = by_name["AWD1_AS400_CG"]
    assert idle["site"] == "Hartford Site"
    assert idle["card_name"] == "Hartford"
    assert idle["host"] == "10.0.0.1"
    assert idle["status"] == "idle_or_copied"
    assert idle["map_count"] == 6
    assert idle["flash_time"] == "2026-01-15_0830"
    assert idle["error"] == ""
    assert idle["card_id"] == 1
    assert idle["bucket"] == "idle_or_copied"
    assert by_name["STOPPED_CG"]["bucket"] == "stopped"
    cached = server.get_fc_consistgrp_status_cache()
    assert cached is not None
    assert len(cached["rows"]) == 2


def test_live_scan_site_falls_back_to_card_name(monkeypatch):
    server = HealthServer()
    _unlock(server)
    card = _svc_card(1, "Primera", "10.0.0.2", category="")
    server._cards[1] = card
    server.set_monitor_enabled(card_id=1, enabled=True)
    monkeypatch.setattr(server, "sync_from_app", lambda: 0)
    monkeypatch.setattr(
        server,
        "_snap_run_command",
        _snap_runner({1: {"groups": _groups_output(("0", "CG1", "copying", "2"))}}),
    )
    result = server.scan_fc_consistgrp_status_live()
    assert result["rows"][0]["site"] == "Primera"
    assert result["rows"][0]["bucket"] == "copying"


def test_live_scan_filters_by_card_id(monkeypatch):
    server = HealthServer()
    _unlock(server)
    for card_id, name in ((1, "SiteA"), (2, "SiteB")):
        server._cards[card_id] = _svc_card(card_id, name, f"10.0.0.{card_id}")
        server.set_monitor_enabled(card_id=card_id, enabled=True)
    monkeypatch.setattr(server, "sync_from_app", lambda: 0)
    monkeypatch.setattr(
        server,
        "_snap_run_command",
        _snap_runner(
            {
                1: {"groups": _groups_output(("0", "A_CG", "idle_or_copied", "1"))},
                2: {"groups": _groups_output(("0", "B_CG", "stopped", "1"))},
            }
        ),
    )
    result = server.scan_fc_consistgrp_status_live(card_id=2)
    assert len(result["rows"]) == 1
    assert result["rows"][0]["name"] == "B_CG"
    assert result["rows"][0]["card_name"] == "SiteB"


def test_live_scan_skips_monitor_off_and_ineligible(monkeypatch):
    server = HealthServer()
    _unlock(server)
    server._cards[1] = _svc_card(1, "Off", "10.0.0.1")
    server._cards[2] = _svc_card(
        2, "HPE", "10.0.0.2", device_profile="hpe_primera_600"
    )
    server._cards[3] = _svc_card(3, "On", "10.0.0.3")
    server.set_monitor_enabled(card_id=1, enabled=False)
    server.set_monitor_enabled(card_id=2, enabled=True)
    server.set_monitor_enabled(card_id=3, enabled=True)
    monkeypatch.setattr(server, "sync_from_app", lambda: 0)
    monkeypatch.setattr(
        server,
        "_snap_run_command",
        _snap_runner(
            {
                1: {"groups": _groups_output(("0", "OFF_CG", "stopped", "0"))},
                2: {"groups": _groups_output(("0", "HPE_CG", "stopped", "0"))},
                3: {"groups": _groups_output(("0", "ON_CG", "idle_or_copied", "1"))},
            }
        ),
    )
    result = server.scan_fc_consistgrp_status_live()
    assert [row["name"] for row in result["rows"]] == ["ON_CG"]


def test_live_scan_per_card_error_continues(monkeypatch):
    server = HealthServer()
    _unlock(server)
    server._cards[1] = _svc_card(1, "Broken", "10.0.0.1")
    server._cards[2] = _svc_card(2, "Good", "10.0.0.2")
    server.set_monitor_enabled(card_id=1, enabled=True)
    server.set_monitor_enabled(card_id=2, enabled=True)
    monkeypatch.setattr(server, "sync_from_app", lambda: 0)

    def factory(card: HealthCard):
        if card.card_id == 1:

            def fail(_command: str) -> str:
                raise RuntimeError("ssh timeout")

            return fail
        return _snap_runner(
            {2: {"groups": _groups_output(("0", "GOOD_CG", "idle_or_copied", "1"))}}
        )(card)

    monkeypatch.setattr(server, "_snap_run_command", factory)
    result = server.scan_fc_consistgrp_status_live()
    assert len(result["errors"]) == 1
    assert result["errors"][0]["card_name"] == "Broken"
    assert len(result["rows"]) == 1
    assert result["rows"][0]["name"] == "GOOD_CG"


def test_live_scan_sorts_by_site_card_name(monkeypatch):
    server = HealthServer()
    _unlock(server)
    server._cards[1] = _svc_card(1, "ZCard", "10.0.0.1", category="BSite")
    server._cards[2] = _svc_card(2, "ACard", "10.0.0.2", category="ASite")
    server.set_monitor_enabled(card_id=1, enabled=True)
    server.set_monitor_enabled(card_id=2, enabled=True)
    monkeypatch.setattr(server, "sync_from_app", lambda: 0)
    monkeypatch.setattr(
        server,
        "_snap_run_command",
        _snap_runner(
            {
                1: {
                    "groups": _groups_output(
                        ("0", "z_cg", "stopped", "0"),
                        ("1", "a_cg", "stopped", "0"),
                    )
                },
                2: {"groups": _groups_output(("0", "mid_cg", "copying", "1"))},
            }
        ),
    )
    result = server.scan_fc_consistgrp_status_live()
    names = [row["name"] for row in result["rows"]]
    assert names == ["mid_cg", "a_cg", "z_cg"]


def test_export_requires_prior_scan():
    server = HealthServer()
    _unlock(server)
    try:
        server.export_fc_consistgrp_status_bytes(format="xlsx")
        assert False, "expected LookupError"
    except LookupError as exc:
        assert "refresh" in str(exc).lower()


def test_export_filters_by_bucket_and_card_id(monkeypatch):
    server = HealthServer()
    _unlock(server)
    server.set_fc_consistgrp_status_cache(
        {
            "rows": [
                {
                    "site": "Hartford",
                    "card_name": "Hartford",
                    "host": "10.0.0.1",
                    "name": "IDLE_CG",
                    "status": "idle_or_copied",
                    "map_count": 1,
                    "flash_time": "",
                    "error": "",
                    "card_id": 1,
                    "bucket": "idle_or_copied",
                },
                {
                    "site": "Hartford",
                    "card_name": "Hartford",
                    "host": "10.0.0.1",
                    "name": "STOP_CG",
                    "status": "stopped",
                    "map_count": 0,
                    "flash_time": "",
                    "error": "",
                    "card_id": 1,
                    "bucket": "stopped",
                },
                {
                    "site": "Other",
                    "card_name": "Other",
                    "host": "10.0.0.2",
                    "name": "OTHER_IDLE",
                    "status": "idle_or_copied",
                    "map_count": 2,
                    "flash_time": "",
                    "error": "",
                    "card_id": 2,
                    "bucket": "idle_or_copied",
                },
            ],
            "errors": [],
        }
    )
    body, filename, content_type = server.export_fc_consistgrp_status_bytes(
        format="xlsx",
        card_id=1,
        bucket="idle_or_copied",
    )
    assert filename.endswith(".xlsx")
    assert "spreadsheetml" in content_type
    workbook = load_workbook(BytesIO(body))
    sheet = workbook["FC CG Status"]
    assert sheet["D2"].value == "IDLE_CG"
    assert sheet["D3"].value is None


def test_api_fc_consistgrp_status_routes_declared():
    get_src = inspect.getsource(_HealthHandler.do_GET)
    assert "/api/fc-consistgrp/status/live" in get_src
    assert "/api/fc-consistgrp/status/export" in get_src


def test_fc_consistgrp_cards_includes_site_monitor_and_profile(monkeypatch):
    server = HealthServer()
    card = _svc_card(1, "Hartford", "10.0.0.1", category="HTFD")
    server._cards[1] = card
    server.set_monitor_enabled(card_id=1, enabled=True)
    monkeypatch.setattr(server, "sync_from_app", lambda: 0)
    cards = server.fc_consistgrp_cards()
    assert len(cards) == 1
    assert cards[0]["site"] == "HTFD"
    assert cards[0]["monitor_on"] is True
    assert cards[0]["device_profile"] == "flashsystem_7200"
    assert cards[0]["card_type"] == "ssh"
