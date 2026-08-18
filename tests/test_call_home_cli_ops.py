from launchpad.call_home_cli_ops import (
    build_apply_array_steps,
    build_remove_array_steps,
    collect_call_home_state,
    is_email_already_stopped,
    mask_password_in_cmd,
    masked_steps_payload,
    parse_email_servers,
    parse_email_users,
    parse_lssystem_contact_location,
    preview_hash,
    quote_cli_arg,
    run_call_home_steps,
    smtp_add_requested,
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


def test_apply_contact_location_then_mkemailserver():
    steps, warnings, runnable = build_apply_array_steps(
        contact={
            "name": "SANArch",
            "reply": "sanarch@walgreens.com",
            "primary": "224-567-8901",
            "alternate": "",
        },
        location={
            "company": "Walgreens",
            "street": "1805 GREENS RD",
            "city": "Houston",
            "state": "TX",
            "postal": "77032",
            "country": "US",
            "comment": "Walgreens Houston",
        },
        smtp={
            "ip": "172.29.62.98",
            "port": "25",
            "username": "avijaytc",
            "password": "s3cret",
        },
        servers=[],
    )
    assert runnable is True
    assert warnings == []
    assert [s.kind for s in steps] == ["chemail", "chemail", "mkemailserver"]
    assert steps[0].cmd.startswith("svctask chemail")
    assert "-contact" in steps[0].cmd and "-reply" in steps[0].cmd
    assert "-organization" in steps[1].cmd and "-location" in steps[1].cmd
    assert "svctask mkemailserver -ip 172.29.62.98 -port 25" in steps[2].cmd
    assert "-username avijaytc" in steps[2].cmd
    assert "s3cret" in steps[2].cmd
    assert all("mkemailuser" not in s.cmd for s in steps)
    assert all("startemail" not in s.cmd for s in steps)
    assert all("chcloudcallhome" not in s.cmd for s in steps)
    assert all("chsystem" not in s.cmd for s in steps)
    payload = masked_steps_payload(steps)
    assert "s3cret" not in payload[2]["cmd"]
    assert "********" in payload[2]["cmd"]


def test_apply_skips_empty_smtp_and_blocks_existing_server():
    steps, warnings, runnable = build_apply_array_steps(
        contact={"name": "SANArch", "reply": "", "primary": "", "alternate": ""},
        location={
            "company": "",
            "street": "",
            "city": "",
            "state": "",
            "postal": "",
            "country": "",
            "comment": "",
        },
        smtp={"ip": "", "port": "", "username": "", "password": ""},
        servers=[],
    )
    assert runnable is True
    assert [s.kind for s in steps] == ["chemail"]
    assert "mkemailserver" not in steps[0].cmd

    steps2, warnings2, runnable2 = build_apply_array_steps(
        contact={"name": "SANArch", "reply": "", "primary": "", "alternate": ""},
        location={
            "company": "",
            "street": "",
            "city": "",
            "state": "",
            "postal": "",
            "country": "",
            "comment": "",
        },
        smtp={
            "ip": "172.29.62.98",
            "port": "25",
            "username": "avijaytc",
            "password": "s3cret",
        },
        servers=[{"id": "0", "name": "emailserver0", "ip": "1.2.3.4", "port": "25", "username": ""}],
    )
    assert runnable2 is False
    assert steps2 == []
    assert any("already exists" in w.lower() for w in warnings2)

    steps3, warnings3, runnable3 = build_apply_array_steps(
        contact={"name": "", "reply": "", "primary": "", "alternate": ""},
        location={
            "company": "",
            "street": "",
            "city": "",
            "state": "",
            "postal": "",
            "country": "",
            "comment": "",
        },
        smtp={"ip": "", "port": "", "username": "", "password": ""},
        servers=[],
    )
    assert runnable3 is False
    assert any("nothing to apply" in w.lower() for w in warnings3)
    assert smtp_add_requested({"ip": "1.2.3.4", "port": "", "username": "", "password": ""}) is True
    assert smtp_add_requested({"ip": "", "port": "", "username": "", "password": ""}) is False


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


def test_preview_hash_kind_and_password_not_plaintext():
    payload = {
        "contact": {"name": "SANArch", "reply": "a@b.com", "primary": "", "alternate": ""},
        "smtp": {"ip": "1.2.3.4", "port": "25", "username": "u", "password": "s3cret"},
        "arrays": [
            {
                "card_id": 2,
                "location": {
                    "company": "Wags",
                    "street": "",
                    "city": "",
                    "state": "",
                    "postal": "",
                    "country": "",
                    "comment": "",
                },
            }
        ],
    }
    apply_hash = preview_hash("apply", payload)
    other = dict(payload)
    other["smtp"] = dict(payload["smtp"], password="other")
    assert preview_hash("apply", other) != apply_hash
    assert "s3cret" not in apply_hash
    remove_hash = preview_hash("remove", {"arrays": [{"card_id": 2}]})
    assert remove_hash != apply_hash


def test_run_stopemail_already_stopped_is_success():
    def run_cmd(command: str) -> str:
        raise RuntimeError("CMMVC6186E The e-mail service is already stopped.")

    steps, _, _ = build_remove_array_steps(users=[], servers=[])
    result = run_call_home_steps(steps, run_cmd)
    assert result["ok"] is True
    assert result["log"][0]["ok"] is True

    secret_steps, _, _ = build_apply_array_steps(
        contact={"name": "", "reply": "", "primary": "", "alternate": ""},
        location={
            "company": "",
            "street": "",
            "city": "",
            "state": "",
            "postal": "",
            "country": "",
            "comment": "",
        },
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
