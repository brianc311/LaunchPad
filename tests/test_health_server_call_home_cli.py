from launchpad.call_home_cli_ops import preview_hash
from launchpad.health_server import HealthServer


def _server() -> HealthServer:
    server = HealthServer()
    server.register_card(
        card_id=1, name="Houston", host="hou.example", port=22,
        username="admin", key_path="/dev/null", device_profile="flashsystem_9200",
    )
    server.register_card(
        card_id=2, name="Anderson", host="and.example", port=22,
        username="admin", key_path="/dev/null", device_profile="flashsystem_9200",
    )
    server.register_card(
        card_id=3, name="HPE box", host="hpe.example", port=22,
        username="3paradm", key_path="/dev/null", device_profile="hpe_3par_8450",
    )
    return server


CLOUD = "id:status\n0:active\n"
SERVERS = "id:name:IP_address:port:username\n0:emailserver0:172.29.62.98:25:avijaytc\n"
USERS = "id:name:address:user_type\n0:support:callhome0@de.ibm.com:support\n"
LSYS = "email_contact:SANArch\nemail_reply:a@b.com\nemail_organization:Wags\n"
EMPTY_SERVERS = "id:name:IP_address:port\n"


def _bind(monkeypatch, mapping):
    calls: list[str] = []

    def bind_host(card, **kwargs):
        def run_cmd(command: str) -> str:
            calls.append(command)
            for needle, out in mapping:
                if needle in command:
                    return out
            return ""
        return run_cmd

    monkeypatch.setattr(HealthServer, "_snap_run_command", staticmethod(bind_host))
    return calls


def test_cards_ibm_only():
    names = {row["name"] for row in _server().call_home_cards()}
    assert names == {"Houston", "Anderson"}


def test_run_without_confirm_or_wrong_kind_hash_does_not_mutate(monkeypatch):
    server = _server()
    calls = _bind(monkeypatch, [("lscloudcallhome", CLOUD), ("lsemailserver", EMPTY_SERVERS), ("lsemailuser", ""), ("lssystem", LSYS)])
    payload = {
        "contact": {"name": "SANArch", "reply": "a@b.com", "primary": "", "alternate": ""},
        "smtp": {"ip": "", "port": "", "username": "", "password": ""},
        "arrays": [{"card_id": 1, "location": {"company": "Wags", "street": "", "city": "", "state": "", "postal": "", "country": "", "comment": ""}}],
    }
    out = server.run_call_home_apply(payload, confirm=False)
    assert out["ok"] is False
    assert not any(c.startswith("svctask") for c in calls)
    payload["preview_hash"] = preview_hash("remove", payload)
    payload["confirm"] = True
    out2 = server.run_call_home_apply(payload, confirm=True)
    assert out2["ok"] is False
    assert not any(c.startswith("svctask") for c in calls)


def test_existing_server_blocks_all_apply_commands(monkeypatch):
    server = _server()
    calls = _bind(monkeypatch, [("lscloudcallhome", CLOUD), ("lsemailserver", SERVERS), ("lsemailuser", USERS), ("lssystem", LSYS)])
    payload = {
        "contact": {"name": "SANArch", "reply": "a@b.com", "primary": "", "alternate": ""},
        "smtp": {"ip": "10.0.0.1", "port": "25", "username": "u", "password": "s3cret"},
        "arrays": [{"card_id": 1, "location": {"company": "Wags", "street": "", "city": "", "state": "", "postal": "", "country": "", "comment": ""}}],
    }
    preview = server.preview_call_home_apply(payload)
    assert preview["ok"] is False
    assert preview["arrays"][0]["runnable"] is False
    joined = str(preview)
    assert "s3cret" not in joined
    payload["preview_hash"] = preview_hash("apply", payload)
    result = server.run_call_home_apply(payload, confirm=True)
    assert result["ok"] is False
    assert not any(c.startswith("svctask chemail") for c in calls)
    assert not any("mkemailserver" in c for c in calls)


def test_apply_then_remove_order(monkeypatch):
    server = _server()
    calls = _bind(monkeypatch, [("lscloudcallhome", CLOUD), ("lsemailserver", EMPTY_SERVERS), ("lsemailuser", USERS), ("lssystem", LSYS)])
    payload = {
        "contact": {"name": "SANArch", "reply": "a@b.com", "primary": "", "alternate": ""},
        "smtp": {"ip": "10.0.0.1", "port": "25", "username": "u", "password": "s3cret"},
        "arrays": [{"card_id": 1, "location": {"company": "Wags", "street": "", "city": "", "state": "", "postal": "", "country": "", "comment": ""}}],
    }
    payload["preview_hash"] = preview_hash("apply", payload)
    result = server.run_call_home_apply(payload, confirm=True)
    assert result["ok"] is True
    mutate = [c for c in calls if c.startswith("svctask")]
    assert mutate[0].startswith("svctask chemail")
    assert mutate[-1].startswith("svctask mkemailserver")
    assert "s3cret" in mutate[-1]
    log_cmd = result["arrays"][0]["log"][-1]["cmd"]
    assert "s3cret" not in log_cmd
    remove = {"arrays": [{"card_id": 1}]}
    remove["preview_hash"] = preview_hash("remove", remove)
    calls2 = _bind(
        monkeypatch,
        [
            ("lscloudcallhome", CLOUD),
            ("lsemailserver", SERVERS),
            ("lsemailuser", USERS),
            ("lssystem", LSYS),
        ],
    )
    removed = server.run_call_home_remove(remove, confirm=True)
    assert removed["ok"] is True
    mutate2 = [c for c in calls2 if c.startswith("svctask")]
    assert mutate2[0] == "svctask stopemail"
    assert any(c.startswith("svctask rmemailuser") for c in mutate2)
    assert mutate2[-1].startswith("svctask rmemailserver")
