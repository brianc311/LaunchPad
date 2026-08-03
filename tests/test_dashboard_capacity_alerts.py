from launchpad.dashboard_capacity_alerts import (
    card_capacity_severity,
    filter_capacity_issues,
    fleet_capacity_alert_summary,
    is_capacity_issue,
)


def test_is_capacity_issue_by_category_and_message():
    assert is_capacity_issue({"category": "capacity", "message": "x", "severity": "warn"})
    assert is_capacity_issue(
        {"category": "other", "message": "Pool CPG_OS01 is 82.3% full", "severity": "warn"}
    )
    assert is_capacity_issue(
        {"category": "other", "message": "Running at 91.0% capacity", "severity": "critical"}
    )
    assert not is_capacity_issue(
        {"category": "node", "message": "Node 1 offline", "severity": "critical"}
    )


def test_card_severity_critical_wins_and_gates():
    issues = [
        {"category": "capacity", "severity": "warn", "message": "Pool A is 82.0% full"},
        {"category": "capacity", "severity": "critical", "message": "Pool B is 98.0% full"},
    ]
    assert card_capacity_severity(issues, monitor_on=True, updated_at="2026-08-03") == "critical"
    assert card_capacity_severity(issues, monitor_on=False, updated_at="2026-08-03") is None
    assert card_capacity_severity(issues, monitor_on=True, updated_at=None) is None
    assert (
        card_capacity_severity(
            [{"category": "capacity", "severity": "warn", "message": "Pool A is 82.0% full"}],
            monitor_on=True,
            updated_at="2026-08-03",
        )
        == "warn"
    )


def test_fleet_summary_counts_sites_not_issues():
    cards = [
        {
            "id": 1,
            "name": "A",
            "updated_at": "t",
            "health_issues": [
                {"category": "capacity", "severity": "critical", "message": "Pool X is 99% full"},
                {"category": "capacity", "severity": "warn", "message": "Pool Y is 81% full"},
            ],
        },
        {
            "id": 2,
            "name": "B",
            "updated_at": "t",
            "health_issues": [
                {"category": "capacity", "severity": "warn", "message": "Pool Z is 82% full"},
            ],
        },
        {
            "id": 3,
            "name": "C",
            "updated_at": "t",
            "health_issues": [
                {"category": "capacity", "severity": "warn", "message": "Pool W is 85% full"},
            ],
        },
    ]
    summary = fleet_capacity_alert_summary(cards, {1: True, 2: True, 3: False})
    assert summary["critical_sites"] == 1
    assert summary["warn_sites"] == 1  # id 2 only; id 3 monitor off
    assert summary["has_alert"] is True
    assert "CRITICAL" in summary["label"]
    assert "WARNING" in summary["label"]


def test_fleet_summary_hidden_when_empty():
    summary = fleet_capacity_alert_summary(
        [{"id": 1, "updated_at": "t", "health_issues": []}],
        {1: True},
    )
    assert summary["has_alert"] is False
    assert summary["label"] == ""
