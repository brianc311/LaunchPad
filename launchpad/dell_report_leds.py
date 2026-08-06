"""Utilization LED styling for Dell Report (green / yellow at 80%)."""

from __future__ import annotations

GREEN_FILL = "22C55E"
AMBER_FILL = "F59E0B"
# Kept for older call sites / docs; no longer used for primary util LEDs.
RED_FILL = "EF4444"

UTIL_YELLOW_THRESHOLD = 0.80


def utilization_led_fill(utilization: float | None) -> str | None:
    """utilization is 0..1 fraction.

    <0.80 → green; ≥0.80 → yellow/amber. None/invalid → None.
    """
    if utilization is None or not (0.0 <= utilization <= 1.0):
        return None
    if utilization < UTIL_YELLOW_THRESHOLD:
        return GREEN_FILL
    return AMBER_FILL
