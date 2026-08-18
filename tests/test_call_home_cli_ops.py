from launchpad.call_home_cli_ops import (
    build_apply_array_steps,
    build_cloud_array_steps,
    build_remove_array_steps,
    build_smtp_array_steps,
    build_users_array_steps,
    collect_call_home_state,
    is_email_already_started,
    is_email_already_stopped,
    mask_password_in_cmd,
    parse_email_servers,
    parse_email_users,
    parse_lssystem_contact_location,
    preview_hash,
    quote_cli_arg,
    run_call_home_steps,
    sanitize_location_state,
)


SERVER_SAMPLE = """id:name:IP_address:port:username
0:emailserver0:172.29.62.98:25:avijaytc
"""

USER_SAMPLE = """id:name:address:user_type
0:support:callhome0@de.ibm.com:support
1:local:EISSAN-Alerts@walgreens.com:local
"""

LSYSTEM_SAMPLE = """id:0001
name:V5kHOU-g3v1
email_contact:SANArch
email_reply:sanarch@walgreens.com
email_contact_primary:224-567-8901
email_contact_alternate:224-567-8902
email_organization:Walgreens
email_street:1805 GREENS RD
email_city:Houston
email_state:TX
email_zip:77032
email_country:US
email_contact_location:Walgreens Houston 1805 GREENS RD
"""

CLOUD_SAMPLE = """id:status
0:active
"""


def test_quote_cli_arg_quotes_email_and_spaces():
    assert quote_cli_arg("25") == "25"
    assert quote_cli_arg("172.29.62.98") == "172.29.62.98"
    assert quote_cli_arg("sanarch@walgreens.com") == '"sanarch@walgreens.com"'
    assert quote_cli_arg("Walgreens Houston") == '"Walgreens Houston"'


def test_quote_cli_arg_rejects_quote_and_newline():
    try:
        quote_cli_arg('bad"value')
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError")
    try:
        quote_cli_arg("bad\nvalue")
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError")


def test_mask_password_and_already_stopped():
    cmd = 'svctask mkemailserver -ip 1.2.3.4 -port 25 -username avijaytc -password "s3cret"'
    masked = mask_password_in_cmd(cmd)
    assert "s3cret" not in masked
    assert "********" in masked
    assert is_email_already_stopped("CMMVC6186E The e-mail service is already stopped.")
    assert not is_email_already_stopped("CMMVC0000E some other failure")


def test_parse_servers_users_and_lssystem():
    servers = parse_email_servers(SERVER_SAMPLE)
    assert servers[0]["ip"] == "172.29.62.98"
    assert servers[0]["port"] == "25"
    assert servers[0]["username"] == "avijaytc"
    users = parse_email_users(USER_SAMPLE)
    assert users[0]["address"] == "callhome0@de.ibm.com"
    assert users[1]["user_type"] == "local"
    contact, location = parse_lssystem_contact_location(LSYSTEM_SAMPLE)
    assert contact["name"] == "SANArch"
    assert contact["reply"] == "sanarch@walgreens.com"
    assert location["company"] == "Walgreens"
    assert location["comment"] == "Walgreens Houston 1805 GREENS RD"
    assert location["postal"] == "77032"


def test_collect_uses_four_commands():
    calls: list[str] = []

    def run_cmd(command: str) -> str:
        calls.append(command)
        if "lscloudcallhome" in command:
            return CLOUD_SAMPLE
        if "lsemailserver" in command:
            return SERVER_SAMPLE
        if "lsemailuser" in command:
            return USER_SAMPLE
        if "lssystem" in command:
            return LSYSTEM_SAMPLE
        raise AssertionError(command)

    state = collect_call_home_state(run_cmd)
    assert state["ok"] is True
    assert state["cloud_status"].lower() == "active"
    assert "172.29.62.98:25" in state["smtp_summary"]
    assert any("lscloudcallhome" in c for c in calls)
    assert any("lsemailserver" in c for c in calls)
    assert any("lsemailuser" in c for c in calls)
    assert any(c.strip() == "svcinfo lssystem" or c.startswith("svcinfo lssystem") for c in calls)
    assert not any("lsvolumegroupmember" in c for c in calls)
    assert len([c for c in calls if c.startswith("svcinfo ")]) <= 8


def test_sanitize_running_stopped_state():
    assert sanitize_location_state({"state": "running"})["state"] == ""
    assert sanitize_location_state({"state": "STOPPED"})["state"] == ""
    assert sanitize_location_state({"state": "SC"})["state"] == "SC"
    text = "email_state:running\nemail_city:Williamston\n"
    _contact, location = parse_lssystem_contact_location(text)
    assert location["state"] == ""
    assert location["city"] == "Williamston"


