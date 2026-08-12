from launchpad.health_alert_state import same_health_alert_card_id


def test_same_health_alert_card_id_accepts_int_str():
    assert same_health_alert_card_id(3, 3)
    assert same_health_alert_card_id(3, "3")
    assert same_health_alert_card_id("12", 12)
    assert not same_health_alert_card_id(3, 4)
    assert not same_health_alert_card_id(3, None)
