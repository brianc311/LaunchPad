"""Export Array FlashCopy CG summary rows to Excel."""

from __future__ import annotations

from io import BytesIO
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

SUMMARY_HEADERS: tuple[str, ...] = (
    "Name",
    "Status",
    "Maps",
    "Host maps",
    "Size",
    "Policy",
    "Snaps/week",
)

SUMMARY_FIELDS: tuple[str, ...] = (
    "name",
    "status",
    "fc_map_count",
    "host_map_count",
    "total_size",
    "policy",
    "snaps_per_week",
)

_SHEET_NAME = "FC CG Summary"


def _rows(items: list[dict[str, Any]], fields: tuple[str, ...]) -> list[tuple[Any, ...]]:
    return [tuple(item.get(field, "") for field in fields) for item in items]


def _write_sheet(
    worksheet,
    headers: tuple[str, ...],
    rows: list[tuple[Any, ...]],
) -> None:
    fill = PatternFill("solid", fgColor="1F4E79")
    font = Font(bold=True, color="FFFFFF")
    border = Border(
        left=Side(style="thin", color="B4C6E7"),
        right=Side(style="thin", color="B4C6E7"),
        top=Side(style="thin", color="B4C6E7"),
        bottom=Side(style="thin", color="B4C6E7"),
    )
    for column, title in enumerate(headers, start=1):
        cell = worksheet.cell(row=1, column=column, value=title)
        cell.fill = fill
        cell.font = font
        cell.alignment = Alignment(horizontal="center", wrap_text=True)
        cell.border = border
    for row_index, row in enumerate(rows, start=2):
        for column, value in enumerate(row, start=1):
            cell = worksheet.cell(row=row_index, column=column, value=value)
            cell.alignment = Alignment(vertical="top", wrap_text=True)
            cell.border = border
    worksheet.freeze_panes = "A2"
    for index, title in enumerate(headers, start=1):
        worksheet.column_dimensions[get_column_letter(index)].width = max(
            12, min(42, len(title) + 2)
        )
    if rows:
        last_column = get_column_letter(len(headers))
        worksheet.auto_filter.ref = f"A1:{last_column}{len(rows) + 1}"


def export_fc_cg_summary_xlsx(rows: list[dict]) -> bytes:
    """Return a workbook with one FC CG Summary sheet."""
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = _SHEET_NAME
    _write_sheet(sheet, SUMMARY_HEADERS, _rows(rows, SUMMARY_FIELDS))

    output = BytesIO()
    workbook.save(output)
    return output.getvalue()
