from launchpad.lun_builder import LUN_BUILDER_HTML


def test_lun_builder_offline_inventory_markers():
    assert 'id="view-mode-plan"' in LUN_BUILDER_HTML
    assert 'id="view-mode-inventory"' in LUN_BUILDER_HTML
    assert 'id="inventory-banner"' in LUN_BUILDER_HTML
    assert "/api/lun-offline-inventory" in LUN_BUILDER_HTML
    assert "Offline copy · last updated" in LUN_BUILDER_HTML
    assert "Online · last updated" in LUN_BUILDER_HTML
    assert "Inventory · Updated" in LUN_BUILDER_HTML
    assert "inventory only" in LUN_BUILDER_HTML
