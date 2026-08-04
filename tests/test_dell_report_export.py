from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO

from openpyxl import load_workbook

from launchpad.dell_report_export import (
    STUB_SHEET_NAMES,
    build_dell_report_workbook,
    bytes_to_gib,
    workbook_to_bytes,
)
from launchpad.dell_report_leds import AMBER_FILL, GREEN_FILL, RED_FILL


def _minimal_row(**overrides) -> dict:
    row = {
        "facility": "Data center -WAG1",
        "array_name": "V7K001",
        "model": "FlashSystem 9200",
        "prior_usable_gib": 100.0,
        "prior_used_gib": 50.0,
        "prior_util": 0.5,
        "curr_usable_gib": 100.0,
        "curr_used_gib": 60.0,
        "curr_util": 0.6,
        "weekly_growth": 0.2,
    }
    row.update(overrides)
    return row


def test_bytes_to_gib():
    assert bytes_to_gib(0) == 0.0
    assert bytes_to_gib(1024**3) == 1.0
    assert bytes_to_gib(2.5 * 1024**3) == 2.5


def test_stub_sheet_names_include_required_tabs():
    names = " ".join(STUB_SHEET_NAMES)
    for token in ("PowerMax", "PowerStore", "NetApp", "Data Domain", "ECS"):
        assert token in names


def test_workbook_has_ibm_hp_and_stub():
    wb = build_dell_report_workbook(
        ibm_rows=[_minimal_row()],
        hp_rows=[_minimal_row(array_name="3PAR001", model="HPE 3PAR 8450")],
    )
    assert "IBM Report" in wb.sheetnames
    assert "HP Report" in wb.sheetnames
    assert any("PowerMax" in name for name in wb.sheetnames)
    stub = wb[[name for name in wb.sheetnames if "PowerMax" in name][0]]
    assert stub.max_row <= 5


def test_home_sheet_title():
    wb = build_dell_report_workbook(ibm_rows=[], hp_rows=[])
    home = wb.worksheets[0]
    title_cells = [
        str(cell.value)
        for row in home.iter_rows(max_row=5)
        for cell in row
        if cell.value
    ]
    joined = " ".join(title_cells)
    assert "Dell Technologies Managed Services" in joined
    assert "Capacity Management Report" in joined


def test_rows_sorted_by_facility_then_array_name():
    wb = build_dell_report_workbook(
        ibm_rows=[
            _minimal_row(facility="Z-facility", array_name="Z-array"),
            _minimal_row(facility="A-facility", array_name="B-array"),
            _minimal_row(facility="A-facility", array_name="A-array"),
        ],
        hp_rows=[],
    )
    ws = wb["IBM Report"]
    data_start = _data_start_row(ws)
    facilities = [ws.cell(row, 1).value for row in range(data_start, ws.max_row + 1)]
    arrays = [ws.cell(row, 2).value for row in range(data_start, ws.max_row + 1)]
    assert facilities == ["A-facility", "A-facility", "Z-facility"]
    assert arrays == ["A-array", "B-array", "Z-array"]


def test_gib_and_utilization_values_written():
    wb = build_dell_report_workbook(
        ibm_rows=[_minimal_row()],
        hp_rows=[],
        report_date=datetime(2026, 6, 15, tzinfo=timezone.utc),
    )
    ws = wb["IBM Report"]
    row = _data_start_row(ws)
    assert ws.cell(row, 1).value == "Data center -WAG1"
    assert ws.cell(row, 2).value == "V7K001"
    assert ws.cell(row, 3).value == "FlashSystem 9200"
    assert ws.cell(row, 4).value == 100.0
    assert ws.cell(row, 5).value == 50.0
    assert ws.cell(row, 6).value == 0.5
    assert ws.cell(row, 7).value == 100.0
    assert ws.cell(row, 8).value == 60.0
    assert ws.cell(row, 9).value == 0.6
    assert ws.cell(row, 10).value == 0.2
    assert ws.cell(row, 6).number_format == "0.0%"
    assert ws.cell(row, 9).number_format == "0.0%"
    assert ws.cell(row, 10).number_format == "0.0%"


def test_utilization_conditional_formatting():
    wb = build_dell_report_workbook(
        ibm_rows=[_minimal_row()],
        hp_rows=[_minimal_row()],
    )
    for sheet_name in ("IBM Report", "HP Report"):
        ws = wb[sheet_name]
        rules = [rule for group in ws.conditional_formatting for rule in group.rules]
        cell_is_rules = [rule for rule in rules if getattr(rule, "type", None) == "cellIs"]
        assert len(cell_is_rules) >= 3
        fills = {
            rule.dxf.fill.fgColor.rgb[-6:].upper()
            for rule in cell_is_rules
            if rule.dxf is not None
            and rule.dxf.fill is not None
            and rule.dxf.fill.fgColor is not None
            and rule.dxf.fill.fgColor.rgb is not None
        }
        assert GREEN_FILL in fills
        assert AMBER_FILL in fills
        assert RED_FILL in fills


def test_workbook_to_bytes_roundtrip():
    wb = build_dell_report_workbook(
        ibm_rows=[_minimal_row()],
        hp_rows=[_minimal_row(array_name="3PAR001")],
    )
    payload = workbook_to_bytes(wb)
    assert isinstance(payload, bytes)
    assert payload[:2] == b"PK"
    loaded = load_workbook(BytesIO(payload))
    assert "IBM Report" in loaded.sheetnames
    assert "HP Report" in loaded.sheetnames


def _data_start_row(ws) -> int:
    for row in range(1, ws.max_row + 1):
        if ws.cell(row, 1).value == "Facility":
            return row + 1
    raise AssertionError("Facility header row not found")
