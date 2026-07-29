from pathlib import Path

from launchpad.firmware_catalog import (
    load_firmware_catalog,
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


def test_save_load_firmware_catalog_round_trip():
    db = _FakeDb()
    catalog = {
        "flashsystem_7300": ["8.5.0", "8.6.0", "8.6.1"],
        "ibm_ds8884": ["7.9"],
    }
    saved = save_firmware_catalog(db, catalog)
    assert saved == catalog
    assert load_firmware_catalog(db) == catalog
