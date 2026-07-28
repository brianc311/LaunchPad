from launchpad.system_connectivity import (
    hpe_call_home_na_row,
    is_system_connectivity_eligible,
    parse_hpe_shownet_dns_ntp,
    parse_svc_call_home,
    parse_svc_dns,
    parse_svc_ntp_from_lssystem,
    parse_svc_snmp,
    parse_ds_networkport_dns,
)


def test_eligible_monitor_on_svc_hpe_ds():
    assert is_system_connectivity_eligible(
        {"card_type": "ssh", "device_profile": "flashsystem_7200"}, monitor_on=True
    )
    assert is_system_connectivity_eligible(
        {"card_type": "ssh", "device_profile": "hpe_primera_600"}, monitor_on=True
    )
    assert is_system_connectivity_eligible(
        {"card_type": "ssh", "device_profile": "ibm_ds8884"}, monitor_on=True
    )
    assert not is_system_connectivity_eligible(
        {"card_type": "ssh", "device_profile": "flashsystem_7200"}, monitor_on=False
    )


def test_parse_svc_call_home_enabled():
    out = "id:status:error_sequence_number\n0:enabled:0\n"
    configured, status, details = parse_svc_call_home(out)
    assert configured == "yes"
    assert "enabled" in status.lower() or "enabled" in details.lower()


def test_parse_svc_dns_yes_and_no():
    yes_out = "id:name:IP_address\n0:dns1:10.1.1.1\n"
    assert parse_svc_dns(yes_out)[0] == "yes"
    no_out = "id:name:IP_address\n"
    assert parse_svc_dns(no_out)[0] == "no"


def test_parse_svc_snmp_strips_secrets():
    out = "id:IP:port:community\n0:10.2.2.2:162:public\n"
    configured, status, details = parse_svc_snmp(out)
    assert configured == "yes"
    assert "public" not in details.lower()
    assert "10.2.2.2" in details


def test_parse_svc_ntp():
    out = "id:name\ncluster_ntp_IP_address:10.3.3.3\n"
    # Also accept key:value lssystem style lines mixed with colon tables
    kv = "name:cluster1\ncluster_ntp_IP_address:10.3.3.3\n"
    assert parse_svc_ntp_from_lssystem(kv)[0] == "yes"
    empty = "name:cluster1\ncluster_ntp_IP_address:\n"
    assert parse_svc_ntp_from_lssystem(empty)[0] == "no"


def test_parse_hpe_shownet():
    out = """
IP Address    Netmask/PrefixLen Nodes Active Speed Duplex AutoNeg Status
10.1.1.10     255.255.255.0      01      1  1000 Full   Yes     Active
Default route :   10.1.1.1
NTP server    :   10.5.5.5
DNS server    :   10.6.6.6
"""
    parsed = parse_hpe_shownet_dns_ntp(out)
    assert parsed["dns"][0] == "yes"
    assert "10.6.6.6" in parsed["dns"][2]
    assert parsed["ntp"][0] == "yes"
    assert "10.5.5.5" in parsed["ntp"][2]


def test_hpe_call_home_na():
    assert hpe_call_home_na_row()[0] == "n/a"


def test_parse_ds_dns():
    out = (
        "ID IP address Subnet Mask Gateway Primary DNS Secondary DNS State\n"
        "I9814 10.0.1.2 255.255.255.0 10.0.1.1 9.0.0.10 9.0.0.11 Online\n"
    )
    configured, status, details = parse_ds_networkport_dns(out)
    assert configured == "yes"
    assert "9.0.0.10" in details