def test_apply_contact_location_only():
    steps, warnings, runnable = build_apply_array_steps(
        contact={"name": "SANArch", "reply": "a@b.com", "primary": "", "alternate": ""},
        location={
            "company": "Walgreens", "street": "", "city": "", "state": "",
            "postal": "", "country": "", "comment": "",
        },
    )
    assert runnable is True
    assert warnings == []
    assert [s.kind for s in steps] == ["chemail", "chemail"]
    assert all("mkemailserver" not in s.cmd for s in steps)
    assert all("chemailserver" not in s.cmd for s in steps)
    empty, warns, ok = build_apply_array_steps(
        contact={"name": "", "reply": "", "primary": "", "alternate": ""},
        location={
            "company": "", "street": "", "city": "", "state": "",
            "postal": "", "country": "", "comment": "",
        },
    )
    assert ok is False
    assert empty == []
    assert any("nothing to apply" in w.lower() for w in warns)


def test_smtp_mk_vs_chemail_vs_two_servers():
    add, _, ok = build_smtp_array_steps(
        smtp={"ip": "172.29.62.98", "port": "25", "username": "u", "password": "s3cret"},
        servers=[],
    )
    assert ok is True
    assert add[0].kind == "mkemailserver"
    assert "s3cret" in add[0].cmd

    change, _, ok2 = build_smtp_array_steps(
        smtp={"ip": "10.0.0.1", "port": "25", "username": "u", "password": ""},
        servers=[{"id": "0", "name": "emailserver0", "ip": "172.29.62.98", "port": "25", "username": "u"}],
    )
    assert ok2 is True
    assert change[0].kind == "chemailserver"
    assert change[0].cmd.startswith("svctask chemailserver 0")
    assert "-ip" in change[0].cmd and "-port" in change[0].cmd
    assert "-password" not in change[0].cmd

    blocked, warns, ok3 = build_smtp_array_steps(
        smtp={"ip": "10.0.0.1", "port": "25", "username": "", "password": ""},
        servers=[
            {"id": "0", "name": "emailserver0", "ip": "1.2.3.4", "port": "25", "username": ""},
            {"id": "1", "name": "emailserver1", "ip": "1.2.3.5", "port": "25", "username": ""},
        ],
    )
    assert ok3 is False
    assert blocked == []
    assert any("more than one" in w.lower() for w in warns)

    skip, _, ok4 = build_smtp_array_steps(
        smtp={"ip": "", "port": "", "username": "", "password": ""},
        servers=[],
    )
    assert ok4 is False
    assert skip == []

    need_pw, pw_warns, ok5 = build_smtp_array_steps(
        smtp={"ip": "1.2.3.4", "port": "25", "username": "newuser", "password": ""},
        servers=[{"id": "0", "name": "emailserver0", "ip": "1.2.3.4", "port": "25", "username": "old"}],
    )
    assert ok5 is False
    assert any("password" in w.lower() for w in pw_warns)


def test_users_remove_then_add_then_startemail():
    steps, _, ok = build_users_array_steps(
        existing=[
            {"id": "0", "name": "support", "address": "callhome0@de.ibm.com", "user_type": "support"},
            {"id": "1", "name": "local", "address": "old@wags.com", "user_type": "local"},
        ],
        remove_ids=["1"],
        add=[{"address": "EISSAN-Alerts@walgreens.com", "user_type": "local"}],
    )
    assert ok is True
    assert [s.kind for s in steps] == ["rmemailuser", "mkemailuser", "startemail"]
    assert steps[0].cmd == "svctask rmemailuser 1"
    assert "mkemailuser" in steps[1].cmd
    assert "-usertype local" in steps[1].cmd
    assert "EISSAN-Alerts@walgreens.com" in steps[1].cmd
    assert steps[2].cmd == "svctask startemail"

    none, warns, ok2 = build_users_array_steps(existing=[], remove_ids=[], add=[])
    assert ok2 is False
    assert none == []

    dup, dup_warns, ok3 = build_users_array_steps(
        existing=[{"id": "0", "name": "support", "address": "callhome0@de.ibm.com", "user_type": "support"}],
        remove_ids=[],
        add=[{"address": "callhome0@de.ibm.com", "user_type": "support"}],
    )
    assert ok3 is False
    assert any("duplicate" in w.lower() for w in dup_warns)

    bad, bad_warns, ok4 = build_users_array_steps(
        existing=[],
        remove_ids=[],
        add=[{"address": "a@b.com", "user_type": "inventory"}],
    )
    assert ok4 is False
    assert any("usertype" in w.lower() or "user type" in w.lower() for w in bad_warns)

    remove_only, _, ok5 = build_users_array_steps(
        existing=[{"id": "0", "name": "support", "address": "a@b.com", "user_type": "support"}],
        remove_ids=["0"],
        add=[],
    )
    assert ok5 is True
    assert [s.kind for s in remove_only] == ["rmemailuser"]


