from launchpad.health_server import DASHBOARD_HTML


def test_dashboard_has_health_site_select():
    html = DASHBOARD_HTML
    assert 'id="health-site-select"' in html
    assert '<option value="">None</option>' in html
    assert '<label>Site <select id="health-site-select">' in html


def test_dashboard_site_select_near_filter_bar():
    html = DASHBOARD_HTML
    filter_bar_start = html.index('<div class="filter-bar no-print">')
    filter_bar_end = html.index("</div>", filter_bar_start)
    filter_bar = html[filter_bar_start:filter_bar_end]
    assert 'id="health-site-select"' in filter_bar
