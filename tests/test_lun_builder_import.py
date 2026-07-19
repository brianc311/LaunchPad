import csv
from io import BytesIO, StringIO
import zipfile

from openpyxl import Workbook

from launchpad.lun_builder_import import (
    map_fc_hosts,
    merge_hosts,
    parse_lun_builder_upload,
)


def _csv_content(fieldnames: list[str], row: dict[str, str]) -> bytes:
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerow(row)
    return buffer.getvalue().encode("utf-8")


def test_parse_simple_luns_csv():
    content = _csv_content(
        ["purpose", "count", "size", "pool_or_cpg", "storage_profile"],
        {
            "purpose": "ora1vg",
            "count": "2",
            "size": "100GB",
            "pool_or_cpg": "P0",
            "storage_profile": "flashsystem_5200",
        },
    )

    result = parse_lun_builder_upload("luns.csv", content)

    assert result["hosts"] == []
    assert len(result["luns"]) == 1
    assert result["luns"][0]["purpose"] == "ora1vg"
    assert result["luns"][0]["count"] == 2


def test_parse_hosts_csv_uses_flexible_headers():
    content = _csv_content(
        ["LPAR Name", "WWPN 1", "WWPN 2", "Required"],
        {
            "LPAR Name": "host1",
            "WWPN 1": "AA",
            "WWPN 2": "BB",
            "Required": "Yes",
        },
    )

    result = parse_lun_builder_upload("hosts.csv", content)

    assert result["hosts"][0]["lpar_name"] == "host1"
    assert result["hosts"][0]["wwpn1"] == "AA"
    assert result["hosts"][0]["required"] is True
    assert result["luns"] == []


def test_parse_exported_xlsx_hosts_and_lun_plan():
    workbook = Workbook()
    hosts = workbook.active
    hosts.title = "Hosts"
    hosts.append(["LPAR Name", "WWPN 1", "WWPN 2"])
    hosts.append(["host1", "AA", "BB"])
    luns = workbook.create_sheet("LUN Plan")
    luns.append(
        [
            "Volume Name",
            "Source Batch",
            "Size",
            "Storage Profile",
            "Pool / CPG",
        ]
    )
    luns.append(["ora1vg_01", "ora1vg", "100GB", "flashsystem_5200", "P0"])
    output = BytesIO()
    workbook.save(output)

    result = parse_lun_builder_upload("build.xlsx", output.getvalue())

    assert result["hosts"][0]["lpar_name"] == "host1"
    assert result["luns"][0]["purpose"] == "ora1vg"


def test_parse_zip_of_csv_files():
    output = BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr(
            "hosts.csv",
            _csv_content(
                ["lpar_name", "wwpn1"],
                {"lpar_name": "host1", "wwpn1": "AA"},
            ),
        )
        archive.writestr(
            "luns.csv",
            _csv_content(
                ["purpose", "size"],
                {"purpose": "data", "size": "10GB"},
            ),
        )

    result = parse_lun_builder_upload("build.zip", output.getvalue())

    assert len(result["hosts"]) == 1
    assert len(result["luns"]) == 1


def test_merge_hosts_dedupes_by_lpar_name_and_wwpn1():
    existing = [{"lpar_name": "h1", "wwpn1": "AA", "notes": "keep"}]
    incoming = [
        {"lpar_name": "h1", "wwpn1": "AA", "notes": "duplicate"},
        {"lpar_name": "h2", "wwpn1": "BB"},
    ]

    merged = merge_hosts(existing, incoming)

    assert len(merged) == 2
    assert merged[0]["notes"] == "keep"


def test_map_fc_hosts_maps_name_and_first_two_wwpns_without_vios_fields():
    cards = [
        {
            "name": "Storage A",
            "fc_hosts": [
                {
                    "host_name": "host1",
                    "wwpns": "AA:00; BB:00; CC:00",
                    "site_name": "ignored",
                }
            ],
        }
    ]

    hosts = map_fc_hosts(cards, card_name="Storage A")

    assert hosts == [
        {"lpar_name": "host1", "wwpn1": "AA:00", "wwpn2": "BB:00"}
    ]


def test_map_fc_hosts_warns_when_named_card_is_missing():
    hosts, warnings = map_fc_hosts([], card_name="Missing", include_warnings=True)

    assert hosts == []
    assert warnings == ['FC WWPN card "Missing" was not found.']
