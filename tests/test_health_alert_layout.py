from pathlib import Path

import pytest
from PIL import Image

from launchpad.ui.health_alert_layout import (
    apply_art_scrim,
    build_health_alert_surface,
    format_alert_issue_text,
    load_alert_art_image,
)
from launchpad.ui.theme import get_theme

GROUP = {
    "card_id": 7,
    "card_name": "Valparaiso, IN",
    "issues": [
        {"message": "Canister offline", "fingerprint": "7:node:a"},
        {"message": "Hard drive failed", "fingerprint": "7:drive:b"},
        {"message": "I/O card failed (port 2 on node1)", "fingerprint": "7:io:c"},
        {"message": "Canister lost power", "fingerprint": "7:power:d"},
    ],
}


def test_scrim_darkens_art():
    bright = Image.new("RGBA", (4, 4), (255, 255, 255, 255))
    darkened = apply_art_scrim(bright, alpha=165)
    assert darkened.size == bright.size
    assert darkened.getpixel((0, 0))[0] < 160


def test_scrim_alpha_zero_is_a_no_op():
    bright = Image.new("RGBA", (2, 2), (200, 100, 50, 255))
    assert apply_art_scrim(bright, alpha=0).getpixel((0, 0)) == (200, 100, 50, 255)


def test_issue_text_truncates_with_remainder():
    text = format_alert_issue_text(GROUP, limit=2)
    assert text.splitlines() == ["Canister offline", "Hard drive failed", "+2 more"]


def test_issue_text_falls_back_when_empty():
    assert format_alert_issue_text({"issues": []}) == "Critical health issue"


@pytest.fixture(scope="module")
def ctk_root():
    ctk = pytest.importorskip("customtkinter")
    try:
        root = ctk.CTk()
    except Exception as exc:  # no display / no Tk build
        pytest.skip(f"Tk unavailable: {exc}")
    root.withdraw()
    try:
        yield ctk, root
    finally:
        root.destroy()


def _art_png(tmp_path: Path) -> Path:
    path = tmp_path / "VALPARAISO, IN.png"
    Image.new("RGB", (64, 32), (30, 90, 200)).save(path)
    return path


def _full_bleed(widget) -> bool:
    info = widget.place_info()
    if not info:
        return False
    try:
        return float(info.get("relwidth") or 0) >= 1.0 and float(info.get("relheight") or 0) >= 1.0
    except (TypeError, ValueError):
        return False


def test_alert_surface_leaves_the_art_uncovered(ctk_root, tmp_path: Path):
    ctk, root = ctk_root
    parent = ctk.CTkFrame(root, width=420, height=300)
    parent.pack()
    art_image = load_alert_art_image(_art_png(tmp_path), (360, 210))
    assert art_image is not None

    parts = build_health_alert_surface(
        parent,
        theme=get_theme("dark"),
        group=GROUP,
        art_image=art_image,
        on_acknowledge=lambda: None,
        on_pause=lambda minutes: None,
        on_alarm_toggle=lambda: None,
        on_close=lambda: None,
    )
    root.update_idletasks()

    backdrop = parts["backdrop"]
    assert backdrop.cget("image") is art_image
    assert _full_bleed(backdrop)

    children = parent.winfo_children()
    stacking = [str(child) for child in children]
    assert str(backdrop) in stacking

    # Regression for C1: nothing opaque may be stacked full-bleed over the art.
    covering = [
        child
        for child in children
        if child is not backdrop
        and _full_bleed(child)
        and stacking.index(str(child)) > stacking.index(str(backdrop))
    ]
    assert covering == []

    # And specifically no transparent CTkFrame (which CTk paints opaque anyway).
    transparent_frames = [
        child
        for child in children
        if isinstance(child, ctk.CTkFrame)
        and getattr(child, "_fg_color", None) == "transparent"
    ]
    assert transparent_frames == []

    for panel in (parts["header"], parts["controls"]):
        assert getattr(panel, "_fg_color", None) != "transparent"
        assert not _full_bleed(panel)

    parent.destroy()


def test_alert_surface_without_art_still_builds(ctk_root):
    ctk, root = ctk_root
    parent = ctk.CTkFrame(root, width=420, height=300)
    parent.pack()
    parts = build_health_alert_surface(
        parent,
        theme=get_theme("dark"),
        group=GROUP,
        art_image=None,
        on_acknowledge=lambda: None,
        on_pause=lambda minutes: None,
        on_alarm_toggle=lambda: None,
        on_close=lambda: None,
    )
    root.update_idletasks()
    assert parts["art_image"] is None
    assert parts["backdrop"].cget("text").startswith("Canister offline")
    parent.destroy()
