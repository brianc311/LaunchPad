import csv
import zipfile
from io import BytesIO, StringIO
from pathlib import Path

from launchpad import health_server as health_server_mod
from launchpad.fc_wwpn_report import FC_WWPN_REPORT_HTML
from launchpad.fc_wwpn_export import (
    MAPPINGS_FABRIC_HEADERS,
    MAPPINGS_HOST_HEADERS,
    MAPPINGS_LUN_HEADERS,
    build_fc_mappings_workbook,
    export_fc_mappings_csv_zip,
    mappings_rows_from_card,
)


def _fixture_card() -> dict:
    return {
        "id": 7,
        "name": "Carolina, PR",
        "fc_hosts": [
            {
                "host_id": "1",
                "host_name": "APR1",
                "status": "online",
                "protocol": "scsi",
                "wwpn_count": "2",
                "wwpns": "AABB",
            }
        ],
        "fc_mappings": [
            {
                "host_name": "APR1",
                "vdisk_name": "vol1",
                "scsi_id": "0",
                "vdisk_id": "10",
                "host_wwpns": "AABB",
            }
        ],
        "fc_fabric": [
            {
                "node_name": "node1",
                "local_wwpn": "500507681018C3FB",
                "remote_wwpn": "C050760C0A500008",
                "host_name": "APR1",
                "state": "active",
                "local_port": "4",
            }
        ],
    }


def test_mappings_rows_from_card_matches_modal_columns():
    hosts, maps, fabric = mappings_rows_from_card(_fixture_card())
    assert hosts == [("1", "APR1", "online", "scsi", "2", "AABB")]
    assert maps == [("APR1", "vol1", "0", "10", "AABB")]
    assert fabric == [
        ("node1", "500507681018C3FB", "C050760C0A500008", "APR1", "active", "4")
    ]


def test_build_fc_mappings_workbook_has_three_sheets():
    wb, h, m, f = build_fc_mappings_workbook([_fixture_card()])
    assert wb.sheetnames == ["Hosts", "LUN Mappings", "Fabric Logins"]
    assert (h, m, f) == (1, 1, 1)
    assert [c.value for c in wb["Hosts"][1]] == list(MAPPINGS_HOST_HEADERS)
    assert [c.value for c in wb["LUN Mappings"][1]] == list(MAPPINGS_LUN_HEADERS)
    assert [c.value for c in wb["Fabric Logins"][1]] == list(MAPPINGS_FABRIC_HEADERS)
    assert wb["Hosts"]["B2"].value == "APR1"
    assert wb["Fabric Logins"]["A2"].value == "node1"


def test_export_fc_mappings_csv_zip_contains_three_files():
    raw = export_fc_mappings_csv_zip([_fixture_card()])
    with zipfile.ZipFile(BytesIO(raw)) as archive:
        assert set(archive.namelist()) == {
            "hosts.csv",
            "lun_mappings.csv",
            "fabric_logins.csv",
        }
        hosts = list(csv.reader(StringIO(archive.read("hosts.csv").decode("utf-8-sig"))))
        assert hosts[0] == list(MAPPINGS_HOST_HEADERS)
        assert hosts[1][1] == "APR1"
        fabric = list(
            csv.reader(StringIO(archive.read("fabric_logins.csv").decode("utf-8-sig")))
        )
        assert fabric[0] == list(MAPPINGS_FABRIC_HEADERS)
        assert fabric[1][0] == "node1"


def test_fc_wwpn_modal_exposes_mappings_export_controls():
    for text in (
        'id="modal-export-excel-btn"',
        'id="modal-export-csv-btn"',
        'id="modal-print-btn"',
        "Export Excel",
        "Export CSV",
        "Print / Save PDF",
        "/api/fc-wwpn-mappings-export",
        'params.set("card_id", String(activeCard.id))',
        'params.set("format", format)',
        "function printModalMappings(",
        "Hosts & WWPNs",
        "LUN Mappings",
        "Fabric Logins",
        "window.print()",
    ):
        assert text in FC_WWPN_REPORT_HTML


def test_health_server_exposes_fc_wwpn_mappings_export_route():
    source = Path(health_server_mod.__file__).read_text(encoding="utf-8")
    assert 'path == "/api/fc-wwpn-mappings-export"' in source
    assert "build_fc_mappings_workbook" in source
    assert "export_fc_mappings_csv_zip" in source
    assert '{"error": "card_id required"}' in source or '"card_id required"' in source
    assert '"Unknown card_id"' in source
    assert '"format must be xlsx or csv"' in source
