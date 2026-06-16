import os
import shutil
from pathlib import Path

from PIL import Image

from launchpad.config import APP_NAME, BRANDING_DIR, DEFAULT_APP_NAME

SETTING_APP_NAME = "app_name"
SETTING_LOGO_FILE = "logo_file"


def get_app_name(db) -> str:
    name = (db.get_setting(SETTING_APP_NAME, DEFAULT_APP_NAME) or "").strip()
    return name or DEFAULT_APP_NAME


def logo_path(db) -> Path | None:
    filename = (db.get_setting(SETTING_LOGO_FILE, "") or "").strip()
    if not filename:
        return None
    path = BRANDING_DIR / filename
    return path if path.exists() else None


def save_logo(db, source: str | Path) -> Path:
    BRANDING_DIR.mkdir(parents=True, exist_ok=True)
    source_path = Path(source)
    if not source_path.exists():
        raise FileNotFoundError(f"Logo file not found: {source_path}")

    dest = BRANDING_DIR / "logo.png"
    with Image.open(source_path) as image:
        image = image.convert("RGBA")
        max_size = (256, 256)
        image.thumbnail(max_size, Image.Resampling.LANCZOS)
        image.save(dest, format="PNG")

    db.set_setting(SETTING_LOGO_FILE, dest.name)
    return dest


def clear_logo(db) -> None:
    path = logo_path(db)
    if path and path.exists():
        path.unlink(missing_ok=True)
    db.set_setting(SETTING_LOGO_FILE, "")


def save_app_name(db, name: str) -> str:
    cleaned = name.strip() or DEFAULT_APP_NAME
    db.set_setting(SETTING_APP_NAME, cleaned)
    return cleaned


def load_ctk_logo(db, size: tuple[int, int] = (36, 36)):
    path = logo_path(db)
    if not path:
        return None
    try:
        import customtkinter as ctk

        image = Image.open(path)
        return ctk.CTkImage(light_image=image, dark_image=image, size=size)
    except OSError:
        return None


def load_ctk_logo_large(db, max_height: int = 72):
    path = logo_path(db)
    if not path:
        return None
    try:
        import customtkinter as ctk

        image = Image.open(path)
        width, height = image.size
        if height > max_height and height > 0:
            scale = max_height / height
            size = (max(1, int(width * scale)), max_height)
        else:
            size = (width, height)
        return ctk.CTkImage(light_image=image, dark_image=image, size=size)
    except OSError:
        return None


def window_title(db, suffix: str = "") -> str:
    name = get_app_name(db)
    if suffix:
        return f"{name} — {suffix}"
    return name
