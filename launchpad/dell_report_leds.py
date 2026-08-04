"""Utilization band → Excel fill color for Dell Report LED styling."""

from __future__ import annotations

GREEN_FILL = "22C55E"
AMBER_FILL = "F59E0B"
RED_FILL = "EF4444"


def utilization_led_fill(utilization: float | None) -> str | None:
    """utilization is 0..1 fraction. <0.70 → '22C55E'; <0.90 → 'F59E0B';
    else 'EF4444'. None/invalid → None."""
    if utilization is None or not (0.0 <= utilization <= 1.0):
        return None
    if utilization < 0.70:
        return GREEN_FILL
    if utilization < 0.90:
        return AMBER_FILL
    return RED_FILL
