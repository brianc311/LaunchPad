from launchpad.health_server import DASHBOARD_HTML


def test_dashboard_has_card_active_issues_markup():
    html = DASHBOARD_HTML
    for text in (
        "Active Issues",
        "card-active-issues",
        "cardActiveIssuesHtml",
        "No active issues.",
        "health_issues",
    ):
        assert text in html
