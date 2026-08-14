from launchpad.storage_inventory_page import STORAGE_INVENTORY_HTML, STORAGE_INVENTORY_PATH


def test_storage_inventory_script_does_not_break_on_class_quotes():
    script = STORAGE_INVENTORY_HTML.split("<script>", 1)[1]
    assert '"<tr class="' not in script
    assert '"<details class="' not in script
    assert "refreshLive" in script
    assert "loadCache" in script
    assert "renderSites" in script
    assert "siteStatus" in script


def test_storage_inventory_loads_sites_from_cards():
    html = STORAGE_INVENTORY_HTML
    assert "/api/cards" in html
    assert "loadSiteOptions" in html


def test_storage_inventory_page_markers():
    assert STORAGE_INVENTORY_PATH == "/storage-inventory"
    html = STORAGE_INVENTORY_HTML
    assert "Storage Inventory" in html
    assert 'id="site-filter"' in html or 'id="siteFilter"' in html
    assert "Refresh live" in html
    assert "Export Excel" in html
    assert "/api/storage-inventory/live" in html
    assert "/api/storage-inventory/export" in html
    assert "Total Devices" in html
    assert "Devices with Issues" in html
    assert "{{APP_VERSION}}" in html
    assert 'id="si-sites"' in html
    assert "site-red" in html
    assert "site-orange" in html
    assert "site-green" in html
    assert "site-card" in html
    assert "(no site)" in html
    assert "Issues / Notes (" in html
    heading = html.split("<script>", 1)[0]
    assert ">Issues Summary<" not in heading
    assert 'id="si-issues-body"' not in html
    assert 'id="si-inventory-body"' not in html


def test_storage_inventory_sites_and_issues_start_collapsed():
    script = STORAGE_INVENTORY_HTML.split("<script>", 1)[1]
    assert "<details open" not in script
    assert 'open="' not in script


def test_storage_inventory_age_toggle_and_progress_markers():
    html = STORAGE_INVENTORY_HTML
    heading = html.split("<script>", 1)[0]
    script = html.split("<script>", 1)[1]
    assert "Recent" in heading
    assert "Older" in heading
    assert ">All<" in heading or "All</" in heading
    assert 'id="si-age-recent"' in html
    assert 'id="si-age-older"' in html
    assert 'id="si-age-all"' in html
    assert 'id="si-progress-wrap"' in html
    assert 'id="si-progress-bar"' in html
    assert "/api/storage-inventory/progress" in script
    assert "issues_recent" in script
    assert "issues_older" in script
    assert 'ageMode = "recent"' in script or "ageMode = 'recent'" in script
    assert '"<div class="' not in script
