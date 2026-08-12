"""Shared layout for the desktop health-alert surfaces drawn over PNG art.

CustomTkinter has no alpha compositing: a widget with ``fg_color="transparent"``
still paints its master's colour, so a full-bleed frame stacked over the art label
hides the art entirely. Everything here therefore draws the alert text *into* the
art label (``compound="center"``) over a Pillow-darkened copy of the art, and keeps
opaque widgets confined to the header and control bars.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import customtkinter as ctk
from PIL import Image

SCRIM_ALPHA = 165
SNOOZE_MINUTES = (5, 10, 15, 20)


def apply_art_scrim(image: Image.Image, *, alpha: int = SCRIM_ALPHA) -> Image.Image:
    """Darken art so alert text drawn on top of it stays legible."""
    base = image.convert("RGBA")
    scrim = Image.new("RGBA", base.size, (0, 0, 0, max(0, min(255, int(alpha)))))
    return Image.alpha_composite(base, scrim)


def load_alert_art_image(
    art_path: Path | None,
    size: tuple[int, int],
    *,
    alpha: int = SCRIM_ALPHA,
) -> ctk.CTkImage | None:
    if art_path is None:
        return None
    try:
        art = apply_art_scrim(Image.open(art_path), alpha=alpha)
    except OSError:
        return None
    return ctk.CTkImage(light_image=art, dark_image=art, size=size)


def format_alert_issue_text(group: dict[str, Any], *, limit: int = 3) -> str:
    issues = group.get("issues") or []
    lines = [
        str(issue.get("message") or "").strip()
        for issue in issues[:limit]
        if str(issue.get("message") or "").strip()
    ]
    remaining = max(0, len(issues) - limit)
    if remaining:
        lines.append(f"+{remaining} more")
    return "\n".join(lines) or "Critical health issue"


def build_health_alert_surface(
    parent,
    *,
    theme: dict,
    group: dict[str, Any],
    art_image: ctk.CTkImage | None,
    on_acknowledge: Callable[[], None],
    on_pause: Callable[[int], None],
    on_alarm_toggle: Callable[[], None],
    on_close: Callable[[], None],
    alarm_muted: bool = False,
    title: str = "ALERT",
    title_size: int = 20,
    message_size: int = 12,
    wraplength: int = 320,
    button_height: int = 26,
) -> dict[str, Any]:
    """Place the alert surface into ``parent`` and return its parts.

    The art label fills ``parent``; the header and control bars are opaque but only
    cover a band at the top and bottom, so the art stays visible in between.
    """
    card_name = str(group.get("card_name") or f"Card {group.get('card_id')}")
    issue_text = format_alert_issue_text(group)

    backdrop = ctk.CTkLabel(
        parent,
        text=issue_text,
        image=art_image,
        compound="center",
        font=ctk.CTkFont(size=message_size, weight="bold"),
        text_color="#FFFFFF" if art_image is not None else theme["text"],
        fg_color=theme["surface"] if art_image is None else "transparent",
        wraplength=wraplength,
        justify="center",
    )
    backdrop.place(relx=0, rely=0, relwidth=1, relheight=1)

    header = ctk.CTkFrame(parent, fg_color=theme["surface"], corner_radius=0)
    header.place(relx=0, rely=0, relwidth=1)
    ctk.CTkLabel(
        header,
        text=title,
        font=ctk.CTkFont(size=title_size, weight="bold"),
        text_color=theme["danger"],
        anchor="w",
    ).pack(side="left", padx=(12, 8), pady=6)
    ctk.CTkLabel(
        header,
        text=card_name,
        font=ctk.CTkFont(size=max(11, title_size - 6), weight="bold"),
        text_color=theme["accent"],
        anchor="e",
    ).pack(side="right", padx=(8, 12), pady=6)

    controls = ctk.CTkFrame(parent, fg_color=theme["surface"], corner_radius=0)
    controls.place(relx=0, rely=1.0, relwidth=1, anchor="sw")

    primary = ctk.CTkFrame(controls, fg_color=theme["surface"])
    primary.pack(fill="x", padx=10, pady=(8, 2))
    ctk.CTkButton(
        primary,
        text="Suppress",
        height=button_height,
        fg_color=theme["accent"],
        hover_color=theme["accent_soft"],
        command=on_acknowledge,
    ).pack(side="left", fill="x", expand=True, padx=(0, 3))
    ctk.CTkButton(
        primary,
        text="Alarm on" if alarm_muted else "Alarm off",
        height=button_height,
        fg_color=theme["surface_alt"],
        hover_color=theme["border"],
        command=on_alarm_toggle,
    ).pack(side="left", fill="x", expand=True, padx=(3, 0))

    snooze = ctk.CTkFrame(controls, fg_color=theme["surface"])
    snooze.pack(fill="x", padx=10, pady=2)
    for minutes in SNOOZE_MINUTES:
        ctk.CTkButton(
            snooze,
            text=f"Snooze {minutes}",
            height=max(22, button_height - 2),
            font=ctk.CTkFont(size=10),
            fg_color=theme["surface_alt"],
            hover_color=theme["border"],
            command=lambda m=minutes: on_pause(m),
        ).pack(side="left", fill="x", expand=True, padx=2)

    close_button = ctk.CTkButton(
        controls,
        text="Close",
        height=max(22, button_height - 2),
        fg_color=theme["surface_alt"],
        hover_color=theme["border"],
        command=on_close,
    )
    close_button.pack(fill="x", padx=10, pady=(2, 8))

    return {
        "backdrop": backdrop,
        "header": header,
        "controls": controls,
        "close": close_button,
        "art_image": art_image,
    }
