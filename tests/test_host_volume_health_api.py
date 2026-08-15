import inspect

from launchpad.health_server import HealthCard, HealthServer, _HealthHandler
from launchpad.host_volume_health_page import HOST_VOLUME_HEALTH_PATH


def _unlock(server: HealthServer) -> None:
    server.set_settings_backend(lambda _key, default: default, lambda _key, _value: None)


def test_live_scan_requires_unlock(monkeypatch):
    server = HealthServer()
    monkeypatch.setattr(server, "is_unlocked", lambda: False)
    try:
        server.scan_host_volume_health_live()
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "unlock" in str(exc).lower()


def test_live_scan_ibm_happy_path(monkeypatch):
    server = HealthServer()
    _unlock(server)
    card = HealthCard(
        card_id=1,
        name="Hartford",
        host="10.0.0.1",
        port=22,
        username="user",
        key_path="/tmp/key",
        device_profile="flashsystem_7200",
    )
    server._cards[1] = card
    server.set_monitor_enabled(card_id=1, enabled=True)
    monkeypatch.setattr(server, "sync_from_app", lambda: 0)

    def _runner(_card):
        def run(command):
            if "lshost" in command:
                return "id:name:status\n0:bad_host:offline\n1:good_host:online\n"
            if "lsvdisk" in command:
                return "id:name:mdisk_grp_name:status\n0:bad_vol:Pool0:degraded\n1:ok_vol:Pool0:online\n"
            return ""

        return run

    monkeypatch.setattr(server, "_lun_run_command", _runner)
    result = server.scan_host_volume_health_live()
    assert result["errors"] == []
    assert len(result["hosts"]) == 1
    assert result["hosts"][0]["host_name"] == "bad_host"
    assert result["hosts"][0]["status"] == "offline"
    assert len(result["volumes"]) == 1
    assert result["volumes"][0]["volume_name"] == "bad_vol"
    assert result["volumes"][0]["pool_or_cpg"] == "Pool0"


def test_parse_showvv_volumes_uses_state_not_mstr():
    from launchpad.volume_find import parse_showvv_volumes

    output = (
        "Id,Name,Rd,Mstr,State,UsrCPG\n"
        "0,vv_bad,rw,---,degraded,SSD_r5\n"
        "1,vv_ok,rw,3/1/0,normal,SSD_r5\n"
    )
    vols = parse_showvv_volumes(output)
    by_name = {v["name"]: v for v in vols}
    assert by_name["vv_bad"]["status"] == "degraded"
    assert by_name["vv_bad"]["mstr"] == "---"
    assert by_name["vv_ok"]["status"] == "normal"
    assert by_name["vv_ok"]["mstr"] == "3/1/0"


def test_live_scan_hpe_happy_path(monkeypatch):
    server = HealthServer()
    _unlock(server)
    card = HealthCard(
        card_id=2,
        name="Primera",
        host="10.0.0.2",
        port=22,
        username="3paradm",
        key_path="",
        password="secret",
        device_profile="hpe_primera_600",
    )
    server._cards[2] = card
    server.set_monitor_enabled(card_id=2, enabled=True)
    monkeypatch.setattr(server, "sync_from_app", lambda: 0)

    def fake_hpe(_host, _port, _user, commands, **_kwargs):
        outputs = []
        for command in commands:
            if command == "showhost":
                outputs.append("Id,Name,State\n0,bad_host,offline\n1,good_host,online\n")
            elif command == "showvv":
                outputs.append(
                    "Id,Name,Prov,Type,CopyOf,BsId,Rd,State,UsrCPG,SnpCPG\n"
                    "0,vv_bad,full,base,--,0,rw,degraded,SSD_r5,-\n"
                    "1,vv_ok,full,base,--,0,rw,normal,SSD_r5,-\n"
                    "2,vv_mstr_only,full,base,--,0,rw,normal,SSD_r5,-\n"
                )
            else:
                outputs.append("")
        return outputs

    monkeypatch.setattr(
        "launchpad.health_server.run_ssh_auth_hpe_commands",
        fake_hpe,
    )
    result = server.scan_host_volume_health_live()
    assert result["errors"] == []
    assert len(result["hosts"]) == 1
    assert result["hosts"][0]["host_name"] == "bad_host"
    assert len(result["volumes"]) == 1
    assert result["volumes"][0]["volume_name"] == "vv_bad"
    assert result["volumes"][0]["status"] == "degraded"


