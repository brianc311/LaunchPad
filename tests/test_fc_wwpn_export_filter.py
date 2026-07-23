from launchpad.fc_wwpn_export import (
    DEFAULT_FC_EXPORT_GROUPS,
    cards_for_fc_export,
    filter_cards_for_fc_export,
    parse_fc_export_groups,
)


def _card(cid: int, name: str) -> dict:
    return {"id": cid, "name": name, "device_profile": "flashsystem_7200", "fc_available": True}


def test_filter_cards_for_fc_export_none_returns_all():
    cards = [_card(1, "Hartford, CT"), _card(2, "Anderson, SC")]
    assert filter_cards_for_fc_export(cards) == cards
    assert filter_cards_for_fc_export(cards, card_id="", card_name="") == cards


def test_filter_cards_for_fc_export_by_card_id():
    cards = [_card(1, "Hartford, CT"), _card(2, "Anderson, SC")]
    out = filter_cards_for_fc_export(cards, card_id="2")
    assert [c["id"] for c in out] == [2]


def test_filter_cards_for_fc_export_by_card_name_case_insensitive():
    cards = [_card(1, "Hartford, CT"), _card(2, "Anderson, SC")]
    out = filter_cards_for_fc_export(cards, card_name="hartford, ct")
    assert [c["id"] for c in out] == [1]


def test_filter_cards_for_fc_export_card_id_wins_over_name():
    cards = [_card(1, "Hartford, CT"), _card(2, "Anderson, SC")]
    out = filter_cards_for_fc_export(cards, card_id="2", card_name="Hartford, CT")
    assert [c["id"] for c in out] == [2]


def test_filter_cards_for_fc_export_unknown_id_returns_empty():
    cards = [_card(1, "Hartford, CT")]
    assert filter_cards_for_fc_export(cards, card_id="99") == []


def test_parse_fc_export_groups_defaults_and_empty():
    assert parse_fc_export_groups({}) == set(DEFAULT_FC_EXPORT_GROUPS)
    assert parse_fc_export_groups({"groups": [""]}) == set()
    assert parse_fc_export_groups({"groups": ["wag1,other"]}) == {"wag1", "other"}


def test_cards_for_fc_export_wag1_only():
    cards = [
        {"name": "WAG1-A", "category": "", "host": "", "model": "", "device_profile": ""},
        {"name": "WAG2-B", "category": "", "host": "", "model": "", "device_profile": ""},
    ]
    kept = cards_for_fc_export(cards, {"wag1"})
    assert [c["name"] for c in kept] == ["WAG1-A"]
