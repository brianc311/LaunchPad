from launchpad.capacity_export import (
    card_ids_included_for_export,
    keep_inventory_row,
)


def test_include_off_false_keeps_only_monitor_on():
    ids = card_ids_included_for_export(
        [1, 2, 3],
        include_monitor_off=False,
        monitor_enabled={1: True, 2: False},
    )
    assert ids == frozenset({1})


def test_include_off_true_keeps_all_ids():
    ids = card_ids_included_for_export(
        [1, 2],
        include_monitor_off=True,
        monitor_enabled={1: False, 2: False},
    )
    assert ids == frozenset({1, 2})


def test_missing_monitor_key_treated_as_off():
    ids = card_ids_included_for_export(
        [9],
        include_monitor_off=False,
        monitor_enabled={},
    )
    assert ids == frozenset()


def test_keep_inventory_row_rules():
    included = frozenset({5})
    assert keep_inventory_row(
        matched_card_id=5,
        included_card_ids=included,
        include_monitor_off=False,
    )
    assert not keep_inventory_row(
        matched_card_id=6,
        included_card_ids=included,
        include_monitor_off=False,
    )
    assert not keep_inventory_row(
        matched_card_id=None,
        included_card_ids=included,
        include_monitor_off=False,
    )
    assert keep_inventory_row(
        matched_card_id=None,
        included_card_ids=included,
        include_monitor_off=True,
    )
