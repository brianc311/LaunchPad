from launchpad.capacity_pool_family import capacity_pool_family


def test_ibm_flashsystem():
    assert capacity_pool_family("flashsystem_9200") == "ibm"


def test_hpe_maps_from_dell_report_hp():
    assert capacity_pool_family("hpe_primera_a670") == "hpe"
    assert capacity_pool_family("hp_3par_8200") == "hpe"


def test_dell_prefix():
    assert capacity_pool_family("dell_powermax_8000") == "dell"
    assert capacity_pool_family("dell_unity_650f") == "dell"


def test_unknown_empty():
    assert capacity_pool_family("netapp_aff") == ""
    assert capacity_pool_family("") == ""


def test_site_name_fallback_ibm():
    assert capacity_pool_family("", site_name="CHI FlashSystem 01") == "ibm"
