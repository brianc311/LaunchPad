from launchpad.flashsystem_fc import parse_fc_hosts
from launchpad.site_lookup_data import inventory_from_command_results, shape_hosts_for_lookup


def test_parse_fc_hosts_reads_type_column():
    output = (
        "id:name:port_count:status:type:protocol\n"
        "0:pen_hrdcesx_vm01:8:online:generic:scsi\n"
        "1:ACT1_AS400:2:online:generic:scsi\n"
    )
    hosts = parse_fc_hosts(output)
    assert hosts[0]["host_name"] == "pen_hrdcesx_vm01"
    assert hosts[0]["type"] == "generic"
    assert hosts[1]["type"] == "generic"


def test_parse_fc_hosts_defaults_type_to_generic_when_missing():
    output = "id:name:port_count:status:protocol\n0:host1:2:online:scsi\n"
    hosts = parse_fc_hosts(output)
    assert hosts[0]["type"] == "Generic"
    assert hosts[0]["host_type"] == "Generic"


def test_inventory_from_command_results_ibm_hosts_include_type():
    results = [
        {
            "label": "FC - Hosts",
            "command": "svcinfo lshost -delim :",
            "output": "id:name:port_count:status:protocol\n0:host1:2:online:scsi\n",
            "error": None,
        }
    ]
    hosts, _volumes, _maps = inventory_from_command_results(
        results, device_profile="flashsystem_7200"
    )
    assert hosts[0]["host_name"] == "host1"
    assert hosts[0]["type"] == "Generic"
    assert hosts[0]["name"] == "host1"


def test_shape_hosts_preserves_ibm_type():
    shaped = shape_hosts_for_lookup(
        [{"host_name": "h1", "status": "online", "type": "generic", "port_count": "2"}]
    )
    assert shaped[0]["type"] == "generic"
