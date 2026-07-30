from launchpad.health_server import HealthServer


def _unlock(server: HealthServer) -> None:
    server.set_settings_backend(lambda _key, default: default, lambda _key, _value: None)


def test_export_fc_cg_summary_requires_group_id_in_handler_source():
    import inspect
    from launchpad.health_server import _HealthHandler

    source = inspect.getsource(_HealthHandler.do_GET)
    assert "/api/contingency-groups/fc-cg-summary/export" in source


def test_export_fc_cg_summary_bytes_happy_path(monkeypatch):
    server = HealthServer()
    _unlock(server)

    def fake_summary(group_id):
        assert group_id == "g1"
        return {
            "ok": True,
            "warnings": [],
            "card": {"name": "Hartford", "id": 1},
            "summaries": [
                {
                    "name": "AAN1_FC",
                    "status": "idle_or_copied",
                    "fc_map_count": 1,
                    "host_map_count": 1,
                    "total_size": "10.0 GB",
                    "policy": "",
                    "snaps_per_week": 1,
                }
            ],
        }

    monkeypatch.setattr(server, "contingency_fc_cg_summary", fake_summary)
    body, filename, content_type = server.export_fc_cg_summary_bytes(group_id="g1")
    assert body[:2] == b"PK"
    assert filename.startswith("FC_CG_Summary_Hartford_")
    assert filename.endswith(".xlsx")
    assert "spreadsheetml" in content_type


def test_export_fc_cg_summary_bytes_raises_when_not_ok(monkeypatch):
    server = HealthServer()
    monkeypatch.setattr(
        server,
        "contingency_fc_cg_summary",
        lambda _gid: {
            "ok": False,
            "warnings": ["LaunchPad must be unlocked to collect FlashCopy CG summary."],
            "summaries": [],
            "card": None,
        },
    )
    try:
        server.export_fc_cg_summary_bytes(group_id="g1")
        assert False, "expected LookupError"
    except LookupError as exc:
        assert "unlock" in str(exc).lower()
