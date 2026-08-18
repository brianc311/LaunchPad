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


def test_contact_apply_succeeds_with_existing_server(monkeypatch):
    server = _server()
    calls = _bind(monkeypatch, [("lscloudcallhome", CLOUD), ("lsemailserver", SERVERS), ("lsemailuser", USERS), ("lssystem", LSYS)])
    payload = {
        "contact": {"name": "SANArch", "reply": "a@b.com", "primary": "", "alternate": ""},
        "arrays": [{"card_id": 1, "location": {"company": "Wags", "street": "", "city": "", "state": "", "postal": "", "country": "", "comment": ""}}],
    }
    preview = server.preview_call_home_apply(payload)
    assert preview["ok"] is True
    assert preview["arrays"][0]["runnable"] is True
    payload["preview_hash"] = preview_hash("apply", payload)
    result = server.run_call_home_apply(payload, confirm=True)
    assert result["ok"] is True
    mutate = [c for c in calls if c.startswith("svctask")]
    assert mutate[0].startswith("svctask chemail")
    assert any(c.startswith("svctask chemail") for c in mutate)
    assert not any("mkemailserver" in c for c in mutate)
    assert not any("chemailserver" in c for c in mutate)


def test_smtp_two_servers_not_runnable_one_server_changes(monkeypatch):
    server = _server()
    two = (
        "id:name:IP_address:port:username\n"
        "0:emailserver0:172.29.62.98:25:avijaytc\n"
        "1:emailserver1:172.29.62.99:25:avijaytc\n"
    )
    calls = _bind(monkeypatch, [("lscloudcallhome", CLOUD), ("lsemailserver", two), ("lsemailuser", USERS), ("lssystem", LSYS)])
    payload = {
        "arrays": [{"card_id": 1, "smtp": {"ip": "10.0.0.1", "port": "25", "username": "u", "password": "s3cret"}}]
    }
    preview = server.preview_call_home_smtp(payload)
    assert preview["ok"] is False
    assert preview["arrays"][0]["runnable"] is False
    payload["preview_hash"] = preview_hash("smtp", payload)
    result = server.run_call_home_smtp(payload, confirm=True)
    assert result["ok"] is False
    assert not any(c.startswith("svctask") for c in calls)

    calls2 = _bind(monkeypatch, [("lscloudcallhome", CLOUD), ("lsemailserver", SERVERS), ("lsemailuser", USERS), ("lssystem", LSYS)])
    one = {
        "arrays": [{"card_id": 1, "smtp": {"ip": "10.0.0.1", "port": "25", "username": "u", "password": "s3cret"}}]
    }
    one["preview_hash"] = preview_hash("smtp", one)
    result2 = server.run_call_home_smtp(one, confirm=True)
    assert result2["ok"] is True
    mutate = [c for c in calls2 if c.startswith("svctask")]
    assert mutate[0].startswith("svctask chemailserver")
    assert not any("mkemailserver" in c for c in mutate)


def test_apply_then_remove_order(monkeypatch):
    server = _server()
    calls = _bind(monkeypatch, [("lscloudcallhome", CLOUD), ("lsemailserver", EMPTY_SERVERS), ("lsemailuser", USERS), ("lssystem", LSYS)])
    payload = {
        "contact": {"name": "SANArch", "reply": "a@b.com", "primary": "", "alternate": ""},
        "arrays": [{"card_id": 1, "location": {"company": "Wags", "street": "", "city": "", "state": "", "postal": "", "country": "", "comment": ""}}],
    }
    payload["preview_hash"] = preview_hash("apply", payload)
    result = server.run_call_home_apply(payload, confirm=True)
    assert result["ok"] is True
    mutate = [c for c in calls if c.startswith("svctask")]
    assert mutate
    assert all(c.startswith("svctask chemail") for c in mutate)
    assert not any("mkemailserver" in c for c in mutate)
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


def test_smtp_chemailserver_in_place(monkeypatch):
    server = _server()
    calls = _bind(monkeypatch, [("lscloudcallhome", CLOUD), ("lsemailserver", SERVERS), ("lsemailuser", USERS), ("lssystem", LSYS)])
    payload = {
        "arrays": [{"card_id": 1, "smtp": {"ip": "10.0.0.1", "port": "25", "username": "u", "password": "s3cret"}}]
    }
    payload["preview_hash"] = preview_hash("smtp", payload)
    result = server.run_call_home_smtp(payload, confirm=True)
    assert result["ok"] is True
    mutate = [c for c in calls if c.startswith("svctask")]
    assert mutate[0].startswith("svctask chemailserver")
    assert "s3cret" in mutate[0]
    assert "s3cret" not in result["arrays"][0]["log"][0]["cmd"]


def test_users_and_cloud_and_hash_isolation(monkeypatch):
    server = _server()
    calls = _bind(monkeypatch, [("lscloudcallhome", CLOUD), ("lsemailserver", SERVERS), ("lsemailuser", USERS), ("lssystem", LSYS)])
    users = {
        "arrays": [{"card_id": 1, "remove_ids": ["0"], "add": [{"address": "ops@wags.com", "user_type": "local"}]}],
        "confirm": True,
        "preview_hash": preview_hash("apply", {"contact": {}, "arrays": [{"card_id": 1, "location": {}}]}),
    }
    bad = server.run_call_home_users(users, confirm=True)
    assert bad["ok"] is False
    assert not any("mkemailuser" in c for c in calls)
    users["preview_hash"] = preview_hash("users", users)
    good = server.run_call_home_users(users, confirm=True)
    assert good["ok"] is True
    mutate = [c for c in calls if c.startswith("svctask")]
    assert mutate[0].startswith("svctask rmemailuser")
    assert any("mkemailuser" in c for c in mutate)
    assert mutate[-1] == "svctask startemail"
    cloud = {
        "arrays": [{"card_id": 1, "requested": "disable"}],
        "confirm": True,
        "preview_hash": preview_hash("cloud", {"arrays": [{"card_id": 1, "requested": "disable"}]}),
    }
    calls2 = _bind(monkeypatch, [("lscloudcallhome", "id:status\n0:active\n"), ("lsemailserver", EMPTY_SERVERS), ("lsemailuser", ""), ("lssystem", LSYS)])
    out = server.run_call_home_cloud(cloud, confirm=True)
    assert out["ok"] is True
    assert any("chcloudcallhome -enable no" in c for c in calls2)
