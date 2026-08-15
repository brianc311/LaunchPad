from launchpad.capacity_report import CAPACITY_REPORT_HTML


def test_capacity_report_has_site_select():
    html = CAPACITY_REPORT_HTML
    assert 'id="capacity-site-select"' in html
    assert '<option value="">All servers</option>' in html
    assert '<label>Site <select id="capacity-site-select">' in html


def _hero_actions_block(html: str) -> str:
    marker = '<div class="hero-actions no-print">'
    start = html.index(marker)
    depth = 0
    i = start
    while i < len(html):
        open_at = html.find("<div", i)
        close_at = html.find("</div>", i)
        if close_at < 0:
            raise AssertionError("hero-actions is missing a closing </div>")
        if open_at != -1 and open_at < close_at:
            depth += 1
            i = open_at + 4
        else:
            depth -= 1
            i = close_at + len("</div>")
            if depth == 0:
                return html[start:i]
    raise AssertionError("hero-actions is unclosed")


def test_capacity_site_select_in_hero_actions():
    html = CAPACITY_REPORT_HTML
    hero_actions = _hero_actions_block(html)
    assert 'id="capacity-site-select"' in hero_actions
    select_pos = html.index('id="capacity-site-select"')
    wrap_pos = html.index('id="cap-progress-wrap"')
    print_pos = html.index('id="print-meta"')
    assert select_pos < wrap_pos < print_pos
    assert 'id="cap-progress-wrap"' not in hero_actions


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
    hide_fn = script.split("function hideProgress()", 1)[1].split(
        "function applyProgress", 1
    )[0]
    assert "cardsCache.length" in load_fn
    assert "cardsLoadedOnce" in load_fn
    assert "hideProgress()" in load_fn
    assert "Could not load servers" in load_fn
    assert "Loading servers…" in load_fn or "Loading servers..." in load_fn
    assert "refreshStatusEl" not in hide_fn
