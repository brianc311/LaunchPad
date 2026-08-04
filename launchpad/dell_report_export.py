"""Build Dell Managed Services capacity report workbooks (.xlsx)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from io import BytesIO

from openpyxl import Workbook
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from launchpad.dell_report_leds import AMBER_FILL, GREEN_FILL, RED_FILL

REPORT_TITLE = "Dell Technologies Managed Services - Capacity Management Report"
HOME_SHEET_NAME = "Home"
IBM_SHEET_NAME = "IBM Report"
HP_SHEET_NAME = "HP Report"

STUB_SHEET_NAMES: list[str] = [
    "PowerMax Report",
    "PowerStore Report",
    "NetApp Report",
    "Data Domain Report",
    "ECS Report",
]

_DATA_COLUMNS = (
    ("facility", None),
    ("array_name", None),
    ("model", None),
    ("prior_usable_gib", "0.00"),
    ("prior_used_gib", "0.00"),
    ("prior_util", "0.0%"),
    ("curr_usable_gib", "0.00"),
    ("curr_used_gib", "0.00"),
    ("curr_util", "0.0%"),
    ("weekly_growth", "0.0%"),
)

_HEADER_LABELS = (
    "Facility",
    "Storage Array",
    "Model Number",
    "Usable (GiB)",
    "Used (GiB)",
    "Utilization %",
    "Usable (GiB)",
    "Used (GiB)",
    "Utilization %",
    "Weekly Growth %",
)

_UTIL_COLUMNS = (6, 9)
_GIB = 1024**3


def bytes_to_gib(num_bytes: float) -> float:
    return num_bytes / _GIB


def build_dell_report_workbook(
    *,
    ibm_rows: list[dict],
    hp_rows: list[dict],
    report_date: datetime | None = None,
) -> Workbook:
    when = _coerce_utc(report_date)
    wb = Workbook()
    _build_home_sheet(wb.active, report_date=when)
    _build_data_sheet(wb.create_sheet(IBM_SHEET_NAME), ibm_rows, report_date=when)
    _build_data_sheet(wb.create_sheet(HP_SHEET_NAME), hp_rows, report_date=when)
    for name in STUB_SHEET_NAMES:
        _build_stub_sheet(wb.create_sheet(name), report_date=when)
    return wb


def workbook_to_bytes(wb: Workbook) -> bytes:
    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def _coerce_utc(when: datetime | None) -> datetime:
    if when is None:
        return datetime.now(timezone.utc)
    if when.tzinfo is None:
        return when.replace(tzinfo=timezone.utc)
    return when.astimezone(timezone.utc)


def _format_report_date(when: datetime) -> str:
    return when.strftime("%B %d, %Y")


def _prior_week_date(when: datetime) -> str:
    return _format_report_date(when - timedelta(days=7))


def _build_home_sheet(ws: Worksheet, *, report_date: datetime) -> None:
    ws.title = HOME_SHEET_NAME
    ws["A1"] = REPORT_TITLE
    ws["A1"].font = Font(bold=True, size=14)
    ws["A2"] = f"Report date: {_format_report_date(report_date)}"
    ws["A4"] = "Sheets"
    ws["A4"].font = Font(bold=True)
    row = 5
    for title in [IBM_SHEET_NAME, HP_SHEET_NAME, *STUB_SHEET_NAMES]:
        ws.cell(row=row, column=1, value=title)
        row += 1
    ws.column_dimensions["A"].width = 48


def _build_stub_sheet(ws: Worksheet, *, report_date: datetime) -> None:
    _write_sheet_header(ws, report_date=report_date)


def _build_data_sheet(
    ws: Worksheet,
    rows: list[dict],
    *,
    report_date: datetime,
) -> None:
    header_row = _write_sheet_header(ws, report_date=report_date)
    data_start = header_row + 1
    sorted_rows = sorted(
        rows,
        key=lambda row: (
            str(row.get("facility") or "").lower(),
            str(row.get("array_name") or "").lower(),
        ),
    )
    for offset, row in enumerate(sorted_rows):
        excel_row = data_start + offset
        for col, (key, number_format) in enumerate(_DATA_COLUMNS, start=1):
            value = row.get(key)
            cell = ws.cell(row=excel_row, column=col, value=value)
            if number_format is not None:
                cell.number_format = number_format
    if sorted_rows:
        _apply_utilization_formatting(ws, data_start, data_start + len(sorted_rows) - 1)


def _write_sheet_header(ws: Worksheet, *, report_date: datetime) -> int:
    ws["A1"] = "Home"
    ws["B1"] = REPORT_TITLE
    ws["B1"].font = Font(bold=True)
    ws["D2"] = _prior_week_date(report_date)
    ws["G2"] = _format_report_date(report_date)
    ws["D2"].alignment = Alignment(horizontal="center")
    ws["G2"].alignment = Alignment(horizontal="center")
    ws.merge_cells("D2:F2")
    ws.merge_cells("G2:I2")
    ws["D3"] = "Prior Week"
    ws["G3"] = "Current Week"
    ws["D3"].font = Font(bold=True)
    ws["G3"].font = Font(bold=True)
    ws["D3"].alignment = Alignment(horizontal="center")
    ws["G3"].alignment = Alignment(horizontal="center")
    ws.merge_cells("D3:F3")
    ws.merge_cells("G3:I3")
    header_row = 4
    for col, label in enumerate(_HEADER_LABELS, start=1):
        cell = ws.cell(row=header_row, column=col, value=label)
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="center", wrap_text=True)
    widths = (22, 24, 20, 14, 14, 14, 14, 14, 14, 16)
    for col, width in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(col)].width = width
    return header_row


def _apply_utilization_formatting(
    ws: Worksheet,
    start_row: int,
    end_row: int,
) -> None:
    green = PatternFill("solid", fgColor=GREEN_FILL)
    amber = PatternFill("solid", fgColor=AMBER_FILL)
    red = PatternFill("solid", fgColor=RED_FILL)
    for col in _UTIL_COLUMNS:
        column = get_column_letter(col)
        cell_range = f"{column}{start_row}:{column}{end_row}"
        ws.conditional_formatting.add(
            cell_range,
            CellIsRule(operator="lessThan", formula=["0.7"], fill=green, stopIfTrue=True),
        )
        ws.conditional_formatting.add(
            cell_range,
            CellIsRule(
                operator="between",
                formula=["0.7", "0.8999999999"],
                fill=amber,
                stopIfTrue=True,
            ),
        )
        ws.conditional_formatting.add(
            cell_range,
            CellIsRule(
                operator="greaterThanOrEqual",
                formula=["0.9"],
                fill=red,
                stopIfTrue=True,
            ),
        )
