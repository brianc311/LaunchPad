from launchpad.fc_wwpn_export import cards_for_fc_export
from launchpad.snapshot_schedule_export import filter_cards_by_groups, site_group


def test_site_group_classifies_wag_names():
    assert site_group({"name": "WAG1-Anderson", "category": "", "host": "", "model": "", "device_profile": ""}) == "wag1"
    assert site_group({"name": "Lab", "category": "WAG2", "host": "", "model": "", "device_profile": ""}) == "wag2"
    assert site_group({"name": "Moreno", "category": "CA", "host": "", "model": "", "device_profile": ""}) == "other"


def test_filter_cards_by_groups_wag1_only():
    cards = [
        {"name": "WAG1-A", "category": "", "host": "", "model": "", "device_profile": ""},
        {"name": "WAG2-B", "category": "", "host": "", "model": "", "device_profile": ""},
        {"name": "Other-C", "category": "Lab", "host": "", "model": "", "device_profile": ""},
    ]
    kept = filter_cards_by_groups(cards, {"wag1"})
    assert [c["name"] for c in kept] == ["WAG1-A"]


def test_filter_cards_empty_groups_yields_empty():
    cards = [{"name": "WAG1-A", "category": "", "host": "", "model": "", "device_profile": ""}]
    assert filter_cards_by_groups(cards, set()) == []


def test_cards_for_fc_export_wag1_only():
    cards = [
        {"name": "WAG1-A", "category": "", "host": "", "model": "", "device_profile": ""},
        {"name": "WAG2-B", "category": "", "host": "", "model": "", "device_profile": ""},
    ]
    kept = cards_for_fc_export(cards, {"wag1"})
    assert [c["name"] for c in kept] == ["WAG1-A"]


def test_cards_for_fc_export_all_groups_keeps_all():
    cards = [
        {"name": "WAG1-A", "category": "", "host": "", "model": "", "device_profile": ""},
        {"name": "WAG2-B", "category": "", "host": "", "model": "", "device_profile": ""},
        {"name": "Other-C", "category": "Lab", "host": "", "model": "", "device_profile": ""},
    ]
    kept = cards_for_fc_export(cards, {"wag1", "wag2", "other"})
    assert [c["name"] for c in kept] == ["WAG1-A", "WAG2-B", "Other-C"]
