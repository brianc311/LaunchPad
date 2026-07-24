"""Export Health Dashboard summary rows to Excel."""

from __future__ import annotations

from io import BytesIO
from typing import Any, Mapping

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

HEALTH_SUMMARY_HEADERS = (
    "Card",
    "Host / Site IP",
    "Profile / Model",
    "Monitor",
    "Status",
    "Issue count",
)


def _monitor_on(card_id: int, monitor_enabled: Mapping[int | str, bool]) -> bool:
    if card_id in monitor_enabled:
        return bool(monitor_enabled[card_id])
    return bool(monitor_enabled.get(str(card_id), False))


def derive_health_status(
    card: dict[str, Any],
    *,
    monitor_enabled: Mapping[int | str, bool],
) -> str:
    card_id = int(card.get("id", 0))
    if not _monitor_on(card_id, monitor_enabled):
        return "monitoring off"
    issues = card.get("health_issues") or []
    if issues:
        return "has issues"
    return "healthy"


def profile_or_model(card: dict[str, Any]) -> str:
    model = str(card.get("model") or "").strip()
    if model:
        return model
    return str(card.get("device_profile") or "").strip()


def health_summary_row(
    card: dict[str, Any],
    *,
    monitor_enabled: Mapping[int | str, bool],
) -> tuple[str, str, str, str, str, int]:
    card_id = int(card.get("id", 0))
    monitor_on = _monitor_on(card_id, monitor_enabled)
    issues = card.get("health_issues") or []
    return (
        str(card.get("name") or ""),
        str(card.get("host") or ""),
        profile_or_model(card),
        "on" if monitor_on else "off",
        derive_health_status(card, monitor_enabled=monitor_enabled),
        len(issues),
    )


def filter_health_summary_cards(
    cards: list[dict[str, Any]],
    *,
    card_id: int | None = None,
) -> list[dict[str, Any]]:
    if card_id is None:
        return list(cards)
    return [card for card in cards if int(card.get("id", -1)) == card_id]


def _summary_rows(
    cards: list[dict[str, Any]],
    *,
    monitor_enabled: Mapping[int | str, bool],
) -> list[tuple[str, str, str, str, str, int]]:
    sorted_cards = sorted(
        cards,
        key=lambda card: str(card.get("name") or "").lower(),
    )
    return [
        health_summary_row(card, monitor_enabled=monitor_enabled)
        for card in sorted_cards
    ]


def _styled_summary_workbook(rows: list[tuple[str, str, str, str, str, int]]) -> Workbook:
    wb = Workbook()
    ws = wb.active
    ws.title = "Summary"

    header_fill = PatternFill("solid", fgColor="1F4E79")
    header_font = Font(bold=True, color="FFFFFF", size=11)
    alt_fill = PatternFill("solid", fgColor="D9E8F5")
    thin = Side(style="thin", color="B4C6E7")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    for col, title in enumerate(HEALTH_SUMMARY_HEADERS, start=1):
        cell = ws.cell(row=1, column=col, value=title)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = border

    for row_idx, row in enumerate(rows, start=2):
        for col_idx, value in enumerate(row, start=1):
            cell = ws.cell(row=row_idx, column=col_idx, value=value)
            cell.border = border
            cell.alignment = Alignment(vertical="top", wrap_text=True)
            if row_idx % 2 == 0:
                cell.fill = alt_fill

    widths = (24, 18, 28, 10, 16, 12)
    for col, width in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(col)].width = width

    ws.freeze_panes = "A2"
    if rows:
        ws.auto_filter.ref = (
            f"A1:{get_column_letter(len(HEALTH_SUMMARY_HEADERS))}{len(rows) + 1}"
        )
    return wb


def build_health_summary_workbook(
    cards: list[dict[str, Any]],
    *,
    monitor_enabled: Mapping[int | str, bool],
) -> bytes:
    rows = _summary_rows(cards, monitor_enabled=monitor_enabled)
    wb = _styled_summary_workbook(rows)
    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
