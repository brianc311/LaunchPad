import re

DEFAULT_GLOW = "#FF6B00"

_HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


def normalize_color(value: str, fallback: str = DEFAULT_GLOW) -> str:
    if not value:
        return fallback
    cleaned = value.strip()
    if cleaned.count("#") > 1:
        parts = [part for part in cleaned.split("#") if part]
        if parts:
            cleaned = f"#{parts[0][:6]}"
    if _HEX_RE.match(cleaned):
        return cleaned.upper()
    return fallback


def ctk_color(value: str, fallback: str = DEFAULT_GLOW) -> tuple[str, str]:
    color = normalize_color(value, fallback)
    return color, color
