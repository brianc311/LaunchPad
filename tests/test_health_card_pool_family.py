from launchpad.capacity_units import set_capacity_unit_mode
from launchpad.health_server import HealthCard


def test_to_api_includes_pool_family_ibm():
    card = HealthCard(
        card_id=1,
        name="FS1",
        host="10.0.0.1",
        port=22,
        username="user",
        key_path="",
        device_profile="flashsystem_9200",
    )
    api = card.to_api()
    assert api["pool_family"] == "ibm"


def test_to_api_includes_pool_family_dell():
    card = HealthCard(
        card_id=2,
        name="PM1",
        host="10.0.0.2",
        port=22,
        username="user",
        key_path="",
        device_profile="dell_powermax_8000",
    )
    api = card.to_api()
    assert api["pool_family"] == "dell"


def test_to_api_includes_current_capacity_unit_mode():
    set_capacity_unit_mode("si")
    card = HealthCard(
        card_id=3,
        name="FS2",
        host="10.0.0.3",
        port=22,
        username="user",
        key_path="",
    )

    assert card.to_api()["capacity_unit_mode"] == "si"
