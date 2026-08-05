from launchpad.dell_report_facility import facility_from_name
from launchpad.dell_report_family import dell_report_family
from launchpad.dell_report_leds import (
    AMBER_FILL,
    GREEN_FILL,
    UTIL_YELLOW_THRESHOLD,
    utilization_led_fill,
)


def test_facility_wag_and_other():
    assert facility_from_name("HPE - foo - WAG1") == "Data center -WAG1"
    assert facility_from_name("site wag2 bar") == "Data center -WAG2"
    assert facility_from_name("v5kPEN-g3v1 Distribution") == "Distribution center"
    assert facility_from_name("mystery-box") == "Other"


def test_facility_wag_priority_over_dc_host_prefix():
    assert facility_from_name("V7K237XW-WAG1") == "Data center -WAG1"
    assert facility_from_name("V7K37WP_wag2") == "Data center -WAG2"


def test_facility_distribution_patterns():
    assert facility_from_name("east-dc-primary") == "Distribution center"
    assert facility_from_name("v7kNYC-g2") == "Distribution center"
    assert facility_from_name("v5k remote backup") == "Remote"


def test_facility_vag_aliases():
    assert facility_from_name("DS8884 VAG1") == "Data center -WAG1"
    assert facility_from_name("site vag2 svc") == "Data center -WAG2"


def test_facility_v5k_token_anywhere():
    assert facility_from_name("host-v5kPEN-g3v1") == "Distribution center"


def test_family_ibm_hp():
    assert dell_report_family("flashsystem_9500") == "ibm"
    assert dell_report_family("hpe_3par_8450") == "hp"
    assert dell_report_family("dell_powermax") is None


def test_family_manufacturer_hint():
    assert dell_report_family("unknown", manufacturer="IBM") == "ibm"
    assert dell_report_family("unknown", manufacturer="HPE") == "hp"


def test_led_bands():
    assert UTIL_YELLOW_THRESHOLD == 0.80
    assert utilization_led_fill(0.79) == GREEN_FILL
    assert utilization_led_fill(0.80) == AMBER_FILL
    assert utilization_led_fill(0.95) == AMBER_FILL


def test_led_invalid():
    assert utilization_led_fill(None) is None
    assert utilization_led_fill(-0.1) is None
    assert utilization_led_fill(1.1) is None