def test_live_scan_per_card_error_keeps_success(monkeypatch):
    server = HealthServer()
    _unlock(server)
    fail_card = HealthCard(
        card_id=1,
        name="Broken",
        host="10.0.0.1",
        port=22,
        username="user",
        key_path="/tmp/key",
        device_profile="flashsystem_7200",
    )
    ok_card = HealthCard(
        card_id=2,
        name="Good",
        host="10.0.0.2",
        port=22,
        username="user",
        key_path="/tmp/key",
        device_profile="flashsystem_7200",
    )
    server._cards[1] = fail_card
    server._cards[2] = ok_card
    server.set_monitor_enabled(card_id=1, enabled=True)
    server.set_monitor_enabled(card_id=2, enabled=True)
    monkeypatch.setattr(server, "sync_from_app", lambda: 0)

    def _runner(card):
        if card.card_id == 1:
            def fail(_command):
                raise RuntimeError("ssh timeout")

            return fail

        def run(command):
            if "lshost" in command:
                return "id:name:status\n0:ok_host:offline\n"
            return ""

        return run

    monkeypatch.setattr(server, "_lun_run_command", _runner)
    result = server.scan_host_volume_health_live()
    assert len(result["errors"]) == 1
    assert result["errors"][0]["card_name"] == "Broken"
    assert len(result["hosts"]) == 1
    assert result["hosts"][0]["card_name"] == "Good"


def test_live_scan_filters_by_card_id(monkeypatch):
    server = HealthServer()
    _unlock(server)
    for card_id, name in ((1, "SiteA"), (2, "SiteB")):
        card = HealthCard(
            card_id=card_id,
            name=name,
            host=f"10.0.0.{card_id}",
            port=22,
            username="user",
            key_path="/tmp/key",
            device_profile="flashsystem_7200",
        )
        server._cards[card_id] = card
        server.set_monitor_enabled(card_id=card_id, enabled=True)
    monkeypatch.setattr(server, "sync_from_app", lambda: 0)

    def _runner(card):
        return lambda command: (
            f"id:name:status\n0:{card.name}_host:offline\n"
            if "lshost" in command
            else ""
        )

    monkeypatch.setattr(server, "_lun_run_command", _runner)
    result = server.scan_host_volume_health_live(card_id=2)
    assert len(result["hosts"]) == 1
    assert result["hosts"][0]["host_name"] == "SiteB_host"
    assert result["hosts"][0]["card_name"] == "SiteB"


def test_api_host_volume_health_routes_declared():
    get_src = inspect.getsource(_HealthHandler.do_GET)
    post_src = inspect.getsource(_HealthHandler.do_POST)
    assert HOST_VOLUME_HEALTH_PATH in get_src or "/host-volume-health" in get_src
    assert "/api/host-volume-health/live" in get_src or "/api/host-volume-health/live" in post_src


def test_host_volume_health_progress_idle_and_after_scan(monkeypatch):
    server = HealthServer()
    _unlock(server)
    idle = server.host_volume_health_progress_snapshot()
    assert idle == {"running": False, "done": 0, "total": 0, "current": ""}
    card = HealthCard(
        card_id=1,
        name="Hartford",
        host="10.0.0.1",
        port=22,
        username="user",
        key_path="/tmp/key",
        device_profile="flashsystem_7200",
    )
    server._cards[1] = card
    server.set_monitor_enabled(card_id=1, enabled=True)
    monkeypatch.setattr(server, "sync_from_app", lambda: 0)
    monkeypatch.setattr(
        server,
        "_lun_run_command",
        lambda _card: (lambda command: "id:name:status\n0:h:online\n" if "lshost" in command else "id:name:mdisk_grp_name:status\n0:v:Pool0:online\n"),
    )
    server.scan_host_volume_health_live()
    done = server.host_volume_health_progress_snapshot()
    assert done["running"] is False
    assert done["done"] == 1
    assert done["total"] == 1


def test_host_volume_health_progress_card_id_total_one(monkeypatch):
    server = HealthServer()
    _unlock(server)
    for card_id, name in ((1, "SiteA"), (2, "SiteB")):
        server._cards[card_id] = HealthCard(
            card_id=card_id,
            name=name,
            host="10.0.0.1",
            port=22,
            username="user",
            key_path="/tmp/key",
            device_profile="flashsystem_7200",
        )
        server.set_monitor_enabled(card_id=card_id, enabled=True)
    monkeypatch.setattr(server, "sync_from_app", lambda: 0)
    monkeypatch.setattr(
        server,
        "_lun_run_command",
        lambda card: (
            lambda command: (
                f"id:name:status\n0:{card.name}_host:offline\n"
                if "lshost" in command
                else ""
            )
        ),
    )
    server.scan_host_volume_health_live(card_id=2)
    snap = server.host_volume_health_progress_snapshot()
    assert snap["total"] == 1
    assert snap["done"] == 1
    assert snap["running"] is False


def test_host_volume_health_progress_route_no_unlock():
    source = inspect.getsource(_HealthHandler.do_GET)
    assert "/api/host-volume-health/progress" in source
    chunk = source.split('if path == "/api/host-volume-health/progress"')[1].split("if path ==")[0]
    assert "is_unlocked" not in chunk
    assert "host_volume_health_progress_snapshot" in chunk
