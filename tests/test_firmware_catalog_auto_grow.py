from launchpad.firmware_catalog import (
    grow_catalog_from_currents,
    insert_version_sorted,
    load_firmware_auto_add,
    save_firmware_auto_add,
    version_sort_key,
)


class _FakeDB:
    def __init__(self):
        self._s = {}

    def get_setting(self, key, default=""):
        return self._s.get(key, default)

    def set_setting(self, key, value):
        self._s[key] = value


def test_insert_version_sorted_middle_start_end():
    assert insert_version_sorted(["8.5.0", "8.6.1"], "8.6.0") == (
        ["8.5.0", "8.6.0", "8.6.1"],
        True,
    )
    assert insert_version_sorted(["8.6.0", "8.6.1"], "8.5.0") == (
        ["8.5.0", "8.6.0", "8.6.1"],
        True,
    )
    assert insert_version_sorted(["8.5.0", "8.6.0"], "8.6.1") == (
        ["8.5.0", "8.6.0", "8.6.1"],
        True,
    )


def test_insert_version_sorted_duplicate_and_blank():
    assert insert_version_sorted(["8.6.0"], "8.6.0") == (["8.6.0"], False)
    assert insert_version_sorted(["8.6.0"], "") == (["8.6.0"], False)
    assert insert_version_sorted(["8.6.0"], "  ") == (["8.6.0"], False)


def test_grow_catalog_from_currents_counts_inserts():
    catalog = {"flashsystem_7300": ["8.5.0", "8.6.1"]}
    updated, n = grow_catalog_from_currents(
        catalog,
        [
            ("flashsystem_7300", "8.6.0"),
            ("flashsystem_7300", "8.6.0"),  # dup in batch
            ("flashsystem_7300", "8.6.1"),  # already present
            ("", "9.0.0"),
            ("flashsystem_7300", ""),
        ],
    )
    assert n == 1
    assert updated["flashsystem_7300"] == ["8.5.0", "8.6.0", "8.6.1"]


def test_auto_add_setting_default_off_and_persist():
    db = _FakeDB()
    assert load_firmware_auto_add(db) is False
    assert save_firmware_auto_add(db, True) is True
    assert load_firmware_auto_add(db) is True
    assert save_firmware_auto_add(db, False) is False
    assert load_firmware_auto_add(db) is False
