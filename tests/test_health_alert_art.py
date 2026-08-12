from pathlib import Path

import pytest

from launchpad.health_alert_art import (
    HEALTH_ALERTS_SUBDIR,
    normalize_alert_art_key,
    package_art_dir,
    resolve_health_alert_art,
)


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


def test_package_art_dir_exists_in_source_tree():
    art_dir = package_art_dir()
    assert art_dir.is_dir()
    assert art_dir.name == HEALTH_ALERTS_SUBDIR
    assert art_dir.parent.name == "resources"
    assert list(art_dir.glob("*.png"))


def test_launchpad_spec_bundles_health_alert_art():
    spec = Path("LaunchPad.spec").read_text(encoding="utf-8")
    assert "launchpad/resources/health-alerts" in spec
    assert "health_alert_art" in spec


@pytest.fixture
def packaged_art(tmp_path: Path) -> Path:
    for name in (
        "ANDERSON, SC.png",
        "HPE-PLN-W01BHANA101-3pc-WAG1.png",
        "HPE-hpew101sstor01-WAG2.png",
        "HPE-hpew102sstor01-WAG1.png",
        "VALPARAISO__IN-e901bfef.png",
        "WINDSOR, WI.png",
    ):
        (tmp_path / name).write_bytes(b"\x89PNG\r\n\x1a\n")
    return tmp_path


@pytest.mark.parametrize("card_name", ["A", "HPE", "HP", "W"])
def test_short_card_names_do_not_resolve(packaged_art: Path, card_name: str):
    assert resolve_health_alert_art(card_name, art_dir=packaged_art) is None


def test_partial_hpe_name_does_not_resolve_to_another_array(packaged_art: Path):
    assert resolve_health_alert_art("HPE-hpew1", art_dir=packaged_art) is None


def test_exact_stem_still_resolves(packaged_art: Path):
    hit = resolve_health_alert_art("HPE-hpew101sstor01-WAG2", art_dir=packaged_art)
    assert hit is not None
    assert hit.name == "HPE-hpew101sstor01-WAG2.png"


def test_valparaiso_resolves_against_packaged_names(packaged_art: Path):
    hit = resolve_health_alert_art("Valparaiso, IN", art_dir=packaged_art)
    assert hit is not None
    assert hit.name == "VALPARAISO__IN-e901bfef.png"


def test_valparaiso_plain_filename_resolves(tmp_path: Path):
    png = tmp_path / "VALPARAISO, IN.png"
    png.write_bytes(b"\x89PNG\r\n\x1a\n")
    assert resolve_health_alert_art("Valparaiso, IN", art_dir=tmp_path) == png


def test_boundary_aligned_longer_card_name_resolves(packaged_art: Path):
    hit = resolve_health_alert_art("Anderson, SC Rack 4", art_dir=packaged_art)
    assert hit is not None
    assert hit.name == "ANDERSON, SC.png"
