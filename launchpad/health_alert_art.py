"""Resolve health-alert overlay PNG art by card name."""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

from launchpad.config import BRANDING_DIR

HEALTH_ALERTS_SUBDIR = "health-alerts"

# A prefix match this short (e.g. a card literally named "A" or "HPE") would pick an
# arbitrary array's art, which is actively misleading during an incident.
MIN_PREFIX_MATCH_CHARS = 4

_SOURCE_ART_DIR = Path(__file__).resolve().parent / "resources" / HEALTH_ALERTS_SUBDIR


def package_art_dir() -> Path:
    """Directory holding the art shipped with the product.

    PyInstaller unpacks ``datas`` under ``sys._MEIPASS``, so the frozen build has to
    look there rather than next to the (archived) module source.
    """
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", "")
        if base:
            bundled = Path(base) / "launchpad" / "resources" / HEALTH_ALERTS_SUBDIR
            if bundled.is_dir():
                return bundled
    return _SOURCE_ART_DIR


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


def _prefix_match_score(card_key: str, stem_key: str) -> int | None:
    """Length of a boundary-aligned prefix shared by both keys, or None for no match.

    Both sides must be substantial and the prefix must end on a ``_`` separator, so
    ``HPE`` cannot claim ``HPE-PLN-W01BHANA101`` and ``HPE-hpew1`` cannot claim
    ``HPE-hpew101sstor01``.
    """
    if len(card_key) < MIN_PREFIX_MATCH_CHARS or len(stem_key) < MIN_PREFIX_MATCH_CHARS:
        return None
    if card_key == stem_key:
        return len(card_key)
    if stem_key.startswith(card_key) and stem_key[len(card_key)] == "_":
        return len(card_key)
    if card_key.startswith(stem_key) and card_key[len(stem_key)] == "_":
        return len(stem_key)
    return None


def resolve_health_alert_art(
    card_name: str,
    *,
    art_dir: Path | None = None,
) -> Path | None:
    target_dir = art_dir if art_dir is not None else ensure_health_alert_art_dir()
    card_key = normalize_alert_art_key(card_name)
    if not card_key:
        return None

    prefix_matches: list[tuple[int, Path]] = []

    for png_path in _list_png_files(target_dir):
        stem_key = _normalize_art_stem(png_path.stem)
        if not stem_key:
            continue
        if stem_key == card_key:
            return png_path
        score = _prefix_match_score(card_key, stem_key)
        if score is not None:
            prefix_matches.append((score, png_path))

    if not prefix_matches:
        return None

    prefix_matches.sort(key=lambda item: (-item[0], str(item[1]).lower()))
    if len(prefix_matches) > 1 and prefix_matches[0][0] == prefix_matches[1][0]:
        # Equally good candidates: showing the wrong array's art is worse than none.
        return None
    return prefix_matches[0][1]


def ensure_health_alert_art_dir() -> Path:
    branding_art_dir = BRANDING_DIR / HEALTH_ALERTS_SUBDIR
    branding_art_dir.mkdir(parents=True, exist_ok=True)

    source_dir = package_art_dir()
    if not _list_png_files(branding_art_dir) and source_dir.is_dir():
        for src in _list_png_files(source_dir):
            dest = branding_art_dir / src.name
            if not dest.exists():
                shutil.copy2(src, dest)

    return branding_art_dir
