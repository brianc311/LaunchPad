from launchpad.capacity_report import CAPACITY_REPORT_HTML


def test_capacity_report_has_site_select():
    html = CAPACITY_REPORT_HTML
    assert 'id="capacity-site-select"' in html
    assert '<option value="">All servers</option>' in html
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


def test_capacity_report_progress_markers():
    html = CAPACITY_REPORT_HTML
    script = html.split("<script>", 1)[1]
    assert 'id="cap-progress-wrap"' in html
    assert 'id="cap-progress-bar"' in html
    assert "function hideProgress()" in script
    assert "progressActive" in script
    assert "Loading servers…" in script or "Loading servers..." in script
    assert " / " in script and " arrays" in script
    assert "refreshAllSequential" in script
    assert "loadCards" in script
    assert '"<div class="' not in script


def test_capacity_refresh_updates_bar_as_site_starts():
    script = CAPACITY_REPORT_HTML.split("<script>", 1)[1]
    refresh_fn = script.split("async function refreshAllSequential()", 1)[1].split(
        "function updatePrintMeta", 1
    )[0]
    assert "progressActive = true" in refresh_fn
    assert "hideProgress()" in refresh_fn
    assert "Refresh complete." in refresh_fn
    assert "card.name" in refresh_fn
    assert "index" in refresh_fn


def test_capacity_load_cards_bar_only_when_cache_empty():
    script = CAPACITY_REPORT_HTML.split("<script>", 1)[1]
    load_fn = script.split("async function loadCards()", 1)[1].split(
        "if (printBtn)", 1
    )[0]
    assert "cardsCache.length" in load_fn
    assert "hideProgress()" in load_fn
    assert "Could not load servers" in load_fn
