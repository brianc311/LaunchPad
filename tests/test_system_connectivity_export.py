from io import BytesIO
import zipfile
from openpyxl import load_workbook
from launchpad.system_connectivity_export import (
    export_system_connectivity_csv_zip,
    export_system_connectivity_xlsx,
    filter_payload_by_card_id,
)


def _sample():
    row_a = {
        "card_id": 1, "site": "Hartford", "card_name": "Hartford", "host": "10.0.0.1",
        "vendor": "ibm", "profile": "flashsystem_7200", "configured": "yes",
        "status": "enabled", "details": "10.1.1.1", "error": "",
    }
    row_b = {**row_a, "card_id": 2, "site": "Primera", "card_name": "Primera", "host": "10.0.0.2", "vendor": "hpe"}
    return {
        "call_home": [row_a, row_b],
        "dns": [row_a],
        "snmp": [],
        "ntp": [row_a],
        "errors": [],
    }


def test_filter_by_card_id():
    scoped = filter_payload_by_card_id(_sample(), card_id=1)
    assert len(scoped["call_home"]) == 1
    assert scoped["call_home"][0]["card_name"] == "Hartford"


def test_xlsx_four_sheets():
    body = export_system_connectivity_xlsx(_sample())
    wb = load_workbook(BytesIO(body))
    assert wb.sheetnames == ["Call Home", "DNS", "SNMP", "NTP"]


def test_csv_zip_members():
    body = export_system_connectivity_csv_zip(_sample())
    with zipfile.ZipFile(BytesIO(body)) as zf:
        names = set(zf.namelist())
    assert names == {"call_home.csv", "dns.csv", "snmp.csv", "ntp.csv"}
