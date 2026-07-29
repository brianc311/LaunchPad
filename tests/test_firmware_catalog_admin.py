from pathlib import Path

from launchpad.firmware_catalog import (
    load_firmware_catalog,
    merge_catalog_for_admin_save,
    save_firmware_catalog,
)


class _FakeDb:
    def __init__(self):
        self.values = {}

    def get_setting(self, key, default=""):
        return self.values.get(key, default)

    def set_setting(self, key, value):
        self.values[key] = value


def test_admin_view_has_firmware_catalog_tab():
    source = (
        Path(__file__).parents[1] / "launchpad" / "ui" / "admin_view.py"
    ).read_text(encoding="utf-8")
    assert 'self.tabs.add("Firmware catalog")' in source or '"Firmware catalog"' in source
    assert "save_firmware_catalog" in source
    assert "load_firmware_catalog" in source
    assert "_build_firmware_catalog_panel" in source


def test_admin_firmware_auto_add_checkbox():
    source = (
        Path(__file__).parents[1] / "launchpad" / "ui" / "admin_view.py"
    ).read_text(encoding="utf-8")
    assert "Auto-add firmware from live scans" in source
    assert "save_firmware_auto_add" in source
    assert "load_firmware_auto_add" in source
    assert "When on, Refresh live inserts unseen Current" in source


def test_save_load_firmware_catalog_round_trip():
    db = _FakeDb()
    catalog = {
        "flashsystem_7300": ["8.5.0", "8.6.0", "8.6.1"],
        "ibm_ds8884": ["7.9"],
    }
    saved = save_firmware_catalog(db, catalog)
    assert saved == catalog
    assert load_firmware_catalog(db) == catalog


def test_merge_catalog_for_admin_save_keeps_db_auto_grow_and_current_edits():
    """Stale in-memory other profiles must not wipe DB auto-grown versions."""
    stale_memory = {
        "flashsystem_7300": ["8.5.0"],
        "ibm_ds8884": ["7.9"],
    }
    db_after_grow = {
        "flashsystem_7300": ["8.5.0", "8.6.0"],
        "ibm_ds8884": ["7.9", "7.9.1"],
    }
    current_ui = ["8.5.0", "8.5.1"]  # unsaved edit on current profile
    merged = merge_catalog_for_admin_save(db_after_grow, "flashsystem_7300", current_ui)
    assert merged["flashsystem_7300"] == current_ui
    assert merged["ibm_ds8884"] == ["7.9", "7.9.1"]
    # Stale memory must not win for non-current profiles
    assert merged["ibm_ds8884"] != stale_memory["ibm_ds8884"]


def test_admin_save_reloads_db_before_write():
    source = (
        Path(__file__).parents[1] / "launchpad" / "ui" / "admin_view.py"
    ).read_text(encoding="utf-8")
    assert "merge_catalog_for_admin_save" in source
    assert "load_firmware_catalog(self.db)" in source
    save_idx = source.index("def _firmware_catalog_save")
    save_body = source[save_idx : save_idx + 800]
    assert "merge_catalog_for_admin_save" in save_body
    assert "load_firmware_catalog(self.db)" in save_body
