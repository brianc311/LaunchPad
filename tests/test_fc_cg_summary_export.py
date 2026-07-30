from io import BytesIO

from openpyxl import load_workbook

from launchpad.fc_cg_summary_export import SUMMARY_FIELDS, SUMMARY_HEADERS, export_fc_cg_summary_xlsx


def test_summary_headers_include_flash_time_and_progress_after_status():
    assert SUMMARY_HEADERS == (
        "Name",
        "Status",
        "Flash time",
        "Progress",
        "Maps",
        "Host maps",
        "Size",
        "Policy",
        "Snaps/week",
    )
    assert SUMMARY_FIELDS == (
        "name",
        "status",
        "flash_time",
        "progress_pct",
        "fc_map_count",
        "host_map_count",
        "total_size",
        "policy",
        "snaps_per_week",
    )


def test_export_fc_cg_summary_xlsx_sheet_headers_and_rows():
    rows = [
        {
            "name": "AAN1_FC",
            "status": "idle_or_copied",
            "flash_time": "2026-07-30 10:00:00",
            "progress_pct": None,
            "fc_map_count": 84,
            "host_map_count": 48,
            "total_size": "5.8 TB",
            "policy": "",
            "snaps_per_week": 0.44,
        },
        {
            "name": "COPYING_CG",
            "status": "copying",
            "flash_time": "",
            "progress_pct": 40,
            "fc_map_count": 2,
            "host_map_count": 0,
            "total_size": "10 GB",
            "policy": "weekly",
            "snaps_per_week": 1,
        },
    ]
    body = export_fc_cg_summary_xlsx(rows)
    wb = load_workbook(BytesIO(body))
    assert wb.sheetnames == ["FC CG Summary"]
    ws = wb["FC CG Summary"]
    assert [cell.value for cell in ws[1]] == list(SUMMARY_HEADERS)
    assert ws["A2"].value == "AAN1_FC"
    assert ws["C2"].value == "2026-07-30 10:00:00"
    assert ws["D2"].value in ("", None)
    assert ws["E2"].value == 84
    assert ws["G2"].value == "5.8 TB"
    assert ws["I2"].value == 0.44
    assert ws["C3"].value in ("", None)
    assert ws["D3"].value == "40%"
