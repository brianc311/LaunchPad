from launchpad.fc_wwpn_filter import card_matches_search, normalize_wwpn


def test_normalize_wwpn_strips_colons_and_spaces():
    assert normalize_wwpn("10:00:00:00:c9:a1:b2:c3") == "10000000C9A1B2C3"
    assert normalize_wwpn("  aa bb  ") == "AABB"


def test_empty_query_matches_all():
    card = {"name": "Site", "fc_ports": [], "fc_hosts": [], "fc_mappings": [], "fc_fabric": []}
    assert card_matches_search(card, "") is True
    assert card_matches_search(card, "   ") is True


def test_matches_local_and_remote_wwpn():
    card = {
        "fc_ports": [{"wwpn": "10:00:00:00:c9:a1:b2:c3", "remote_wwpns": "20:00:00:00:11:22:33:44"}],
        "fc_hosts": [],
        "fc_mappings": [],
        "fc_fabric": [{"local_wwpn": "AA", "remote_wwpn": "BB:CC", "host_name": ""}],
    }
    assert card_matches_search(card, "c9a1b2c3") is True
    assert card_matches_search(card, "2000000011223344") is True
    assert card_matches_search(card, "bbcc") is True
    assert card_matches_search(card, "deadbeef") is False


def test_matches_host_and_volume_names():
    card = {
        "fc_ports": [],
        "fc_hosts": [{"host_name": "esx-wag1-01", "wwpns": "AA:BB"}],
        "fc_mappings": [{"vdisk_name": "ADC-Data01", "host_name": "esx-wag1-01"}],
        "fc_fabric": [],
    }
    assert card_matches_search(card, "esx-wag1") is True
    assert card_matches_search(card, "adc-data") is True
    assert card_matches_search(card, "missing") is False
