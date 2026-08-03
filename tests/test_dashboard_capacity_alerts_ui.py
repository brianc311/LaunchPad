from pathlib import Path

CARD = Path("launchpad/ui/card_widget.py").read_text(encoding="utf-8")


def test_glowcard_has_set_capacity_alert():
    assert "def set_capacity_alert(" in CARD
    assert "CRIT" in CARD
    assert "WARN" in CARD