def test_cloud_only_when_changed():
    steps, _, ok = build_cloud_array_steps(requested="enable", configured="no")
    assert ok is True
    assert steps[0].cmd == "svctask chcloudcallhome -enable yes"
    steps2, _, ok2 = build_cloud_array_steps(requested="disable", configured="yes")
    assert ok2 is True
    assert steps2[0].cmd == "svctask chcloudcallhome -enable no"
    skip, _, ok3 = build_cloud_array_steps(requested="enable", configured="yes")
    assert ok3 is False
    assert skip == []


def test_preview_hash_isolates_kinds_and_hides_password():
    smtp_payload = {
        "arrays": [{"card_id": 1, "smtp": {"ip": "1.2.3.4", "port": "25", "username": "u", "password": "s3cret"}}]
    }
    h_smtp = preview_hash("smtp", smtp_payload)
    other = {"arrays": [{"card_id": 1, "smtp": {"ip": "1.2.3.4", "port": "25", "username": "u", "password": "other"}}]}
    assert preview_hash("smtp", other) != h_smtp
    assert "s3cret" not in h_smtp
    apply_payload = {
        "contact": {"name": "A", "reply": "", "primary": "", "alternate": ""},
        "arrays": [{"card_id": 1, "location": {
            "company": "", "street": "", "city": "", "state": "", "postal": "", "country": "", "comment": "",
        }}],
    }
    assert preview_hash("apply", apply_payload) != h_smtp
    assert preview_hash("users", {"arrays": [{"card_id": 1, "remove_ids": ["0"], "add": []}]}) != h_smtp
    assert preview_hash("cloud", {"arrays": [{"card_id": 1, "requested": "enable"}]}) != h_smtp
    assert preview_hash("remove", {"arrays": [{"card_id": 1}]}) != h_smtp


def test_startemail_already_started_is_success():
    assert is_email_already_started("CMMVC6187E The e-mail service is already started.")
    steps, _, _ = build_users_array_steps(
        existing=[],
        remove_ids=[],
        add=[{"address": "a@b.com", "user_type": "local"}],
    )

    def run_cmd(command: str) -> str:
        if "startemail" in command:
            raise RuntimeError("CMMVC6187E The e-mail service is already started.")
        return "ok"

    result = run_call_home_steps(steps, run_cmd)
    assert result["ok"] is True
    assert result["log"][-1]["ok"] is True


def test_remove_order_stop_users_servers():
    steps, warnings, runnable = build_remove_array_steps(
        users=[
            {"id": "0", "name": "support", "address": "callhome0@de.ibm.com", "user_type": "support"},
            {"id": "1", "name": "local", "address": "a@b.com", "user_type": "local"},
        ],
        servers=[{"id": "0", "name": "emailserver0", "ip": "1.2.3.4", "port": "25", "username": ""}],
    )
    assert runnable is True
    assert [s.kind for s in steps] == [
        "stopemail",
        "rmemailuser",
        "rmemailuser",
        "rmemailserver",
    ]
    assert steps[0].cmd == "svctask stopemail"
    assert steps[1].cmd == "svctask rmemailuser 0"
    assert steps[3].cmd == "svctask rmemailserver 0"

    empty_steps, _, empty_ok = build_remove_array_steps(users=[], servers=[])
    assert empty_ok is True
    assert [s.kind for s in empty_steps] == ["stopemail"]


def test_run_stopemail_already_stopped_is_success():
    def run_cmd(command: str) -> str:
        raise RuntimeError("CMMVC6186E The e-mail service is already stopped.")

    steps, _, _ = build_remove_array_steps(users=[], servers=[])
    result = run_call_home_steps(steps, run_cmd)
    assert result["ok"] is True
    assert result["log"][0]["ok"] is True

    secret_steps, _, _ = build_smtp_array_steps(
        smtp={"ip": "1.2.3.4", "port": "25", "username": "u", "password": "s3cret"},
        servers=[],
    )
    logged: list[str] = []

    def run_smtp(command: str) -> str:
        logged.append(command)
        return "ok"

    result2 = run_call_home_steps(secret_steps, run_smtp)
    assert "s3cret" in logged[0]
    assert "s3cret" not in result2["log"][0]["cmd"]
    assert "********" in result2["log"][0]["cmd"]
