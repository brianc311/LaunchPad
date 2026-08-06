from launchpad.database import Database
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


def test_jiggler_setting_persists(tmp_path):
    db = Database(tmp_path / "t.db")
    assert setting_to_enabled(db.get_setting(SETTING_MOUSE_JIGGLER, "")) is False

    db.set_setting(SETTING_MOUSE_JIGGLER, "true")
    assert db.get_setting(SETTING_MOUSE_JIGGLER) == "true"
    assert setting_to_enabled(db.get_setting(SETTING_MOUSE_JIGGLER)) is True

    db.set_setting(SETTING_MOUSE_JIGGLER, "false")
    assert db.get_setting(SETTING_MOUSE_JIGGLER) == "false"
    assert setting_to_enabled(db.get_setting(SETTING_MOUSE_JIGGLER)) is False


def test_set_enabled_true_requests_keep_awake_and_nudges_immediately():
    nudges = []
    keeps = []
    clears = []
    j = MouseJiggler(
        interval_sec=60,
        nudge_fn=lambda: nudges.append(1),
        keep_awake_fn=lambda: keeps.append(1),
        clear_keep_awake_fn=lambda: clears.append(1),
    )
    j.set_enabled(True)
    assert keeps == [1]
    assert nudges == [1]
    j.set_enabled(False)
    assert clears == [1]
    j.stop()


def test_stop_clears_keep_awake_even_if_already_disabled():
    clears = []
    j = MouseJiggler(
        interval_sec=60,
        nudge_fn=lambda: None,
        keep_awake_fn=lambda: None,
        clear_keep_awake_fn=lambda: clears.append(1),
    )
    j.stop()
    assert clears == [1]


def test_default_windows_nudge_calls_keep_awake_and_sendinput(monkeypatch):
    from launchpad import mouse_jiggler as mj

    calls = []
    monkeypatch.setattr(mj, "request_keep_awake", lambda: calls.append("keep"))
    monkeypatch.setattr(mj, "send_relative_mouse_nudge", lambda: calls.append("send"))
    mj._default_nudge()
    assert calls == ["keep", "send"]
