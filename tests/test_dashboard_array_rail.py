from types import SimpleNamespace

from launchpad.dashboard_array_rail import (
    SETTING_ARRAY_RAIL_COLLAPSED,
    can_open_rail_gui,
    collapsed_from_setting,
    filter_dashboard_cards,
    open_rail_gui,
    rail_gui_url,
    rail_row_subtitle,
    rail_row_title,
    setting_from_collapsed,
)


def test_setting_key():
    assert SETTING_ARRAY_RAIL_COLLAPSED == "dashboard_array_rail_collapsed"


def test_filter_dashboard_cards_by_query():
    cards = [
        SimpleNamespace(name="Hartford, CT", host="10.1.1.1", category="Remote", serial_number=""),
        SimpleNamespace(name="Tempe, AZ", host="10.2.2.2", category="Remote", serial_number="SN1"),
    ]
    assert [c.name for c in filter_dashboard_cards(cards, query="tempe")] == ["Tempe, AZ"]
    assert [c.name for c in filter_dashboard_cards(cards, query="10.1")] == ["Hartford, CT"]
    assert [c.name for c in filter_dashboard_cards(cards, query="sn1")] == ["Tempe, AZ"]
    assert len(filter_dashboard_cards(cards, query="")) == 2


def test_rail_gui_url_prefers_url_then_host():
    assert rail_gui_url(SimpleNamespace(url="https://gui", host="10.0.0.1")) == "https://gui"
    assert rail_gui_url(SimpleNamespace(url="", host="10.245.16.56")) == "https://10.245.16.56"
    assert rail_gui_url(SimpleNamespace(url="", host="")) == ""
    assert can_open_rail_gui(SimpleNamespace(url="", host="10.0.0.1")) is True
    assert can_open_rail_gui(SimpleNamespace(url="", host="")) is False


def test_rail_gui_url_3par_uses_8443():
    card = SimpleNamespace(
        url="",
        host="pla-w023par01",
        device_profile="hpe_3par_8200",
    )
    assert rail_gui_url(card) == "https://pla-w023par01:8443"


def test_rail_gui_url_primera_no_8443():
    card = SimpleNamespace(
        url="",
        host="pla-w023par01",
        device_profile="hpe_primera_600",
    )
    assert rail_gui_url(card) == "https://pla-w023par01"


def test_rail_row_labels():
    card = SimpleNamespace(name="Anderson, SC", host="10.3.3.3", url="")
    assert rail_row_title(card) == "Anderson, SC"
    assert rail_row_subtitle(card) == "10.3.3.3"


def test_collapse_setting_roundtrip():
    assert collapsed_from_setting("true") is True
    assert collapsed_from_setting("false") is False
    assert collapsed_from_setting(None) is False
    assert setting_from_collapsed(True) == "true"
    assert setting_from_collapsed(False) == "false"


def test_open_rail_gui_opens_browser(monkeypatch):
    opened: list[str] = []
    monkeypatch.setattr(
        "launchpad.dashboard_array_rail.webbrowser.open",
        lambda url: opened.append(url),
    )
    msg = open_rail_gui(
        SimpleNamespace(url="", host="10.9.9.9", name="X", device_profile="")
    )
    assert msg == "Opened GUI"
    assert opened == ["https://10.9.9.9"]


def test_open_rail_gui_requires_target():
    try:
        open_rail_gui(SimpleNamespace(url="", host="", name="X"))
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "host" in str(exc).lower() or "url" in str(exc).lower()
