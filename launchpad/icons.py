from __future__ import annotations

DEFAULT_ICONS_BY_TYPE = {
    "ssh": "terminal",
    "rdp": "desktop",
    "web": "globe",
}

ICON_CHOICES: dict[str, str] = {
    "terminal": "⌨",
    "server": "🖥",
    "desktop": "🖳",
    "globe": "🌐",
    "cloud": "☁",
    "router": "📡",
    "database": "🗄",
    "lock": "🔒",
    "star": "⭐",
    "fire": "🔥",
    "bolt": "⚡",
    "shield": "🛡",
    "linux": "🐧",
    "windows": "🪟",
    "link": "🔗",
    "code": "💻",
    "monitor": "🖥",
    "phone": "📱",
    "mail": "✉",
    "chart": "📊",
}


def resolve_icon(icon: str, card_type: str) -> str:
    if icon and icon != "default" and icon in ICON_CHOICES:
        return ICON_CHOICES[icon]
    fallback = DEFAULT_ICONS_BY_TYPE.get(card_type, "terminal")
    return ICON_CHOICES.get(fallback, "●")


def icon_menu_labels() -> list[str]:
    return list(ICON_CHOICES.keys())
