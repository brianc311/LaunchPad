from launchpad.fc_wwpn_export import filter_cards_for_fc_export


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
