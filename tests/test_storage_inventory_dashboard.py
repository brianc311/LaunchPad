from pathlib import Path


def test_dashboard_has_storage_inventory_button():
    text = Path("launchpad/ui/dashboard_view.py").read_text(encoding="utf-8")
    assert '("Storage Inventory"' in text or '(\"Storage Inventory\"' in text
    assert "_open_storage_inventory" in text
