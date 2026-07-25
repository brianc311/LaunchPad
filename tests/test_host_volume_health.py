from launchpad.host_volume_health import (
    normalize_gui_url,
    status_is_offline_or_degraded,
)


def test_status_offline_degraded():
    assert status_is_offline_or_degraded("offline") is True
    assert status_is_offline_or_degraded("degraded") is True
    assert status_is_offline_or_degraded("offline_unconfigured") is True
    assert status_is_offline_or_degraded("online") is False
    assert status_is_offline_or_degraded("active") is False
    assert status_is_offline_or_degraded("") is False


def test_normalize_gui_url():
    assert normalize_gui_url("10.1.2.3") == "https://10.1.2.3"
    assert normalize_gui_url("https://x") == "https://x"
    assert normalize_gui_url("  ") == ""
