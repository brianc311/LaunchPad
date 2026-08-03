"""Connection Dashboard collapsible array rail helpers."""

from __future__ import annotations

import webbrowser
from typing import Any

from launchpad.host_volume_health import resolve_gui_url

SETTING_ARRAY_RAIL_COLLAPSED = "dashboard_array_rail_collapsed"


def filter_dashboard_cards(cards: list[Any], *, query: str = "") -> list[Any]:
    query = query.strip().lower()
    return [
        card
        for card in cards
        if not query
        or query in card.name.lower()
        or query in card.host.lower()
        or query in card.category.lower()
        or query in (getattr(card, "serial_number", "") or "").lower()
    ]


def rail_gui_url(card: Any) -> str:
    return resolve_gui_url(
        str(getattr(card, "url", "") or ""),
        str(getattr(card, "host", "") or ""),
    )


def can_open_rail_gui(card: Any) -> bool:
    return bool(rail_gui_url(card))


def rail_row_title(card: Any) -> str:
    return str(getattr(card, "name", "") or "").strip() or "Unnamed"


def rail_row_subtitle(card: Any) -> str:
    host = str(getattr(card, "host", "") or "").strip()
    if host:
        return host
    return str(getattr(card, "url", "") or "").strip()


def open_rail_gui(card: Any) -> str:
    url = rail_gui_url(card)
    if not url:
        raise ValueError("No Host or URL on this card — set Host or URL in Admin.")
    webbrowser.open(url)
    return "Opened GUI"


def collapsed_from_setting(raw: str | None) -> bool:
    return str(raw or "").strip().lower() == "true"


def setting_from_collapsed(collapsed: bool) -> str:
    return "true" if collapsed else "false"
