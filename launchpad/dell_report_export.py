"""Build Dell Managed Services capacity report workbooks (.xlsx)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from io import BytesIO
from typing import Any

from openpyxl import Workbook
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from launchpad.capacity_export import ExportSite
from launchpad.dell_report_facility import facility_from_name
from launchpad.dell_report_family import dell_report_family
from launchpad.dell_report_leds import AMBER_FILL, GREEN_FILL, RED_FILL, utilization_led_fill
from launchpad.dell_report_snapshots import (
    has_week_snapshot,
    iso_week_key,
    prior_and_current_for_card,
    upsert_week_snapshot,
    weekly_growth_fraction,
)
from launchpad.flashsystem_health import capacity_summary_from_pools

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


def collect_dell_report_rows(
    sites: list[ExportSite | dict[str, Any]],
    *,
    snapshot_store: dict,
    now: datetime | None = None,
) -> tuple[list[dict], list[dict], dict]:
    """Split ibm/hp rows from capacity_summary; upsert current week if missing;
    attach prior/current/growth; return (ibm_rows, hp_rows, updated_store)."""
    when = _coerce_utc(now)
    week = iso_week_key(when)
    captured_at = when.isoformat()
    store = dict(snapshot_store or {})
    ibm_rows: list[dict] = []
    hp_rows: list[dict] = []

    for site in sites:
        card_id = _site_value(site, "card_id")
        name = str(_site_value(site, "name") or "")
        device_profile = str(_site_value(site, "device_profile") or "")
        family = dell_report_family(device_profile)
        if family is None or card_id is None:
            continue

        summary = _capacity_summary_for_site(site)
        if not summary:
            continue

        total_bytes = float(summary.get("total_bytes") or 0)
        used_bytes = float(summary.get("used_bytes") or 0)
        if total_bytes <= 0:
            continue

        facility = facility_from_name(name)
        model = str(summary.get("name") or device_profile or "")
        array_name = name

        if not has_week_snapshot(store, card_id, week):
            store = upsert_week_snapshot(
                store,
                card_id=card_id,
                week=week,
                usable_bytes=total_bytes,
                used_bytes=used_bytes,
                model=model,
                facility=facility,
                family=family,
                array_name=array_name,
                captured_at=captured_at,
            )

        prior, current = prior_and_current_for_card(
            store, card_id, current_week=week
        )
        if current is None:
            continue

        row = _row_from_snapshots(prior, current)
        if family == "ibm":
            ibm_rows.append(row)
        else:
            hp_rows.append(row)

    return ibm_rows, hp_rows, store


def maybe_upsert_dell_snapshot_for_card(
    card: Any,
    *,
    snapshot_store: dict,
    now: datetime | None = None,
) -> dict:
    """Best-effort upsert for the current ISO week when missing."""
    when = _coerce_utc(now)
    week = iso_week_key(when)
    card_id = getattr(card, "card_id", None)
    name = str(getattr(card, "name", "") or "")
    device_profile = str(getattr(card, "device_profile", "") or "")
    family = dell_report_family(device_profile)
    if family is None or card_id is None:
        return snapshot_store

    from launchpad.flashsystem_health import analyze_health

    analysis = analyze_health(
        name,
        getattr(card, "command_results", None),
        getattr(card, "metrics", None),
    )
    summary = analysis.get("capacity_summary")
    pools = analysis.get("pools") or []
    if (not summary or not int(summary.get("total_bytes") or 0)) and pools:
        summary = capacity_summary_from_pools(pools) or summary
    if not summary:
        return snapshot_store

    total_bytes = float(summary.get("total_bytes") or 0)
    used_bytes = float(summary.get("used_bytes") or 0)
    if total_bytes <= 0:
        return snapshot_store

    if has_week_snapshot(snapshot_store, card_id, week):
        return snapshot_store

    return upsert_week_snapshot(
        snapshot_store,
        card_id=card_id,
        week=week,
        usable_bytes=total_bytes,
        used_bytes=used_bytes,
        model=str(summary.get("name") or device_profile or ""),
        facility=facility_from_name(name),
        family=family,
        array_name=name,
        captured_at=when.isoformat(),
    )


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


def _site_value(site: ExportSite | dict[str, Any], key: str) -> Any:
    if isinstance(site, dict):
        return site.get(key)
    return getattr(site, key, None)


def _capacity_summary_for_site(site: ExportSite | dict[str, Any]) -> dict[str, Any] | None:
    summary = _site_value(site, "capacity_summary")
    pools = _site_value(site, "pools") or []
    if (not summary or not int(summary.get("total_bytes") or 0)) and pools:
        summary = capacity_summary_from_pools(pools) or summary
    return summary if isinstance(summary, dict) else None


def _util_fraction(used_bytes: float, total_bytes: float) -> float | None:
    if total_bytes <= 0:
        return None
    return used_bytes / total_bytes


def _row_from_snapshots(prior: dict | None, current: dict) -> dict:
    curr_usable = float(current.get("usable_bytes") or 0)
    curr_used = float(current.get("used_bytes") or 0)
    growth = None
    prior_usable_gib = None
    prior_used_gib = None
    prior_util = None
    if prior is not None:
        prior_usable = float(prior.get("usable_bytes") or 0)
        prior_used = float(prior.get("used_bytes") or 0)
        prior_usable_gib = bytes_to_gib(prior_usable)
        prior_used_gib = bytes_to_gib(prior_used)
        prior_util = _util_fraction(prior_used, prior_usable)
        growth = weekly_growth_fraction(prior_used, curr_used)

    return {
        "facility": current.get("facility") or "",
        "array_name": current.get("array_name") or "",
        "model": current.get("model") or "",
        "prior_usable_gib": prior_usable_gib,
        "prior_used_gib": prior_used_gib,
        "prior_util": prior_util,
        "curr_usable_gib": bytes_to_gib(curr_usable),
        "curr_used_gib": bytes_to_gib(curr_used),
        "curr_util": _util_fraction(curr_used, curr_usable),
        "weekly_growth": growth,
    }


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
    _write_grouped_facility_rows(ws, rows, data_start=data_start)
    if rows:
        end_row = data_start + len(rows) - 1
        _apply_direct_utilization_fills(ws, data_start, end_row)
        _apply_utilization_formatting(ws, data_start, end_row)


def _write_grouped_facility_rows(
    ws: Worksheet,
    rows: list[dict],
    *,
    data_start: int,
) -> None:
    sorted_rows = sorted(
        rows,
        key=lambda row: (
            str(row.get("facility") or "").lower(),
            str(row.get("array_name") or "").lower(),
        ),
    )
    last_facility: str | None = None
    for offset, row in enumerate(sorted_rows):
        excel_row = data_start + offset
        facility = row.get("facility")
        if facility == last_facility:
            facility_value = None
        else:
            facility_value = facility
            last_facility = facility
        for col, (key, number_format) in enumerate(_DATA_COLUMNS, start=1):
            value = facility_value if key == "facility" else row.get(key)
            cell = ws.cell(row=excel_row, column=col, value=value)
            if number_format is not None:
                cell.number_format = number_format


def _apply_direct_utilization_fills(
    ws: Worksheet,
    start_row: int,
    end_row: int,
    util_columns: tuple[int, ...] = _UTIL_COLUMNS,
) -> None:
    for row in range(start_row, end_row + 1):
        for col in util_columns:
            cell = ws.cell(row=row, column=col)
            fill_color = utilization_led_fill(cell.value)
            if fill_color is not None:
                cell.fill = PatternFill("solid", fgColor=fill_color)


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
