from launchpad.storage_inventory_page import STORAGE_INVENTORY_HTML, STORAGE_INVENTORY_PATH


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
    assert "Issues Summary" in html
    assert "{{APP_VERSION}}" in html
