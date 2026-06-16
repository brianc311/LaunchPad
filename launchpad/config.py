import os
from pathlib import Path

APP_NAME = "LaunchPad"
APP_VERSION = "1.0.0"
DEFAULT_APP_NAME = APP_NAME

APP_DATA_DIR = Path(os.environ.get("APPDATA", Path.home())) / APP_NAME
DB_PATH = APP_DATA_DIR / "launchpad.db"
TEMP_DIR = APP_DATA_DIR / "temp"
BRANDING_DIR = APP_DATA_DIR / "branding"

DEFAULT_GLOW_COLOR = "#FF6B00"
DEFAULT_CATEGORY = "General"

CARD_TYPES = ("ssh", "rdp", "web")
