from pathlib import Path

CARD = Path("launchpad/ui/card_widget.py").read_text(encoding="utf-8")
DASH = Path("launchpad/ui/dashboard_view.py").read_text(encoding="utf-8")


def test_glowcard_has_set_capacity_alert():
    assert "def set_capacity_alert(" in CARD
    assert "CRIT" in CARD
    assert "WARN" in CARD


def test_capacity_badge_visible_in_compact_layout():
    """Spec option C: per-card CRIT/WARN stays visible when cards_compact is default."""
    assert "capacity_alert_badge_compact" in CARD
    assert "def _place_capacity_alert_badges(" in CARD
    # Compact badge lives in bottom_left (beside status LED), not only expanded header
    assert "self.capacity_alert_badge_compact = ctk.CTkLabel(\n            self.bottom_left," in CARD
    # Collapsed path grids compact badge; expanded still uses header badge
    assert 'compact.grid(row=0, column=1, padx=(0, 6), sticky="w")' in CARD
    assert 'header.grid(row=0, column=4, sticky="e", padx=(4, 4))' in CARD
    # Destroy cleanup mirrors status LED tip (card-level bind)
    assert 'bind("<Destroy>", lambda _e: self._hide_capacity_alert_tip(), add="+")' in CARD
    # Deferred leave + pointer check so topmost tip does not stick over the card
    assert "def _schedule_hide_capacity_alert_tip(" in CARD
    assert "def _hide_capacity_alert_tip_if_away(" in CARD
    assert "def _pointer_over_capacity_tip_widgets(" in CARD
    assert 'bind("<Leave>", self._schedule_hide_capacity_alert_tip)' in CARD


def test_dashboard_wires_capacity_alert_strip():
    assert "_refresh_capacity_alerts" in DASH
    assert "fleet_capacity_alert_summary" in DASH
    assert "CAPACITY_ALERT_POLL_MS" in DASH
    assert "set_capacity_alert" in DASH
