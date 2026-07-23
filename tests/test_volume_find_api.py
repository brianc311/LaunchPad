from launchpad.health_server import HealthServer, HealthCard


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


def test_find_volumes_live_requires_unlock(monkeypatch):
    server = HealthServer()
    monkeypatch.setattr(server, "is_unlocked", lambda: False)
    try:
        server.find_volumes("x", mode="live")
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "unlock" in str(exc).lower()


def test_api_volume_find_route_declared():
    import inspect
    from launchpad.health_server import _HealthHandler

    src = inspect.getsource(_HealthHandler.do_GET)
    assert "/api/volume-find" in src
