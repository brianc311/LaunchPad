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


def test_update_card_host_requires_unlock(monkeypatch):
    server = HealthServer()
    monkeypatch.setattr(server, "is_unlocked", lambda: False)
    try:
        server.update_volume_find_card_host(1, "10.1.1.1")
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "unlock" in str(exc).lower()


def test_update_card_host_normalizes_and_patches():
    server = HealthServer()
    _unlock(server)
    applied = {}

    def patcher(card_id, *, host=None, name=None):
        applied["card_id"] = card_id
        applied["host"] = host
        applied["name"] = name
        return {"card_id": card_id, "host": host or "", "name": name or "Site"}

    server.set_card_patcher(patcher)
    server._cards[1] = HealthCard(
        card_id=1,
        name="Site",
        host="10.0.0.1",
        port=22,
        username="user",
        key_path="/tmp/key",
        device_profile="flashsystem_7200",
    )
    result = server.update_volume_find_card_host(1, "https://10.244.25.158/")
    assert result["host"] == "10.244.25.158"
    assert applied["host"] == "10.244.25.158"
    assert applied["card_id"] == 1
    assert server._cards[1].host == "10.244.25.158"


def test_update_card_host_rejects_empty():
    server = HealthServer()
    _unlock(server)
    server.set_card_patcher(
        lambda card_id, *, host=None, name=None: {
            "card_id": card_id,
            "host": host or "",
            "name": name or "",
        }
    )
    try:
        server.update_volume_find_card_host(1, "https:///")
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "host" in str(exc).lower()


def test_ensure_anderson_rename_idempotent():
    server = HealthServer()
    _unlock(server)
    applied = []

    def patcher(card_id, *, host=None, name=None):
        applied.append({"card_id": card_id, "host": host, "name": name})
        card = server._cards[card_id]
        if host is not None:
            card.host = host
        if name is not None:
            card.name = name
        return {"card_id": card_id, "host": card.host, "name": card.name}

    server.set_card_patcher(patcher)
    server._cards[11] = HealthCard(
        card_id=11,
        name="WILLIAMSTON (ANDERSON) SC",
        host="",
        port=22,
        username="user",
        key_path="/tmp/key",
        device_profile="flashsystem_7200",
    )
    plan = server.ensure_anderson_card_rename()
    assert plan is not None
    assert plan["new_name"] == "Anderson, SC"
    assert plan["new_host"] == "10.244.25.158"
    assert server._cards[11].name == "Anderson, SC"
    assert server._cards[11].host == "10.244.25.158"
    assert len(applied) == 1
    assert server.ensure_anderson_card_rename() is None
    assert len(applied) == 1


def test_api_volume_find_card_host_route_declared():
    import inspect
    from launchpad.health_server import _HealthHandler

    src = inspect.getsource(_HealthHandler.do_POST)
    assert "/api/volume-find/card-host" in src


def test_find_hosts_cache_uses_fc_hosts(monkeypatch):
    server = HealthServer()
    card = HealthCard(
        card_id=1,
        name="Woodland Hills, CA",
        host="10.244.66.227",
        port=22,
        username="user",
        key_path="/tmp/key",
        device_profile="flashsystem_9500",
        command_results=[
            {
                "command": "svcinfo lshost -delim :",
                "output": "id:name:port_count\n0:woo_esx_cluster:2\n",
            }
        ],
    )
    server._cards[1] = card
    server.set_monitor_enabled(card_id=1, enabled=True)
    monkeypatch.setattr(server, "sync_from_app", lambda: 0)
    result = server.find_volumes("woo", mode="cache", find_type="host")
    assert result["errors"] == []
    assert len(result["matches"]) == 1
    match = result["matches"][0]
    assert match["host_name"] == "woo_esx_cluster"
    assert match["source"] == "cache"
    assert match["host"] == "10.244.66.227"


def test_find_hosts_live_requires_unlock(monkeypatch):
    server = HealthServer()
    monkeypatch.setattr(server, "is_unlocked", lambda: False)
    try:
        server.find_volumes("x", mode="live", find_type="host")
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "unlock" in str(exc).lower()
        assert "host" in str(exc).lower()


def test_find_hosts_live_ibm_happy_path(monkeypatch):
    server = HealthServer()
    _unlock(server)
    card = HealthCard(
        card_id=1,
        name="Woodland Hills, CA",
        host="10.244.66.227",
        port=22,
        username="user",
        key_path="/tmp/key",
        device_profile="flashsystem_9500",
    )
    server._cards[1] = card
    server.set_monitor_enabled(card_id=1, enabled=True)
    monkeypatch.setattr(server, "sync_from_app", lambda: 0)

    def _runner(_card):
        return lambda command: (
            "id:name:port_count\n0:woo_esx_cluster:2\n"
            if "lshost" in command
            else ""
        )

    monkeypatch.setattr(server, "_lun_run_command", _runner)
    result = server.find_volumes("woo", mode="live", find_type="host")
    assert result["errors"] == []
    assert len(result["matches"]) == 1
    match = result["matches"][0]
    assert match["host_name"] == "woo_esx_cluster"
    assert match["source"] == "live"
    assert match["vendor"] == "ibm"
    assert match["host"] == "10.244.66.227"
    assert match.get("wwpns", "") == ""


def test_find_volumes_default_type_unchanged(monkeypatch):
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
    assert "host_name" not in result["matches"][0]
