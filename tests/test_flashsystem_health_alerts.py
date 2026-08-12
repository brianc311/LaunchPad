from launchpad.flashsystem_health import _apply_operator_wording, analyze_health
from launchpad.health_alert_state import collect_critical_candidates, issue_fingerprint


def test_analyze_alerts_uses_description_when_message_empty():
    output = (
        "id:message:description:object_name\n"
        "1::Battery fault:node1\n"
    )
    result = analyze_health(
        "Valparaiso, IN",
        [
            {
                "label": "Health - Alerts",
                "command": "svcinfo lseventlog -alert yes -delim :",
                "output": output,
                "error": None,
            }
        ],
        None,
    )
    assert any("Battery" in i["message"] for i in result["health_issues"])
    assert not any(
        i.get("message") in ("", None)
        for i in result["health_issues"]
        if i.get("category") in ("alert", "nvme", "cpu", "memory")
    )


def test_analyze_drives_offline_is_critical():
    output = (
        "id:status:use\n"
        "0:offline:member\n"
        "1:degraded:member\n"
        "2:online:member\n"
    )
    result = analyze_health(
        "Valparaiso, IN",
        [
            {
                "label": "Health - Drives",
                "command": "svcinfo lsdrive -delim :",
                "output": output,
                "error": None,
            }
        ],
        None,
    )
    drive_issues = [i for i in result["health_issues"] if i.get("category") == "drive"]
    assert len(drive_issues) >= 2
    assert all(i["severity"] == "critical" for i in drive_issues)


def test_lsportfc_offline_is_io_critical():
    output = "id:fc_io_port_id:status\n0:1:offline\n1:2:active\n"
    result = analyze_health(
        "Site",
        [
            {
                "label": "FC - Ports WWPN",
                "command": "svcinfo lsportfc -delim :",
                "output": output,
                "error": None,
            }
        ],
        None,
    )
    ios = [
        issue
        for issue in result["health_issues"]
        if issue.get("category") in ("io", "fc")
    ]
    assert len(ios) == 1
    assert ios[0]["severity"] == "critical"
    assert ios[0]["message"] == "I/O card failed (port 1)"


def test_power_alert_with_offline_canister_wording():
    result = analyze_health(
        "Site",
        [
            {
                "label": "Health - Controllers",
                "command": "svcinfo lsnodecanister -delim :",
                "output": "name:status\nnode1:offline\nnode2:online\n",
                "error": None,
            },
            {
                "label": "Health - Alerts",
                "command": "svcinfo lseventlog -alert yes -delim :",
                "output": (
                    "id:message:description:object_name\n"
                    "1:Canister communication lost:Power supply failure:node1\n"
                ),
                "error": None,
            },
        ],
        None,
    )

    power_issues = [
        issue
        for issue in result["health_issues"]
        if issue["message"] == "Canister lost power"
    ]
    assert power_issues
    assert all(issue["severity"] == "critical" for issue in power_issues)


def test_bad_components_use_operator_wording():
    result = analyze_health(
        "Site",
        [
            {
                "label": "Health - Controllers",
                "command": "svcinfo lsnodecanister -delim :",
                "output": "name:status\nnode1:failed\n",
                "error": None,
            },
            {
                "label": "Health - Drives",
                "command": "svcinfo lsdrive -delim :",
                "output": "id:status\n0:degraded\n1:failed\n",
                "error": None,
            },
        ],
        None,
    )
    messages = {issue["message"] for issue in result["health_issues"]}

    assert "Canister failed" in messages
    assert "Hard drive failed" in messages

    card = {
        "id": 7,
        "name": "Site",
        "error": None,
        "health_issues": result["health_issues"],
    }
    drive_candidates = [
        candidate
        for candidate in collect_critical_candidates(card, monitor_on=True)
        if candidate["category"] == "drive"
    ]
    assert len(drive_candidates) == 2
    assert len({candidate["fingerprint"] for candidate in drive_candidates}) == 2
    assert {
        issue_fingerprint(7, "drive", "Drive 0 is degraded"),
        issue_fingerprint(7, "drive", "Drive 1 is failed"),
    } == {candidate["fingerprint"] for candidate in drive_candidates}


def test_canister_wording_retains_distinct_node_controller_candidates():
    issues = [
        {
            "severity": "critical",
            "category": "controller",
            "message": "Controller node1 is offline",
        },
        {
            "severity": "critical",
            "category": "node",
            "message": "Node node2 is offline",
        },
    ]
    _apply_operator_wording(issues, [])

    candidates = collect_critical_candidates(
        {
            "id": 7,
            "name": "Site",
            "error": None,
            "health_issues": issues,
        },
        monitor_on=True,
    )

    assert [issue["message"] for issue in issues] == [
        "Canister offline",
        "Canister offline",
    ]
    assert {(candidate["category"], candidate["message"]) for candidate in candidates} == {
        ("controller", "Canister offline"),
        ("node", "Canister offline"),
    }
