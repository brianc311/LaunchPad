from launchpad.fc_wwpn_export import rows_from_card_api
from launchpad.flashsystem_fc import format_fc_port_label


def test_format_fc_port_label_rules():
    assert format_fc_port_label(None) == ""
    assert format_fc_port_label("") == ""
    assert format_fc_port_label("0") == "fc0"
    assert format_fc_port_label("3") == "fc3"
    assert format_fc_port_label("12") == "fc12"
    assert format_fc_port_label("fc0") == "fc0"
    assert format_fc_port_label("FC1") == "fc1"
    assert format_fc_port_label("1/1") == "1/1"
    assert format_fc_port_label("host") == "host"


def test_export_rows_port_column_uses_fc_label():
    card = {
        "name": "Hartford",
        "category": "DC",
        "host": "10.0.0.1",
        "model": "flashsystem_7200",
        "fc_ports": [
            {
                "node_name": "node1",
                "port_id": "0",
                "wwpn": "AABBCCDDEEFF0011",
                "status": "active",
                "speed": "16Gb",
                "attachment": "host",
                "logged_in_count": "1",
                "remote_wwpns": "",
                "fabric_hosts": "",
            }
        ],
        "fc_hosts": [],
        "fc_host_maps": [],
    }
    port_rows, _hosts, _maps = rows_from_card_api(card)
    assert port_rows[0][5] == "fc0"
