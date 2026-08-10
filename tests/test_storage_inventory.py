from launchpad.storage_inventory import (
    build_issues_notes,
    format_phone_home_cell,
    format_smtp_cell,
    inventory_commands_for_profile,
    inventory_totals,
    parse_svc_lsemailserver,
    parse_svc_lsrcrelationship,
    parse_svc_lssystem_identity,
    row_has_issues,
)


def test_inventory_commands_svc_includes_smtp_and_rcrelationship():
    cmds = inventory_commands_for_profile("flashsystem_7200")
    assert cmds["smtp"] == ["lsemailserver -delim :"]
    assert cmds["data_protection"] == ["lsrcrelationship -delim :"]
    assert cmds["call_home"] == ["lscloudcallhome -delim :"]


def test_inventory_commands_hpe_smtp_empty_call_home_empty():
    cmds = inventory_commands_for_profile("hpe_3par_8400")
    assert cmds["smtp"] == []
    assert cmds["call_home"] == []
    assert cmds["data_protection"] == ["showrcopy"]


def test_parse_svc_identity_and_smtp_and_rcrelationship():
    model, serial = parse_svc_lssystem_identity(
        "id:78E31NF\nname:v7kand-g3v1\nproduct_name:IBM FlashSystem 7200\n"
    )
    assert model == "IBM FlashSystem 7200"
    assert serial == "78E31NF"
    cfg, status, details = parse_svc_lsemailserver(
        "id:name:IP_address:port\n0:smtp1:172.29.62.98:25\n"
    )
    assert cfg == "yes"
    assert "172.29.62.98" in details
    cfg2, _, details2 = parse_svc_lsemailserver("id:name:IP_address:port\n")
    assert cfg2 == "no"
    assert "Not configured" in details2
    yes_cfg, _, _ = parse_svc_lsrcrelationship(
        "id:name:master_cluster_id:master_cluster_name\n0:rel1:1:clusterA\n"
    )
    assert yes_cfg == "yes"
    no_cfg, _, _ = parse_svc_lsrcrelationship(
        "id:name:master_cluster_id:master_cluster_name\n"
    )
    assert no_cfg == "no"


def test_issues_notes_and_totals():
    notes = build_issues_notes(
        phone_configured="no",
        data_protection_configured="no",
        smtp_configured="no",
        dns_configured="yes",
        ntp_configured="no",
        health_issues=[{"message": "Running at 91.0% capacity"}],
        extra_errors=[],
    )
    assert "Phone Home not configured" in notes
    assert "Data Protection not configured" in notes
    assert "SMTP not configured" in notes
    assert "NTP not configured" in notes
    assert "Running at 91.0% capacity" in notes
    assert format_phone_home_cell(configured="no", details="", vendor="IBM") == (
        "No — Not configured"
    )
    assert format_smtp_cell(configured="yes", details="172.29.62.98") == "172.29.62.98"
    rows = [
        {"issues": ""},
        {"issues": notes},
    ]
    assert row_has_issues(rows[1]) is True
    assert inventory_totals(rows) == {"total_devices": 2, "devices_with_issues": 1}
