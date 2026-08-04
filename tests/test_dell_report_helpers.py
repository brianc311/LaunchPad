from launchpad.dell_report_facility import facility_from_name
from launchpad.dell_report_family import dell_report_family
from launchpad.dell_report_leds import utilization_led_fill


def test_facility_wag_and_other():
    assert facility_from_name("HPE - foo - WAG1") == "Data center -WAG1"
    assert facility_from_name("site wag2 bar") == "Data center -WAG2"
    assert facility_from_name("v5kPEN-g3v1 Distribution") == "Distribution center"
    assert facility_from_name("mystery-box") == "Other"


def test_facility_distribution_patterns():
    assert facility_from_name("east-dc-primary") == "Distribution center"
    assert facility_from_name("v7kNYC-g2") == "Distribution center"
    assert facility_from_name("v5k remote backup") == "Other"


def test_family_ibm_hp():
    assert dell_report_family("flashsystem_9500") == "ibm"
    assert dell_report_family("hpe_3par_8450") == "hp"
    assert dell_report_family("dell_powermax") is None


def test_family_manufacturer_hint():
    assert dell_report_family("unknown", manufacturer="IBM") == "ibm"
    assert dell_report_family("unknown", manufacturer="HPE") == "hp"


def test_led_bands():
    assert utilization_led_fill(0.69) == "22C55E"
    assert utilization_led_fill(0.70) == "F59E0B"
    assert utilization_led_fill(0.89) == "F59E0B"
    assert utilization_led_fill(0.90) == "EF4444"


def test_led_invalid():
    assert utilization_led_fill(None) is None
    assert utilization_led_fill(-0.1) is None
    assert utilization_led_fill(1.1) is None
