"""Resolve health-alert overlay PNG art by card name."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from launchpad.config import BRANDING_DIR

HEALTH_ALERTS_SUBDIR = "health-alerts"

_PACKAGE_ART_DIR = Path(__file__).resolve().parent / "resources" / HEALTH_ALERTS_SUBDIR

_DIST_SUFFIXES = (
    "DISTRIBUTION CENTER",
    "DIST CENTER",
    "DISTRIBUTION",
)

_HEX_SUFFIX_RE = re.compile(r"-[0-9a-f]{4,}$", re.IGNORECASE)
_NON_ALNUM_RE = re.compile(r"[^A-Z0-9]")
_MULTI_UNDERSCORE_RE = re.compile(r"_{2,}")


def normalize_alert_art_key(name: str) -> str:
    key = str(name or "").upper()
    for suffix in _DIST_SUFFIXES:
        if key.endswith(suffix):
            key = key[: -len(suffix)]
            break
    key = key.strip()
    key = _NON_ALNUM_RE.sub("_", key)
    key = _MULTI_UNDERSCORE_RE.sub("__", key)
    return key.strip("_")


def _strip_hex_suffixes(stem: str) -> str:
    core = stem
    while True:
        match = _HEX_SUFFIX_RE.search(core)
        if not match:
            break
        core = core[: match.start()]
    return core


def _normalize_art_stem(stem: str) -> str:
    return normalize_alert_art_key(_strip_hex_suffixes(stem))


def _list_png_files(art_dir: Path) -> list[Path]:
    if not art_dir.is_dir():
        return []
    files: list[Path] = []
    for pattern in ("*.png", "*.PNG"):
        files.extend(art_dir.glob(pattern))
    return sorted({path.resolve() for path in files})


def resolve_health_alert_art(
    card_name: str,
    *,
    art_dir: Path | None = None,
) -> Path | None:
    target_dir = art_dir if art_dir is not None else ensure_health_alert_art_dir()
    card_key = normalize_alert_art_key(card_name)
    if not card_key:
        return None

    exact_match: Path | None = None
    prefix_matches: list[tuple[int, Path]] = []

    for png_path in _list_png_files(target_dir):
        stem_key = _normalize_art_stem(png_path.stem)
        if not stem_key:
            continue
        if stem_key == card_key:
            exact_match = png_path
            break
        if stem_key.startswith(card_key) or card_key.startswith(stem_key):
            prefix_matches.append((len(stem_key), png_path))

    if exact_match is not None:
        return exact_match

    if not prefix_matches:
        return None

    prefix_matches.sort(key=lambda item: (-item[0], str(item[1]).lower()))
    return prefix_matches[0][1]


def ensure_health_alert_art_dir() -> Path:
    branding_art_dir = BRANDING_DIR / HEALTH_ALERTS_SUBDIR
    branding_art_dir.mkdir(parents=True, exist_ok=True)

    if not _list_png_files(branding_art_dir) and _PACKAGE_ART_DIR.is_dir():
        for src in _list_png_files(_PACKAGE_ART_DIR):
            dest = branding_art_dir / src.name
            if not dest.exists():
                shutil.copy2(src, dest)

    return branding_art_dir
