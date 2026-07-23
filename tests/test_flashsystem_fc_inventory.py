"""FC inventory analyze: attach fabric remotes to ports when WWPNs differ (NPIV)."""

from launchpad.flashsystem_fc import analyze_fc_inventory


def _carolina_command_results() -> list[dict]:
    """lsportfc physical WWPNs differ from lsfabric local (NPIV) WWPNs.

    Real Carolina-style pattern: fabric local_port aligns with fc_io_port_id,
    not with the physical port WWPN shown in lsportfc.
    """
    ports_out = (
        "id:fc_io_port_id:port_id:type:port_speed:node_id:node_name:WWPN:status:attachment\n"
        "0:1:1:fc:32Gb:1:node1:500507681011C3FB:active:switch\n"
        "1:2:2:fc:32Gb:1:node1:500507681012C3FB:active:switch\n"
        "2:3:3:fc:32Gb:1:node1:500507681013C3FB:active:switch\n"
        "3:4:4:fc:32Gb:1:node1:500507681014C3FB:active:switch\n"
        "24:4:4:fc:32Gb:2:node2:500507681011C3F3:active:switch\n"
    )
    fabric_out = (
        "remote_wwpn:id:node_id:node_name:local_wwpn:local_port:state:name:type\n"
        "C050760C0A500008:0:1:node1:500507681018C3FB:4:active:APR1:host\n"
        "C050760C0A500008:1:2:node2:500507681018C3F3:4:active:APR1:host\n"
        "C050760C0A500000:2:1:node1:500507681016C3FB:2:active:APR1:host\n"
        "C050760C0A500004:3:1:node1:500507681015C3FB:1:active:APR1:host\n"
    )
    return [
        {
            "label": "FC - Ports WWPN",
            "command": "svcinfo lsportfc -delim :",
            "output": ports_out,
        },
        {
            "label": "FC - Fabric",
            "command": "svcinfo lsfabric -delim :",
            "output": fabric_out,
        },
    ]


def test_analyze_fc_inventory_attaches_remotes_when_npiv_wwpn_differs():
    fc = analyze_fc_inventory(_carolina_command_results())
    by_id = {p["port_id"]: p for p in fc["fc_ports"]}

    # Physical WWPN does not equal fabric local_wwpn — must still attach via port id.
    assert by_id["0"]["wwpn"] == "500507681011C3FB"
    assert by_id["0"]["logged_in_count"] == "1"
    assert "C050760C0A500004" in by_id["0"]["remote_wwpns"]
    assert "APR1" in by_id["0"]["fabric_hosts"]

    assert by_id["1"]["logged_in_count"] == "1"
    assert "C050760C0A500000" in by_id["1"]["remote_wwpns"]

    assert by_id["3"]["logged_in_count"] == "1"
    assert "C050760C0A500008" in by_id["3"]["remote_wwpns"]

    assert by_id["24"]["logged_in_count"] == "1"
    assert "C050760C0A500008" in by_id["24"]["remote_wwpns"]


def test_analyze_fc_inventory_still_joins_by_matching_wwpn():
    ports_out = (
        "id:fc_io_port_id:node_name:WWPN:status:attachment\n"
        "0:1:node1:500507681018C3FB:active:switch\n"
    )
    fabric_out = (
        "remote_wwpn:node_name:local_wwpn:local_port:state:name\n"
        "C050760C0A500008:node1:500507681018C3FB:9:active:APR1\n"
    )
    results = [
        {"label": "FC - Ports", "command": "svcinfo lsportfc -delim :", "output": ports_out},
        {"label": "FC - Fabric", "command": "svcinfo lsfabric -delim :", "output": fabric_out},
    ]
    fc = analyze_fc_inventory(results)
    port = fc["fc_ports"][0]
    assert port["logged_in_count"] == "1"
    assert port["remote_wwpns"] == "C050760C0A500008"
