from launchpad.fc_wwpn_search import (
    card_matches_fc_query,
    find_cards_matching_fc_query,
    normalize_wwpn,
)


def test_normalize_wwpn_strips_colons_and_spaces():
    assert normalize_wwpn("10:00:00:00:c9:a1:b2:c3") == "10000000C9A1B2C3"
    assert normalize_wwpn("  aa bb  ") == "AABB"


def test_empty_query_matches_all_for_filter_semantics():
    card = {"name": "Site", "fc_ports": [], "fc_hosts": [], "fc_mappings": [], "fc_fabric": []}
    assert card_matches_fc_query(card, "") is True


def test_find_empty_query_returns_no_matches():
    cards = [{"id": 1, "name": "A", "fc_ports": [{"wwpn": "AA"}]}]
    assert find_cards_matching_fc_query(cards, "") == []
    assert find_cards_matching_fc_query(cards, "   ") == []


def test_matches_local_and_remote_wwpn():
    card = {
        "name": "Carolina, PR",
        "fc_ports": [{"wwpn": "10:00:00:00:c9:a1:b2:c3", "remote_wwpns": "20:00:00:00:11:22:33:44"}],
        "fc_hosts": [],
        "fc_mappings": [],
        "fc_fabric": [{"local_wwpn": "AA", "remote_wwpn": "BB:CC", "host_name": ""}],
    }
    assert card_matches_fc_query(card, "c9a1b2c3") is True
    assert card_matches_fc_query(card, "2000000011223344") is True
    assert card_matches_fc_query(card, "deadbeef") is False


def test_matches_host_and_volume_names():
    card = {
        "name": "Hartford, CT",
        "fc_ports": [],
        "fc_hosts": [{"host_name": "pconsps3", "wwpns": "AA:BB"}],
        "fc_mappings": [{"vdisk_name": "pconsps_archvg_1", "host_name": "pconsps3"}],
        "fc_fabric": [],
    }
    assert card_matches_fc_query(card, "pconsps3") is True
    assert card_matches_fc_query(card, "archvg") is True


def test_find_sorts_by_name_and_returns_hits_only():
    cards = [
        {"id": 2, "name": "Zed", "fc_ports": [{"wwpn": "AA"}], "fc_hosts": [], "fc_mappings": [], "fc_fabric": []},
        {"id": 1, "name": "Alpha", "fc_ports": [{"wwpn": "AA"}], "fc_hosts": [], "fc_mappings": [], "fc_fabric": []},
        {"id": 3, "name": "Other", "fc_ports": [{"wwpn": "BB"}], "fc_hosts": [], "fc_mappings": [], "fc_fabric": []},
    ]
    found = find_cards_matching_fc_query(cards, "AA")
    assert [c["name"] for c in found] == ["Alpha", "Zed"]


def test_matches_fc_ports_by_node_only():
    card = {
        "fc_ports": [],
        "fc_ports_by_node": [
            {
                "node": "node1",
                "ports": [
                    {
                        "wwpn": "10:00:00:00:c9:a1:b2:c3",
                        "remote_wwpns": "20:00:00:00:11:22:33:44",
                    }
                ],
            }
        ],
        "fc_hosts": [],
        "fc_mappings": [],
        "fc_fabric": [],
    }
    assert card_matches_fc_query(card, "c9a1b2c3") is True
    assert card_matches_fc_query(card, "2000000011223344") is True
    assert card_matches_fc_query(card, "deadbeef") is False


def test_space_formatted_wwpn_field_matches_normalized_query():
    card = {
        "fc_ports": [{"wwpn": "10 00 00 00 c9 a1 b2 c3", "remote_wwpns": ""}],
        "fc_hosts": [],
        "fc_mappings": [],
        "fc_fabric": [],
    }
    assert card_matches_fc_query(card, "10000000c9a1b2c3") is True


def test_concatenated_wwpn_fields_do_not_false_positive():
    card = {
        "fc_ports": [
            {"wwpn": "AA", "remote_wwpns": ""},
            {"wwpn": "BB", "remote_wwpns": ""},
        ],
        "fc_hosts": [],
        "fc_mappings": [],
        "fc_fabric": [],
    }
    assert card_matches_fc_query(card, "AABB") is False
    assert card_matches_fc_query(card, "AA") is True
    assert card_matches_fc_query(card, "BB") is True
