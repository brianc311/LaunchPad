from launchpad.site_lookup import SITE_LOOKUP_HTML, SITE_LOOKUP_PATH


def test_site_lookup_path_and_markers():
    assert SITE_LOOKUP_PATH == "/site-lookup"
    html = SITE_LOOKUP_HTML
    assert "Site Lookup" in html
    assert "/api/cards" in html
    assert "/api/site-lookup/cache?card_id=" in html
    assert "/api/site-lookup/refresh" in html
    assert "Live Refresh" in html
    for label in ("Hosts", "Volumes", "Consistency Groups", "Policy", "Pools", "CPGs"):
        assert label in html
    assert "isHpeProfile" in html
    assert "poolLabel" in html


def test_site_lookup_policy_tab_and_empty_copy():
    html = SITE_LOOKUP_HTML
    assert 'tabs.push(["policies", "Policy"])' in html
    assert "</b>Policies</div>" in html
    assert "No snapshot policies on this array" in html
    assert "snapshot_policies_available" in html
    assert "function renderPolicies" in html
    assert "<th>Name</th><th>Schedule</th><th>Retention</th>" in html
    render = html.split("function renderPayload() {", 1)[1].split(
        "async function selectCard", 1
    )[0]
    assert render.find('["consistency_groups", "Consistency Groups"]') < render.find(
        '["policies", "Policy"]'
    )
    assert render.find('["policies", "Policy"]') < render.find('["pools", poolsName]')
    assert "const showPolicies = profileSupportsConsistencyGroups(card);" in render
    assert "snapshot_policies_available: profileSupportsConsistencyGroups(card)" in html


def test_site_lookup_page_contracts():
    html = SITE_LOOKUP_HTML
    assert "{{APP_VERSION}}" in html
    assert "Not available for this profile" in html
    assert "No rows" in html
    assert 'method: "POST"' in html
    assert "refreshBtn.disabled = true" in html
    assert "Last updated:" in html
    assert "Offline" in html
    assert "Offline LUN" in html
    assert "sourceBadge" in html
    assert "fc_hosts" in html
    assert "fc_mappings" in html
    assert "V7KTMP-G2V1" not in html


def test_site_lookup_format_bytes_marks_unknown_sizes():
    format_bytes = SITE_LOOKUP_HTML.split("function formatBytes(n) {", 1)[1].split(
        "function renderPools", 1
    )[0]

    assert "const bytes = numberValue(n);" in format_bytes
    assert 'if (bytes == null) return "—";' in format_bytes


def test_consistency_groups_are_rendered_regardless_of_device_profile():
    render_function = SITE_LOOKUP_HTML.split(
        "function renderConsistencyGroups(data) {", 1
    )[1].split("function numberValue", 1)[0]

    assert "consistency_groups_available" not in render_function
    assert "const groups = data.consistency_groups" in render_function


def test_inventory_empty_states_follow_profile_support():
    html = SITE_LOOKUP_HTML
    hosts_function = html.split("function renderHosts(data) {", 1)[1].split(
        "function renderVolumes", 1
    )[0]
    volumes_function = html.split("function renderVolumes(data) {", 1)[1].split(
        "function renderConsistencyGroups", 1
    )[0]
    groups_function = html.split(
        "function renderConsistencyGroups(data) {", 1
    )[1].split("function numberValue", 1)[0]
    pools_function = html.split("function renderPools(data) {", 1)[1].split(
        "function statusText", 1
    )[0]

    for inventory_function in (hosts_function, volumes_function, groups_function):
        assert "profileSupportsConsistencyGroups(data.card)" in inventory_function
    assert "emptyMessage(false)" in pools_function


def test_live_refresh_discards_stale_responses_via_generation_guard():
    html = SITE_LOOKUP_HTML

    assert "let refreshGeneration = 0;" in html
    assert "refreshGeneration += 1;" in html
    assert "const gen = refreshGeneration;" in html
    assert "if (gen !== refreshGeneration) return;" in html
    assert "const requestedCardId = currentCard.id;" in html
    assert "refreshingCardIds.add(requestedCardId);" in html
    assert "refreshingCardIds.has(currentCard.id)" in html


def test_site_lookup_export_controls():
    html = SITE_LOOKUP_HTML
    assert "Export Excel" in html
    assert "Export CSV" in html
    assert "Include Offline sheet" in html
    assert "/api/site-lookup/export" in html
    assert "include_offline" in html
    assert "exportExcelBtn.disabled" in html or "export-excel-btn" in html
