"""Re-encode packaged health-alert art to overlay-appropriate size and weight.

The overlays render at 360x210 (card) and 640x360 (dialog), so shipping 1588x672
unoptimized PNGs costs the installer ~85 MB for no visible gain. Run from the repo
root: ``python tools/optimize_health_alert_art.py``.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image

DEFAULT_DIR = Path(__file__).resolve().parents[1] / "launchpad" / "resources" / "health-alerts"
DEFAULT_MAX_WIDTH = 960


def optimize(path: Path, *, max_width: int) -> tuple[int, int]:
    before = path.stat().st_size
    with Image.open(path) as source:
        image = source.convert("RGB")
        if image.width > max_width:
            height = max(1, round(image.height * max_width / image.width))
            image = image.resize((max_width, height), Image.LANCZOS)
        image.save(path, format="PNG", optimize=True)
    return before, path.stat().st_size


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", type=Path, default=DEFAULT_DIR)
    parser.add_argument("--max-width", type=int, default=DEFAULT_MAX_WIDTH)
    args = parser.parse_args()

    total_before = 0
    total_after = 0
    for path in sorted(args.dir.glob("*.png")):
        before, after = optimize(path, max_width=args.max_width)
        total_before += before
        total_after += after
        print(f"{path.name}: {before / 1_048_576:.2f} MB -> {after / 1_048_576:.2f} MB")
    print(
        f"total: {total_before / 1_048_576:.1f} MB -> {total_after / 1_048_576:.1f} MB"
    )


if __name__ == "__main__":
    main()
