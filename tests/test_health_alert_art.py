from pathlib import Path

from launchpad.health_alert_art import normalize_alert_art_key, resolve_health_alert_art


def test_normalize_strips_distribution_center_suffix():
    assert "VALPARAISO" in normalize_alert_art_key("Valparaiso, IN Distribution Center")
    assert "DISTRIBUTION" not in normalize_alert_art_key("Valparaiso, IN Distribution Center")


def test_resolve_matches_valparaiso_filename(tmp_path: Path):
    png = tmp_path / "VALPARAISO__IN-e901bfef.png"
    png.write_bytes(b"\x89PNG\r\n\x1a\n")
    hit = resolve_health_alert_art("Valparaiso, IN", art_dir=tmp_path)
    assert hit == png


def test_resolve_missing_returns_none(tmp_path: Path):
    assert resolve_health_alert_art("Unknown Site, ZZ", art_dir=tmp_path) is None
