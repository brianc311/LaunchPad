from launchpad.health_server import HealthServer, HealthCard


def _unlock(server: HealthServer) -> None:
    server.set_settings_backend(lambda _key, default: default, lambda _key, _value: None)


def test_find_volumes_cache_uses_command_results(monkeypatch):
    server = HealthServer()
    card = HealthCard(
        card_id=1,
        name="Hartford",
        host="10.0.0.1",
        port=22,
        username="user",
        key_path="/tmp/key",
        device_profile="flashsystem_7200",
        command_results=[
            {
                "command": "svcinfo lsvdisk -delim :",
                "output": "id:name:mdisk_grp_name\n0:pconsps_archvg_1:Pool0\n",
            }
        ],
    )
    server._cards[1] = card
    server.set_monitor_enabled(card_id=1, enabled=True)
    monkeypatch.setattr(server, "sync_from_app", lambda: 0)
    result = server.find_volumes("archvg", mode="cache")
    assert result["matches"]
    assert result["matches"][0]["volume"] == "pconsps_archvg_1"
    assert result["matches"][0]["source"] == "cache"
    assert result["matches"][0]["host"] == "10.0.0.1"


def test_find_volumes_live_requires_unlock(monkeypatch):
    server = HealthServer()
    monkeypatch.setattr(server, "is_unlocked", lambda: False)
    try:
        server.find_volumes("x", mode="live")
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "unlock" in str(exc).lower()


def test_find_volumes_live_ibm_happy_path(monkeypatch):
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
        return lambda command: (
            "id:name:mdisk_grp_name\n0:pconsps_archvg_1:Pool0\n"
            if "lsvdisk" in command
            else ""
        )

    monkeypatch.setattr(server, "_lun_run_command", _runner)
    result = server.find_volumes("archvg", mode="live")
    assert result["errors"] == []
    assert len(result["matches"]) == 1
    match = result["matches"][0]
    assert match["volume"] == "pconsps_archvg_1"
    assert match["source"] == "live"
    assert match["vendor"] == "ibm"
    assert match["host"] == "10.0.0.1"


def test_find_volumes_live_hpe_happy_path(monkeypatch):
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

    def fake_hpe(*_args, **_kwargs):
        return [
            "Id,Name,Rd,Mstr,HostDisp,VV_WWN,Prov,Type,CopyOf,BsId,UsrCPG,SnpCPG\n"
            "0,vv_archvg_prod,----,normal,0,5000ABCD,full,base,--,0,SSD_r5,-\n"
        ]

    monkeypatch.setattr(
        "launchpad.health_server.run_ssh_auth_hpe_commands",
        fake_hpe,
    )
    result = server.find_volumes("archvg", mode="live")
    assert result["errors"] == []
    assert len(result["matches"]) == 1
    match = result["matches"][0]
    assert match["volume"] == "vv_archvg_prod"
    assert match["source"] == "live"
    assert match["vendor"] == "hpe"
    assert match["pool_or_cpg"] == "SSD_r5"


def test_find_volumes_live_per_card_error_keeps_success(monkeypatch):
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
        return lambda command: (
            "id:name:mdisk_grp_name\n0:good_archvg:Pool0\n"
            if "lsvdisk" in command
            else ""
        )

    monkeypatch.setattr(server, "_lun_run_command", _runner)
    result = server.find_volumes("archvg", mode="live")
    assert len(result["errors"]) == 1
    assert result["errors"][0]["card_name"] == "Broken"
    assert "timeout" in result["errors"][0]["error"].lower()
    assert len(result["matches"]) == 1
    assert result["matches"][0]["volume"] == "good_archvg"
    assert result["matches"][0]["card_name"] == "Good"
    assert result["matches"][0]["source"] == "live"


def test_api_volume_find_route_declared():
    import inspect
    from launchpad.health_server import _HealthHandler

    src = inspect.getsource(_HealthHandler.do_GET)
    assert "/api/volume-find" in src
