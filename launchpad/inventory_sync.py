from __future__ import annotations

import re


def is_flashcopy_target_name(name: str) -> bool:
    text = str(name or "").strip()
    if not text:
        return False
    # Matches *_snap, *_snapN, *_Snap1, and ..._snap_...
    return bool(re.search(r"(?i)(^|_)snap\d*(_|$)", text))
