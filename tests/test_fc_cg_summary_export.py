from io import BytesIO

from openpyxl import load_workbook

from launchpad.fc_cg_summary_export import SUMMARY_HEADERS, export_fc_cg_summary_xlsx


def test_export_fc_cg_summary_xlsx_sheet_headers_and_rows():
    rows = [
        {
            "name": "AAN1_FC",
            "status": "idle_or_copied",
            "fc_map_count": 84,
            "host_map_count": 48,
            "total_size": "5.8 TB",
            "policy": "",
            "snaps_per_week": 0.44,
        }
    ]
    body = export_fc_cg_summary_xlsx(rows)
    wb = load_workbook(BytesIO(body))
    assert wb.sheetnames == ["FC CG Summary"]
    ws = wb["FC CG Summary"]
    assert [cell.value for cell in ws[1]] == list(SUMMARY_HEADERS)
    assert ws["A2"].value == "AAN1_FC"
    assert ws["C2"].value == 84
    assert ws["E2"].value == "5.8 TB"
    assert ws["G2"].value == 0.44
