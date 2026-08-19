from pathlib import Path

DASH = Path("launchpad/ui/dashboard_view.py").read_text(encoding="utf-8")
DIALOG = Path("launchpad/ui/health_alert_dialog.py").read_text(encoding="utf-8")
CARD = Path("launchpad/ui/card_widget.py").read_text(encoding="utf-8")
LAYOUT = Path("launchpad/ui/health_alert_layout.py").read_text(encoding="utf-8")


def test_health_alert_dialog_module():
    assert "class HealthAlertDialog" in DIALOG
    assert "HEALTH_ALERT_POLL_MS" in DIALOG
    assert "group_health_alerts" in DIALOG
    assert "Critical Health Alert" in DIALOG
    assert "resolve_health_alert_art" in DIALOG
    assert "build_health_alert_surface" in DIALOG
    assert "load_alert_art_image" in DIALOG


def test_health_alert_layout_module():
    assert "def build_health_alert_surface(" in LAYOUT
    assert 'text="Suppress"' in LAYOUT
    assert "Alarm off" in LAYOUT
    assert "Alarm on" in LAYOUT
    assert 'f"Snooze {minutes}"' in LAYOUT
    assert "SNOOZE_MINUTES = (5, 10, 15, 20)" in LAYOUT
    assert 'text="Close"' in LAYOUT
    assert "CTkImage" in LAYOUT


def test_dashboard_wires_health_alert_poll():
    assert "_schedule_health_alert_poll" in DASH
    assert "_refresh_health_alerts" in DASH
    assert "HEALTH_ALERT_POLL_MS" in DASH
    assert "HealthAlertDialog" in DASH
    assert "get_health_server" in DASH
    assert "get_health_alerts" in DASH
    assert "play_health_alert_beep" in DASH
    assert "beeped_this_poll" in DASH
    assert "set_health_alarm_muted" in DASH
    assert "ensure_health_alert_art_dir()" in DASH
    assert "set_health_alert_overlay" in DASH


def test_dashboard_remembers_dismissed_overlays():
    assert "_health_alert_overlay_dismissed" in DASH
    assert "_dismiss_health_alert_overlay" in DASH
    assert "_health_alert_group_key" in DASH


def test_dashboard_normalizes_health_alert_card_ids():
    assert "_same_health_alert_card_id" in DASH
    assert "_force_close_health_alert_dialog" in DASH
    assert "_finish_health_alert_dialog" in DASH
    assert "self.after(50," in DASH
    # Dialog actions must bind to the opened dialog instance, not only the
    # dashboard's current pointer (orphaned windows used to no-op).
    assert 'holder: dict[str, Any] = {"dialog": None}' in DASH
    assert "self._acknowledge_health_alert_group(dialog.group, dialog=dialog)" in DASH


def test_card_widget_has_health_alert_overlay_contract():
    assert "def set_health_alert_overlay(" in CARD
    assert "def clear_health_alert_overlay(" in CARD
    assert "build_health_alert_surface(" in CARD
    assert "health_alert_overlay_signature" in CARD


def test_card_widget_exposes_always_visible_alerts_toggle():
    source = Path("launchpad/ui/card_widget.py").read_text(encoding="utf-8")
    assert "Alerts on" in source
    assert "Alerts off" in source
    assert "set_health_alarm_muted" in source


def test_dashboard_wires_alerts_toggle_to_health_alarm():
    assert "_toggle_health_alarm_for_card" in DASH
    assert "set_health_alarm_muted" in DASH


def test_desktop_surfaces_do_not_cover_art_with_transparent_frames():
    # CTk paints fg_color="transparent" with the master colour, so a full-bleed
    # transparent frame would hide the art entirely (final review C1).
    assert 'fg_color="transparent"' not in DIALOG
    backdrop_place = "backdrop.place(relx=0, rely=0, relwidth=1, relheight=1)"
    assert backdrop_place in LAYOUT
    assert "relheight=1" not in LAYOUT.split(backdrop_place)[1]


def test_dashboard_has_alert_popups_toggle():
    assert 'text="Alert popups"' in DASH
    assert "SETTING_ALERT_POPUPS" in DASH
    assert "desktop_alert_popups_enabled" in DASH
    assert "_toggle_alert_popups" in DASH
    assert "alert_popups_switch" in DASH
    assert "grid_columnconfigure(4, weight=1)" in DASH


def test_dashboard_skips_dialog_and_beep_when_alert_popups_off():
    apply = DASH.split("    def _apply_health_alert_payload", 1)[1].split(
        "    def _health_alert_group_key", 1
    )[0]
    assert "self._alert_popups_enabled" in apply
    assert "play_health_alert_beep" in apply
    assert "_sync_health_alert_overlays" in apply
    assert "_show_next_health_alert" in apply
    toggle = DASH.split("    def _toggle_alert_popups", 1)[1].split("    def ", 1)[0]
    assert "_force_close_health_alert_dialog" in toggle
    assert 'set_setting(SETTING_ALERT_POPUPS, "true"' in DASH or (
        'SETTING_ALERT_POPUPS, "true"' in toggle
    )
