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
