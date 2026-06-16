THEMES = {
    "dark": {
        "mode": "dark",
        "bg": "#0B0F14",
        "surface": "#121821",
        "surface_alt": "#1A2230",
        "text": "#E8EDF5",
        "muted": "#8B98AB",
        "accent": "#FF6B00",
        "accent_soft": "#FF8533",
        "border": "#2A3444",
        "success": "#22C55E",
        "danger": "#EF4444",
    },
    "light": {
        "mode": "light",
        "bg": "#F3F6FA",
        "surface": "#FFFFFF",
        "surface_alt": "#EEF2F7",
        "text": "#111827",
        "muted": "#6B7280",
        "accent": "#FF6B00",
        "accent_soft": "#FF8533",
        "border": "#D1D5DB",
        "success": "#16A34A",
        "danger": "#DC2626",
    },
}


def get_theme(name: str) -> dict:
    return THEMES.get(name, THEMES["dark"])
