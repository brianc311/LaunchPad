from launchpad.capacity_report import CAPACITY_REPORT_HTML


def test_capacity_report_has_site_select():
    html = CAPACITY_REPORT_HTML
    assert 'id="capacity-site-select"' in html
    assert '<option value="">None</option>' in html
    assert '<label>Site <select id="capacity-site-select">' in html


def test_capacity_site_select_in_hero_actions():
    html = CAPACITY_REPORT_HTML
    hero_start = html.index('<div class="hero-actions no-print">')
    hero_end = html.index("</div>", hero_start)
    hero_actions = html[hero_start:hero_end]
    assert 'id="capacity-site-select"' in hero_actions


def test_capacity_excel_export_passes_card_id():
    html = CAPACITY_REPORT_HTML
    assert "card_id" in html
    assert "capacity-site-select" in html


def test_capacity_report_has_critical_alert_banner():
    html = CAPACITY_REPORT_HTML
    assert 'id="fleet-alerts"' in html
    assert "capacity-alert" in html
    assert "CRITICAL" in html
    assert "capacityIssues" in html
