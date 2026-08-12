from launchpad.flashsystem_health import analyze_health


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
    assert ios
    assert all(issue["severity"] == "critical" for issue in ios)
    assert any(
        "I/O" in issue["message"] or "I/O card" in issue["message"]
        for issue in ios
    )


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
                    "1::Power supply failure:node1\n"
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
                "output": "id:status\n0:degraded\n",
                "error": None,
            },
        ],
        None,
    )
    messages = {issue["message"] for issue in result["health_issues"]}

    assert "Canister failed" in messages
    assert "Hard drive failed" in messages
