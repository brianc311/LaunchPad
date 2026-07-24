from launchpad.mouse_jiggler import (
    SETTING_MOUSE_JIGGLER,
    MouseJiggler,
    setting_to_enabled,
)


def test_setting_default_off():
    assert setting_to_enabled("") is False
    assert setting_to_enabled("false") is False
    assert setting_to_enabled("true") is True
    assert SETTING_MOUSE_JIGGLER == "mouse_jiggler_enabled"


def test_jiggler_set_enabled_calls_nudge_on_timer(monkeypatch):
    calls = []
    j = MouseJiggler(interval_sec=0.05, nudge_fn=lambda: calls.append(1))
    j.set_enabled(True)
    import time

    time.sleep(0.2)
    j.set_enabled(False)
    assert len(calls) >= 1
